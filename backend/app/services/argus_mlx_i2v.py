"""Fail-closed MiniMax H3 Argus/MLX subprocess runner."""
from __future__ import annotations

import json
import math
import os
import re
import signal
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings

_STREAM_TAIL = 16 * 1024
_LOG_TAIL = 24 * 1024
_SECRET = re.compile(r"(?i)\b(token|key|secret|password)\s*=\s*([^\s]+)")


@dataclass(frozen=True)
class ArgusMlxI2VRequest:
    job_id: str
    staged_image: Path
    prompt: str
    width: int
    height: int
    total_seconds: int
    native_frames: int
    seed: int


@dataclass(frozen=True)
class ArgusMlxI2VResult:
    output_path: Path
    profile_path: Path
    log_tail: str
    fps: float
    frame_count: int
    duration: float
    width: int
    height: int


class ArgusMlxI2VError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, exit_code: int | None = None,
                 log_tail: str = ""):
        self.code = code
        self.safe_message = _sanitize(safe_message)[:2048]
        self.exit_code = exit_code
        self.log_tail = _sanitize(log_tail)[-_LOG_TAIL:]
        super().__init__(self.safe_message)


def _sanitize(value: str) -> str:
    text = _SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", str(value))
    return "".join(ch if ch in "\n\r\t" or ord(ch) >= 32 else "?" for ch in text)


def _terminate_process_group(process: subprocess.Popen, *, grace: float = 5.0) -> None:
    if process.poll() is not None:
        process.wait()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=grace)


def _probe_muxed_mp4(settings: Settings, path: Path, *, width: int, height: int,
                      native_frames: int) -> dict[str, int | float | str]:
    if not path.is_file() or path.stat().st_size < 1:
        raise ArgusMlxI2VError("output_missing", "Argus output MP4 is missing or empty")
    try:
        decoded = subprocess.run(
            [settings.argus_mlx_ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120, shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArgusMlxI2VError("decode_failed", "MP4 decode validation failed") from exc
    if decoded.returncode:
        raise ArgusMlxI2VError("decode_failed", "MP4 cannot be fully decoded")
    try:
        probe = subprocess.run(
            [settings.argus_mlx_ffprobe, "-v", "error", "-show_streams", "-show_format",
             "-count_frames", "-of", "json", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, shell=False,
            check=False, text=True,
        )
        payload = json.loads(probe.stdout) if probe.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise ArgusMlxI2VError("probe_failed", "MP4 metadata validation failed") from exc
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        raise ArgusMlxI2VError("probe_failed", "MP4 metadata validation failed")
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise ArgusMlxI2VError("video_missing", "MP4 has no video stream")
    if not audio:
        raise ArgusMlxI2VError("audio_missing", "MP4 has no audio stream")
    if video.get("codec_name") != "h264":
        raise ArgusMlxI2VError("video_codec_invalid", "MP4 video codec must be H.264")
    if audio.get("codec_name") != "aac":
        raise ArgusMlxI2VError("audio_codec_invalid", "MP4 audio codec must be AAC")
    def ratio(raw: Any) -> float:
        left, right = str(raw).split("/", 1)
        return float(left) / float(right)
    try:
        fps = ratio(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        frames = int(video.get("nb_read_frames") or video.get("nb_frames"))
        duration = float(payload.get("format", {}).get("duration") or video.get("duration"))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ArgusMlxI2VError("probe_failed", "MP4 timing metadata is invalid") from exc
    if not math.isclose(fps, 24.0, abs_tol=0.01):
        raise ArgusMlxI2VError("fps_invalid", "MP4 frame rate must be 24 FPS")
    if int(video.get("width", 0)) != width or int(video.get("height", 0)) != height:
        raise ArgusMlxI2VError("dimensions_invalid", "MP4 dimensions do not match request")
    if frames != native_frames:
        raise ArgusMlxI2VError("frame_count_invalid", "MP4 frame count does not match request")
    if not math.isclose(duration, native_frames / 24.0, abs_tol=1 / 24 + 0.002):
        raise ArgusMlxI2VError("duration_invalid", "MP4 duration does not match native frames")
    return {"fps": fps, "frame_count": frames, "duration": duration,
            "width": width, "height": height}


class ArgusMlxI2VRunner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None

    def validate_prerequisites(self) -> None:
        if not self.settings.argus_mlx_accept_license:
            raise ArgusMlxI2VError(
                "license_not_accepted",
                "MiniMax-H3 model license has not been explicitly accepted by the operator",
            )
        runtime_root = Path(self.settings.argus_mlx_runtime_root).expanduser().absolute()
        configured_python = Path(self.settings.argus_mlx_python).expanduser().absolute()
        expected_python = runtime_root / ".venv" / "bin" / "python"
        if configured_python != expected_python:
            raise ArgusMlxI2VError(
                "runtime_python_mismatch",
                "Argus Python must be the configured runtime .venv/bin/python",
            )
        checks = (
            ("argus_mlx_runtime_root", "runtime_missing", "dir", False),
            ("argus_mlx_python", "python_missing", "file", True),
            ("argus_mlx_generate_script", "script_missing", "file", False),
            ("argus_mlx_checkpoint", "checkpoint_missing", "dir", False),
            ("argus_mlx_transformer", "transformer_missing", "dir", False),
            ("argus_mlx_turbo_lora", "turbo_lora_missing", "dir", False),
            ("argus_mlx_hf_cache", "hf_cache_missing", "dir", False),
            ("argus_mlx_ffmpeg", "ffmpeg_missing", "file", True),
            ("argus_mlx_ffprobe", "ffprobe_missing", "file", True),
        )
        for key, code, kind, executable in checks:
            path = Path(getattr(self.settings, key))
            valid = path.is_dir() if kind == "dir" else path.is_file()
            if not valid or (executable and not os.access(path, os.X_OK)):
                raise ArgusMlxI2VError(code, f"required setting {key} is unavailable")
        manifests = (
            (Path(self.settings.argus_mlx_checkpoint) / "model_index.json", "checkpoint_incomplete"),
            (Path(self.settings.argus_mlx_checkpoint) / "text_encoder" / "model.safetensors.index.json", "checkpoint_incomplete"),
            (Path(self.settings.argus_mlx_transformer) / "config.json", "transformer_incomplete"),
            (Path(self.settings.argus_mlx_transformer) / "model.safetensors.index.json", "transformer_incomplete"),
            (Path(self.settings.argus_mlx_turbo_lora) / "adapter.safetensors.index.json", "turbo_lora_incomplete"),
        )
        for manifest, code in manifests:
            if not manifest.is_file():
                raise ArgusMlxI2VError(
                    code, f"required Argus model manifest is missing: {manifest.name}"
                )
        root = Path(self.settings.argus_mlx_work_root)
        try:
            root.mkdir(parents=True, exist_ok=True)
            if not os.access(root, os.W_OK):
                raise OSError
        except OSError as exc:
            raise ArgusMlxI2VError("storage_unavailable", "argus_mlx_work_root is unavailable") from exc

    def build_argv(self, request: ArgusMlxI2VRequest, work_dir: Path) -> list[str]:
        s = self.settings
        return [s.argus_mlx_python, s.argus_mlx_generate_script, request.prompt,
                "--checkpoint", s.argus_mlx_checkpoint, "--transformer", s.argus_mlx_transformer,
                "--turbo-lora", s.argus_mlx_turbo_lora, "--turbo-lora-scale", "1.0",
                "--profile", "quality", "--low-memory", "--stream-blocks",
                "--image", str(request.staged_image), "--anchor", "first",
                "--resolution", f"{request.width}x{request.height}",
                "--duration", str(request.total_seconds), "--steps", "9", "--seed", str(request.seed),
                "--memory-pressure-guard", "--no-block-cache", "--dense-dequant-profile", "off",
                "--require-muxed-mp4", "--ffmpeg", s.argus_mlx_ffmpeg,
                "--forward-profile-json", str(work_dir / "forward-profile.json"),
                "--output", str(work_dir / "output.mp4")]

    def run(self, request: ArgusMlxI2VRequest) -> ArgusMlxI2VResult:
        self.validate_prerequisites()
        work_dir = (Path(self.settings.argus_mlx_work_root) / request.job_id).resolve()
        root = Path(self.settings.argus_mlx_work_root).resolve()
        if not work_dir.is_relative_to(root) or work_dir == root:
            raise ArgusMlxI2VError("invalid_job_id", "job id cannot select a work path")
        work_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        output, profile, log_path = work_dir / "output.mp4", work_dir / "forward-profile.json", work_dir / "runner.log"
        tails: dict[str, deque[bytes]] = {"stdout": deque(), "stderr": deque()}
        sizes = {"stdout": 0, "stderr": 0}
        def drain(name: str, stream, log):
            while chunk := stream.read(4096):
                log.write(chunk); log.flush(); tails[name].append(chunk); sizes[name] += len(chunk)
                while sizes[name] > _STREAM_TAIL and tails[name]: sizes[name] -= len(tails[name].popleft())
        try:
            env = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL", "DYLD_LIBRARY_PATH"}}
            env["HF_HOME"] = self.settings.argus_mlx_hf_cache
            env["HUGGINGFACE_HUB_CACHE"] = self.settings.argus_mlx_hf_cache
            env["MINIMAX_H3_ACCEPT_LICENSE"] = "1"
            for directory in (work_dir / "home", work_dir / "tmp", work_dir / "cache"):
                directory.mkdir()
            env["HOME"] = str(work_dir / "home")
            env["TMPDIR"] = str(work_dir / "tmp")
            env["XDG_CACHE_HOME"] = str(work_dir / "cache")
            with log_path.open("ab", buffering=0) as log:
                process = subprocess.Popen(self.build_argv(request, work_dir), cwd=self.settings.argus_mlx_runtime_root,
                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, shell=False)
                with self._lock: self._process = process
                threads = [threading.Thread(target=drain, args=(name, stream, log), daemon=True)
                           for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
                for thread in threads: thread.start()
                try: code = process.wait(timeout=self.settings.argus_mlx_timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    _terminate_process_group(process)
                    for thread in threads:
                        thread.join(timeout=5)
                    timeout_tail = b"\n".join(
                        b"".join(tails[key]) for key in ("stdout", "stderr")
                    ).decode("utf-8", "replace")
                    raise ArgusMlxI2VError(
                        "timeout", "Argus generation timed out", log_tail=timeout_tail
                    ) from exc
                finally:
                    for thread in threads: thread.join(timeout=5)
                    with self._lock:
                        if self._process is process: self._process = None
            tail = _sanitize(b"\n".join(b"".join(tails[k]) for k in ("stdout", "stderr")).decode("utf-8", "replace"))[-_LOG_TAIL:]
            if code:
                raise ArgusMlxI2VError("process_failed", "Argus generation process failed", exit_code=code, log_tail=tail)
            metadata = _probe_muxed_mp4(self.settings, output, width=request.width, height=request.height, native_frames=request.native_frames)
            return ArgusMlxI2VResult(output, profile, tail, float(metadata["fps"]), int(metadata["frame_count"]),
                                    float(metadata["duration"]), request.width, request.height)
        except Exception:
            output.unlink(missing_ok=True); profile.unlink(missing_ok=True)
            raise

    def shutdown(self) -> None:
        with self._lock: process = self._process
        if process is not None: _terminate_process_group(process)
