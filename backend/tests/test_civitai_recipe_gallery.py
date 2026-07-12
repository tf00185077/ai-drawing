"""CIV-E recipe provenance bundle persistence and fail-closed API tests."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.recording import save
from app.db.database import Base, get_db
from app.main import app
from app.services.civitai_recipe_gallery import ProvenanceValidationError, build_recipe_provenance_bundle


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _recipe(
    seed: int = 9223372036854775807,
    resource_sha256: str = "a" * 64,
    workflow: dict | None = None,
    inputs: list[dict] | None = None,
) -> dict:
    recipe = {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": 1},
        "base_prompt": "audit prompt",
        "negative_prompt": "lowres",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": resource_sha256}],
        "sampling": {"seed": seed, "steps": 20, "cfg": 7.0, "sampler": "euler", "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling", "sampling": {}}],
        "runtime": {"engine": "ComfyUI", "engine_version": "1", "reference": "runtime:1"},
    }
    if workflow is not None:
        recipe["workflow"] = {
            "reference": "civ-d:workflow",
            "snapshot": workflow,
            "snapshot_sha256": _sha(workflow),
        }
    if inputs is not None:
        recipe["inputs"] = inputs
    return recipe


def _bundle(tmp_path: Path) -> dict:
    input_path = tmp_path / "pose.png"
    input_path.write_bytes(b"pose")
    resource_path = tmp_path / "base.safetensors"
    resource_path.write_bytes(b"model")
    resource_sha = _sha_bytes(resource_path)
    workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 9223372036854775807}}}
    recipe = _recipe(resource_sha256=resource_sha, workflow=workflow)
    return build_recipe_provenance_bundle(
        recipe=recipe,
        workflow=workflow,
        input_hashes=[{"reference": "pose.png", "sha256": _sha_bytes(input_path), "required": True, "local_path": str(input_path)}],
        resource_locks=[{"index": 0, "kind": "checkpoint", "sha256": resource_sha, "local_path": str(resource_path), "local_sha256": resource_sha}],
        runtime_provenance=_recipe()["runtime"],
        reproduction_level="workflow_ready_but_runtime_may_differ",
    )


def _sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bundle_canonicalizes_and_validates_recipe_and_workflow(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    assert bundle["recipe_sha256"] == _sha(bundle["recipe"])
    assert bundle["workflow_sha256"] == _sha(bundle["workflow"])
    assert bundle["recipe"]["sampling"]["seed"] == 9223372036854775807


def test_bundle_rejects_resource_identity_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceValidationError) as raised:
        build_recipe_provenance_bundle(
            recipe=_recipe(), workflow={"1": {"class_type": "KSampler", "inputs": {}}},
            input_hashes=[],
            resource_locks=[{"index": 0, "kind": "checkpoint", "sha256": "b" * 64}],
            runtime_provenance=_recipe()["runtime"],
            reproduction_level="not_reproducible",
        )
    assert raised.value.code == "resource_lock_identity_mismatch"


@pytest.fixture
def client(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with factory() as db:
        save(image_path="recipe.png", prompt="audit prompt", recipe_provenance=_bundle(tmp_path), db=db)
        save(image_path="legacy.png", prompt="legacy", db=db)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_recipe_export_and_rerun_use_verified_bundle(client: TestClient) -> None:
    response = client.get("/api/gallery/1/export?format=recipe")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"schema_version", "gallery", "recipe", "recipe_sha256", "workflow", "workflow_sha256", "input_hashes", "resource_locks", "runtime_provenance", "reproduction_level"}
    assert payload["recipe_sha256"] == _sha(payload["recipe"])

    with patch("app.api.gallery.submit_custom", return_value="recipe-job") as custom, patch("app.api.gallery.submit") as legacy:
        rerun = client.post("/api/gallery/1/rerun")
    assert rerun.status_code == 202
    custom.assert_called_once()
    legacy.assert_not_called()
    params = custom.call_args.args[0]
    assert params["workflow"] == payload["workflow"]
    assert "seed" not in params
    assert "input_refs" not in params


def test_recipe_export_and_rerun_fail_closed_on_tampered_workflow(client: TestClient) -> None:
    # The API fixture deliberately uses a fresh session; update through the service-visible row.
    from app.api import gallery
    dependency = app.dependency_overrides[get_db]
    db = next(dependency())
    try:
        row = db.get(__import__("app.db.models", fromlist=["GeneratedImage"]).GeneratedImage, 1)
        row.recipe_workflow_json = '{"tampered":true}'
        db.commit()
    finally:
        db.close()

    with patch("app.api.gallery.submit_custom") as custom, patch("app.api.gallery.submit") as legacy:
        exported = client.get("/api/gallery/1/export?format=recipe")
        rerun = client.post("/api/gallery/1/rerun")
    assert exported.status_code == 409
    assert exported.json()["detail"]["error"] == "workflow_snapshot_binding_mismatch"
    assert rerun.status_code == 409
    custom.assert_not_called()
    legacy.assert_not_called()


@pytest.mark.parametrize(
    ("manifest_field", "mode", "expected_error"),
    [
        ("recipe_input_hashes_json", "missing", "required_input_missing"),
        ("recipe_input_hashes_json", "mismatch", "input_hash_mismatch"),
        ("recipe_resource_locks_json", "missing", "resource_lock_missing"),
        ("recipe_resource_locks_json", "mismatch", "resource_lock_hash_mismatch"),
    ],
)
def test_recipe_export_fail_closed_on_local_input_or_resource_file_failure(
    client: TestClient, manifest_field: str, mode: str, expected_error: str,
) -> None:
    """CIV-E-AC5: recipe export independently audits required local files."""
    dependency = app.dependency_overrides[get_db]
    db = next(dependency())
    try:
        row = db.get(__import__("app.db.models", fromlist=["GeneratedImage"]).GeneratedImage, 1)
        manifest = json.loads(getattr(row, manifest_field))
        path = Path(manifest[0]["local_path"])
        if mode == "missing":
            path.unlink()
        else:
            path.write_bytes(b"tampered")
        db.commit()
    finally:
        db.close()

    with patch("app.api.gallery.submit_custom") as custom, patch("app.api.gallery.submit") as legacy:
        exported = client.get("/api/gallery/1/export?format=recipe")
    assert exported.status_code == 409
    detail = exported.json()["detail"]
    assert detail["error"] == expected_error
    assert detail["field"].startswith("input_hashes[" if manifest_field == "recipe_input_hashes_json" else "resource_locks[")
    custom.assert_not_called()
    legacy.assert_not_called()


def test_recipe_rerun_fail_closed_on_missing_required_input(client: TestClient) -> None:
    dependency = app.dependency_overrides[get_db]
    db = next(dependency())
    try:
        row = db.get(__import__("app.db.models", fromlist=["GeneratedImage"]).GeneratedImage, 1)
        manifest = json.loads(row.recipe_input_hashes_json)
        Path(manifest[0]["local_path"]).unlink()
        db.commit()
    finally:
        db.close()

    with patch("app.api.gallery.submit_custom") as custom, patch("app.api.gallery.submit") as legacy:
        rerun = client.post("/api/gallery/1/rerun")
    assert rerun.status_code == 409
    assert rerun.json()["detail"]["error"] == "required_input_missing"
    custom.assert_not_called()
    legacy.assert_not_called()


def test_legacy_recipe_export_is_conflict_and_legacy_rerun_stays_compatible(client: TestClient) -> None:
    assert client.get("/api/gallery/2/export?format=recipe").status_code == 409
    with patch("app.api.gallery.submit", return_value="legacy-job") as legacy:
        response = client.post("/api/gallery/2/rerun")
    assert response.status_code == 202
    legacy.assert_called_once()


def test_bundle_rejects_recipe_workflow_snapshot_that_differs_from_stored_workflow(tmp_path: Path) -> None:
    resource = tmp_path / "base.safetensors"
    resource.write_bytes(b"model")
    recipe_workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}
    stored_workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 2}}}

    with pytest.raises(ProvenanceValidationError) as raised:
        build_recipe_provenance_bundle(
            recipe=_recipe(workflow=recipe_workflow, resource_sha256=_sha_bytes(resource)),
            workflow=stored_workflow,
            input_hashes=[],
            resource_locks=[{
                "index": 0, "kind": "checkpoint", "sha256": _sha_bytes(resource),
                "local_path": str(resource),
            }],
            runtime_provenance=_recipe()["runtime"],
            reproduction_level="workflow_ready_but_runtime_may_differ",
        )
    assert raised.value.code == "workflow_snapshot_binding_mismatch"


@pytest.mark.parametrize(
    ("entry", "expected_code", "expected_field"),
    [
        ({"reference": "subject", "sha256": "a" * 64, "required": True}, "required_input_local_path_missing", ".local_path"),
        ({"reference": "subject", "sha256": "a" * 64, "required": False, "local_path": "/tmp/x"}, "required_input_manifest_invalid", ".required"),
    ],
)
def test_bundle_rejects_required_input_without_rerunnable_local_manifest(
    tmp_path: Path, entry: dict, expected_code: str, expected_field: str,
) -> None:
    resource = tmp_path / "base.safetensors"
    resource.write_bytes(b"model")
    workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}
    with pytest.raises(ProvenanceValidationError) as raised:
        build_recipe_provenance_bundle(
            recipe=_recipe(
                workflow=workflow, resource_sha256=_sha_bytes(resource),
                inputs=[{"reference": "subject", "sha256": "a" * 64, "kind": "image"}],
            ),
            workflow=workflow,
            input_hashes=[entry],
            resource_locks=[{
                "index": 0, "kind": "checkpoint", "sha256": _sha_bytes(resource),
                "local_path": str(resource),
            }],
            runtime_provenance=_recipe()["runtime"],
            reproduction_level="workflow_ready_but_runtime_may_differ",
        )
    assert raised.value.code == expected_code
    assert raised.value.field.endswith(expected_field)


def test_bundle_rejects_resource_lock_without_local_path(tmp_path: Path) -> None:
    workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}
    with pytest.raises(ProvenanceValidationError) as raised:
        build_recipe_provenance_bundle(
            recipe=_recipe(workflow=workflow), workflow=workflow, input_hashes=[],
            resource_locks=[{"index": 0, "kind": "checkpoint", "sha256": "a" * 64}],
            runtime_provenance=_recipe()["runtime"],
            reproduction_level="workflow_ready_but_runtime_may_differ",
        )
    assert raised.value.code == "resource_lock_local_path_missing"


def test_recipe_rerun_binds_verified_image_pose_and_mask_through_actual_queue(tmp_path: Path) -> None:
    """CIV-E-AC4: use queue's real upload/injection contract, not a dead input_refs key."""
    from app.core import queue

    gallery = tmp_path / "gallery"
    gallery.mkdir()
    subject = gallery / "subject.png"
    pose = gallery / "pose.png"
    mask = gallery / "mask.png"
    resource = tmp_path / "base.safetensors"
    for path, payload in ((subject, b"subject"), (pose, b"pose"), (mask, b"mask"), (resource, b"model")):
        path.write_bytes(payload)
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {"seed": 9223372036854775807}},
        "10": {"class_type": "LoadImage", "inputs": {"image": "old-subject.png"}},
        "11": {"class_type": "LoadImage", "inputs": {"image": "old-pose.png"}},
        "12": {"class_type": "LoadImageMask", "inputs": {"image": "old-mask.png"}},
    }
    bundle = build_recipe_provenance_bundle(
        recipe=_recipe(
            workflow=workflow, resource_sha256=_sha_bytes(resource),
            inputs=[
                {"reference": "subject", "sha256": _sha_bytes(subject), "kind": "image"},
                {"reference": "pose", "sha256": _sha_bytes(pose), "kind": "pose"},
                {"reference": "mask", "sha256": _sha_bytes(mask), "kind": "mask"},
            ],
        ),
        workflow=workflow,
        input_hashes=[
            {"reference": "subject", "sha256": _sha_bytes(subject), "required": True, "local_path": str(subject)},
            {"reference": "pose", "sha256": _sha_bytes(pose), "required": True, "local_path": str(pose)},
            {"reference": "mask", "sha256": _sha_bytes(mask), "required": True, "local_path": str(mask)},
        ],
        resource_locks=[{"index": 0, "kind": "checkpoint", "sha256": _sha_bytes(resource), "local_path": str(resource)}],
        runtime_provenance=_recipe()["runtime"],
        reproduction_level="workflow_ready_but_runtime_may_differ",
    )
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    class FakeComfy:
        submitted_prompt = None

        def upload_image(self, path: Path) -> dict:
            return {"name": path.name}

        def submit_prompt(self, prompt: dict) -> str:
            self.submitted_prompt = prompt
            return "comfy-prompt"

    settings = SimpleNamespace(
        comfyui_checkpoints_dir=str(tmp_path), lora_default_checkpoint="", lora_sdxl=False,
        gallery_dir=str(gallery), controlnet_default_pose_image="",
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        with factory() as db:
            save(image_path="recipe.png", recipe_provenance=bundle, db=db)
        queue._reset_for_test()
        fake_comfy = FakeComfy()
        with patch("app.api.gallery.get_settings", return_value=settings), \
             patch("app.core.queue.get_settings", return_value=settings), \
             patch("app.api.gallery.submit_custom", wraps=queue.submit_custom) as submit_custom:
            response = TestClient(app).post("/api/gallery/1/rerun")
            queue._process_pending(fake_comfy)
        assert response.status_code == 202
        submit_custom.assert_called_once()
        submitted_params = submit_custom.call_args.args[0]
        assert "seed" not in submitted_params
        assert set(submitted_params).issuperset({"workflow", "image", "image_pose", "mask"})
        assert "input_refs" not in submitted_params
        assert fake_comfy.submitted_prompt["10"]["inputs"]["image"] == "subject.png"
        assert fake_comfy.submitted_prompt["11"]["inputs"]["image"] == "pose.png"
        assert fake_comfy.submitted_prompt["12"]["inputs"]["image"] == "mask.png"
    finally:
        queue._reset_for_test()
        app.dependency_overrides.clear()
