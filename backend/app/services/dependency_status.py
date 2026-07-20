from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Protocol
from urllib.request import urlopen

from app.config import Settings
from app.core.resources import MODEL_EXTENSIONS
from app.schemas.system import ComfyUIState, ComfyUIStatus, SystemStatus


PROBE_TIMEOUT_SECONDS = 2.0


class ComfyUIProbe(Protocol):
    def __call__(self, url: str, *, timeout: float) -> object: ...


DirectoryReader = Callable[[Path], Iterable[Path]]


@dataclass
class _Inventory:
    checkpoint_names: set[str] = field(default_factory=set)
    diffusion_model_names: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)


def probe_comfyui(url: str, *, timeout: float) -> bool:
    """Return whether a ComfyUI system-stats endpoint returns a JSON object."""
    with urlopen(url, timeout=timeout) as response:
        payload = json.load(response)
    return isinstance(payload, dict)


def _read_directory(path: Path) -> Iterable[Path]:
    return list(path.iterdir())


def _split_paths(configured_paths: str) -> list[Path]:
    return [
        Path(part.strip()).expanduser()
        for part in configured_paths.split(",")
        if part.strip()
    ]


def _scan_generation_files(
    configured_paths: str,
    *,
    label: str,
    directory_reader: DirectoryReader,
) -> tuple[set[str], list[str]]:
    names: set[str] = set()
    missing = False
    unreadable = False

    for directory in _split_paths(configured_paths):
        try:
            if not directory.exists() or not directory.is_dir():
                missing = True
                continue
            entries = directory_reader(directory)
            for entry in entries:
                if entry.is_file() and entry.suffix.lower() in MODEL_EXTENSIONS:
                    canonical_path = entry.resolve(strict=False)
                    names.add(os.path.normcase(str(canonical_path)))
        except OSError:
            unreadable = True

    warnings: list[str] = []
    if missing:
        warnings.append(f"{label} 模型目錄不存在。")
    if unreadable:
        warnings.append(f"{label} 模型目錄無法讀取。")
    return names, warnings


def _model_inventory(settings: Settings, directory_reader: DirectoryReader) -> _Inventory:
    checkpoints, checkpoint_warnings = _scan_generation_files(
        settings.comfyui_checkpoints_dir,
        label="checkpoints",
        directory_reader=directory_reader,
    )
    diffusion_models, diffusion_warnings = _scan_generation_files(
        settings.comfyui_diffusion_models_dir,
        label="diffusion_models",
        directory_reader=directory_reader,
    )
    return _Inventory(
        checkpoint_names=checkpoints,
        diffusion_model_names=diffusion_models,
        warnings=[*checkpoint_warnings, *diffusion_warnings],
    )


def _status(
    settings: Settings,
    *,
    state: ComfyUIState,
    configured: bool,
    reachable: bool,
    hint: str,
    inventory: _Inventory | None = None,
    warnings: list[str] | None = None,
) -> SystemStatus:
    current = inventory or _Inventory()
    return SystemStatus(
        comfyui=ComfyUIStatus(
            mode=settings.comfyui_mode,
            state=state,
            configured=configured,
            reachable=reachable,
            model_count=len(current.checkpoint_names) + len(current.diffusion_model_names),
            checkpoint_count=len(current.checkpoint_names),
            diffusion_model_count=len(current.diffusion_model_names),
            warnings=current.warnings if warnings is None else warnings,
            hint=hint,
        )
    )


def get_system_status(
    settings: Settings,
    *,
    probe: ComfyUIProbe = probe_comfyui,
    directory_reader: DirectoryReader = _read_directory,
) -> SystemStatus:
    """Report application health separately from the optional ComfyUI dependency."""
    if settings.comfyui_mode == "disabled":
        return _status(
            settings,
            state="not_configured",
            configured=False,
            reachable=False,
            hint=(
                "執行 setup.ps1 reconfigure 或 ./setup.sh reconfigure "
                "以設定或安裝 ComfyUI。"
            ),
        )

    endpoint = f"{settings.comfyui_base_url.rstrip('/')}/system_stats"
    try:
        reachable = probe(endpoint, timeout=PROBE_TIMEOUT_SECONDS) is True
    except Exception:
        reachable = False

    if not reachable:
        return _status(
            settings,
            state="unreachable",
            configured=True,
            reachable=False,
            warnings=[],
            hint=(
                "請啟動已設定的 ComfyUI，或執行 setup.ps1 reconfigure／"
                "./setup.sh reconfigure 更新設定。"
            ),
        )

    inventory = _model_inventory(settings, directory_reader)
    model_count = len(inventory.checkpoint_names) + len(inventory.diffusion_model_names)
    if model_count == 0:
        return _status(
            settings,
            state="no_models",
            configured=True,
            reachable=True,
            inventory=inventory,
            warnings=[],
            hint="ComfyUI 已連線；請自行將 checkpoint 或 diffusion model 放入對應模型目錄。",
        )

    if inventory.warnings:
        return _status(
            settings,
            state="degraded",
            configured=True,
            reachable=True,
            inventory=inventory,
            hint="ComfyUI 可使用，但部分模型目錄不可用；請檢查掛載與讀取權限。",
        )

    return _status(
        settings,
        state="connected",
        configured=True,
        reachable=True,
        inventory=inventory,
        hint="ComfyUI 與生圖模型已就緒。",
    )
