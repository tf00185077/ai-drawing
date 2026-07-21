from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import LauncherState, LocalSettings


class ConfigurationError(RuntimeError):
    """Raised when generated launcher configuration cannot be validated."""


_MODEL_MOUNTS = (
    ("models/checkpoints", "/comfyui/models/checkpoints"),
    ("models/loras", "/comfyui/models/loras"),
    ("models/diffusion_models", "/comfyui/models/diffusion_models"),
    ("models/text_encoders", "/comfyui/models/text_encoders"),
    ("models/vae", "/comfyui/models/vae"),
    ("models/embeddings", "/comfyui/models/embeddings"),
    ("models/controlnet", "/comfyui/models/controlnet"),
    ("models/upscale_models", "/comfyui/models/upscale_models"),
    ("input", "/comfyui/input"),
)

_SENSITIVE_PARTS = ("authorization", "token", "secret", "password")


@dataclass(frozen=True)
class _DestinationSnapshot:
    destination: Path
    existed: bool
    backup_path: Path | None


def parse_env(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key:
            parsed[key] = value
    return parsed


def render_env(
    settings: LocalSettings,
    preserved: Mapping[str, str] | None = None,
) -> str:
    connected = settings.comfy_mode.value != "disabled"
    base_url = (
        f"http://host.docker.internal:{settings.comfyui_port}"
        if connected
        else ""
    )
    ws_url = (
        f"ws://host.docker.internal:{settings.comfyui_port}/ws"
        if connected
        else ""
    )
    values = {
        "COMFYUI_MODE": settings.comfy_mode.value,
        "COMFYUI_BASE_URL": base_url,
        "COMFYUI_WS_URL": ws_url,
        "COMFYUI_CHECKPOINTS_DIR": "/comfyui/models/checkpoints",
        "COMFYUI_LORAS_DIR": "/comfyui/models/loras",
        "COMFYUI_DIFFUSION_MODELS_DIR": "/comfyui/models/diffusion_models",
        "COMFYUI_TEXT_ENCODERS_DIR": "/comfyui/models/text_encoders",
        "COMFYUI_VAE_DIR": "/comfyui/models/vae",
        "COMFYUI_EMBEDDINGS_DIR": "/comfyui/models/embeddings",
        "COMFYUI_CONTROLNET_DIR": "/comfyui/models/controlnet",
        "COMFYUI_UPSCALE_MODELS_DIR": "/comfyui/models/upscale_models",
        "COMFYUI_INPUT_DIR": "/comfyui/input",
        "DATABASE_URL": "sqlite:////data/database/auto_draw.db",
        "OUTPUT_DIR": "/data/outputs",
        "GALLERY_DIR": "/data/gallery",
        "PROMPT_LIBRARY_DIR": "/workspace/prompt_library",
        "LORA_TRAIN_DIR": "/data/lora_train",
        "WATCH_DIRS": "/data/lora_train",
        "MCP_BACKEND_API_URL": f"http://127.0.0.1:{settings.backend_port}",
        "BACKEND_PORT": str(settings.backend_port),
        "FRONTEND_PORT": str(settings.frontend_port),
    }
    authorization = (preserved or {}).get("CIVITAI_AUTHORIZATION")
    if authorization:
        values["CIVITAI_AUTHORIZATION"] = authorization
    return "".join(f"{key}={value}\n" for key, value in values.items())


def render_compose_override(settings: LocalSettings) -> str:
    if settings.comfy_paths is None:
        return "services: {}\n"

    lines = ["services:", "  backend:", "    volumes:"]
    for relative_path, target in _MODEL_MOUNTS:
        source = settings.comfy_paths.root / relative_path
        lines.extend(
            (
                "      - type: bind",
                f"        source: {json.dumps(str(source), ensure_ascii=True)}",
                f"        target: {target}",
            )
        )
    return "\n".join(lines) + "\n"


def _temporary_path(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def atomic_write(path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        temporary_path = _temporary_path(path, content)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _snapshot_destination(path: Path) -> _DestinationSnapshot:
    if not path.exists():
        return _DestinationSnapshot(path, existed=False, backup_path=None)

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    backup_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as backup, path.open("rb") as source:
            shutil.copyfileobj(source, backup)
    except BaseException:
        backup_path.unlink(missing_ok=True)
        raise
    return _DestinationSnapshot(path, existed=True, backup_path=backup_path)


def _restore_snapshots(snapshots: list[_DestinationSnapshot]) -> None:
    restoration_errors: list[Exception] = []
    for snapshot in snapshots:
        try:
            if snapshot.existed:
                assert snapshot.backup_path is not None
                snapshot.backup_path.replace(snapshot.destination)
            else:
                snapshot.destination.unlink(missing_ok=True)
        except Exception as error:
            restoration_errors.append(error)
    if restoration_errors:
        raise ConfigurationError("configuration replacement failed and rollback failed") from restoration_errors[0]


def load_state(path: Path) -> LauncherState | None:
    if not path.exists():
        return None
    try:
        return LauncherState.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(f"invalid launcher state: {error}") from error


def write_configuration(
    root: Path,
    settings: LocalSettings,
    state: LauncherState,
    validate: Callable[[Path, Path], bool],
) -> None:
    root = Path(root)
    env_path = root / ".env"
    override_path = root / ".ai-drawing" / "compose.local.yaml"
    state_path = root / "data" / "bootstrap" / "state.json"
    destinations = (env_path, override_path, state_path)
    temporary_paths: list[Path] = []
    snapshots: list[_DestinationSnapshot] = []
    replacement_started = False
    try:
        previous_env = (
            parse_env(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
        )
        for destination, content in zip(
            destinations,
            (
                render_env(settings, previous_env),
                render_compose_override(settings),
                state.to_json() + "\n",
            ),
            strict=True,
        ):
            temporary_paths.append(_temporary_path(destination, content))
        if not validate(temporary_paths[0], temporary_paths[1]):
            raise ConfigurationError("generated Compose configuration failed validation")
        for destination in destinations:
            snapshots.append(_snapshot_destination(destination))
        replacement_started = True
        for temporary_path, destination in zip(temporary_paths, destinations, strict=True):
            temporary_path.replace(destination)
    except ConfigurationError:
        raise
    except Exception as error:
        if replacement_started:
            _restore_snapshots(snapshots)
        raise ConfigurationError("unable to write generated configuration") from error
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
        for snapshot in snapshots:
            if snapshot.backup_path is not None:
                snapshot.backup_path.unlink(missing_ok=True)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: (
                "[REDACTED]"
                if any(part in str(key).lower() for part in _SENSITIVE_PARTS)
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value
