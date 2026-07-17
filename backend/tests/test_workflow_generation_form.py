from __future__ import annotations

import json
from pathlib import Path

from app.core.workflow_form import build_generation_forms


def _write(root: Path, name: str, *, modality="txt2img", io=None, conditioning=None):
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "workflow.ckpt"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 2468, "steps": 31, "cfg": 5.5, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1152, "batch_size": 2}},
    }
    (root / f"{name}.json").write_text(json.dumps(workflow), encoding="utf-8")
    (root / f"{name}.meta.json").write_text(json.dumps({"id": name, "modality": modality, "model_family": "sdxl", "io": io or ["text"], "conditioning": conditioning or [], "description": name}), encoding="utf-8")


def test_generation_forms_filter_and_describe_workflow_defaults(tmp_path: Path) -> None:
    _write(tmp_path, "plain")
    _write(tmp_path, "pose", io=["text", "pose_ref"], conditioning=["controlnet_pose"])
    result = build_generation_forms(tmp_path, resources={"checkpoints": ["installed.ckpt"]}, object_info={})
    assert [item.id for item in result.items] == ["plain"]
    fields = {item.name: item for item in result.items[0].fields}
    assert fields["checkpoint"].default == "workflow.ckpt"
    assert fields["checkpoint"].options == ["installed.ckpt"]
    assert fields["steps"].default == 31
    assert fields["seed"].default == 2468
    assert fields["width"].default == 768
