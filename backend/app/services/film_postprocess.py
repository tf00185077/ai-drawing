"""Exact-count FILM post-processing for fixed video jobs (Apple Silicon friendly)."""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def output_fps(*, target_frames: int, total_seconds: float) -> float:
    if target_frames < 2 or total_seconds <= 0:
        raise ValueError("target_frames must be >= 2 and total_seconds must be positive")
    return (target_frames - 1) / total_seconds


def source_position(index: int, *, source_frames: int, target_frames: int) -> tuple[int, int, float]:
    """Map an output frame onto the source endpoint span, including exact endpoints."""
    if source_frames < 2 or target_frames < source_frames or not 0 <= index < target_frames:
        raise ValueError("invalid frame mapping")
    position = index * (source_frames - 1) / (target_frames - 1)
    left = min(int(math.floor(position)), source_frames - 1)
    right = min(left + 1, source_frames - 1)
    return left, right, position - left


def probe_video(path: Path, *, ffprobe: str | None = None) -> dict[str, Any]:
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe is required for FILM post-processing")
    result = subprocess.run(
        [executable, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,nb_frames,r_frame_rate", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return stream


def interpolate_video_exact(*, input_path: Path, output_path: Path, target_frames: int, total_seconds: float, model_path: Path, work_root: Path, ffmpeg: str | None = None, ffprobe: str | None = None) -> dict[str, Any]:
    """Create exactly target_frames while preserving source frame 0/last and their span."""
    ffmpeg_exe = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required for FILM post-processing")
    if not model_path.is_file():
        raise FileNotFoundError(f"FILM model not found: {model_path}")
    work_root.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="film_", dir=work_root))
    source_dir, output_dir = temp / "source", temp / "output"
    source_dir.mkdir()
    output_dir.mkdir()
    try:
        subprocess.run([ffmpeg_exe, "-y", "-i", str(input_path), str(source_dir / "%06d.png")], check=True, capture_output=True)
        frames = sorted(source_dir.glob("*.png"))
        if len(frames) < 2:
            raise RuntimeError("FILM requires at least two decoded frames")
        if target_frames < len(frames):
            raise ValueError("FILM target cannot be smaller than decoded source frame count")

        # Heavy imports stay inside the post-process path, not backend startup/tests.
        import numpy as np
        import torch
        from PIL import Image

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        model = torch.jit.load(str(model_path), map_location=device).eval()

        def load_image(path: Path):
            array = np.asarray(Image.open(path).convert("RGB"), dtype="float32") / 255.0
            return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(device=device, dtype=torch.float16)

        def save_image(tensor, path: Path) -> None:
            array = tensor.clamp(0, 1).float().cpu()[0].permute(1, 2, 0).numpy()
            Image.fromarray((array * 255).round().astype("uint8")).save(path)

        cached: dict[int, Any] = {}
        with torch.no_grad():
            for output_index in range(target_frames):
                left, right, fraction = source_position(output_index, source_frames=len(frames), target_frames=target_frames)
                destination = output_dir / f"{output_index + 1:06d}.png"
                if fraction <= 1e-9 or left == right:
                    shutil.copy2(frames[left], destination)
                    continue
                a = cached.setdefault(left, load_image(frames[left]))
                b = cached.setdefault(right, load_image(frames[right]))
                middle = model(a, b, torch.tensor([[fraction]], dtype=torch.float16, device=device))
                save_image(middle, destination)
                # Bound memory to adjacent source pairs.
                cached = {key: value for key, value in cached.items() if key >= left}

        fps = output_fps(target_frames=target_frames, total_seconds=total_seconds)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [ffmpeg_exe, "-y", "-framerate", f"{fps:.12g}", "-i", str(output_dir / "%06d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(output_path)],
            check=True,
            capture_output=True,
        )
        info = probe_video(output_path, ffprobe=ffprobe)
        try:
            actual_frames = int(info["nb_frames"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("ffprobe did not report FILM output frame count") from exc
        if actual_frames != target_frames:
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"FILM output frame mismatch: expected {target_frames}, got {actual_frames}")
        return {
            "fps": fps,
            "frame_count": actual_frames,
            "timeline_span_seconds": total_seconds,
            "container_duration_seconds": actual_frames / fps,
            "width": int(info["width"]),
            "height": int(info["height"]),
            "timeline_contract": "first_to_last_span",
        }
    finally:
        shutil.rmtree(temp, ignore_errors=True)
