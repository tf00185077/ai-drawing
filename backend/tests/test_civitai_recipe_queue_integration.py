"""CIV-F/V-A queue/provenance forwarding contracts; completely offline."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core import queue


def _canonical_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _audited_bundle(workflow: dict) -> dict:
    return {
        "schema_version": "1.0",
        "recipe": {"source": {"image_id": 1}},
        "workflow": workflow,
        "recipe_sha256": "a" * 64,
        "workflow_sha256": _canonical_sha256(workflow),
        "input_hashes": [],
        "resource_locks": [],
        "runtime_provenance": {"engine": "ComfyUI", "engine_version": "1", "reference": "runtime:1"},
        "reproduction_level": "workflow_ready_but_runtime_may_differ",
    }


def _settings(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        comfyui_checkpoints_dir=str(tmp_path), lora_default_checkpoint="", lora_sdxl=False,
        gallery_dir=str(tmp_path), controlnet_default_pose_image="default-pose.png",
    )


def test_recipe_run_queue_completion_forwards_the_same_verified_bundle_to_recording(tmp_path) -> None:
    gallery = tmp_path / "gallery"
    bundle = {"schema_version": "1.0", "recipe": {"source": {"image_id": 1}}, "workflow": {"1": {}}, "recipe_sha256": "a" * 64, "workflow_sha256": "b" * 64, "input_hashes": [], "resource_locks": [], "runtime_provenance": {"engine": "ComfyUI", "engine_version": "1", "reference": "runtime:1"}, "reproduction_level": "workflow_ready_but_runtime_may_differ"}
    job = queue._Job("recipe-job", {"workflow": {"1": {}}, "recipe_provenance": bundle}, "2026-01-01T00:00:00Z")

    class FakeComfy:
        def fetch_image(self, *args, **kwargs):
            return b"png"

    settings = type("Settings", (), {"gallery_dir": str(gallery)})()
    with patch("app.core.queue.get_settings", return_value=settings), patch("app.core.queue.recording_save") as save:
        assert queue._save_job_outputs(FakeComfy(), job, [{"filename": "output.png", "artifact_type": "image"}]) == 1
    assert save.call_args.kwargs["recipe_provenance"] is bundle


def test_audited_recipe_queue_submits_exact_canonical_workflow_without_apply_params(tmp_path) -> None:
    """CIV-V-A-AC2: the audited snapshot bypasses all mutable queue behavior."""
    queue._reset_for_test()
    workflow = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "locked.safetensors"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 123, "steps": 30, "cfg": 5.5}},
    }
    bundle = _audited_bundle(workflow)
    job_id = queue.submit_custom({"workflow": workflow, "recipe_provenance": bundle})
    comfy = MagicMock()
    comfy.submit_prompt.return_value = "prompt-1"

    with patch("app.core.queue.get_settings", return_value=_settings(tmp_path)) as get_settings, \
         patch("app.core.queue.default_checkpoint") as default_checkpoint, \
         patch("app.core.queue.random.randint") as random_seed, \
         patch("app.core.queue.apply_params") as apply:
        queue._process_pending(comfy)

    get_settings.assert_not_called()
    default_checkpoint.assert_not_called()
    random_seed.assert_not_called()
    comfy.upload_image.assert_not_called()
    apply.assert_not_called()
    comfy.submit_prompt.assert_called_once_with(workflow)
    assert comfy.submit_prompt.call_args.args[0] == bundle["workflow"]
    assert _canonical_sha256(comfy.submit_prompt.call_args.args[0]) == bundle["workflow_sha256"]
    assert queue.get_job_status(job_id)["status"] == "running"


def test_audited_recipe_queue_rejects_workflow_or_digest_mismatch_before_comfy_submit(tmp_path) -> None:
    """CIV-V-A-AC3: any audited workflow/digest disagreement fails closed."""
    mismatches = [
        ({"1": {"inputs": {"value": "job"}}}, {"1": {"inputs": {"value": "bundle"}}}, None),
        ({"1": {"inputs": {"value": "same"}}}, {"1": {"inputs": {"value": "same"}}}, "0" * 64),
    ]
    for job_workflow, provenance_workflow, declared_hash in mismatches:
        queue._reset_for_test()
        bundle = _audited_bundle(provenance_workflow)
        if declared_hash is not None:
            bundle["workflow_sha256"] = declared_hash
        job_id = queue.submit_custom({"workflow": job_workflow, "recipe_provenance": bundle})
        comfy = MagicMock()

        with patch("app.core.queue.get_settings", return_value=_settings(tmp_path)), \
             patch("app.core.queue.apply_params") as apply:
            queue._process_pending(comfy)

        apply.assert_not_called()
        comfy.submit_prompt.assert_not_called()
        status = queue.get_job_status(job_id)
        assert status is not None
        assert status["status"] == "failed"
        assert "audited_workflow_hash_mismatch" in status["error"]
