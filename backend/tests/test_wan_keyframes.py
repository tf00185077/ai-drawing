from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from app.config import Settings
from app.core.wan_keyframes import build_wan_keyframe_workflow


def _write_dummy_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")


def test_build_wan_keyframe_workflow_stages_inputs_and_batches_dynamic_images(tmp_path) -> None:
    gallery = tmp_path / "gallery"
    comfy_input = tmp_path / "comfy-input"
    for name in ["a.png", "b.png", "c.png"]:
        _write_dummy_png(gallery / "2026-06-23" / name)

    settings = cast(Settings, SimpleNamespace(gallery_dir=str(gallery), comfyui_input_dir=str(comfy_input)))
    wf = build_wan_keyframe_workflow(
        settings=settings,
        image_paths=["2026-06-23/a.png", "2026-06-23/b.png", "2026-06-23/c.png"],
        prompt="stable multi keyframe video",
        negative_prompt="bad",
        width=320,
        height=480,
        length=33,
        fps=8.0,
        steps=5,
        cfg=1.2,
        seed=1234,
        filename_prefix="video/test_wan_keyframes",
        task_slug="unit_test_wan",
    )

    assert (comfy_input / "unit_test_wan" / "keyframe_01.png").exists()
    assert (comfy_input / "unit_test_wan" / "keyframe_02.png").exists()
    assert (comfy_input / "unit_test_wan" / "keyframe_03.png").exists()
    assert list((comfy_input / "unit_test_wan").glob("silent_*ms.wav"))

    load_nodes = [node for node in wf.values() if node.get("class_type") == "LoadImage"]
    assert [node["inputs"]["image"] for node in load_nodes] == [
        "unit_test_wan/keyframe_01.png",
        "unit_test_wan/keyframe_02.png",
        "unit_test_wan/keyframe_03.png",
    ]
    image_batch_nodes = [node for node in wf.values() if node.get("class_type") == "ImageBatch"]
    assert len(image_batch_nodes) == 2
    assert wf["120"]["inputs"]["images"] == ["114", 0]
    assert wf["120"]["inputs"]["segment_length"] == 33
    assert wf["98"]["inputs"]["width"] == 320
    assert wf["98"]["inputs"]["height"] == 480
    assert wf["98"]["inputs"]["length"] == 33
    assert wf["94"]["inputs"]["fps"] == 8.0
    assert wf["108"]["inputs"]["filename_prefix"] == "video/test_wan_keyframes"
    assert wf["93"]["inputs"]["text"] == "stable multi keyframe video"
    assert wf["89"]["inputs"]["text"] == "bad"
    assert wf["86"]["inputs"]["steps"] == 5
    assert wf["85"]["inputs"]["steps"] == 5
    assert wf["86"]["inputs"]["noise_seed"] == 1234


def test_build_wan_keyframe_workflow_rejects_path_traversal(tmp_path) -> None:
    settings = cast(Settings, SimpleNamespace(gallery_dir=str(tmp_path / "gallery"), comfyui_input_dir=str(tmp_path / "input")))
    try:
        build_wan_keyframe_workflow(
            settings=settings,
            image_paths=["../a.png", "b.png"],
            prompt="x",
        )
    except ValueError as exc:
        assert "Unsafe gallery path" in str(exc)
    else:
        raise AssertionError("expected unsafe path rejection")


def test_post_generate_video_wan_keyframes_queues_builder_result(client) -> None:
    fake_workflow = {"98": {"class_type": "WanDancerVideo", "inputs": {}}}
    with patch("app.api.generate.build_wan_keyframe_workflow", return_value=fake_workflow) as mock_build:
        with patch("app.api.generate.submit_custom", return_value="wan-job") as mock_submit:
            r = client.post(
                "/api/generate/video/wan-keyframes",
                json={
                    "images": ["2026-06-23/a.png", "2026-06-23/b.png"],
                    "prompt": "smooth keyframe orbit",
                    "negative_prompt": "bad",
                    "width": 320,
                    "height": 480,
                    "length": 33,
                    "fps": 8.0,
                    "steps": 4,
                    "cfg": 1.0,
                    "seed": 123,
                    "filename_prefix": "video/unit",
                },
            )

    assert r.status_code == 201
    assert r.json()["job_id"] == "wan-job"
    mock_build.assert_called_once()
    params = mock_submit.call_args[0][0]
    assert params["workflow"] == fake_workflow
    assert params["prompt"] == "smooth keyframe orbit"
    assert params["template"] == "gen_img2video_wan_5keyframe_single_workflow"
