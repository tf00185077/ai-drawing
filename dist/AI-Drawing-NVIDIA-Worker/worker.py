"""Windows NVIDIA Worker.

ComfyUI stays on loopback. This process owns resource ingestion and proxies only
the API paths required by ai-drawing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")

try:
    from worker.windows.update_contract import (
        RequestLockError,
        UpdateAlreadyRunning,
        UpdateRequest,
        queue_update,
        read_public_update_status,
        write_update_status,
    )
except ModuleNotFoundError:  # Supports direct execution from worker/windows.
    from update_contract import (
        RequestLockError,
        UpdateAlreadyRunning,
        UpdateRequest,
        queue_update,
        read_public_update_status,
        write_update_status,
    )

try:
    from worker.windows.powershell_control import (
        PowerShellCommandManager,
        PowerShellCommandNotFound,
    )
except ModuleNotFoundError:  # Supports direct execution from worker/windows.
    from powershell_control import PowerShellCommandManager, PowerShellCommandNotFound

try:
    from worker.windows.restart_contract import (
        RestartRequest,
        queue_restart,
        read_restart_status,
        write_restart_status,
    )
except ModuleNotFoundError:  # Supports direct execution from worker/windows.
    from restart_contract import (
        RestartRequest,
        queue_restart,
        read_restart_status,
        write_restart_status,
    )

def _runtime_path(
    name: str,
    default: Path,
    *,
    kind: str,
    contained_by: Path | None = None,
) -> Path:
    raw = os.environ.get(name, str(default))
    path = Path(raw)
    if raw != raw.strip() or not path.is_absolute():
        raise ValueError(f"{name} must be an absolute canonical path")
    _reject_reparse_components(name, path)
    try:
        canonical = path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"{name} does not exist") from error
    if kind == "directory" and not canonical.is_dir():
        raise ValueError(f"{name} must name a directory")
    if kind == "file" and not canonical.is_file():
        raise ValueError(f"{name} must name a file")
    if contained_by is not None:
        try:
            canonical.relative_to(contained_by)
        except ValueError as error:
            raise ValueError(f"{name} escapes its managed root") from error
    return canonical


def _reject_reparse_components(name: str, path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
        except OSError as error:
            raise ValueError(f"{name} does not exist") from error
        if current.is_symlink() or attributes & 0x400:
            raise ValueError(f"{name} must not contain a reparse point")


def _reject_existing_reparse_components(name: str, path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            return
        except OSError as error:
            raise ValueError(f"{name} could not be validated") from error
        if current.is_symlink() or attributes & 0x400:
            raise ValueError(f"{name} must not contain a reparse point")


def _existing_runtime_directory(name: str, path: Path, contained_by: Path) -> Path:
    _reject_reparse_components(name, path)
    try:
        canonical_root = contained_by.resolve(strict=True)
        canonical = path.resolve(strict=True)
        canonical.relative_to(canonical_root)
    except (OSError, ValueError) as error:
        raise ValueError(f"{name} escapes its managed root") from error
    if not canonical.is_dir():
        raise ValueError(f"{name} must name a directory")
    return canonical


def _relative_parts(name: str, path: Path, root: Path) -> tuple[str, ...]:
    try:
        return tuple(part.casefold() for part in path.relative_to(root).parts)
    except ValueError as error:
        raise ValueError(f"{name} escapes its managed root") from error


ROOT = _runtime_path(
    "AI_DRAWING_WORKER_ROOT",
    Path(r"C:\AI-Drawing-Worker"),
    kind="directory",
)
RELEASE_ROOT = _runtime_path(
    "AI_DRAWING_WORKER_RELEASE_ROOT",
    ROOT,
    kind="directory",
    contained_by=ROOT,
)
if RELEASE_ROOT != ROOT:
    release_parts = _relative_parts("AI_DRAWING_WORKER_RELEASE_ROOT", RELEASE_ROOT, ROOT)
    if len(release_parts) < 2 or release_parts[0] != "releases":
        raise ValueError("AI_DRAWING_WORKER_RELEASE_ROOT must be inside WORKER_ROOT/releases")
CONFIG_PATH = _runtime_path(
    "AI_DRAWING_WORKER_CONFIG_PATH",
    ROOT / "config" / "worker.json",
    kind="file",
    contained_by=ROOT,
)
if CONFIG_PATH.name.casefold() != "worker.json":
    raise ValueError("AI_DRAWING_WORKER_CONFIG_PATH must name worker.json")
UPDATE_STATE_ROOT = _runtime_path(
    "AI_DRAWING_WORKER_UPDATE_STATE_ROOT",
    ROOT,
    kind="directory",
    contained_by=ROOT,
)
if UPDATE_STATE_ROOT != ROOT:
    state_parts = _relative_parts(
        "AI_DRAWING_WORKER_UPDATE_STATE_ROOT", UPDATE_STATE_ROOT, ROOT
    )
    in_staging = bool(state_parts) and state_parts[0] == "staging"
    in_owned_config = state_parts[:2] == ("config", "update-owned")
    if not in_staging and not in_owned_config:
        raise ValueError(
            "AI_DRAWING_WORKER_UPDATE_STATE_ROOT must be inside staging or config/update-owned"
        )
COMFYUI_ROOT = _runtime_path(
    "AI_DRAWING_COMFYUI_ROOT",
    ROOT / "runtime" / "ComfyUI",
    kind="directory",
    contained_by=RELEASE_ROOT,
)
expected_comfy_root = (
    ROOT / "runtime" / "ComfyUI" if RELEASE_ROOT == ROOT else RELEASE_ROOT / "ComfyUI"
).resolve(strict=False)
if COMFYUI_ROOT != expected_comfy_root:
    raise ValueError("AI_DRAWING_COMFYUI_ROOT must name the release ComfyUI directory")


def _partial_root() -> Path:
    name = "AI_DRAWING_WORKER_PARTIAL_ROOT"
    expected = (
        ROOT / "cache" / ".partial"
        if RELEASE_ROOT == ROOT
        else RELEASE_ROOT / "cache" / ".partial"
    )
    raw = os.environ.get(name, str(expected))
    path = Path(raw)
    if raw != raw.strip() or not path.is_absolute() or path != expected:
        raise ValueError(f"{name} must name the runtime partial cache")
    if RELEASE_ROOT == ROOT:
        _reject_existing_reparse_components(name, path)
        if path.exists() and not path.is_dir():
            raise ValueError(f"{name} must name a directory")
        return path

    shared_root = _existing_runtime_directory(name, ROOT / "shared", ROOT)
    shared_partial = _existing_runtime_directory(
        name, ROOT / "shared" / "partial", shared_root
    )
    _reject_reparse_components(name, path.parent)
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        is_link = path.is_symlink() or bool(attributes & 0x400)
        target = path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"{name} does not name the managed partial junction") from error
    if not is_link or not target.is_dir() or target != shared_partial:
        raise ValueError(f"{name} does not target WORKER_ROOT/shared/partial")
    return path


PARTIAL_ROOT = _partial_root()


def _verification_root() -> Path:
    name = "AI_DRAWING_WORKER_VERIFICATION_ROOT"
    if RELEASE_ROOT == ROOT:
        expected = PARTIAL_ROOT.parent / "verified"
        parent = expected.parent
        try:
            parent.relative_to(ROOT)
            _reject_existing_reparse_components(name, parent)
            parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as error:
            raise ValueError(f"{name} parent could not be prepared safely") from error
        safe_parent = _existing_runtime_directory(name, parent, ROOT)
    else:
        shared_root = _existing_runtime_directory(name, ROOT / "shared", ROOT)
        safe_parent = _existing_runtime_directory(
            name, ROOT / "shared" / "cache", shared_root
        )
        expected = safe_parent / "verified"

    raw = os.environ.get(name, str(expected))
    path = Path(raw)
    if raw != raw.strip() or not path.is_absolute() or path != expected:
        raise ValueError(f"{name} must name the runtime verification cache")
    try:
        _reject_existing_reparse_components(name, path)
        path.mkdir(exist_ok=True)
    except (OSError, ValueError) as error:
        raise ValueError(f"{name} could not be prepared safely") from error
    return _existing_runtime_directory(name, path, safe_parent)


VERIFICATION_ROOT = _verification_root()
SOURCE_COMMIT_PATH = RELEASE_ROOT / "source-commit.txt"
UPDATE_REQUEST_PATH = UPDATE_STATE_ROOT / "state" / "update-request.json"
UPDATE_STATUS_PATH = UPDATE_STATE_ROOT / "state" / "update-status.json"
RESTART_REQUEST_PATH = UPDATE_STATE_ROOT / "state" / "restart-request.json"
RESTART_STATUS_PATH = UPDATE_STATE_ROOT / "state" / "restart-status.json"


def _comfyui_url() -> str:
    value = os.environ.get("AI_DRAWING_COMFYUI_URL", "http://127.0.0.1:8188")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("AI_DRAWING_COMFYUI_URL must be a loopback HTTP URL with an explicit port") from error
    if (
        value != value.strip()
        or parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or port is None
        or not 1 <= port <= 65535
    ):
        raise ValueError("AI_DRAWING_COMFYUI_URL must be a loopback HTTP URL with an explicit port")
    return value


COMFYUI_URL = _comfyui_url()
MODEL_ROOTS = {
    "checkpoints": COMFYUI_ROOT / "models" / "checkpoints",
    "diffusion_models": COMFYUI_ROOT / "models" / "diffusion_models",
    "text_encoders": COMFYUI_ROOT / "models" / "text_encoders",
    "vae": COMFYUI_ROOT / "models" / "vae",
    "loras": COMFYUI_ROOT / "models" / "loras",
    "controlnet": COMFYUI_ROOT / "models" / "controlnet",
    "upscale_models": COMFYUI_ROOT / "models" / "upscale_models",
    "clip_vision": COMFYUI_ROOT / "models" / "clip_vision",
    "audio": COMFYUI_ROOT / "models" / "audio_encoders",
}


def _config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("Worker is not configured") from error


def _update_state() -> str:
    try:
        return read_public_update_status(UPDATE_STATUS_PATH)["state"]
    except RequestLockError as error:
        raise HTTPException(
            503, detail={"code": "update_lock_unavailable"}
        ) from error


def _require_update_idle() -> None:
    if _update_state() not in {"idle", "ready", "rolled_back", "failed_before_activation"}:
        raise HTTPException(409, detail={"code": "worker_updating"})


def _safe_destination(kind: str, name: str) -> Path:
    root = MODEL_ROOTS.get(kind)
    if root is None:
        raise HTTPException(422, "unsupported resource kind")
    normalized = name.replace("\\", "/")
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(422, "unsafe resource name")
    destination = (root / relative).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as error:
        raise HTTPException(422, "resource escaped model root") from error
    return destination


def _normalized_sha256(value: str) -> str:
    if not _SHA256_PATTERN.fullmatch(value):
        raise HTTPException(422, "invalid resource SHA-256")
    return value.lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar_path(destination: Path) -> Path:
    """Central per-file record of the last verified digest for a model file.

    Kept under cache/ (outside MODEL_ROOTS) so it is neither served to ComfyUI
    nor counted by the LRU cache accounting. Keyed by the destination path so a
    same-named file that is later replaced gets a fresh record.
    """
    key = hashlib.sha256(str(destination).encode("utf-8")).hexdigest()
    return VERIFICATION_ROOT / f"{key}.json"


def _record_verified(destination: Path, sha: str) -> None:
    stat = destination.stat()
    sidecar = _sidecar_path(destination)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": sha}
        ),
        encoding="utf-8",
    )


def _remove_verification(destination: Path) -> None:
    _sidecar_path(destination).unlink(missing_ok=True)


def _verified_sha(destination: Path) -> str:
    """Trusted digest for an existing file without re-reading it every submit.

    Only a sidecar recorded after completed upload verification can trust an
    unchanged file. Missing, malformed, or stale records require retransfer.
    """
    try:
        stat = destination.stat()
        record = json.loads(_sidecar_path(destination).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(record, dict):
        return ""
    sha = record.get("sha256")
    if (
        record.get("size") == stat.st_size
        and record.get("mtime_ns") == stat.st_mtime_ns
        and isinstance(sha, str)
        and _SHA256_PATTERN.fullmatch(sha)
    ):
        return sha.lower()
    return ""


def _touch_atime(destination: Path) -> None:
    """Refresh atime for LRU eviction while preserving mtime (sidecar key)."""
    stat = destination.stat()
    os.utime(destination, ns=(time.time_ns(), stat.st_mtime_ns))


def _model_files() -> list[Path]:
    files: list[Path] = []
    for root in MODEL_ROOTS.values():
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return files


def _enforce_cache(
    *,
    incoming_bytes: int,
    protected: set[Path],
) -> None:
    config = _config()
    limit = int(config.get("cache_gb", 100)) * 1024**3
    reserve = int(config.get("minimum_free_gb", 20)) * 1024**3
    files = _model_files()
    used = sum(path.stat().st_size for path in files)
    free = shutil.disk_usage(ROOT).free
    required = max(0, used + incoming_bytes - limit, reserve + incoming_bytes - free)
    if required <= 0:
        return
    reclaimed = 0
    for path in sorted(files, key=lambda item: item.stat().st_atime):
        if path.resolve() in protected:
            continue
        size = path.stat().st_size
        path.unlink()
        _remove_verification(path)
        reclaimed += size
        if reclaimed >= required:
            break
    if reclaimed < required:
        raise HTTPException(507, "worker cache cannot preserve its free-space reserve")


app = FastAPI(title="AI-Drawing NVIDIA Worker", version="0.3.0")
_powershell_commands = PowerShellCommandManager()


class PowerShellCommandRequest(BaseModel):
    script: str
    working_directory: str | None = None


@app.get("/v1/worker/status")
def status() -> dict[str, Any]:
    config = _config()
    disk = shutil.disk_usage(ROOT)
    try:
        stats = httpx.get(f"{COMFYUI_URL}/system_stats", timeout=5).json()
        comfyui = "ready"
    except Exception:
        stats = {}
        comfyui = "unavailable"
    return {
        "protocol_version": 2,
        "worker_version": "0.3.0",
        "source_commit": SOURCE_COMMIT_PATH.read_text(encoding="utf-8").strip()
        if SOURCE_COMMIT_PATH.is_file()
        else "",
        "update_capability": 1,
        "update_state": _update_state(),
        "comfyui": comfyui,
        "hostname": os.environ.get("COMPUTERNAME", ""),
        "cache_gb": config.get("cache_gb", 100),
        "disk_free": disk.free,
        "system_stats": stats,
    }


@app.post("/v1/powershell/commands", status_code=202)
def submit_powershell_command(request: PowerShellCommandRequest) -> dict[str, Any]:
    return _powershell_commands.submit(
        script=request.script,
        working_directory=request.working_directory,
    )


@app.get("/v1/powershell/commands/{command_id}")
def powershell_command_status(command_id: str) -> dict[str, Any]:
    try:
        return _powershell_commands.get(command_id)
    except PowerShellCommandNotFound as error:
        raise HTTPException(
            404, detail={"code": "powershell_command_not_found"}
        ) from error


@app.post("/v1/powershell/commands/{command_id}/cancel")
def cancel_powershell_command(command_id: str) -> dict[str, Any]:
    try:
        return _powershell_commands.cancel(command_id)
    except PowerShellCommandNotFound as error:
        raise HTTPException(
            404, detail={"code": "powershell_command_not_found"}
        ) from error


@app.post("/v1/admin/update", status_code=202)
def request_update(body: UpdateRequest) -> dict[str, str]:
    try:
        request_id = queue_update(
            UPDATE_REQUEST_PATH, UPDATE_STATUS_PATH, body.target_commit
        )
    except UpdateAlreadyRunning as error:
        raise HTTPException(409, detail={"code": "update_already_running"}) from error
    except RequestLockError as error:
        raise HTTPException(
            503, detail={"code": "update_lock_unavailable"}
        ) from error
    except OSError as error:
        raise HTTPException(
            503, detail={"code": "update_request_unavailable"}
        ) from error
    try:
        subprocess.run(
            ["schtasks.exe", "/Run", "/TN", "AI-Drawing Worker Updater"],
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        try:
            write_update_status(UPDATE_STATUS_PATH, "failed_before_activation")
        except RequestLockError as lock_error:
            raise HTTPException(
                503, detail={"code": "update_lock_unavailable"}
            ) from lock_error
        except OSError as status_error:
            raise HTTPException(
                503, detail={"code": "update_request_unavailable"}
            ) from status_error
        raise HTTPException(503, detail={"code": "update_activation_failed"}) from error
    return {"request_id": request_id, "status": "queued"}


@app.get("/v1/admin/update/status")
def update_status() -> dict[str, Any]:
    try:
        return read_public_update_status(UPDATE_STATUS_PATH)
    except RequestLockError as error:
        raise HTTPException(
            503, detail={"code": "update_lock_unavailable"}
        ) from error
    except OSError as error:
        raise HTTPException(
            503, detail={"code": "update_status_unavailable"}
        ) from error


@app.post("/v1/admin/restart", status_code=202)
def request_restart(body: RestartRequest) -> dict[str, Any]:
    try:
        request_id, created = queue_restart(RESTART_REQUEST_PATH, RESTART_STATUS_PATH)
    except RequestLockError as error:
        raise HTTPException(503, detail={"code": "restart_lock_unavailable"}) from error
    except OSError as error:
        raise HTTPException(503, detail={"code": "restart_request_unavailable"}) from error
    if created:
        try:
            subprocess.run(
                ["schtasks.exe", "/Run", "/TN", "AI-Drawing NVIDIA Worker Restart"],
                check=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as error:
            try:
                write_restart_status(
                    RESTART_STATUS_PATH,
                    request_id,
                    "failed",
                    error_code="RESTART_ACTIVATION_FAILED",
                )
            except RequestLockError as lock_error:
                raise HTTPException(
                    503, detail={"code": "restart_lock_unavailable"}
                ) from lock_error
            except OSError as status_error:
                raise HTTPException(
                    503, detail={"code": "restart_request_unavailable"}
                ) from status_error
            raise HTTPException(503, detail={"code": "restart_activation_failed"}) from error
    return {"request_id": request_id, "state": "queued"}


@app.get("/v1/admin/restart/status")
def restart_status(request_id: str = Query(..., min_length=1, max_length=64)) -> dict[str, Any]:
    try:
        status = read_restart_status(RESTART_STATUS_PATH)
    except RequestLockError as error:
        raise HTTPException(503, detail={"code": "restart_lock_unavailable"}) from error
    except OSError as error:
        raise HTTPException(503, detail={"code": "restart_status_unavailable"}) from error
    if status.get("request_id") != request_id:
        raise HTTPException(404, detail={"code": "restart_request_not_found"})
    return status


@app.post("/v1/resources/plan")
def resource_plan(body: dict[str, Any]) -> dict[str, Any]:
    _require_update_idle()
    missing: list[dict[str, Any]] = []
    protected: set[Path] = set()
    incoming_bytes = 0
    for item in body.get("resources", []):
        kind = str(item.get("kind", ""))
        name = str(item.get("name", ""))
        sha = _normalized_sha256(str(item.get("sha256", "")))
        size = int(item.get("size", -1))
        if size < 0:
            raise HTTPException(422, "invalid resource manifest")
        destination = _safe_destination(kind, name)
        protected.add(destination.resolve())
        if destination.is_file() and destination.stat().st_size == size:
            if _verified_sha(destination) == sha:
                _touch_atime(destination)
                continue
        elif not destination.is_file():
            _remove_verification(destination)
        partial = PARTIAL_ROOT / f"{sha}.part"
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset > size:
            partial.unlink(missing_ok=True)
            offset = 0
        incoming_bytes += size - offset
        missing.append({**item, "sha256": sha, "offset": offset})
    _enforce_cache(incoming_bytes=incoming_bytes, protected=protected)
    return {"missing": missing}


@app.put("/v1/resources/content")
async def resource_content(
    body: bytes = Body(b"", media_type="application/octet-stream"),
    kind: str = Query(...),
    name: str = Query(...),
    sha256: str = Query(..., min_length=64, max_length=64),
    size: int = Query(..., ge=0),
    offset: int = Query(..., ge=0),
    finalize: bool = Query(False),
) -> dict[str, Any]:
    _require_update_idle()
    sha = _normalized_sha256(sha256)
    destination = _safe_destination(kind, name)
    PARTIAL_ROOT.mkdir(parents=True, exist_ok=True)
    partial = PARTIAL_ROOT / f"{sha}.part"
    actual_offset = partial.stat().st_size if partial.exists() else 0
    if actual_offset != offset:
        raise HTTPException(409, detail={"accepted_offset": actual_offset})
    if finalize:
        if body:
            raise HTTPException(422, "finalize request must not contain resource bytes")
        if offset != size:
            raise HTTPException(409, detail={"accepted_offset": actual_offset})
        if size == 0 and not partial.exists():
            partial.touch()
    else:
        mode = "ab" if offset else "wb"
        with partial.open(mode) as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    if partial.stat().st_size < size:
        return {"ready": False, "offset": partial.stat().st_size}
    if partial.stat().st_size != size or _sha256(partial) != sha:
        partial.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        _remove_verification(destination)
        raise HTTPException(422, "resource digest mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(partial, destination)
    # The bytes were just digest-verified above; record the sidecar so future
    # plans trust this file by size+mtime without re-hashing it.
    _record_verified(destination, sha)
    return {"ready": True, "offset": size, "size": size, "sha256": sha}


def _proxy(method: str, path: str, **kwargs: Any) -> Response:
    try:
        response = httpx.request(
            method,
            f"{COMFYUI_URL}{path}",
            timeout=60,
            **kwargs,
        )
    except httpx.HTTPError as error:
        raise HTTPException(502, f"ComfyUI unavailable: {type(error).__name__}") from error
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


@app.post("/v1/workflows/preflight")
def workflow_capabilities(body: dict[str, Any]) -> dict[str, Any]:
    requested = body.get("node_types")
    if not isinstance(requested, list) or any(
        not isinstance(item, str) or not item for item in requested
    ):
        raise HTTPException(422, "node_types must be a list of non-empty strings")
    try:
        response = httpx.get(f"{COMFYUI_URL}/object_info", timeout=30)
        response.raise_for_status()
        object_info = response.json()
    except Exception as error:
        raise HTTPException(502, "ComfyUI capability inspection unavailable") from error
    if not isinstance(object_info, dict):
        raise HTTPException(502, "ComfyUI object_info response is malformed")
    missing = sorted(set(requested) - set(object_info))
    return {"ready": not missing, "missing_node_types": missing}


@app.post("/prompt")
def prompt(body: dict[str, Any]) -> Response:
    _require_update_idle()
    return _proxy("POST", "/prompt", json=body)


@app.get("/queue")
def queue() -> Response:
    return _proxy("GET", "/queue")


@app.get("/history/{prompt_id}")
def history(prompt_id: str) -> Response:
    return _proxy("GET", f"/history/{prompt_id}")


@app.get("/view")
def view(filename: str, subfolder: str = "", type: str = "output") -> Response:
    return _proxy(
        "GET",
        "/view",
        params={"filename": filename, "subfolder": subfolder, "type": type},
    )


@app.post("/upload/image")
async def upload_image(
    image: UploadFile = File(...),
    overwrite: str = "true",
    type: str = "input",
    subfolder: str = "",
) -> Response:
    content = await image.read()
    return _proxy(
        "POST",
        "/upload/image",
        files={"image": (image.filename, content, image.content_type)},
        data={"overwrite": overwrite, "type": type, "subfolder": subfolder},
    )
