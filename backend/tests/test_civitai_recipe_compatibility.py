"""CIV-V-E compatibility preflight: deterministic and strictly side-effect-free."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from app.schemas.generation_recipe import GenerationRecipe

SHA = {letter: letter * 64 for letter in "abcdef"}


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _snapshot(*, nodes: list[str] | None = None) -> dict:
    value = {
        "engine": "comfyui", "engine_version": "1.0",
        "node_types": nodes or ["CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"],
        "sampler_names": ["euler"], "scheduler_names": ["normal"],
    }
    value["snapshot_sha256"] = hashlib.sha256(_canonical(value).encode()).hexdigest()
    return value


def _recipe(*, family: str = "sdxl", lora: bool = False) -> GenerationRecipe:
    resources = [{"kind": "checkpoint", "name": "does-not-infer-family.safetensors", "sha256": SHA["a"]}]
    if lora:
        resources.append({"kind": "lora", "name": "adapter.safetensors", "sha256": SHA["b"], "strength_model": 1.0, "strength_clip": 1.0})
    return GenerationRecipe.model_validate({
        "schema_version": "1.0", "source": {"provider": "civitai", "image_id": 1},
        "base_prompt": "positive", "negative_prompt": "negative", "resources": resources,
        "sampling": {"seed": 1, "steps": 20, "cfg": 7, "sampler": "euler", "scheduler": "normal", "denoise": 1, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    })


def _report(recipe: GenerationRecipe, *, family: str = "sdxl") -> dict:
    entries, locks = [], []
    for index, resource in enumerate(recipe.resources):
        path = f"/locked/{index}-{resource.name}"
        evidence = {"model_family": family} if resource.kind.value in {"checkpoint", "lora"} else {}
        entries.append({"index": index, "status": "resolved", "matched_by": ["sha256"], "expected_identity": {"sha256": resource.sha256}, "actual_identity": {"actual_sha256": resource.sha256, **evidence}, "local_path": path, "diagnostics": {}, "hash_verified": True})
        locks.append({"index": index, "kind": resource.kind.value, "sha256": resource.sha256, "local_path": path, **evidence})
    return {"strict": True, "ready": True, "entries": entries, "resource_lock": locks}


def _preflight(recipe: GenerationRecipe, report: dict, family: str, snapshot: dict) -> dict:
    from app.services.civitai_recipe_compatibility import preflight_recipe_compatibility
    return preflight_recipe_compatibility(recipe, report, requested_model_family=family, runtime_capabilities=snapshot)


@pytest.mark.parametrize("family", ["sdxl", "illustrious"])
def test_compatible_checkpoint_and_ordered_loras_are_deterministic(family: str) -> None:
    recipe = _recipe(lora=True)
    report, snapshot = _report(recipe, family=family), _snapshot(nodes=sorted(["CheckpointLoaderSimple", "LoraLoader", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"]))
    before = deepcopy((recipe, report, snapshot))
    first = _preflight(recipe, report, family, snapshot)
    second = _preflight(recipe, report, family, snapshot)
    assert _canonical(first) == _canonical(second)
    assert first["status"] == "compatible" and first["compatible"] is True, first
    assert [item["recipe_index"] for item in first["resources"]] == [0, 1]
    assert (recipe, report, snapshot) == before


@pytest.mark.parametrize("evidence", [None, "generic", "flux", ["sdxl", "illustrious"]])
def test_checkpoint_family_evidence_fails_closed_without_filename_inference(evidence: object) -> None:
    recipe, report = _recipe(), _report(_recipe())
    if evidence is None:
        report["entries"][0]["actual_identity"].pop("model_family")
        report["resource_lock"][0].pop("model_family")
    else:
        report["entries"][0]["actual_identity"]["model_family"] = evidence
        report["resource_lock"][0]["model_family"] = evidence
    result = _preflight(recipe, report, "sdxl", _snapshot())
    assert result["compatible"] is False
    assert any(item["code"] == "unknown_model_family" for item in result["diagnostics"])


@pytest.mark.parametrize("mutate,code", [
    (lambda report: report.update(strict=False), "resource_report_not_strict"),
    (lambda report: report.update(ready=False), "resource_report_not_ready"),
    (lambda report: report["entries"].append(deepcopy(report["entries"][0])), "resolution_entry_duplicate"),
    (lambda report: report["resource_lock"].append(deepcopy(report["resource_lock"][0])), "resource_lock_duplicate"),
])
def test_report_invariants_fail_closed(mutate, code: str) -> None:
    recipe, report = _recipe(), _report(_recipe())
    mutate(report)
    result = _preflight(recipe, report, "sdxl", _snapshot())
    assert result["compatible"] is False
    assert any(item["code"] == code for item in result["diagnostics"])


def test_a1111_sampler_alias_matches_the_compiler_runtime_identifier() -> None:
    """Compatibility and compilation must agree on canonical ComfyUI sampler names."""
    recipe = _recipe()
    recipe.sampling.sampler = "Euler a"
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "SaveImage", "VAEDecode",
    ]))
    snapshot["sampler_names"] = ["euler_ancestral"]
    snapshot["snapshot_sha256"] = hashlib.sha256(
        _canonical({key: snapshot[key] for key in (
            "engine", "engine_version", "node_types", "sampler_names", "scheduler_names"
        )}).encode()
    ).hexdigest()

    result = _preflight(recipe, _report(recipe), "sdxl", snapshot)

    assert result["compatible"] is True, result


def test_runtime_hash_and_required_node_fail_closed() -> None:
    recipe, report = _recipe(), _report(_recipe())
    wrong_hash = _snapshot(); wrong_hash["snapshot_sha256"] = "0" * 64
    assert any(item["code"] == "runtime_snapshot_hash_mismatch" for item in _preflight(recipe, report, "sdxl", wrong_hash)["diagnostics"])
    missing_node = _snapshot(nodes=["CheckpointLoaderSimple"])
    assert any(item["code"] == "runtime_node_missing" for item in _preflight(recipe, report, "sdxl", missing_node)["diagnostics"])


def test_unsupported_resource_kind_is_data_not_a_build_attempt() -> None:
    recipe = _recipe()
    recipe = GenerationRecipe.model_validate({**recipe.model_dump(), "resources": recipe.model_dump()["resources"] + [{"kind": "other", "name": "unknown.bin", "sha256": SHA["c"]}]})
    result = _preflight(recipe, _report(recipe), "sdxl", _snapshot())
    assert result["compatible"] is False
    assert any(item["code"] == "unsupported_resource_kind" for item in result["diagnostics"])


@pytest.mark.parametrize("missing_field", ["strength_model", "strength_clip"])
def test_lora_without_explicit_dual_strength_is_rejected_before_compilation(missing_field: str) -> None:
    recipe = _recipe(lora=True)
    setattr(recipe.resources[1], missing_field, None)
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler",
        "LoraLoader", "SaveImage", "VAEDecode",
    ]))

    result = _preflight(recipe, _report(recipe), "sdxl", snapshot)

    assert result["compatible"] is False
    assert any(item["code"] == "unsupported_operation" and item["canonical_field"] == "resources[1]" for item in result["diagnostics"])


def test_distinct_lora_clip_skip_values_are_rejected_before_compilation() -> None:
    recipe = _recipe(lora=True)
    recipe = GenerationRecipe.model_validate({
        **recipe.model_dump(),
        "resources": recipe.model_dump()["resources"] + [{
            "kind": "lora", "name": "second.safetensors", "sha256": SHA["c"],
            "strength_model": 1.0, "strength_clip": 1.0, "clip_skip": 3,
        }],
    })
    recipe.resources[1].clip_skip = 2
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPSetLastLayer", "CLIPTextEncode", "EmptyLatentImage",
        "KSampler", "LoraLoader", "SaveImage", "VAEDecode",
    ]))

    result = _preflight(recipe, _report(recipe), "sdxl", snapshot)

    assert result["compatible"] is False
    assert any(item["code"] == "unsupported_operation" and item["canonical_field"] == "resources" for item in result["diagnostics"])


def _feature_recipe(feature: str) -> GenerationRecipe:
    recipe = _recipe()
    payload = recipe.model_dump()
    if feature == "dw_preprocessor":
        payload["resources"].append({"kind": "controlnet", "name": "pose.safetensors", "sha256": SHA["b"]})
        payload["inputs"] = [{"reference": "pose.png", "sha256": SHA["c"], "kind": "image"}]
        payload["controls"] = [{
            "kind": "controlnet", "input_ref": "pose.png", "preprocessor": "dwpreprocessor",
            "resource": {"kind": "controlnet", "sha256": SHA["b"]},
        }]
    elif feature == "hires":
        payload["resources"].append({"kind": "upscaler", "name": "4x.pth", "sha256": SHA["b"]})
        payload["passes"].append({
            "name": "hires", "inherits_from": "base", "scale": 1.5,
            "sampling": {"width": 768, "height": 768, "denoise": 0.4},
            "upscale_resource": {"kind": "upscaler", "sha256": SHA["b"]},
        })
    elif feature == "face_restore":
        payload["resources"].append({"kind": "detailer", "name": "face.onnx", "sha256": SHA["b"]})
        payload["postprocess"] = [{"kind": "face_restore", "resource": {"kind": "detailer", "sha256": SHA["b"]}}]
    else:
        raise AssertionError(feature)
    return GenerationRecipe.model_validate(payload)


@pytest.mark.parametrize(
    ("feature", "missing_node"),
    [
        ("dw_preprocessor", "DWPreprocessor"),
        ("hires", "ImageScale"),
        ("hires", "VAEEncode"),
        ("face_restore", "FaceRestore"),
    ],
)
def test_compiler_feature_node_contract_fails_closed_when_a_required_node_is_missing(feature: str, missing_node: str) -> None:
    recipe = _feature_recipe(feature)
    nodes = {
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "SaveImage", "VAEDecode",
        "ControlNetApplyAdvanced", "ControlNetLoader", "DWPreprocessor", "LoadImage",
        "ImageScale", "ImageScaleBy", "ImageUpscaleWithModel", "UpscaleModelLoader", "VAEEncode", "FaceRestore",
    }
    nodes.remove(missing_node)

    result = _preflight(recipe, _report(recipe), "sdxl", _snapshot(nodes=sorted(nodes)))

    assert result["compatible"] is False
    assert any(item["code"] == "runtime_node_missing" and missing_node in item["message"] for item in result["diagnostics"])


def test_preflight_paths_are_pure_with_all_runtime_side_effects_bombed(monkeypatch) -> None:
    """CIV-V-E must remain a decision boundary even when all adjacent runtime seams explode."""
    from pathlib import Path

    from app.core import comfyui, queue
    from app.services import civitai_recipe_pipeline, civitai_recipe_workflow_compiler
    from sqlalchemy.orm import Session

    def bomb(*_args, **_kwargs):
        raise AssertionError("compatibility preflight touched a forbidden side-effect seam")

    monkeypatch.setattr(civitai_recipe_workflow_compiler, "compile_generation_recipe_workflow", bomb)
    monkeypatch.setattr(civitai_recipe_pipeline.CivitaiHttpTransport, "get_json", bomb)
    monkeypatch.setattr(queue, "submit_custom", bomb)
    monkeypatch.setattr(queue, "cancel", bomb)
    monkeypatch.setattr(comfyui.ComfyUIClient, "submit_prompt", bomb)
    monkeypatch.setattr(Session, "execute", bomb)
    for method in ("query", "get", "scalar", "scalars", "add", "add_all", "delete", "flush", "commit"):
        monkeypatch.setattr(Session, method, bomb)
    monkeypatch.setattr(Path, "write_text", bomb)
    monkeypatch.setattr(Path, "write_bytes", bomb)
    monkeypatch.setattr(Path, "replace", bomb)
    monkeypatch.setattr(Path, "unlink", bomb)

    recipe = _recipe()
    report = _report(recipe)
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "SaveImage", "VAEDecode",
    ]))
    before = deepcopy((recipe, report, snapshot))
    compatible = _preflight(recipe, report, "sdxl", snapshot)

    rejected_report = deepcopy(report)
    rejected_report["resource_lock"][0].pop("model_family")
    rejected_report["entries"][0]["actual_identity"].pop("model_family")
    rejected_before = deepcopy(rejected_report)
    incompatible = _preflight(recipe, rejected_report, "sdxl", snapshot)

    assert compatible["compatible"] is True
    assert incompatible["compatible"] is False
    assert (recipe, report, snapshot) == before
    assert rejected_report == rejected_before


def test_family_evidence_is_trimmed_casefolded_and_emitted_canonically() -> None:
    recipe = _recipe(lora=True)
    report = _report(recipe)
    for entry, lock in zip(report["entries"], report["resource_lock"], strict=True):
        entry["actual_identity"]["model_family"] = "  SDXL  "
        lock["model_family"] = "sDxL"
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler",
        "LoraLoader", "SaveImage", "VAEDecode",
    ]))

    result = _preflight(recipe, report, "sdxl", snapshot)

    assert result["compatible"] is True, result
    assert [item["declared_model_family"] for item in result["resources"]] == ["sdxl", "sdxl"]


def test_single_lora_clip_skip_requires_clip_set_last_layer_runtime_node() -> None:
    recipe = _recipe(lora=True)
    recipe.resources[1].clip_skip = 2
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler",
        "LoraLoader", "SaveImage", "VAEDecode",
    ]))

    result = _preflight(recipe, _report(recipe), "sdxl", snapshot)

    assert result["compatible"] is False
    assert any(item["code"] == "runtime_node_missing" and "CLIPSetLastLayer" in item["message"] for item in result["diagnostics"])


def test_multiple_vae_resources_are_not_compiler_expressible() -> None:
    recipe = GenerationRecipe.model_validate({
        **_recipe().model_dump(),
        "resources": _recipe().model_dump()["resources"] + [
            {"kind": "vae", "name": "one.vae", "sha256": SHA["b"]},
            {"kind": "vae", "name": "two.vae", "sha256": SHA["c"]},
        ],
    })
    snapshot = _snapshot(nodes=sorted([
        "CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler",
        "SaveImage", "VAEDecode", "VAELoader",
    ]))

    result = _preflight(recipe, _report(recipe), "sdxl", snapshot)

    assert result["compatible"] is False
    assert any(item["code"] == "resource_cardinality" and item["canonical_field"] == "resources" for item in result["diagnostics"])


def test_empty_passes_fail_closed_like_the_current_compiler() -> None:
    from app.services.civitai_recipe_pipeline import report_from_payload
    from app.services.civitai_recipe_workflow_compiler import (
        RecipeCompileError,
        compile_generation_recipe_workflow,
    )

    recipe = GenerationRecipe.model_validate({**_recipe().model_dump(), "passes": []})

    result = _preflight(recipe, _report(recipe), "sdxl", _snapshot())

    assert result["compatible"] is False
    assert any(
        item["code"] == "passes_missing" and item["canonical_field"] == "passes"
        for item in result["diagnostics"]
    )
    with pytest.raises(RecipeCompileError) as exc_info:
        compile_generation_recipe_workflow(
            recipe,
            report_from_payload(_report(recipe)),
            model_family="sdxl",
            input_bindings={},
        )
    assert exc_info.value.diagnostic["code"] == "passes_missing"
