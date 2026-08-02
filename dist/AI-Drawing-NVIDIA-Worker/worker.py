"""Open Windows NVIDIA Worker control and direct ComfyUI proxy."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

try:
    from worker.windows.powershell_control import (
        PowerShellCommandManager,
        PowerShellCommandNotFound,
    )
except ModuleNotFoundError:  # Supports direct execution from worker/windows.
    from powershell_control import PowerShellCommandManager, PowerShellCommandNotFound


def _comfyui_url() -> str:
    value = os.environ.get("AI_DRAWING_COMFYUI_URL", "http://127.0.0.1:8188")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(
            "AI_DRAWING_COMFYUI_URL must be a loopback HTTP URL with an explicit port"
        ) from error
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
        raise ValueError(
            "AI_DRAWING_COMFYUI_URL must be a loopback HTTP URL with an explicit port"
        )
    return value


COMFYUI_URL = _comfyui_url()

app = FastAPI(title="AI-Drawing NVIDIA Worker", version="0.3.0")
_powershell_commands = PowerShellCommandManager()


class PowerShellCommandRequest(BaseModel):
    script: str
    working_directory: str | None = None


@app.get("/v1/worker/status")
def status() -> dict[str, Any]:
    return {
        "protocol_version": 2,
        "worker_version": "0.3.0",
        "hostname": os.environ.get("COMPUTERNAME", ""),
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


@app.post("/prompt")
def prompt(body: dict[str, Any]) -> Response:
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
