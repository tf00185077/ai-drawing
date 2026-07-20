from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .constants import STATE_SCHEMA_VERSION


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
class HostInfo:
    system: str
    machine: str
    home: Path


@dataclass(frozen=True)
class ComfyPaths:
    root: Path


@dataclass(frozen=True)
class LocalSettings:
    comfy_mode: ComfyMode
    comfyui_port: int


@dataclass(frozen=True)
class LauncherState:
    schema_version: int
    comfy_mode: ComfyMode
    comfyui_root: Path | None
    device: DeviceMode | None
    comfyui_port: int
    managed_pid: int | None
    managed_identity: str | None

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

        return cls(
            schema_version=raw["schema_version"],
            comfy_mode=ComfyMode(raw["comfy_mode"]),
            comfyui_root=(
                Path(raw["comfyui_root"])
                if raw.get("comfyui_root") is not None
                else None
            ),
            device=DeviceMode(raw["device"]) if raw.get("device") is not None else None,
            comfyui_port=raw["comfyui_port"],
            managed_pid=raw.get("managed_pid"),
            managed_identity=raw.get("managed_identity"),
        )
