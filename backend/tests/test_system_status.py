from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings, get_settings
from app.services.dependency_status import get_system_status


class Probe:
    def __init__(self, result: object = True, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, *, timeout: float) -> object:
        self.calls.append((url, timeout))
        if self.error is not None:
            raise self.error
        return self.result


def _settings(tmp_path: Path, *, mode: str = "external") -> Settings:
    checkpoints = tmp_path / "checkpoints"
    diffusion_models = tmp_path / "diffusion_models"
    checkpoints.mkdir(exist_ok=True)
    diffusion_models.mkdir(exist_ok=True)
    return Settings(
        _env_file=None,
        comfyui_mode=mode,
        comfyui_base_url="http://comfy.internal:8188/",
        comfyui_checkpoints_dir=str(checkpoints),
        comfyui_diffusion_models_dir=str(diffusion_models),
    )


def test_disabled_does_not_probe_or_scan_filesystem(tmp_path: Path) -> None:
    settings = _settings(tmp_path, mode="disabled")
    probe = Probe()
    scanned: list[Path] = []

    result = get_system_status(
        settings,
        probe=probe,
        directory_reader=lambda path: scanned.append(path) or [],
    )

    assert result.application == "healthy"
    assert result.comfyui.state == "not_configured"
    assert result.comfyui.configured is False
    assert result.comfyui.reachable is False
    assert result.comfyui.model_count == 0
    assert probe.calls == []
    assert scanned == []
    assert "reconfigure" in result.comfyui.hint


def test_unreachable_overrides_filesystem_inventory(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    probe = Probe(result=False)
    scanned: list[Path] = []

    result = get_system_status(
        settings,
        probe=probe,
        directory_reader=lambda path: scanned.append(path) or [],
    )

    assert result.comfyui.state == "unreachable"
    assert result.comfyui.configured is True
    assert result.comfyui.reachable is False
    assert probe.calls == [("http://comfy.internal:8188/system_stats", 2.0)]
    assert scanned == []
    assert "啟動" in result.comfyui.hint


@pytest.mark.parametrize(
    "probe",
    [
        Probe(error=TimeoutError("late")),
        Probe(error=ConnectionError("offline")),
        Probe(result={"not": "a boolean probe result"}),
    ],
)
def test_probe_timeout_connection_and_malformed_results_never_escape(
    tmp_path: Path,
    probe: Probe,
) -> None:
    result = get_system_status(_settings(tmp_path), probe=probe)

    assert result.application == "healthy"
    assert result.comfyui.state == "unreachable"
    assert result.comfyui.warnings == []


def test_reachable_without_generation_model_is_no_models(tmp_path: Path) -> None:
    result = get_system_status(_settings(tmp_path), probe=Probe())

    assert result.comfyui.state == "no_models"
    assert result.comfyui.reachable is True
    assert result.comfyui.model_count == 0
    assert result.comfyui.checkpoint_count == 0
    assert result.comfyui.diffusion_model_count == 0
    assert "checkpoint" in result.comfyui.hint
    assert "失敗" not in result.comfyui.hint


def test_counts_checkpoint_and_split_generation_models_with_canonical_deduplication(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    checkpoints = Path(settings.comfyui_checkpoints_dir)
    diffusion_models = Path(settings.comfyui_diffusion_models_dir)
    (checkpoints / "anime.safetensors").write_text("model", encoding="utf-8")
    (checkpoints / "notes.txt").write_text("ignore", encoding="utf-8")
    (diffusion_models / "flux.pth").write_text("model", encoding="utf-8")
    (diffusion_models / "wan.ckpt").write_text("model", encoding="utf-8")
    settings.comfyui_checkpoints_dir = f"{checkpoints},{checkpoints}"

    result = get_system_status(settings, probe=Probe())

    assert result.comfyui.state == "connected"
    assert result.comfyui.checkpoint_count == 1
    assert result.comfyui.diffusion_model_count == 2
    assert result.comfyui.model_count == 3
    assert result.comfyui.warnings == []


def test_same_model_filename_in_distinct_directories_is_counted_separately(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    first = tmp_path / "checkpoint-library-a"
    second = tmp_path / "checkpoint-library-b"
    first.mkdir()
    second.mkdir()
    (first / "shared-name.safetensors").write_text("first", encoding="utf-8")
    (second / "shared-name.safetensors").write_text("second", encoding="utf-8")
    settings.comfyui_checkpoints_dir = f"{first},{second},{first}"

    result = get_system_status(settings, probe=Probe())

    assert result.comfyui.state == "connected"
    assert result.comfyui.checkpoint_count == 2
    assert result.comfyui.model_count == 2


def test_usable_model_with_missing_configured_alternative_is_degraded(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    Path(settings.comfyui_checkpoints_dir, "model.safetensors").write_text(
        "model", encoding="utf-8"
    )
    settings.comfyui_diffusion_models_dir = str(tmp_path / "private-location")

    result = get_system_status(settings, probe=Probe())

    assert result.comfyui.state == "degraded"
    assert result.comfyui.model_count == 1
    assert result.comfyui.warnings == ["diffusion_models 模型目錄不存在。"]
    assert str(tmp_path) not in " ".join(result.comfyui.warnings)
    assert "權限" in result.comfyui.hint


def test_usable_model_with_unreadable_directory_is_degraded(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    checkpoint = Path(settings.comfyui_checkpoints_dir) / "model.ckpt"
    checkpoint.write_text("model", encoding="utf-8")
    diffusion_dir = Path(settings.comfyui_diffusion_models_dir)

    def read_directory(path: Path):
        if path == diffusion_dir:
            raise PermissionError("contains secret path")
        return list(path.iterdir())

    result = get_system_status(
        settings,
        probe=Probe(),
        directory_reader=read_directory,
    )

    assert result.comfyui.state == "degraded"
    assert result.comfyui.model_count == 1
    assert result.comfyui.warnings == ["diffusion_models 模型目錄無法讀取。"]
    assert "secret" not in " ".join(result.comfyui.warnings)


def test_status_dto_warning_lists_are_not_shared(tmp_path: Path) -> None:
    first = get_system_status(_settings(tmp_path), probe=Probe(result=False))
    second = get_system_status(_settings(tmp_path), probe=Probe(result=False))

    first.comfyui.warnings.append("local mutation")

    assert second.comfyui.warnings == []


def test_status_api_serializes_typed_disabled_response(client, monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path, mode="disabled")
    client.app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = client.get("/api/system/status")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "application": "healthy",
        "comfyui": {
            "mode": "disabled",
            "state": "not_configured",
            "configured": False,
            "reachable": False,
            "model_count": 0,
            "checkpoint_count": 0,
            "diffusion_model_count": 0,
            "warnings": [],
            "hint": "執行 setup.ps1 reconfigure 或 ./setup.sh reconfigure 以設定或安裝 ComfyUI。",
        },
    }


def test_health_remains_application_only_when_comfyui_is_unreachable(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
