"""Backend-owned, fixed Discord video workflows and their deterministic contract."""
from __future__ import annotations

import copy
import json
import re
import secrets
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal

VIDEO_SECONDS_MIN = 1.0
VIDEO_SECONDS_MAX = 20.0
VIDEO_FRAMES_MIN = 17
VIDEO_FRAMES_MAX = 321
FILM_FRAMES_MAX = 1921
IMAGE_MAX_BYTES = 20 * 1024 * 1024
VIDEO_MAX_BYTES = 100 * 1024 * 1024
IMAGE_TYPES = {
    "image/png": frozenset({".png"}),
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/webp": frozenset({".webp"}),
}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
DEFAULT_NEGATIVE = (
    "photorealistic, 3d render, live action, identity change, face distortion, "
    "malformed eyes, extra limbs, flicker, jitter, blur, camera shake, scene change, "
    "text, watermark, low quality"
)
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "workflows"


@dataclass(frozen=True)
class VideoTiming:
    seconds: float
    source_frames: int
    film_frames: int
    source_fps: float
    output_fps: float


@dataclass(frozen=True)
class MiniMaxH3Timing:
    requested_seconds: int
    source_frames: int
    source_fps: float
    timeline_span_seconds: float
    container_duration_seconds: float


def validate_minimax_h3_timing(seconds: int) -> MiniMaxH3Timing:
    """Align a requested duration to H3's 17k+5 frame contract at fixed 24 FPS."""
    if type(seconds) is not int or not 1 <= seconds <= 5:
        raise ValueError("total_seconds must be an integer between 1 and 5")
    requested_frames = round(seconds * 24)
    source_frames = requested_frames + ((5 - requested_frames) % 17)
    timeline_span = (source_frames - 1) / 24.0
    return MiniMaxH3Timing(
        requested_seconds=seconds,
        source_frames=source_frames,
        source_fps=24.0,
        timeline_span_seconds=timeline_span,
        container_duration_seconds=source_frames / 24.0,
    )


def validate_video_timing(seconds: float, source_frames: int, film_frames: int) -> VideoTiming:
    """Validate first-frame-to-last-frame timing; FPS is (frames - 1) / seconds."""
    if not VIDEO_SECONDS_MIN <= seconds <= VIDEO_SECONDS_MAX:
        raise ValueError("total_seconds must be between 1 and 20")
    if not VIDEO_FRAMES_MIN <= source_frames <= VIDEO_FRAMES_MAX:
        raise ValueError("source_frames must be between 17 and 321")
    if (source_frames - 1) % 4:
        raise ValueError("source_frames must be representable by Wan latent: 4n+1")
    if not source_frames <= film_frames <= FILM_FRAMES_MAX:
        raise ValueError("film_target_frames must be >= source_frames and <= 1921")
    return VideoTiming(
        seconds=float(seconds),
        source_frames=source_frames,
        film_frames=film_frames,
        source_fps=(source_frames - 1) / float(seconds),
        output_fps=(film_frames - 1) / float(seconds),
    )


def validate_video_dimensions(width: int, height: int) -> tuple[int, int]:
    if not 256 <= width <= 2048 or not 256 <= height <= 2048:
        raise ValueError("width and height must be between 256 and 2048")
    if width % 16 or height % 16:
        raise ValueError("width and height must be multiples of 16")
    return width, height


def validate_minimax_h3_dimensions(width: int, height: int) -> tuple[int, int]:
    if type(width) is not int or type(height) is not int:
        raise ValueError("width and height must be integers")
    if not 256 <= width <= 1024 or not 256 <= height <= 1024:
        raise ValueError("width and height must be between 256 and 1024")
    if width % 32 or height % 32:
        raise ValueError("MiniMax H3 width and height must be multiples of 32")
    if width * height > 786432:
        raise ValueError("MiniMax H3 output must not exceed 786432 pixels")
    return width, height


def validate_attachment(filename: str, content_type: str | None, size: int | None, *, kind: Literal["image", "video"]) -> str:
    types = IMAGE_TYPES if kind == "image" else VIDEO_TYPES
    limit = IMAGE_MAX_BYTES if kind == "image" else VIDEO_MAX_BYTES
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    ext = Path(filename or "").suffix.lower()
    expected_extensions = types.get(mime)
    if expected_extensions is None or ext not in (
        expected_extensions
        if isinstance(expected_extensions, frozenset)
        else {expected_extensions}
    ):
        allowed = ", ".join(sorted(types))
        raise ValueError(f"invalid {kind} attachment type; allowed MIME types: {allowed}")
    if size is not None and (size < 1 or size > limit):
        raise ValueError(f"{kind} attachment must be between 1 and {limit} bytes")
    return ext


def _signature_matches(data: bytes, *, mime: str) -> bool:
    """Small allowlist sniff; MIME and extension alone are caller-controlled."""
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime == "video/webm":
        return data.startswith(b"\x1aE\xdf\xa3")
    if mime in {"video/mp4", "video/quicktime"}:
        return len(data) >= 12 and data[4:8] == b"ftyp"
    return False


def stage_upload(stream: BinaryIO, *, filename: str, content_type: str | None, size: int | None, kind: Literal["image", "video"], staging_dir: str) -> Path:
    """Stream an allowlisted upload to an opaque filename under the configured external root."""
    ext = validate_attachment(filename, content_type, size, kind=kind)
    root = Path(staging_dir).expanduser().resolve()
    if not root.is_absolute():
        raise ValueError("video_staging_dir must be absolute")
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{uuid.uuid4().hex}{ext}"
    limit = IMAGE_MAX_BYTES if kind == "image" else VIDEO_MAX_BYTES
    written = 0
    signature = b""
    try:
        with destination.open("xb") as output:
            while chunk := stream.read(1024 * 1024):
                if not signature:
                    signature = chunk[:16]
                written += len(chunk)
                if written > limit:
                    raise ValueError(f"{kind} attachment exceeds {limit} bytes")
                output.write(chunk)
        if written < 1 or (size is not None and written != size):
            raise ValueError(f"{kind} attachment size mismatch")
        mime = (content_type or "").split(";", 1)[0].strip().lower()
        if not _signature_matches(signature, mime=mime):
            raise ValueError(f"{kind} attachment content does not match its MIME type")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def _load(name: str) -> dict[str, Any]:
    with (_TEMPLATE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _safe_prefix(prefix: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("._")
    return f"video/{clean or 'discord_video'}"


def build_animegen_i2v_workflow(
    *, image_path: Path, prompt: str, negative_prompt: str | None,
    timing: VideoTiming, width: int, height: int,
    filename_prefix: str = "discord_animegen_i2v",
) -> dict[str, Any]:
    width, height = validate_video_dimensions(width, height)
    workflow = copy.deepcopy(_load("discord_animegen_i2v_fixed.json"))
    workflow["97"]["inputs"]["image"] = str(image_path)
    workflow["93"]["inputs"]["text"] = prompt
    workflow["89"]["inputs"]["text"] = negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE
    workflow["98"]["inputs"]["width"] = width
    workflow["98"]["inputs"]["height"] = height
    workflow["98"]["inputs"]["length"] = timing.source_frames
    workflow["94"]["inputs"]["fps"] = timing.source_fps
    workflow["108"]["inputs"]["filename_prefix"] = _safe_prefix(filename_prefix)
    return workflow


def build_minimax_h3_i2v_workflow(
    *,
    image_path: Path,
    prompt: str,
    negative_prompt: str | None,
    timing: MiniMaxH3Timing,
    width: int,
    height: int,
    seed: int | None = None,
    filename_prefix: str = "discord_minimax_h3_i2v",
) -> dict[str, Any]:
    width, height = validate_minimax_h3_dimensions(width, height)
    workflow = copy.deepcopy(_load("discord_minimax_h3_i2v_fixed.json"))
    combined_prompt = prompt.strip()
    if negative_prompt and negative_prompt.strip():
        combined_prompt = f"{combined_prompt}\nAvoid: {negative_prompt.strip()}"
    workflow["114"]["inputs"]["image"] = str(image_path)
    workflow["105:104"]["inputs"]["prompt"] = combined_prompt
    workflow["105:104"]["inputs"]["width"] = width
    workflow["105:104"]["inputs"]["height"] = height
    workflow["105:104"]["inputs"]["length"] = timing.source_frames
    workflow["105:126"]["inputs"]["value"] = True
    workflow["105:124"]["inputs"]["value"] = 8
    workflow["105:15"]["inputs"]["noise_seed"] = (
        seed if seed is not None else secrets.randbelow(2**63)
    )
    workflow["92"]["inputs"]["filename_prefix"] = _safe_prefix(filename_prefix)
    workflow["92"]["inputs"]["format"] = "mp4"
    workflow["92"]["inputs"]["format.codec"] = "h264"
    workflow["92"]["inputs"]["codec"] = "h264"
    return workflow


def build_wan_animate_workflow(*, reference_path: Path, driver_path: Path, prompt: str, negative_prompt: str | None, timing: VideoTiming, filename_prefix: str = "discord_wan22_animate") -> dict[str, Any]:
    workflow = copy.deepcopy(_load("discord_wan22_animate_fixed.json"))
    workflow["1"]["inputs"]["file"] = str(driver_path)
    workflow["5"]["inputs"]["image"] = str(reference_path)
    workflow["9"]["inputs"]["text"] = prompt
    workflow["10"]["inputs"]["text"] = negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE
    workflow["15"]["inputs"]["length"] = timing.source_frames
    # Never use length=0: ImageFromBatch interprets it as an empty batch in this graph.
    workflow["19"]["inputs"]["length"] = timing.source_frames
    workflow["20"]["inputs"]["fps"] = timing.source_fps
    workflow["21"]["inputs"]["filename_prefix"] = _safe_prefix(filename_prefix)
    return workflow
