from __future__ import annotations

import asyncio
from contextlib import contextmanager
import ipaddress
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any, Awaitable, BinaryIO, Callable, Iterator

from .models import HostInfo, ProcessIdentity
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


class RelayStateLockTimeout(RuntimeError):
    """Raised without mutation when another launcher holds the state lock too long."""


class RelayStateLockError(RuntimeError):
    """Raised without mutation when the OS state lock cannot be used safely."""


_LOCK_REGISTRY_GUARD = threading.Lock()
_LOCK_REGISTRY: dict[str, threading.RLock] = {}
_LOCK_LOCAL = threading.local()


@dataclass(frozen=True)
class RelayState:
    bind_host: str
    bind_port: int
    target_port: int
    managed_pid: int
    managed_identity: ProcessIdentity

    def to_json(self) -> str:
        return json.dumps(
            {
                "bind_host": self.bind_host,
                "bind_port": self.bind_port,
                "target_port": self.target_port,
                "managed_pid": self.managed_pid,
                "managed_identity": asdict(self.managed_identity),
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
            managed_identity=_parse_identity(raw["managed_identity"]),
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


def _parse_identity(value: object) -> ProcessIdentity:
    identity = ProcessIdentity.from_value(value)
    if identity is None:
        raise ValueError("managed_identity must be a complete process identity")
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
    pumps: set[asyncio.Task[None]] = set()
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(
            _validate_target(target_host),
            _validate_port(target_port),
        )
        pumps = {
            asyncio.create_task(_copy_stream(client_reader, upstream_writer)),
            asyncio.create_task(_copy_stream(upstream_reader, client_writer)),
        }
        done, _pending = await asyncio.wait(
            pumps,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
    finally:
        for task in pumps:
            if not task.done():
                task.cancel()
        if pumps:
            await asyncio.gather(*pumps, return_exceptions=True)
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


def relay_invalid_state_path(project_root: Path) -> Path:
    return Path(project_root) / "data/bootstrap/relay-state.invalid.json"


def relay_lock_path(project_root: Path) -> Path:
    return Path(project_root) / "data/bootstrap/relay-state.lock"


def _thread_lock_for(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve()))
    with _LOCK_REGISTRY_GUARD:
        return _LOCK_REGISTRY.setdefault(key, threading.RLock())


def _try_os_lock(handle: BinaryIO) -> bool:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in {13, 35, 36} or error.winerror in {33, 36}:
                return False
            raise RelayStateLockError(f"cannot acquire relay state lock: {error}") from error
        return True

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    except OSError as error:
        raise RelayStateLockError(f"cannot acquire relay state lock: {error}") from error
    return True


def _release_os_lock(handle: BinaryIO) -> None:
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as error:
        raise RelayStateLockError(f"cannot release relay state lock: {error}") from error


@contextmanager
def relay_state_lock(
    project_root: Path,
    *,
    timeout: float = 5.0,
    poll_interval: float = 0.05,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[None]:
    if timeout <= 0:
        raise ValueError("relay state lock timeout must be positive")
    if poll_interval <= 0:
        raise ValueError("relay state lock poll interval must be positive")

    path = relay_lock_path(project_root).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = os.path.normcase(str(path))
    deadline = monotonic() + timeout
    thread_lock = _thread_lock_for(path)
    remaining = deadline - monotonic()
    if remaining <= 0 or not thread_lock.acquire(timeout=remaining):
        raise RelayStateLockTimeout(f"timed out waiting for relay state lock: {path}")

    held = getattr(_LOCK_LOCAL, "held", None)
    if held is None:
        held = {}
        _LOCK_LOCAL.held = held
    record = held.get(key)
    if record is not None:
        record[1] += 1
        try:
            yield
        finally:
            record[1] -= 1
            thread_lock.release()
        return

    handle: BinaryIO | None = None
    locked = False
    try:
        try:
            handle = path.open("a+b")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
        except OSError as error:
            raise RelayStateLockError(f"cannot open relay state lock: {error}") from error

        while not _try_os_lock(handle):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise RelayStateLockTimeout(
                    f"timed out waiting for relay state lock: {path}"
                )
            sleep(min(poll_interval, remaining))
        locked = True
        held[key] = [handle, 1]
        yield
    finally:
        try:
            held.pop(key, None)
            if handle is not None:
                try:
                    if locked:
                        _release_os_lock(handle)
                finally:
                    handle.close()
        finally:
            thread_lock.release()


def save_relay_state(
    project_root: Path,
    state: RelayState,
    *,
    lock_timeout: float = 5.0,
) -> None:
    with relay_state_lock(project_root, timeout=lock_timeout):
        atomic_write(relay_state_path(project_root), state.to_json() + "\n")


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_relay_state(
    project_root: Path,
    *,
    lock_timeout: float = 5.0,
    replacement_timeout: float = 0.1,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> RelayState | None:
    if replacement_timeout < 0:
        raise ValueError("relay replacement timeout cannot be negative")
    path = relay_state_path(project_root)
    retry_deadline: float | None = None
    while True:
        saw_invalid = False
        with relay_state_lock(project_root, timeout=lock_timeout):
            if not path.is_file():
                if retry_deadline is None:
                    return None
            else:
                raw_bytes = path.read_bytes()
                try:
                    raw = raw_bytes.decode("utf-8")
                    return RelayState.from_json(raw)
                except (
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    UnicodeError,
                    ValueError,
                ):
                    saw_invalid = True
                    _atomic_write_bytes(
                        relay_invalid_state_path(project_root),
                        raw_bytes,
                    )
                    try:
                        current = path.read_bytes()
                    except FileNotFoundError:
                        current = None
                    if current == raw_bytes:
                        path.unlink(missing_ok=True)

        if retry_deadline is None and saw_invalid:
            retry_deadline = monotonic() + replacement_timeout
        if retry_deadline is None:
            return None
        remaining = retry_deadline - monotonic()
        if remaining <= 0:
            return None
        sleep(min(0.01, remaining))


def peek_relay_state(project_root: Path) -> RelayState | None:
    """Read relay ownership without creating locks or repairing invalid state."""
    path = relay_state_path(project_root)
    try:
        raw = path.read_text(encoding="utf-8")
        return RelayState.from_json(raw)
    except (
        FileNotFoundError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
    ):
        return None


def clear_relay_state(
    project_root: Path,
    expected_state: RelayState,
    *,
    lock_timeout: float = 5.0,
) -> bool:
    with relay_state_lock(project_root, timeout=lock_timeout):
        path = relay_state_path(project_root)
        try:
            current = path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, UnicodeError):
            return False
        if current != expected_state.to_json():
            return False
        path.unlink(missing_ok=True)
        return True


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
    monotonic: Callable[[], float] = time.monotonic,
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
    if spawned_identity is None:
        return RelayStartResult(False, "initial_identity_unavailable", None)
    deadline = monotonic() + readiness_timeout
    while True:
        if process.poll() is not None:
            return RelayStartResult(False, "process_exited", None)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        ready = probe(bind_host, bind_port, min(1.0, remaining))
        if monotonic() >= deadline:
            break
        if ready:
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
            except (RelayStateLockTimeout, RelayStateLockError, OSError) as error:
                if isinstance(error, RelayStateLockTimeout):
                    reason = "state_lock_timeout"
                elif isinstance(error, RelayStateLockError):
                    reason = "state_lock_error"
                else:
                    reason = "state_write_failed"
                cleanup = terminate_if_identity_matches(pid, identity, runner, host)
                if cleanup != "terminated":
                    reason = f"{reason}_cleanup_{cleanup}"
                return RelayStartResult(False, reason, None)
            return RelayStartResult(True, "ready", state)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(poll_interval, remaining))

    cleanup = terminate_if_identity_matches(pid, spawned_identity, runner, host)
    reason = "readiness_timeout"
    if cleanup != "terminated":
        reason = f"readiness_timeout_cleanup_{cleanup}"
    return RelayStartResult(False, reason, None)


def stop_relay(
    state: RelayState | None,
    runner: Runner,
    host: HostInfo,
    *,
    project_root: Path | None = None,
) -> RelayStopResult:
    if state is None:
        if project_root is None:
            return RelayStopResult(False, "no_managed_process", None)
        try:
            state = load_relay_state(project_root)
        except RelayStateLockTimeout:
            return RelayStopResult(False, "state_lock_timeout", None)
        except RelayStateLockError:
            return RelayStopResult(False, "state_lock_error", None)
        except OSError:
            return RelayStopResult(False, "state_load_failed", None)
        if state is None:
            return RelayStopResult(False, "no_managed_process", None)

    def clear_failure() -> str | None:
        if project_root is None:
            return None
        try:
            clear_relay_state(project_root, state)
        except RelayStateLockTimeout:
            return "state_lock_timeout"
        except RelayStateLockError:
            return "state_lock_error"
        except OSError:
            return "state_clear_failed"
        return None

    current_identity = read_process_identity(host, state.managed_pid, runner)
    if current_identity is None:
        failure = clear_failure()
        if failure is not None:
            return RelayStopResult(False, f"process_not_found_{failure}", state)
        return RelayStopResult(False, "process_not_found", None)
    if current_identity != state.managed_identity:
        failure = clear_failure()
        if failure is not None:
            return RelayStopResult(
                False,
                f"process_identity_mismatch_{failure}",
                state,
            )
        return RelayStopResult(False, "process_identity_mismatch", None)
    termination = terminate_if_identity_matches(
        state.managed_pid,
        state.managed_identity,
        runner,
        host,
    )
    if termination in {"identity_mismatch", "process_not_found"}:
        failure = clear_failure()
        reason = (
            "process_identity_mismatch"
            if termination == "identity_mismatch"
            else "process_not_found"
        )
        if failure is not None:
            return RelayStopResult(False, f"{reason}_{failure}", state)
        return RelayStopResult(False, reason, None)
    if termination != "terminated":
        return RelayStopResult(False, "termination_failed", state)
    failure = clear_failure()
    if failure is not None:
        return RelayStopResult(True, f"stopped_{failure}", state)
    return RelayStopResult(True, "stopped", None)
