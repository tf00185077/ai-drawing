from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_BACKEND_PORT,
    DEFAULT_COMFYUI_PORT,
    DEFAULT_FRONTEND_PORT,
    STATE_SCHEMA_VERSION,
)


class LauncherCommand(str, Enum):
    SETUP = "setup"
    START = "start"
    STOP = "stop"
    STATUS = "status"
    RECONFIGURE = "reconfigure"
    LOGS = "logs"
    UPDATE_COMFYUI = "update-comfyui"


class ComfyMode(str, Enum):
    DISABLED = "disabled"
    EXTERNAL = "external"
    MANAGED = "managed"


class DeviceMode(str, Enum):
    NVIDIA = "nvidia"
    MPS = "mps"
    CPU = "cpu"


@dataclass(frozen=True)
class ProcessIdentity:
    executable: str
    started_at: str
    command_line: str

    def __post_init__(self) -> None:
        for name in ("executable", "started_at", "command_line"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"process identity {name} must be non-empty")

    @classmethod
    def from_value(cls, value: Any) -> ProcessIdentity | None:
        if not isinstance(value, dict):
            return None
        try:
            return cls(
                executable=value["executable"],
                started_at=value["started_at"],
                command_line=value["command_line"],
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class HostInfo:
    system: str
    machine: str
    home: Path


@dataclass(frozen=True)
class ComfyPaths:
    root: Path

    @classmethod
    def from_root(cls, root: Path) -> ComfyPaths:
        return cls(root=Path(root))


@dataclass(frozen=True)
class LocalSettings:
    comfy_mode: ComfyMode
    comfyui_port: int = DEFAULT_COMFYUI_PORT
    comfy_paths: ComfyPaths | None = None
    backend_port: int = DEFAULT_BACKEND_PORT
    frontend_port: int = DEFAULT_FRONTEND_PORT

    @classmethod
    def disabled(
        cls,
        *,
        backend_port: int = DEFAULT_BACKEND_PORT,
        frontend_port: int = DEFAULT_FRONTEND_PORT,
    ) -> LocalSettings:
        return cls(
            comfy_mode=ComfyMode.DISABLED,
            backend_port=backend_port,
            frontend_port=frontend_port,
        )

    @classmethod
    def connected(
        cls,
        paths: ComfyPaths,
        comfyui_port: int = DEFAULT_COMFYUI_PORT,
        *,
        comfy_mode: ComfyMode = ComfyMode.EXTERNAL,
        backend_port: int = DEFAULT_BACKEND_PORT,
        frontend_port: int = DEFAULT_FRONTEND_PORT,
    ) -> LocalSettings:
        return cls(
            comfy_mode=comfy_mode,
            comfyui_port=comfyui_port,
            comfy_paths=paths,
            backend_port=backend_port,
            frontend_port=frontend_port,
        )


@dataclass(frozen=True)
class LauncherState:
    schema_version: int
    comfy_mode: ComfyMode
    comfyui_root: Path | None
    device: DeviceMode | None
    comfyui_port: int
    managed_pid: int | None
    managed_identity: ProcessIdentity | None
    launcher_installed: bool = False
    installed_root: Path | None = None
    installed_commit: str | None = None

    def to_json(self) -> str:
        def convert(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, Path):
                return str(value)
            return value

        return json.dumps(
            {key: convert(value) for key, value in asdict(self).items()},
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> LauncherState:
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("invalid launcher state JSON") from error

        if not isinstance(raw, dict):
            raise ValueError("launcher state must be a JSON object")
        if raw.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ValueError("unsupported launcher state schema version")
        managed_pid = raw.get("managed_pid")
        if managed_pid is not None and (
            type(managed_pid) is not int or managed_pid <= 0
        ):
            raise ValueError("managed_pid must be a positive integer")
        comfyui_port = raw.get("comfyui_port")
        if type(comfyui_port) is not int or not 1 <= comfyui_port <= 65535:
            raise ValueError("comfyui_port must be an integer from 1 to 65535")

        comfyui_root_value = raw.get("comfyui_root")
        installed_root_value = raw.get("installed_root")
        roots_agree = (
            isinstance(comfyui_root_value, str)
            and bool(comfyui_root_value)
            and isinstance(installed_root_value, str)
            and bool(installed_root_value)
            and os.path.normcase(str(Path(comfyui_root_value).resolve()))
            == os.path.normcase(str(Path(installed_root_value).resolve()))
        )
        has_install_provenance = (
            raw.get("launcher_installed") is True
            and roots_agree
            and isinstance(raw.get("installed_commit"), str)
            and bool(raw.get("installed_commit"))
        )

        return cls(
            schema_version=raw["schema_version"],
            comfy_mode=ComfyMode(raw["comfy_mode"]),
            comfyui_root=(
                Path(raw["comfyui_root"])
                if raw.get("comfyui_root") is not None
                else None
            ),
            device=DeviceMode(raw["device"]) if raw.get("device") is not None else None,
            comfyui_port=comfyui_port,
            managed_pid=managed_pid,
            managed_identity=ProcessIdentity.from_value(raw.get("managed_identity")),
            launcher_installed=has_install_provenance,
            installed_root=(
                Path(raw["installed_root"])
                if has_install_provenance
                else None
            ),
            installed_commit=(
                raw["installed_commit"]
                if has_install_provenance
                else None
            ),
        )
