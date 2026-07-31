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

ROOT = Path(os.environ.get("AI_DRAWING_WORKER_ROOT", r"C:\AI-Drawing-Worker")).resolve()
CONFIG_PATH = ROOT / "config" / "worker.json"
PARTIAL_ROOT = ROOT / "cache" / ".partial"
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


app = FastAPI(title="AI-Drawing NVIDIA Worker", version="0.1.0")


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
        "protocol_version": 1,
        "worker_version": "0.1.0",
        "comfyui": comfyui,
        "hostname": os.environ.get("COMPUTERNAME", ""),
        "cache_gb": config.get("cache_gb", 100),
        "disk_free": disk.free,
        "system_stats": stats,
    }


@app.post("/v1/resources/plan", dependencies=[Depends(_auth)])
def resource_plan(body: dict[str, Any]) -> dict[str, Any]:
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
            if _sha256(destination) == sha:
                os.utime(destination, None)
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
