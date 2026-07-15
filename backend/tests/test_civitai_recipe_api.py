"""CIV-F offline backend API contracts; no network, ComfyUI, or GPU."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_recipe_pipeline import CivitaiHttpTransport
from app.services.civitai_resource_resolution import (
    ResolutionEntry,
    ResourceResolutionReport,
)

SHA = "a" * 64


def recipe_payload(*, runtime: bool = True) -> dict:
    payload = {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": 123},
        "base_prompt": "positive",
        "negative_prompt": "negative",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": SHA}],
        "sampling": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    }
    if runtime:
        payload["runtime"] = {"engine": "ComfyUI", "engine_version": "1", "reference": "runtime:1"}
    return payload


def report_for(recipe: GenerationRecipe, *, ready: bool = True) -> ResourceResolutionReport:
    locks = [{"index": i, "kind": resource.kind.value, "local_path": f"/models/{resource.name}", "sha256": resource.sha256} for i, resource in enumerate(recipe.resources)]
    return ResourceResolutionReport(
        strict=True,
        ready=ready,
        entries=[ResolutionEntry(index=item["index"], status="resolved", matched_by=["sha256"], expected_identity={"sha256": SHA}, actual_identity={"actual_sha256": SHA}, local_path=item["local_path"], diagnostics={}, hash_verified=True) for item in locks],
        resource_lock=locks,
    )


def test_import_uses_existing_acquisition_with_meta_raw_payload_and_redaction() -> None:
    recipe = GenerationRecipe.model_validate(recipe_payload())
    acquisition = Mock()
    acquisition.to_dict.return_value = {"raw_api_payload": {"id": 123}, "recipe": recipe.model_dump(mode="json"), "provenance": {"requests": [{"params": {"withMeta": "true"}}]}}
    acquisition.recipe = recipe
    with patch("app.services.civitai_recipe_pipeline.acquire_civitai_recipe", return_value=acquisition) as acquire:
        response = TestClient(app).post("/api/civitai-recipes/import", json={"locator": "https://civitai.com/images/123"})
    assert response.status_code == 200
    assert acquire.call_args.args[0] == "https://civitai.com/images/123"
    body = response.json()
    assert body["raw_acquisition_payload"] == {"id": 123}
    assert body["recipe"]["schema_version"] == "1.0"
    assert body["reproduction_report"]["level"]
    assert "secret" not in str(body)


def test_production_civitai_transport_follows_api_and_media_redirects() -> None:
    response = Mock(status_code=200, content=b"image-bytes", headers={})
    response.json.return_value = {"items": []}
    response.text = ""

    with patch("app.services.civitai_recipe_pipeline.httpx.get", return_value=response) as get:
        transport = CivitaiHttpTransport()
        transport.get_json("https://civitai.com/api/v1/images", params={"imageId": 123})
        transport.get_bytes("https://image.civitai.com/example.jpeg")

    assert get.call_args_list[0].kwargs["follow_redirects"] is True
    assert get.call_args_list[1].kwargs["follow_redirects"] is True


def test_inspect_is_pure_and_returns_canonical_evidence_diagnostics() -> None:
    with patch("app.api.civitai_recipes.submit_custom") as submit:
        response = TestClient(app).post("/api/civitai-recipes/inspect", json={"recipe": recipe_payload()})
    assert response.status_code == 200
    assert submit.not_called
    body = response.json()
    assert {"reproduction_report", "confirmed", "inferred", "missing"} <= body.keys()


def test_resolve_strict_failure_returns_full_structured_report_and_non_strict_is_not_exact_ready(tmp_path: Path) -> None:
    response = TestClient(app).post("/api/civitai-recipes/resolve", json={"recipe": recipe_payload(), "ledger": [], "strict": True})
    assert response.status_code >= 400
    detail = response.json()["detail"]
    assert detail["code"] == "resource_resolution_failed"
    assert detail["report"]["entries"][0]["status"] == "missing"

    response = TestClient(app).post("/api/civitai-recipes/resolve", json={"recipe": recipe_payload(), "ledger": [], "strict": False})
    assert response.status_code == 200
    assert response.json()["report"]["strict"] is False
    assert response.json()["reproduction_report"]["level"] != "exact_ready"


def test_non_strict_resolve_downgrades_an_intrinsically_exact_report_when_ledger_entries_are_missing_ambiguous_or_mismatched(monkeypatch, tmp_path: Path) -> None:
    """A permissive ledger report is diagnostic, never evidence for an exact replay claim."""
    recipe = GenerationRecipe.model_validate({
        **recipe_payload(),
        "resources": [
            {"kind": "checkpoint", "name": "missing.safetensors", "sha256": "1" * 64},
            {"kind": "lora", "name": "ambiguous.safetensors", "sha256": "2" * 64},
            {"kind": "vae", "name": "mismatch.safetensors", "sha256": "3" * 64},
        ],
    })
    ambiguous = tmp_path / "ambiguous.safetensors"
    ambiguous.write_bytes(b"ambiguous")
    mismatched = tmp_path / "mismatch.vae"
    mismatched.write_bytes(b"mismatched")
    exact = {
        "level": "exact_ready", "missing": [], "critical_missing": [],
        "caveats": [], "requirements": {"all_intrinsic_recipe_evidence": True},
    }
    monkeypatch.setattr("app.services.civitai_recipe_pipeline.inspect_recipe", lambda _: {"reproduction_report": exact})

    response = TestClient(app).post("/api/civitai-recipes/resolve", json={
        "recipe": recipe.model_dump(mode="json"),
        "strict": False,
        "ledger": [
            {"kind": "lora", "local_path": str(ambiguous), "sha256": "2" * 64},
            {"kind": "lora", "local_path": str(ambiguous), "sha256": "2" * 64},
            {"kind": "vae", "local_path": str(mismatched), "sha256": "3" * 64},
        ],
    })

    assert response.status_code == 200
    body = response.json()
    assert [entry["status"] for entry in body["report"]["entries"]] == ["missing", "ambiguous", "mismatch"]
    assert body["reproduction_report"]["level"] != "exact_ready"
    assert body["reproduction_report"]["requirements"]["resource_resolution"] is False
    assert "resource_resolution" in body["reproduction_report"]["caveats"]



def test_compatibility_returns_incompatible_as_structured_success_without_queue() -> None:
    recipe = GenerationRecipe.model_validate(recipe_payload())
    report = report_for(recipe).to_dict()
    # Existing CIV-C locks intentionally lack audited family evidence: incompatible is data, not an HTTP/build error.
    snapshot_document = {"engine": "comfyui", "engine_version": "1", "node_types": sorted(["CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"]), "sampler_names": ["euler"], "scheduler_names": ["normal"]}
    snapshot = {**snapshot_document, "snapshot_sha256": hashlib.sha256(json.dumps(snapshot_document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    with patch("app.api.civitai_recipes.submit_custom") as submit:
        response = TestClient(app).post("/api/civitai-recipes/compatibility", json={"recipe": recipe.model_dump(mode="json"), "resource_report": report, "model_family": "sdxl", "runtime_capabilities": snapshot})
    assert response.status_code == 200
    assert response.json()["compatible"] is False
    assert response.json()["status"] == "incompatible"
    submit.assert_not_called()


def test_compatibility_accepts_backend_owned_resolver_identity_fields() -> None:
    """The compatibility boundary must accept the exact identity-rich CIV-C report shape."""
    recipe = GenerationRecipe.model_validate(recipe_payload())
    report = report_for(recipe).to_dict()
    identity = {
        "civitai_model_id": 376130,
        "civitai_model_version_id": 2940478,
        "civitai_file_id": 2819621,
        "sha256": "a" * 64,
    }
    report["entries"][0]["expected_identity"].update(identity)
    report["entries"][0]["actual_identity"].update(identity)
    report["resource_lock"][0].update({key: value for key, value in identity.items() if key != "sha256"})

    snapshot_document = {
        "engine": "comfyui",
        "engine_version": "1",
        "node_types": sorted(["CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"]),
        "sampler_names": ["euler"],
        "scheduler_names": ["normal"],
    }
    runtime_capabilities = {
        **snapshot_document,
        "snapshot_sha256": hashlib.sha256(
            json.dumps(snapshot_document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    response = TestClient(app).post(
        "/api/civitai-recipes/compatibility",
        json={
            "recipe": recipe.model_dump(mode="json"),
            "resource_report": report,
            "model_family": "sdxl",
            "runtime_capabilities": runtime_capabilities,
        },
    )

    assert response.status_code == 200


def test_compatibility_validation_errors_are_structured_and_redact_secret_sentinels() -> None:
    response = TestClient(app).post("/api/civitai-recipes/compatibility", json={
        "recipe": recipe_payload(),
        "resource_report": {"strict": True, "ready": True},
        "model_family": "sdxl",
        "runtime_capabilities": {"engine": "comfyui", "authorization": "Bearer PRIVATE-COMPATIBILITY-SENTINEL"},
    })

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert "PRIVATE-COMPATIBILITY-SENTINEL" not in json.dumps(response.json())


def test_build_is_fail_closed_before_queue_and_returns_canonical_workflow_hash() -> None:
    recipe = GenerationRecipe.model_validate(recipe_payload())
    report = report_for(recipe)
    with patch("app.api.civitai_recipes.submit_custom") as submit:
        response = TestClient(app).post("/api/civitai-recipes/build", json={"recipe": recipe.model_dump(mode="json"), "resource_report": report.to_dict(), "model_family": "sdxl", "input_bindings": {}})
    assert response.status_code == 200
    body = response.json()
    assert body["workflow_sha256"] == hashlib.sha256(__import__("json").dumps(body["workflow"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert body["resource_locks"] == report.resource_lock
    submit.assert_not_called()

    bad = TestClient(app).post("/api/civitai-recipes/build", json={"recipe": recipe.model_dump(mode="json"), "resource_report": report.to_dict(), "model_family": "unsupported", "input_bindings": {}})
    assert bad.status_code >= 400
    assert bad.json()["detail"]["code"] == "unsupported_model_family"


def test_run_accepts_only_a_provenance_valid_build_and_forwards_its_bundle_to_queue() -> None:
    recipe = GenerationRecipe.model_validate(recipe_payload())
    report = report_for(recipe)
    built = TestClient(app).post("/api/civitai-recipes/build", json={"recipe": recipe.model_dump(mode="json"), "resource_report": report.to_dict(), "model_family": "sdxl", "input_bindings": {}})
    assert built.status_code == 200
    build = built.json()
    with patch("app.api.civitai_recipes.submit_custom", return_value="recipe-job") as submit:
        response = TestClient(app).post("/api/civitai-recipes/run", json={"build": build, "runtime_provenance": recipe_payload()["runtime"]})
    assert response.status_code == 202
    assert response.json()["job_id"] == "recipe-job"
    assert submit.call_args.args[0]["recipe_provenance"]["workflow_sha256"] == build["workflow_sha256"]


def test_run_rejects_invalid_bundle_without_queue_submit() -> None:
    with patch("app.api.civitai_recipes.submit_custom") as submit:
        response = TestClient(app).post("/api/civitai-recipes/run", json={"build": {"recipe": recipe_payload(), "workflow": {"1": {"class_type": "KSampler", "inputs": {}}}, "input_hashes": [], "resource_locks": [], "reproduction_report": {"level": "not_reproducible"}}, "runtime_provenance": {"engine": "different", "engine_version": "1", "reference": "runtime:1"}})
    assert response.status_code >= 400
    submit.assert_not_called()


def test_run_rejects_every_nonempty_queue_params_without_submit() -> None:
    """CIV-V-A-AC1: audited submissions accept no queue-time overrides."""
    recipe = GenerationRecipe.model_validate(recipe_payload())
    report = report_for(recipe)
    built = TestClient(app).post("/api/civitai-recipes/build", json={
        "recipe": recipe.model_dump(mode="json"),
        "resource_report": report.to_dict(),
        "model_family": "sdxl",
        "input_bindings": {},
    })
    assert built.status_code == 200
    queue_param_keys = [
        "prompt", "negative_prompt", "seed", "steps", "cfg", "sampler_name", "scheduler",
        "denoise", "width", "height", "batch_size", "checkpoint", "lora", "loras",
        "lora_strength", "diffusion_model", "text_encoder", "vae", "image", "image_pose",
        "mask", "first_frame", "last_frame", "video_ref", "template", "unexpected",
    ]
    with patch("app.api.civitai_recipes.submit_custom") as submit:
        response = TestClient(app).post("/api/civitai-recipes/run", json={
            "build": built.json(),
            "runtime_provenance": recipe_payload()["runtime"],
            "queue_params": {key: "override" for key in reversed(queue_param_keys)},
        })
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "audited_queue_overrides_forbidden",
        "message": "audited recipe submissions do not permit queue-time overrides",
        "rejected_keys": sorted(queue_param_keys),
    }
    submit.assert_not_called()
