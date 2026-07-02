"""Wan multi-keyframe video workflow builder.

Builds a single ComfyUI workflow that consumes multiple still images as keyframes
through WanDancerPadKeyframes/WanDancerVideo. This is intentionally different
from generating pairwise first/last-frame segments and concatenating them.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import uuid
import wave
from pathlib import Path
from typing import Any

from app.config import Settings

_TEMPLATE_NAME = "gen_img2video_wan_5keyframe_single_workflow.json"
_KEYFRAME_NODE_IDS = {str(i) for i in range(110, 119)}
_AUDIO_NODE_ID = "119"
_PAD_NODE_ID = "120"
_WANDANCER_NODE_ID = "98"
_CREATE_VIDEO_NODE_ID = "94"
_SAVE_VIDEO_NODE_ID = "108"
_POSITIVE_NODE_ID = "93"
_NEGATIVE_NODE_ID = "89"
_HIGH_SAMPLER_NODE_ID = "86"
_LOW_SAMPLER_NODE_ID = "85"


def _template_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "workflows" / _TEMPLATE_NAME


def _safe_stem(value: str, fallback: str = "wan_keyframes") -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or fallback


def _resolve_gallery_file(gallery_dir: Path, rel_path: str) -> Path:
    path = (gallery_dir / rel_path).resolve()
    try:
        path.relative_to(gallery_dir)
    except ValueError as exc:
        raise ValueError(f"Unsafe gallery path: {rel_path}") from exc
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Gallery keyframe not found: {rel_path}")
    return path


def _write_silent_wav(path: Path, *, duration_seconds: float, sample_rate: int = 16000) -> None:
    frames = max(1, int(duration_seconds * sample_rate))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frames)


def _copy_keyframes_to_comfy_input(
    *,
    settings: Settings,
    image_paths: list[str],
    task_slug: str,
) -> tuple[list[str], str]:
    gallery_dir = Path(settings.gallery_dir).expanduser().resolve()
    input_root = Path(settings.comfyui_input_dir).expanduser().resolve()
    task_dir = input_root / task_slug
    task_dir.mkdir(parents=True, exist_ok=True)

    relative_inputs: list[str] = []
    for index, rel_path in enumerate(image_paths, 1):
        source = _resolve_gallery_file(gallery_dir, rel_path)
        ext = source.suffix.lower() or ".png"
        dest_name = f"keyframe_{index:02d}{ext}"
        dest = task_dir / dest_name
        shutil.copy2(source, dest)
        relative_inputs.append(f"{task_slug}/{dest_name}")
    return relative_inputs, str(task_dir)


def _configure_keyframe_nodes(workflow: dict[str, Any], relative_inputs: list[str]) -> None:
    # Remove the fixed five-keyframe nodes from the starter template, then build
    # an N-keyframe LoadImage/ImageBatch chain. Node ids are deterministic to
    # make saved workflows easy to inspect.
    for node_id in _KEYFRAME_NODE_IDS:
        workflow.pop(node_id, None)

    load_ids: list[str] = []
    next_id = 110
    for rel_input in relative_inputs:
        node_id = str(next_id)
        next_id += 1
        workflow[node_id] = {"class_type": "LoadImage", "inputs": {"image": rel_input}}
        load_ids.append(node_id)

    if len(load_ids) == 1:
        final_image_ref: list[Any] = [load_ids[0], 0]
    else:
        current_ref: list[Any] = [load_ids[0], 0]
        for idx, load_id in enumerate(load_ids[1:], 1):
            node_id = str(next_id)
            next_id += 1
            workflow[node_id] = {
                "class_type": "ImageBatch",
                "inputs": {"image1": current_ref, "image2": [load_id, 0]},
            }
            current_ref = [node_id, 0]
        final_image_ref = current_ref

    workflow[_PAD_NODE_ID]["inputs"]["images"] = final_image_ref


def build_wan_keyframe_workflow(
    *,
    settings: Settings,
    image_paths: list[str],
    prompt: str,
    negative_prompt: str | None = None,
    width: int = 320,
    height: int = 480,
    length: int = 161,
    fps: float = 16.1,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
    filename_prefix: str = "video/wan_keyframes",
    task_slug: str | None = None,
) -> dict[str, Any]:
    """Create a WanDancer multi-keyframe API workflow and stage inputs.

    image_paths are gallery_dir-relative paths. They are copied into the ComfyUI
    input directory because LoadImage references ComfyUI input-relative files.
    """
    if len(image_paths) < 2:
        raise ValueError("Wan keyframe video requires at least 2 images")
    if length < 17:
        raise ValueError("length must be at least 17 frames for stable WanDancer timing")
    if width % 16 != 0 or height % 16 != 0:
        raise ValueError("width and height must be multiples of 16")
    if fps <= 0:
        raise ValueError("fps must be positive")

    template = json.loads(_template_path().read_text())
    workflow: dict[str, Any] = copy.deepcopy(template)
    slug = _safe_stem(task_slug or f"wan_keyframes_{uuid.uuid4().hex[:8]}")
    relative_inputs, _ = _copy_keyframes_to_comfy_input(
        settings=settings,
        image_paths=image_paths,
        task_slug=slug,
    )
    _configure_keyframe_nodes(workflow, relative_inputs)

    # A short silent wav keeps WanDancerPadKeyframes in a single segment while
    # still giving it audio duration metadata for keyframe placement.
    segment_duration = length / 30.0
    silent_duration = max(0.3, segment_duration - 0.1)
    audio_rel = f"{slug}/silent_{int(silent_duration * 1000)}ms.wav"
    audio_abs = Path(settings.comfyui_input_dir).expanduser().resolve() / audio_rel
    _write_silent_wav(audio_abs, duration_seconds=silent_duration)

    workflow[_AUDIO_NODE_ID]["inputs"]["audio"] = audio_rel
    workflow[_PAD_NODE_ID]["inputs"]["segment_length"] = length
    workflow[_PAD_NODE_ID]["inputs"]["segment_index"] = 0
    workflow[_PAD_NODE_ID]["inputs"]["audio"] = [_AUDIO_NODE_ID, 0]

    wan_inputs = workflow[_WANDANCER_NODE_ID]["inputs"]
    wan_inputs["width"] = width
    wan_inputs["height"] = height
    wan_inputs["length"] = length
    wan_inputs["start_image"] = [_PAD_NODE_ID, 0]
    wan_inputs["mask"] = [_PAD_NODE_ID, 1]

    workflow[_CREATE_VIDEO_NODE_ID]["inputs"]["fps"] = fps
    workflow[_SAVE_VIDEO_NODE_ID]["inputs"]["filename_prefix"] = filename_prefix

    workflow[_POSITIVE_NODE_ID]["inputs"]["text"] = prompt
    if negative_prompt is not None:
        workflow[_NEGATIVE_NODE_ID]["inputs"]["text"] = negative_prompt

    for node_id in (_HIGH_SAMPLER_NODE_ID, _LOW_SAMPLER_NODE_ID):
        inputs = workflow[node_id]["inputs"]
        inputs["steps"] = steps
        inputs["cfg"] = cfg
    if seed is not None:
        workflow[_HIGH_SAMPLER_NODE_ID]["inputs"]["noise_seed"] = seed
        # Keep the low-noise pass deterministic with the high-noise pass while
        # preserving the template's add_noise=disable behavior.
        workflow[_LOW_SAMPLER_NODE_ID]["inputs"]["noise_seed"] = seed

    return workflow
