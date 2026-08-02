"""NVIDIA Worker client and resource synchronization.

The Worker intentionally presents the small ComfyUI API surface used by the
queue. Before prompt submission it receives a content-addressed resource plan
and any missing files. A selected Worker is fail-closed: this module never
returns the local client as a fallback.
"""
from __future__ import annotations

import hashlib
import ipaddress
import math
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.core.comfyui import ComfyUIClient, ComfyUIError, get_comfy_client
from app.services.nvidia_worker_update import ensure_worker_compatible


class WorkerConfigurationError(RuntimeError):
    pass


def _positive_finite_timeout(value: Any, label: str) -> float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{label} must be positive and finite")
    return float(value)


_runtime_worker_urls: dict[tuple[str, str, int], str] = {}
_runtime_worker_urls_lock = threading.Lock()


def _runtime_key(
    configured_url: str, hostname: str, protocol_version: int
) -> tuple[str, str, int]:
    return (configured_url.rstrip("/"), hostname.casefold(), protocol_version)


def clear_runtime_worker_urls() -> None:
    with _runtime_worker_urls_lock:
        _runtime_worker_urls.clear()


def remember_runtime_worker_url(
    configured_url: str,
    hostname: str,
    protocol_version: int,
    resolved_url: str,
) -> None:
    with _runtime_worker_urls_lock:
        _runtime_worker_urls[
            _runtime_key(configured_url, hostname, protocol_version)
        ] = resolved_url.rstrip("/")


def _remembered_runtime_worker_url(
    configured_url: str,
    hostname: str,
    protocol_version: int,
) -> str | None:
    with _runtime_worker_urls_lock:
        return _runtime_worker_urls.get(_runtime_key(configured_url, hostname, protocol_version))


def _discovery_target(
    failed_url: str, discovery_cidr: str
) -> tuple[str, int, ipaddress.IPv4Network]:
    parsed = urlsplit(failed_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise WorkerConfigurationError("NVIDIA Worker discovery requires a plain HTTP(S) URL")
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError as exc:
        raise WorkerConfigurationError("NVIDIA Worker discovery requires an IPv4 configured URL") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise WorkerConfigurationError("NVIDIA Worker discovery requires an IPv4 configured URL")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port != 8791:
        raise WorkerConfigurationError("NVIDIA Worker discovery is restricted to port 8791")
    try:
        network = ipaddress.ip_network(discovery_cidr or f"{address}/24", strict=False)
    except ValueError as exc:
        raise WorkerConfigurationError("NVIDIA Worker discovery CIDR is invalid") from exc
    if not isinstance(network, ipaddress.IPv4Network) or network.prefixlen != 24 or address not in network:
        raise WorkerConfigurationError(
            "NVIDIA Worker discovery is restricted to the configured IPv4 /24"
        )
    return parsed.scheme, port, network


def _tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _open_worker_candidates(
    *,
    failed_url: str,
    discovery_cidr: str,
    timeout: float,
) -> list[str]:
    scheme, port, network = _discovery_target(failed_url, discovery_cidr)
    failed_host = urlsplit(failed_url.rstrip("/")).hostname
    hosts = [str(host) for host in network.hosts() if str(host) != failed_host]
    open_hosts: list[str] = []
    with ThreadPoolExecutor(max_workers=min(64, len(hosts))) as pool:
        futures = {pool.submit(_tcp_open, host, port, timeout): host for host in hosts}
        for future in as_completed(futures):
            if future.result():
                open_hosts.append(futures[future])
    return [f"{scheme}://{host}:{port}" for host in sorted(open_hosts, key=ipaddress.ip_address)]


def _probe_worker_status(url: str, *, timeout: float) -> dict[str, Any]:
    request_timeout = httpx.Timeout(timeout)
    with httpx.Client(timeout=request_timeout) as client:
        response = client.get(f"{url.rstrip('/')}/v1/worker/status")
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise WorkerConfigurationError("NVIDIA Worker status response must be an object")
    return body


def discover_worker_url(
    *,
    failed_url: str,
    expected_hostname: str,
    expected_protocol_version: int,
    discovery_cidr: str,
    discovery_timeout: float,
) -> str:
    if not expected_hostname:
        raise WorkerConfigurationError("NVIDIA Worker discovery requires NVIDIA_WORKER_HOSTNAME")
    matches: list[str] = []
    for candidate in _open_worker_candidates(
        failed_url=failed_url,
        discovery_cidr=discovery_cidr,
        timeout=discovery_timeout,
    ):
        try:
            status = _probe_worker_status(candidate, timeout=discovery_timeout)
        except (httpx.HTTPError, ValueError, WorkerConfigurationError):
            continue
        if (
            status.get("hostname") == expected_hostname
            and status.get("protocol_version") == expected_protocol_version
        ):
            matches.append(candidate)
    if len(matches) != 1:
        detail = "not found" if not matches else "ambiguous"
        raise WorkerConfigurationError(f"NVIDIA Worker discovery {detail}")
    return matches[0]


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
# digest only while path identity and change metadata remain stable. Cache lives
# in the long-running queue worker process.
_DigestSignature = tuple[int, int, int, int]
_digest_cache: dict[str, tuple[_DigestSignature, str]] = {}
_digest_lock = threading.Lock()


def _read_and_hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _digest_signature(stat: Any) -> _DigestSignature:
    return (
        int(stat.st_size),
        int(stat.st_mtime_ns),
        int(getattr(stat, "st_ino", 0)),
        int(getattr(stat, "st_ctime_ns", round(stat.st_ctime * 1_000_000_000))),
    )


def _digest_changed_error(path: Path) -> WorkerConfigurationError:
    return WorkerConfigurationError(f"resource changed while hashing: {path.name}")


def _digest(path: Path) -> str:
    key = str(path)
    before = path.stat()
    signature = _digest_signature(before)
    with _digest_lock:
        cached = _digest_cache.get(key)
    if cached is not None and cached[0] == signature:
        try:
            after_cache_lookup = path.stat()
        except OSError as error:
            raise _digest_changed_error(path) from error
        if _digest_signature(after_cache_lookup) == signature:
            return cached[1]
        before = after_cache_lookup
        signature = _digest_signature(before)
    try:
        digest = _read_and_hash(path)
        after_hash = path.stat()
    except OSError as error:
        with _digest_lock:
            _digest_cache.pop(key, None)
        raise _digest_changed_error(path) from error
    if _digest_signature(after_hash) != signature:
        with _digest_lock:
            _digest_cache.pop(key, None)
        raise _digest_changed_error(path)
    with _digest_lock:
        _digest_cache[key] = (signature, digest)
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
    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        *,
        expected_hostname: str = "",
        expected_protocol_version: int = 2,
        discovery_enabled: bool = False,
        discovery_cidr: str = "",
        discovery_timeout: float = 0.25,
        configured_url: str | None = None,
    ):
        configured_timeout = _positive_finite_timeout(
            timeout, "configured timeout"
        )
        super().__init__(
            base_url=base_url,
            timeout_submit=configured_timeout,
            timeout_fetch=configured_timeout,
            timeout_queue=configured_timeout,
        )
        self._expected_hostname = expected_hostname
        self._expected_protocol_version = expected_protocol_version
        self._discovery_enabled = discovery_enabled
        self._discovery_cidr = discovery_cidr
        self._discovery_timeout = discovery_timeout
        self._configured_url = (configured_url or base_url).rstrip("/")

    def _request_once(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        configured_timeout = _positive_finite_timeout(
            self._timeout_submit, "configured timeout"
        )
        if timeout is None:
            request_timeout = configured_timeout
        else:
            override = _positive_finite_timeout(timeout, "timeout override")
            request_timeout = min(configured_timeout, override)
        request_timeout = _positive_finite_timeout(
            request_timeout, "effective timeout"
        )
        with httpx.Client(timeout=request_timeout) as client:
            return client.request(method, self._url(path), **kwargs)

    def _request_raw(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            return self._request_once(method, path, timeout=timeout, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if not self._discovery_enabled:
                raise
            resolved_url = discover_worker_url(
                failed_url=self.base_url,
                expected_hostname=self._expected_hostname,
                expected_protocol_version=self._expected_protocol_version,
                discovery_cidr=self._discovery_cidr,
                discovery_timeout=self._discovery_timeout,
            )
            self.base_url = resolved_url
            remember_runtime_worker_url(
                self._configured_url,
                self._expected_hostname,
                self._expected_protocol_version,
                resolved_url,
            )
            return self._request_once(method, path, timeout=timeout, **kwargs)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._request_raw(method, path, **kwargs)
        response.raise_for_status()
        return response

    def health(self, *, timeout: float | None = None) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/worker/status",
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def submit_powershell(
        self,
        script: str,
        *,
        working_directory: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/powershell/commands",
            json={"script": script, "working_directory": working_directory},
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def powershell_status(
        self, command_id: str, *, timeout: float | None = None
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/powershell/commands/{command_id}",
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def cancel_powershell(
        self, command_id: str, *, timeout: float | None = None
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/powershell/commands/{command_id}/cancel",
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

    def request_restart(self, *, timeout: float | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/admin/restart",
            json={},
            **({} if timeout is None else {"timeout": timeout}),
        ).json()

    def restart_status(
        self, request_id: str, *, timeout: float | None = None
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/admin/restart/status",
            params={"request_id": request_id},
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
            response = None
            if offset == resource.size:
                response = self._request(
                    "PUT",
                    "/v1/resources/content",
                    params={
                        "kind": resource.kind,
                        "name": resource.name,
                        "sha256": resource.sha256,
                        "size": resource.size,
                        "offset": offset,
                        "finalize": True,
                    },
                    content=b"",
                    headers={"Content-Type": "application/octet-stream"},
                )
            else:
                with resource.path.open("rb") as source:
                    source.seek(offset)
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
        response = self._request_raw("POST", "/prompt", json=payload)
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


def get_worker_client() -> NvidiaWorkerClient:
    """Build a Worker client using any hostname/protocol runtime URL cache."""
    settings = get_settings()
    if not settings.nvidia_worker_url:
        raise WorkerConfigurationError("NVIDIA Worker is not paired")
    configured_url = settings.nvidia_worker_url.rstrip("/")
    expected_hostname = getattr(settings, "nvidia_worker_hostname", "")
    expected_protocol_version = int(
        getattr(settings, "nvidia_worker_protocol_version", 2)
    )
    runtime_url = _remembered_runtime_worker_url(
        configured_url,
        expected_hostname,
        expected_protocol_version,
    )
    return NvidiaWorkerClient(
        runtime_url or configured_url,
        settings.nvidia_worker_timeout,
        expected_hostname=expected_hostname,
        expected_protocol_version=expected_protocol_version,
        discovery_enabled=bool(
            getattr(settings, "nvidia_worker_discovery_enabled", False)
        ),
        discovery_cidr=getattr(settings, "nvidia_worker_discovery_cidr", ""),
        discovery_timeout=float(
            getattr(settings, "nvidia_worker_discovery_timeout", 0.25)
        ),
        configured_url=configured_url,
    )


def get_generation_client(target: str) -> ComfyUIClient:
    if target == "local":
        return get_comfy_client()
    if target != "worker":
        raise WorkerConfigurationError(f"unsupported execution target: {target}")
    return get_worker_client()
