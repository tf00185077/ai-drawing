from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Awaitable, Callable

from .models import HostInfo
from .platforms import read_process_identity
from .configuration import atomic_write
from .processes import _spawn_logged_process, terminate_if_identity_matches
from .runner import Runner


_RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


class RelayAddressError(ValueError):
    """Raised when relay networking would expose ComfyUI beyond Docker locally."""


@dataclass(frozen=True)
class RelayState:
    bind_host: str
    bind_port: int
    target_port: int
    managed_pid: int
    managed_identity: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "bind_host": self.bind_host,
                "bind_port": self.bind_port,
                "target_port": self.target_port,
                "managed_pid": self.managed_pid,
                "managed_identity": self.managed_identity,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> RelayState:
        raw = json.loads(value)
        if not isinstance(raw, dict):
            raise ValueError("relay state must be a JSON object")
        return cls(
            bind_host=validate_relay_bind(raw["bind_host"]),
            bind_port=_validate_port(raw["bind_port"]),
            target_port=_validate_port(raw["target_port"]),
            managed_pid=_validate_pid(raw["managed_pid"]),
            managed_identity=_validate_identity(raw["managed_identity"]),
        )


@dataclass(frozen=True)
class RelayStartResult:
    started: bool
    reason: str
    state: RelayState | None


@dataclass(frozen=True)
class RelayStopResult:
    stopped: bool
    reason: str
    state: RelayState | None


def _validate_port(port: int) -> int:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be an integer from 1 to 65535")
    return port


def _validate_pid(pid: int) -> int:
    if type(pid) is not int or pid <= 0:
        raise ValueError("managed_pid must be a positive integer")
    return pid


def _validate_identity(identity: str) -> str:
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("managed_identity must be non-empty")
    return identity


def validate_relay_bind(address: str) -> str:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise RelayAddressError("relay bind must be an IPv4 address") from error
    if not isinstance(parsed, ipaddress.IPv4Address):
        raise RelayAddressError("relay bind must be an IPv4 Docker bridge address")
    if not any(parsed in network for network in _RFC1918_NETWORKS):
        raise RelayAddressError("relay bind must be an RFC1918 Docker bridge address")
    if parsed.is_unspecified or parsed.is_loopback or parsed.is_multicast or parsed.is_link_local:
        raise RelayAddressError("relay bind is not a safe Docker bridge address")
    return str(parsed)


def _validate_target(address: str) -> str:
    if address != "127.0.0.1":
        raise RelayAddressError("relay target must be 127.0.0.1")
    return address


async def _copy_stream(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    while data := await reader.read(64 * 1024):
        writer.write(data)
        await writer.drain()
    if writer.can_write_eof():
        writer.write_eof()


async def forward_connection(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    *,
    target_host: str,
    target_port: int,
) -> None:
    upstream_writer: asyncio.StreamWriter | None = None
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(
            _validate_target(target_host),
            _validate_port(target_port),
        )
        await asyncio.gather(
            _copy_stream(client_reader, upstream_writer),
            _copy_stream(upstream_reader, client_writer),
        )
    finally:
        client_writer.close()
        if upstream_writer is not None:
            upstream_writer.close()
        await asyncio.gather(
            client_writer.wait_closed(),
            *(
                (upstream_writer.wait_closed(),)
                if upstream_writer is not None
                else ()
            ),
            return_exceptions=True,
        )


async def run_relay(
    bind_host: str,
    bind_port: int,
    target_host: str,
    target_port: int,
    *,
    start_server: Callable[..., Awaitable[Any]] = asyncio.start_server,
) -> None:
    bind_host = validate_relay_bind(bind_host)
    bind_port = _validate_port(bind_port)
    target_host = _validate_target(target_host)
    target_port = _validate_port(target_port)
    handler = partial(
        forward_connection,
        target_host=target_host,
        target_port=target_port,
    )
    server = await start_server(handler, bind_host, bind_port)
    async with server:
        await server.serve_forever()


def relay_state_path(project_root: Path) -> Path:
    return Path(project_root) / "data/bootstrap/relay-state.json"


def relay_log_path(project_root: Path) -> Path:
    return Path(project_root) / "data/logs/comfyui-relay.log"


def save_relay_state(project_root: Path, state: RelayState) -> None:
    atomic_write(relay_state_path(project_root), state.to_json() + "\n")


def load_relay_state(project_root: Path) -> RelayState | None:
    path = relay_state_path(project_root)
    if not path.is_file():
        return None
    return RelayState.from_json(path.read_text(encoding="utf-8"))


def clear_relay_state(project_root: Path) -> None:
    relay_state_path(project_root).unlink(missing_ok=True)


def build_relay_command(
    *,
    project_root: Path,
    python: Path,
    bind_host: str,
    bind_port: int,
    target_port: int,
) -> list[str]:
    return [
        str(Path(python)),
        str(Path(project_root) / "scripts/comfyui_relay.py"),
        "--bind-host",
        validate_relay_bind(bind_host),
        "--bind-port",
        str(_validate_port(bind_port)),
        "--target-host",
        "127.0.0.1",
        "--target-port",
        str(_validate_port(target_port)),
    ]


def _socket_probe(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _local_bind_probe(host: str, port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def start_relay(
    *,
    project_root: Path,
    python: Path = Path(sys.executable),
    bind_host: str,
    bind_port: int,
    target_port: int,
    host: HostInfo,
    runner: Runner,
    popen: Callable[..., Any] = subprocess.Popen,
    probe: Callable[[str, int, float], bool] = _socket_probe,
    bind_probe: Callable[[str, int], bool] = _local_bind_probe,
    sleep: Callable[[float], None] = time.sleep,
    readiness_timeout: float = 10.0,
    poll_interval: float = 0.2,
) -> RelayStartResult:
    if host.system != "Linux":
        return RelayStartResult(False, "unsupported_platform", None)
    if readiness_timeout <= 0 or poll_interval <= 0:
        raise ValueError("readiness timeout and poll interval must be positive")
    bind_host = validate_relay_bind(bind_host)
    bind_port = _validate_port(bind_port)
    if not bind_probe(bind_host, bind_port):
        return RelayStartResult(False, "bind_not_local", None)
    command = build_relay_command(
        project_root=project_root,
        python=python,
        bind_host=bind_host,
        bind_port=bind_port,
        target_port=target_port,
    )
    try:
        process = _spawn_logged_process(
            command,
            cwd=Path(project_root).resolve(),
            log_path=relay_log_path(Path(project_root).resolve()),
            host=host,
            popen=popen,
        )
    except OSError:
        return RelayStartResult(False, "spawn_failed", None)
    pid = getattr(process, "pid", None)
    if type(pid) is not int or pid <= 0:
        return RelayStartResult(False, "invalid_pid", None)

    if process.poll() is not None:
        return RelayStartResult(False, "process_exited", None)
    spawned_identity = read_process_identity(host, pid, runner)
    attempts = max(1, math.ceil(readiness_timeout / poll_interval) + 1)
    for attempt in range(attempts):
        if process.poll() is not None:
            return RelayStartResult(False, "process_exited", None)
        if probe(bind_host, bind_port, min(1.0, readiness_timeout)):
            identity = read_process_identity(host, pid, runner)
            if identity is None:
                terminate_if_identity_matches(pid, spawned_identity, runner, host)
                return RelayStartResult(False, "identity_unavailable", None)
            if spawned_identity is not None and identity != spawned_identity:
                return RelayStartResult(False, "process_identity_mismatch", None)
            state = RelayState(
                bind_host=bind_host,
                bind_port=bind_port,
                target_port=target_port,
                managed_pid=pid,
                managed_identity=identity,
            )
            try:
                save_relay_state(project_root, state)
            except OSError:
                terminate_if_identity_matches(pid, identity, runner, host)
                return RelayStartResult(False, "state_write_failed", None)
            return RelayStartResult(True, "ready", state)
        if attempt + 1 < attempts:
            sleep(poll_interval)

    cleanup = terminate_if_identity_matches(pid, spawned_identity, runner, host)
    reason = "readiness_timeout"
    if cleanup != "terminated":
        reason = f"readiness_timeout_cleanup_{cleanup}"
    return RelayStartResult(False, reason, None)


def stop_relay(
    state: RelayState,
    runner: Runner,
    host: HostInfo,
    *,
    project_root: Path | None = None,
) -> RelayStopResult:
    current_identity = read_process_identity(host, state.managed_pid, runner)
    if current_identity is None:
        if project_root is not None:
            clear_relay_state(project_root)
        return RelayStopResult(False, "process_not_found", None)
    if current_identity != state.managed_identity:
        if project_root is not None:
            clear_relay_state(project_root)
        return RelayStopResult(False, "process_identity_mismatch", None)
    termination = terminate_if_identity_matches(
        state.managed_pid,
        state.managed_identity,
        runner,
        host,
    )
    if termination in {"identity_mismatch", "process_not_found"}:
        if project_root is not None:
            clear_relay_state(project_root)
        reason = (
            "process_identity_mismatch"
            if termination == "identity_mismatch"
            else "process_not_found"
        )
        return RelayStopResult(False, reason, None)
    if termination != "terminated":
        return RelayStopResult(False, "termination_failed", state)
    if project_root is not None:
        clear_relay_state(project_root)
    return RelayStopResult(True, "stopped", None)
