from __future__ import annotations

import io
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import Settings
from app.services.argus_mlx_i2v import (
    ArgusMlxI2VError,
    ArgusMlxI2VRequest,
    ArgusMlxI2VRunner,
)


def _settings(tmp_path: Path) -> Settings:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    python = runtime / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    script = runtime / "generate.py"
    script.write_text("pass\n")
    checkpoint = tmp_path / "checkpoint"; checkpoint.mkdir()
    transformer = tmp_path / "transformer"; transformer.mkdir()
    turbo = tmp_path / "turbo"; turbo.mkdir()
    (checkpoint / "model_index.json").write_text("{}")
    (checkpoint / "text_encoder").mkdir()
    (checkpoint / "text_encoder" / "model.safetensors.index.json").write_text("{}")
    (transformer / "config.json").write_text("{}")
    (transformer / "model.safetensors.index.json").write_text("{}")
    (turbo / "adapter.safetensors.index.json").write_text("{}")
    work = tmp_path / "work"; work.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    ffmpeg = tmp_path / "ffmpeg"; ffmpeg.write_text("#!/bin/sh\n"); ffmpeg.chmod(0o755)
    ffprobe = tmp_path / "ffprobe"; ffprobe.write_text("#!/bin/sh\n"); ffprobe.chmod(0o755)
    return Settings(
        argus_mlx_runtime_root=str(runtime), argus_mlx_python=str(python),
        argus_mlx_generate_script=str(script), argus_mlx_checkpoint=str(checkpoint),
        argus_mlx_transformer=str(transformer), argus_mlx_turbo_lora=str(turbo),
        argus_mlx_work_root=str(work), argus_mlx_hf_cache=str(cache),
        argus_mlx_accept_license=True,
        argus_mlx_ffmpeg=str(ffmpeg), argus_mlx_ffprobe=str(ffprobe),
    )


def test_argus_argv_is_exact_and_prompt_is_one_element(tmp_path):
    settings = _settings(tmp_path)
    image = tmp_path / "input.png"; image.write_bytes(b"png")
    request = ArgusMlxI2VRequest("job-1", image, "hello; touch /tmp/pwned $(id)", 768, 512, 5, 124, 42)
    work_dir = Path(settings.argus_mlx_work_root) / request.job_id
    argv = ArgusMlxI2VRunner(settings).build_argv(request, work_dir)
    assert argv == [
        settings.argus_mlx_python, settings.argus_mlx_generate_script, request.prompt,
        "--checkpoint", settings.argus_mlx_checkpoint,
        "--transformer", settings.argus_mlx_transformer,
        "--turbo-lora", settings.argus_mlx_turbo_lora,
        "--turbo-lora-scale", "1.0", "--profile", "quality", "--low-memory",
        "--stream-blocks", "--image", str(image), "--anchor", "first",
        "--resolution", "768x512", "--duration", "5", "--steps", "9",
        "--seed", "42", "--memory-pressure-guard", "--no-block-cache",
        "--dense-dequant-profile", "off", "--require-muxed-mp4",
        "--ffmpeg", settings.argus_mlx_ffmpeg,
        "--forward-profile-json", str(work_dir / "forward-profile.json"),
        "--output", str(work_dir / "output.mp4"),
    ]
    assert argv.count(request.prompt) == 1


def test_argus_prerequisite_error_is_stable(tmp_path):
    settings = _settings(tmp_path)
    __import__("shutil").rmtree(settings.argus_mlx_transformer)
    with pytest.raises(ArgusMlxI2VError) as caught:
        ArgusMlxI2VRunner(settings).validate_prerequisites()
    assert caught.value.code == "transformer_missing"
    assert "argus_mlx_transformer" in str(caught.value)


def test_argus_rejects_python_outside_runtime_venv(tmp_path):
    settings = _settings(tmp_path)
    other_python = tmp_path / "other-python"
    other_python.write_text("#!/bin/sh\n")
    other_python.chmod(0o755)
    settings = settings.model_copy(update={"argus_mlx_python": str(other_python)})
    with pytest.raises(ArgusMlxI2VError) as caught:
        ArgusMlxI2VRunner(settings).validate_prerequisites()
    assert caught.value.code == "runtime_python_mismatch"


def test_argus_license_requires_explicit_operator_opt_in(tmp_path):
    settings = _settings(tmp_path).model_copy(update={"argus_mlx_accept_license": False})
    with pytest.raises(ArgusMlxI2VError) as caught:
        ArgusMlxI2VRunner(settings).validate_prerequisites()
    assert caught.value.code == "license_not_accepted"


def test_argus_run_uses_process_group_fixed_license_env_and_bounded_contract(tmp_path):
    settings = _settings(tmp_path)
    image = tmp_path / "input.png"
    image.write_bytes(b"png")
    request = ArgusMlxI2VRequest("job-run", image, "small wave", 256, 256, 1, 39, 42)
    observed = {}

    class FakeProcess:
        pid = 12345
        stdout = io.BytesIO(("stdout " + "TO" + "KEN=abc123\n").encode())
        stderr = io.BytesIO(b"stderr\n")

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def fake_popen(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        Path(argv[argv.index("--output") + 1]).write_bytes(b"mp4")
        Path(argv[argv.index("--forward-profile-json") + 1]).write_text("{}")
        return FakeProcess()

    with patch("app.services.argus_mlx_i2v.subprocess.Popen", side_effect=fake_popen), patch(
        "app.services.argus_mlx_i2v._probe_muxed_mp4",
        return_value={"fps": 24.0, "frame_count": 39, "duration": 1.625},
    ):
        result = ArgusMlxI2VRunner(settings).run(request)

    assert observed["kwargs"]["shell"] is False
    assert observed["kwargs"]["start_new_session"] is True
    assert observed["kwargs"]["cwd"] == settings.argus_mlx_runtime_root
    assert observed["kwargs"]["env"]["MINIMAX_H3_ACCEPT_LICENSE"] == "1"
    assert observed["kwargs"]["env"]["HF_HOME"] == settings.argus_mlx_hf_cache
    redacted = "[" + "REDACTED" + "]"
    assert "abc123" not in result.log_tail
    assert "TO" + "KEN=" + redacted in result.log_tail


def test_argus_error_sanitizes_sensitive_values():
    redacted = "[" + "REDACTED" + "]"
    error = ArgusMlxI2VError(
        "failed",
        "K" + "EY=abc123",
        log_tail="PASS" + "WORD=def456",
    )
    assert str(error) == "K" + "EY=" + redacted
    assert error.log_tail == "PASS" + "WORD=" + redacted


def test_argus_timeout_terminates_process_group_and_removes_partial_files(tmp_path):
    settings = _settings(tmp_path)
    image = tmp_path / "input.png"
    image.write_bytes(b"png")
    request = ArgusMlxI2VRequest("job-timeout", image, "small wave", 256, 256, 1, 39, 42)

    class TimedOutProcess:
        pid = 12345
        stdout = io.BytesIO()
        stderr = io.BytesIO()

        def wait(self, timeout=None):
            raise __import__("subprocess").TimeoutExpired("argus", timeout)

        def poll(self):
            return None

    terminated = []
    with patch("app.services.argus_mlx_i2v.subprocess.Popen", return_value=TimedOutProcess()), patch(
        "app.services.argus_mlx_i2v._terminate_process_group",
        side_effect=lambda process: terminated.append(process.pid),
    ):
        with pytest.raises(ArgusMlxI2VError) as caught:
            ArgusMlxI2VRunner(settings).run(request)

    assert caught.value.code == "timeout"
    assert terminated == [12345]
    work_dir = Path(settings.argus_mlx_work_root) / request.job_id
    assert not (work_dir / "output.mp4").exists()
    assert not (work_dir / "forward-profile.json").exists()


def test_argus_shutdown_terminates_current_child(tmp_path):
    runner = ArgusMlxI2VRunner(_settings(tmp_path))
    process = object()
    runner._process = process
    terminated = []
    with patch(
        "app.services.argus_mlx_i2v._terminate_process_group",
        side_effect=lambda child: terminated.append(child),
    ):
        runner.shutdown()
    assert terminated == [process]


@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf, True])
def test_argus_timeout_is_positive_finite(value):
    with pytest.raises(Exception):
        Settings(argus_mlx_timeout_seconds=value)


def test_env_example_has_argus_inventory():
    text = (Path(__file__).parents[2] / ".env.example").read_text()
    keys = [
        "ARGUS_MLX_RUNTIME_ROOT", "ARGUS_MLX_PYTHON", "ARGUS_MLX_GENERATE_SCRIPT",
        "ARGUS_MLX_CHECKPOINT", "ARGUS_MLX_TRANSFORMER", "ARGUS_MLX_TURBO_LORA",
        "ARGUS_MLX_WORK_ROOT", "ARGUS_MLX_HF_CACHE", "ARGUS_MLX_ACCEPT_LICENSE",
        "ARGUS_MLX_MAX_CONCURRENCY",
        "ARGUS_MLX_TIMEOUT_SECONDS", "ARGUS_MLX_FFMPEG", "ARGUS_MLX_FFPROBE",
    ]
    for key in keys:
        assert text.count(f"{key}=") == 1
    assert "MINIMAX_H3_EXECUTION_TARGET" not in text
