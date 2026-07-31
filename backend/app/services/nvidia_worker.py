"""Paired NVIDIA Worker client and resource synchronization.

The Worker intentionally presents the small ComfyUI API surface used by the
queue. Before prompt submission it receives a content-addressed resource plan
and any missing files. A selected Worker is fail-closed: this module never
returns the local client as a fallback.
"""
from __future__ import annotations

import hashlib
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.config import get_settings
from app.core.comfyui import ComfyUIClient, ComfyUIError, get_comfy_client
from app.services.nvidia_worker_update import ensure_worker_compatible


class WorkerConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResourceRef:
    kind: str
    name: str
    path: Path
    size: int
    sha256: str

    def manifest(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "size": self.size,
            "sha256": self.sha256,
        }


_NODE_RESOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "CheckpointLoaderSimple": (("ckpt_name", "checkpoints"),),
    "UNETLoader": (("unet_name", "diffusion_models"),),
    "UnetLoaderGGUF": (("unet_name", "diffusion_models"),),
    "GGUFLoaderKJ": (("model_name", "diffusion_models"), ("extra_model_name", "diffusion_models")),
    "CLIPLoader": (("clip_name", "text_encoders"),),
    "DualCLIPLoader": (("clip_name1", "text_encoders"), ("clip_name2", "text_encoders")),
    "CLIPVisionLoader": (("clip_name", "clip_vision"),),
    "VAELoader": (("vae_name", "vae"),),
    "LoraLoader": (("lora_name", "loras"),),
    "LoraLoaderModelOnly": (("lora_name", "loras"),),
    "ControlNetLoader": (("control_net_name", "controlnet"),),
    "UpscaleModelLoader": (("model_name", "upscale_models"),),
}


def _roots() -> dict[str, tuple[Path, ...]]:
    settings = get_settings()

    def parts(value: str) -> tuple[Path, ...]:
        return tuple(Path(item).resolve() for item in value.split(",") if item.strip())

    return {
        "checkpoints": parts(settings.comfyui_checkpoints_dir),
        "diffusion_models": parts(settings.comfyui_diffusion_models_dir),
        "text_encoders": parts(settings.comfyui_text_encoders_dir),
        "vae": parts(settings.comfyui_vae_dir),
        "loras": parts(settings.comfyui_loras_dir),
        "controlnet": parts(settings.comfyui_controlnet_dir),
        "upscale_models": parts(settings.comfyui_upscale_models_dir),
        "clip_vision": parts(getattr(settings, "comfyui_clip_vision_dir", "")),
        "audio": parts(getattr(settings, "comfyui_audio_models_dir", "")),
    }


def _safe_name(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise WorkerConfigurationError(f"unsafe workflow resource name: {value}")
    return normalized


def _resolve(kind: str, name: str) -> Path:
    safe = _safe_name(name)
    for root in _roots().get(kind, ()):
        candidate = (root / safe).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"authoritative {kind} resource not found: {safe}")


# Content-addressed model files are large (multi-GB) and effectively immutable.
# Hashing them on every prompt submission is pure disk I/O waste, so cache the
# digest keyed by (path, size, mtime_ns); any real edit changes size or mtime and
# invalidates the entry. Cache lives in the long-running queue worker process.
_digest_cache: dict[str, tuple[int, int, str]] = {}
_digest_lock = threading.Lock()


def _read_and_hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _digest(path: Path) -> str:
    stat = path.stat()
    key = str(path)
    signature = (stat.st_size, stat.st_mtime_ns)
    with _digest_lock:
        cached = _digest_cache.get(key)
        if cached is not None and cached[:2] == signature:
            return cached[2]
    digest = _read_and_hash(path)
    with _digest_lock:
        _digest_cache[key] = (*signature, digest)
    return digest


def workflow_resources(workflow: dict[str, Any]) -> list[ResourceRef]:
    found: dict[tuple[str, str], ResourceRef] = {}
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        bindings = _NODE_RESOURCES.get(str(node.get("class_type", "")))
        if bindings is None:
            continue
        for field, kind in bindings:
            value = node.get("inputs", {}).get(field)
            if not isinstance(value, str) or not value or value.casefold() == "none":
                continue
            safe = _safe_name(value)
            key = (kind, safe.casefold())
            if key in found:
                continue
            path = _resolve(kind, safe)
            found[key] = ResourceRef(
                kind=kind,
                name=safe,
                path=path,
                size=path.stat().st_size,
                sha256=_digest(path),
            )
    return list(found.values())


class NvidiaWorkerClient(ComfyUIClient):
    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        super().__init__(
            base_url=base_url,
            timeout_submit=timeout,
            timeout_fetch=timeout,
            timeout_queue=timeout,
        )
        self._headers = {"Authorization": f"Bearer {token}"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        if timeout is None:
            request_timeout = self._timeout_submit
        else:
            if (
                type(timeout) not in (int, float)
                or not math.isfinite(timeout)
                or timeout <= 0
            ):
                raise ValueError("timeout override must be positive and finite")
            request_timeout = min(self._timeout_submit, float(timeout))
        headers = dict(self._headers)
        headers.update(kwargs.pop("headers", {}))
        with httpx.Client(timeout=request_timeout) as client:
            response = client.request(
                method, self._url(path), headers=headers, **kwargs
            )
        response.raise_for_status()
        return response

    def health(self, *, timeout: float | None = None) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/worker/status",
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def request_update(
        self,
        target_commit: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/admin/update",
            json={"target_commit": target_commit},
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def update_status(self, *, timeout: float | None = None) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/admin/update/status",
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def preflight(
        self,
        node_types: list[str],
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/workflows/preflight",
            json={"node_types": node_types},
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def _synchronize(self, prompt: dict[str, Any]) -> None:
        resources = workflow_resources(prompt)
        plan = self._request(
            "POST",
            "/v1/resources/plan",
            json={"resources": [resource.manifest() for resource in resources]},
        ).json()
        missing = {
            (item["kind"], item["name"], item["sha256"]): int(item.get("offset", 0))
            for item in plan.get("missing", [])
        }
        for resource in resources:
            key = (resource.kind, resource.name, resource.sha256)
            if key not in missing:
                continue
            offset = missing[key]
            with resource.path.open("rb") as source:
                source.seek(offset)
                response = None
                while offset < resource.size:
                    chunk = source.read(min(8 * 1024 * 1024, resource.size - offset))
                    if not chunk:
                        raise WorkerConfigurationError(
                            f"resource ended before declared size: {resource.name}"
                        )
                    response = self._request(
                        "PUT",
                        "/v1/resources/content",
                        params={
                            "kind": resource.kind,
                            "name": resource.name,
                            "sha256": resource.sha256,
                            "size": resource.size,
                            "offset": offset,
                        },
                        content=chunk,
                        headers={"Content-Type": "application/octet-stream"},
                    )
                    offset = int(response.json().get("offset", offset + len(chunk)))
                    if response.json().get("ready"):
                        break
            if response is None:
                continue
            if not response.json().get("ready"):
                raise WorkerConfigurationError(
                    f"worker did not finalize resource: {resource.name}"
                )

    def _preflight(self, prompt: dict[str, Any]) -> None:
        node_types = sorted({
            str(node.get("class_type"))
            for node in prompt.values()
            if isinstance(node, dict) and node.get("class_type")
        })
        result = self.preflight(node_types)
        missing = result.get("missing_node_types") or []
        if missing:
            raise WorkerConfigurationError(
                "worker_missing_nodes: " + ", ".join(str(item) for item in missing)
            )

    def submit_prompt(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> str:
        settings = get_settings()
        if settings.nvidia_worker_auto_update:
            # This is a gate, not a recursive resubmission loop. A mismatched
            # Worker is updated once, then the original prompt is submitted
            # exactly once through the method below. Worker selection remains
            # fail-closed and never switches to local ComfyUI.
            ensure_worker_compatible(
                self,
                timeout=settings.nvidia_worker_update_timeout,
            )
        return self._submit_prompt_once(
            prompt,
            client_id=client_id,
            extra_data=extra_data,
        )

    def _submit_prompt_once(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> str:
        self._preflight(prompt)
        self._synchronize(prompt)
        payload: dict[str, Any] = {"prompt": prompt}
        if client_id:
            payload["client_id"] = client_id
        if extra_data:
            payload["extra_data"] = extra_data
        # The Worker proxies ComfyUI's native /prompt response verbatim, so a
        # validation failure arrives as a non-2xx body carrying {error,
        # node_errors}. Parse it here instead of letting _request's
        # raise_for_status collapse it into an opaque HTTPStatusError, so the
        # local and Worker paths raise the identical ComfyUIError with the same
        # node_errors the queue and UI already surface.
        with httpx.Client(timeout=self._timeout_submit) as client:
            response = client.post(
                self._url("/prompt"), headers=self._headers, json=payload
            )
        if not response.is_success:
            try:
                body = response.json()
            except Exception:
                response.raise_for_status()
                raise  # pragma: no cover - raise_for_status already raised
            raise ComfyUIError(
                str(body.get("error", response.text or response.reason_phrase)),
                node_errors=body.get("node_errors", {}),
            )
        data = response.json()
        if "error" in data:
            raise ComfyUIError(str(data["error"]), node_errors=data.get("node_errors", {}))
        prompt_id = data.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIError("Worker response is missing prompt_id")
        return prompt_id

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        return self._request("GET", f"/history/{prompt_id}").json()

    def get_queue(self) -> dict[str, Any]:
        return self._request("GET", "/queue").json()

    def fetch_image(
        self, filename: str, *, subfolder: str = "", ftype: str = "output"
    ) -> bytes:
        return self._request(
            "GET",
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": ftype},
        ).content

    def upload_image(
        self,
        file_path: Path,
        *,
        overwrite: bool = True,
        subfolder: str = "",
        ftype: str = "input",
    ) -> dict[str, str]:
        with file_path.open("rb") as source:
            response = self._request(
                "POST",
                "/upload/image",
                files={"image": (file_path.name, source, "application/octet-stream")},
                data={
                    "overwrite": "true" if overwrite else "false",
                    "type": ftype,
                    "subfolder": subfolder,
                },
            )
        return response.json()


def get_generation_client(target: str) -> ComfyUIClient:
    if target == "local":
        return get_comfy_client()
    if target != "worker":
        raise WorkerConfigurationError(f"unsupported execution target: {target}")
    settings = get_settings()
    if not settings.nvidia_worker_url or not settings.nvidia_worker_token:
        raise WorkerConfigurationError("NVIDIA Worker is not paired")
    return NvidiaWorkerClient(
        settings.nvidia_worker_url.rstrip("/"),
        settings.nvidia_worker_token,
        settings.nvidia_worker_timeout,
    )
