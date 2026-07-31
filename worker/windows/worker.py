"""Authenticated Windows NVIDIA Worker.

ComfyUI stays on loopback. This process owns resource ingestion and proxies only
the API paths required by ai-drawing.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
try:
    from worker.windows.update_contract import (
        UpdateAlreadyRunning,
        UpdateRequest,
        queue_update,
        read_public_update_status,
        write_update_status,
    )
except ModuleNotFoundError:  # Supports direct execution from worker/windows.
    from update_contract import (
        UpdateAlreadyRunning,
        UpdateRequest,
        queue_update,
        read_public_update_status,
        write_update_status,
    )

ROOT = Path(os.environ.get("AI_DRAWING_WORKER_ROOT", r"C:\AI-Drawing-Worker")).resolve()
CONFIG_PATH = ROOT / "config" / "worker.json"
PARTIAL_ROOT = ROOT / "cache" / ".partial"
SOURCE_COMMIT_PATH = ROOT / "source-commit.txt"
UPDATE_REQUEST_PATH = ROOT / "state" / "update-request.json"
UPDATE_STATUS_PATH = ROOT / "state" / "update-status.json"
COMFYUI_ROOT = ROOT / "runtime" / "ComfyUI"
COMFYUI_URL = "http://127.0.0.1:8188"
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


def _auth(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = str(_config().get("token", ""))
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, "invalid worker token")


def _update_state() -> str:
    return read_public_update_status(UPDATE_STATUS_PATH)["state"]


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
    verified_root = PARTIAL_ROOT.parent / "verified"
    key = hashlib.sha256(str(destination).encode("utf-8")).hexdigest()
    return verified_root / f"{key}.json"


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


def _verified_sha(destination: Path) -> str:
    """Trusted digest for an existing file without re-reading it every submit.

    A sidecar recorded at ingestion (or self-healed here on first sight) lets an
    unchanged file — matching size and mtime_ns — be trusted by a cheap string
    compare. Any real edit advances mtime and forces a one-time rehash.
    """
    stat = destination.stat()
    try:
        record = json.loads(_sidecar_path(destination).read_text(encoding="utf-8"))
        if (
            record.get("size") == stat.st_size
            and record.get("mtime_ns") == stat.st_mtime_ns
        ):
            return str(record.get("sha256", ""))
    except (OSError, ValueError):
        pass
    sha = _sha256(destination)
    _record_verified(destination, sha)
    return sha


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
        reclaimed += size
        if reclaimed >= required:
            break
    if reclaimed < required:
        raise HTTPException(507, "worker cache cannot preserve its free-space reserve")


app = FastAPI(title="AI-Drawing NVIDIA Worker", version="0.3.0")


@app.get("/v1/worker/status", dependencies=[Depends(_auth)])
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


@app.post("/v1/admin/update", dependencies=[Depends(_auth)], status_code=202)
def request_update(body: UpdateRequest) -> dict[str, str]:
    try:
        request_id = queue_update(
            UPDATE_REQUEST_PATH, UPDATE_STATUS_PATH, body.target_commit
        )
    except UpdateAlreadyRunning as error:
        raise HTTPException(409, detail={"code": "update_already_running"}) from error
    try:
        subprocess.run(
            ["schtasks.exe", "/Run", "/TN", "AI-Drawing Worker Updater"],
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        write_update_status(UPDATE_STATUS_PATH, "failed_before_activation")
        raise HTTPException(503, detail={"code": "update_activation_failed"}) from error
    return {"request_id": request_id, "status": "queued"}


@app.get("/v1/admin/update/status", dependencies=[Depends(_auth)])
def update_status() -> dict[str, Any]:
    return read_public_update_status(UPDATE_STATUS_PATH)


@app.post("/v1/resources/plan", dependencies=[Depends(_auth)])
def resource_plan(body: dict[str, Any]) -> dict[str, Any]:
    _require_update_idle()
    missing: list[dict[str, Any]] = []
    protected: set[Path] = set()
    incoming_bytes = 0
    for item in body.get("resources", []):
        kind = str(item.get("kind", ""))
        name = str(item.get("name", ""))
        sha = str(item.get("sha256", ""))
        size = int(item.get("size", -1))
        if len(sha) != 64 or size < 0:
            raise HTTPException(422, "invalid resource manifest")
        destination = _safe_destination(kind, name)
        protected.add(destination.resolve())
        if destination.is_file() and destination.stat().st_size == size:
            if _verified_sha(destination) == sha:
                _touch_atime(destination)
                continue
        partial = PARTIAL_ROOT / f"{sha}.part"
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset > size:
            partial.unlink(missing_ok=True)
            offset = 0
        incoming_bytes += size - offset
        missing.append({**item, "offset": offset})
    _enforce_cache(incoming_bytes=incoming_bytes, protected=protected)
    return {"missing": missing}


@app.put("/v1/resources/content", dependencies=[Depends(_auth)])
async def resource_content(
    body: bytes = Body(..., media_type="application/octet-stream"),
    kind: str = Query(...),
    name: str = Query(...),
    sha256: str = Query(..., min_length=64, max_length=64),
    size: int = Query(..., ge=0),
    offset: int = Query(..., ge=0),
) -> dict[str, Any]:
    _require_update_idle()
    destination = _safe_destination(kind, name)
    PARTIAL_ROOT.mkdir(parents=True, exist_ok=True)
    partial = PARTIAL_ROOT / f"{sha256}.part"
    actual_offset = partial.stat().st_size if partial.exists() else 0
    if actual_offset != offset:
        raise HTTPException(409, detail={"accepted_offset": actual_offset})
    mode = "ab" if offset else "wb"
    with partial.open(mode) as output:
        output.write(body)
        output.flush()
        os.fsync(output.fileno())
    if partial.stat().st_size < size:
        return {"ready": False, "offset": partial.stat().st_size}
    if partial.stat().st_size != size or _sha256(partial) != sha256:
        partial.unlink(missing_ok=True)
        raise HTTPException(422, "resource digest mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(partial, destination)
    # The bytes were just digest-verified above; record the sidecar so future
    # plans trust this file by size+mtime without re-hashing it.
    _record_verified(destination, sha256)
    return {"ready": True, "offset": size, "size": size, "sha256": sha256}


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


@app.post("/v1/workflows/preflight", dependencies=[Depends(_auth)])
def workflow_preflight(body: dict[str, Any]) -> dict[str, Any]:
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


@app.post("/prompt", dependencies=[Depends(_auth)])
def prompt(body: dict[str, Any]) -> Response:
    _require_update_idle()
    return _proxy("POST", "/prompt", json=body)


@app.get("/queue", dependencies=[Depends(_auth)])
def queue() -> Response:
    return _proxy("GET", "/queue")


@app.get("/history/{prompt_id}", dependencies=[Depends(_auth)])
def history(prompt_id: str) -> Response:
    return _proxy("GET", f"/history/{prompt_id}")


@app.get("/view", dependencies=[Depends(_auth)])
def view(filename: str, subfolder: str = "", type: str = "output") -> Response:
    return _proxy(
        "GET",
        "/view",
        params={"filename": filename, "subfolder": subfolder, "type": type},
    )


@app.post("/upload/image", dependencies=[Depends(_auth)])
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
