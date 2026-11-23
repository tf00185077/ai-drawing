from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.core.fixed_video_workflows import (
    build_animegen_i2v_workflow,
    build_minimax_h3_i2v_workflow,
    build_wan_animate_workflow,
    stage_upload,
    validate_minimax_h3_timing,
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
        width=1024,
        height=1024,
    )
    assert workflow["110"]["inputs"]["unet_name"] == "AnimeGen-I2V-GGUF/I2V_high_noise_Q4_K_M.gguf"
    assert workflow["111"]["inputs"]["unet_name"] == "AnimeGen-I2V-GGUF/I2V_low_noise_Q4_K_M.gguf"
    assert workflow["93"]["inputs"]["text"] == "turn and smile"
    assert workflow["89"]["inputs"]["text"] == "bad motion"
    assert workflow["97"]["inputs"]["image"] == str(tmp_path / "input.png")
    assert workflow["98"]["inputs"]["length"] == 81
    assert workflow["98"]["inputs"]["width"] == 1024
    assert workflow["98"]["inputs"]["height"] == 1024
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


def test_minimax_h3_builder_aligns_17k_plus_5_and_uses_exact_stack(tmp_path: Path) -> None:
    timing = validate_minimax_h3_timing(5)
    assert timing.source_frames == 124
    assert timing.timeline_span_seconds == 123 / 24
    assert timing.container_duration_seconds == 124 / 24

    workflow = build_minimax_h3_i2v_workflow(
        image_path=tmp_path / "input.png",
        prompt="wave gently",
        negative_prompt="camera shake, distorted fingers",
        timing=timing,
        width=768,
        height=512,
        seed=123,
    )
    assert workflow["114"]["inputs"]["image"] == str(tmp_path / "input.png")
    assert workflow["105:104"]["inputs"]["prompt"] == (
        "wave gently\nAvoid: camera shake, distorted fingers"
    )
    assert workflow["105:104"]["inputs"]["width"] == 768
    assert workflow["105:104"]["inputs"]["height"] == 512
    assert workflow["105:104"]["inputs"]["length"] == 124
    assert workflow["105:126"]["inputs"]["value"] is True
    assert workflow["105:124"]["inputs"]["value"] == 8
    assert workflow["105:121"]["inputs"]["lora_name"] == (
        "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
    )
    assert workflow["105:6"]["inputs"]["unet_name"] == (
        "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
    )
    assert workflow["105:13"]["inputs"]["clip_name"] == (
        "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    )
    assert workflow["105:11"]["inputs"]["vae_name"] == "minimax_h3_video_vae_fp16.safetensors"
    assert workflow["105:24"]["inputs"]["vae_name"] == "minimax_h3_audio_vae_fp32.safetensors"


@pytest.mark.parametrize("seconds,frames", [(1, 39), (2, 56), (3, 73), (4, 107), (5, 124)])
def test_minimax_h3_timing_contract(seconds: int, frames: int) -> None:
    timing = validate_minimax_h3_timing(seconds)
    assert timing.source_frames == frames
    assert timing.timeline_span_seconds == (frames - 1) / 24
    assert timing.container_duration_seconds == frames / 24


@pytest.mark.parametrize("seconds", [True, 0, 6, 1.5])
def test_minimax_h3_timing_rejects_non_integer_or_out_of_range(seconds) -> None:
    with pytest.raises(ValueError):
        validate_minimax_h3_timing(seconds)


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
