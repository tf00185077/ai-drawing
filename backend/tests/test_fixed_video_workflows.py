from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.core.fixed_video_workflows import (
    build_animegen_i2v_workflow,
    build_wan_animate_workflow,
    stage_upload,
    validate_video_timing,
)
from app.services.film_postprocess import output_fps, source_position


def test_video_timing_uses_first_to_last_span_and_requires_4n_plus_1() -> None:
    timing = validate_video_timing(5.0, 81, 321)
    assert timing.source_fps == 16.0
    assert timing.output_fps == 64.0
    with pytest.raises(ValueError, match="4n\\+1"):
        validate_video_timing(5.0, 80, 321)


def test_animegen_builder_keeps_fixed_models_prompts_length_and_fps(tmp_path: Path) -> None:
    timing = validate_video_timing(5.0, 81, 321)
    workflow = build_animegen_i2v_workflow(
        image_path=tmp_path / "input.png",
        prompt="turn and smile",
        negative_prompt="bad motion",
        timing=timing,
    )
    assert workflow["110"]["inputs"]["unet_name"] == "AnimeGen-I2V-GGUF/I2V_high_noise_Q4_K_M.gguf"
    assert workflow["111"]["inputs"]["unet_name"] == "AnimeGen-I2V-GGUF/I2V_low_noise_Q4_K_M.gguf"
    assert workflow["93"]["inputs"]["text"] == "turn and smile"
    assert workflow["89"]["inputs"]["text"] == "bad motion"
    assert workflow["97"]["inputs"]["image"] == str(tmp_path / "input.png")
    assert workflow["98"]["inputs"]["length"] == 81
    assert workflow["94"]["inputs"]["fps"] == 16.0


def test_wan_animate_builder_wires_reference_driver_face_body_and_nonzero_batch() -> None:
    timing = validate_video_timing(4.0, 65, 257)
    workflow = build_wan_animate_workflow(
        reference_path=Path("reference.png"),
        driver_path=Path("driver.mp4"),
        prompt="follow all motion",
        negative_prompt=None,
        timing=timing,
    )
    assert workflow["12"]["inputs"]["unet_name"] == "Wan2.2-Animate-14B-Q4_K_M.gguf"
    assert workflow["1"]["inputs"]["file"] == "driver.mp4"
    assert workflow["5"]["inputs"]["image"] == "reference.png"
    assert workflow["3"]["inputs"]["detect_face"] == "enable"
    assert workflow["4"]["inputs"]["detect_body"] == "enable"
    assert workflow["15"]["inputs"]["face_video"] == ["3", 0]
    assert workflow["15"]["inputs"]["pose_video"] == ["4", 0]
    assert workflow["15"]["inputs"]["length"] == 65
    assert workflow["19"]["inputs"]["length"] == 65
    assert workflow["19"]["inputs"]["length"] != 0
    assert workflow["20"]["inputs"]["fps"] == 16.0


def test_stage_upload_is_opaque_bounded_signature_checked_and_traversal_safe(tmp_path: Path) -> None:
    payload = b"\x89PNG\r\n\x1a\n" + b"safe"
    path = stage_upload(
        BytesIO(payload),
        filename="../../avatar.png",
        content_type="image/png",
        size=len(payload),
        kind="image",
        staging_dir=str(tmp_path),
    )
    assert path.parent == tmp_path.resolve()
    assert path.name != "avatar.png"
    assert path.suffix == ".png"
    assert path.read_bytes() == payload

    with pytest.raises(ValueError, match="does not match"):
        stage_upload(
            BytesIO(b"not a png"), filename="fake.png", content_type="image/png",
            size=9, kind="image", staging_dir=str(tmp_path),
        )
    assert len(list(tmp_path.iterdir())) == 1


def test_film_exact_target_mapping_and_fps() -> None:
    fps = output_fps(target_frames=321, total_seconds=5.0)
    assert fps == 64.0
    assert 321 / fps == 5.015625  # MP4 container duration includes all frame display intervals.
    assert source_position(0, source_frames=81, target_frames=321) == (0, 1, 0.0)
    assert source_position(320, source_frames=81, target_frames=321) == (80, 80, 0.0)
    assert source_position(2, source_frames=3, target_frames=6) == (0, 1, 0.8)
    assert [source_position(i, source_frames=3, target_frames=6) for i in range(6)][-1][0] == 2
