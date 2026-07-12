"""CIV-F queue/provenance forwarding contract; completely offline."""
from __future__ import annotations

from unittest.mock import patch

from app.core import queue


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
