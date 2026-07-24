from __future__ import annotations

import hashlib
import os
import re
import ipaddress
import json
import socket
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .constants import (
    COMPOSE_ASSET_SHA256,
    COMPOSE_BUNDLED_VERSION,
    COMPOSE_MINIMUM,
    COMPOSE_RELEASE_URL,
)
from .models import HostInfo
from .runner import Runner


MOUNT_PROBE_IMAGE = "busybox:1.36.1"
_RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


class DockerError(RuntimeError):
    def __init__(self, code: str, message: str, hint: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class DockerPreflight:
    docker_version: str
    compose: "ComposeRuntime"

    @property
    def compose_version(self) -> tuple[int, int, int]:
        return self.compose.version

    @property
    def invocation(self) -> tuple[str, ...]:
        return self.compose.invocation


def _run(runner: Runner, args: list[str], *, cwd: Path | None = None):
    try:
        return runner.run(args, cwd=cwd)
    except OSError as error:
        raise DockerError(
            "DOCKER_NOT_FOUND",
            "Docker CLI 無法執行。",
            "請安裝並啟動 Docker Desktop 或 Docker Engine，再重新執行。",
        ) from error


def _parse_compose_version(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?:^|\s)v?(\d+)\.(\d+)(?:\.(\d+))?", value.strip())
    if match is None:
        return None
    return tuple(int(item or 0) for item in match.groups())


def normalize_arch(machine: str) -> str:
    key = machine.lower()
    if key in {"x86_64", "amd64"}:
        return "x86_64"
    if key in {"aarch64", "arm64"}:
        return "aarch64"
    raise DockerError(
        "COMPOSE_BUNDLED_UNSUPPORTED_ARCH",
        f"沒有對應此架構（{machine}）的自帶 Docker Compose。",
        "請改用系統套件管理員安裝 Docker Compose v2.24 以上版本。",
    )


_COMPOSE_OS = {"Windows": "windows", "Darwin": "darwin", "Linux": "linux"}


def compose_asset_name(host: HostInfo) -> str:
    os_name = _COMPOSE_OS.get(host.system)
    if os_name is None:
        raise DockerError(
            "COMPOSE_BUNDLED_UNSUPPORTED_ARCH",
            f"沒有對應此作業系統（{host.system}）的自帶 Docker Compose。",
            "請改用系統套件管理員安裝 Docker Compose v2.24 以上版本。",
        )
    arch = normalize_arch(host.machine)
    suffix = ".exe" if os_name == "windows" else ""
    return f"docker-compose-{os_name}-{arch}{suffix}"


def compose_download_url(host: HostInfo) -> str:
    return f"{COMPOSE_RELEASE_URL}/v{COMPOSE_BUNDLED_VERSION}/{compose_asset_name(host)}"


def compose_expected_sha256(host: HostInfo) -> str:
    asset = compose_asset_name(host)
    digest = COMPOSE_ASSET_SHA256.get(asset)
    if digest is None:
        raise DockerError(
            "COMPOSE_BUNDLED_UNSUPPORTED_ARCH",
            f"沒有為 {asset} 釘選的校驗碼。",
            "請改用系統套件管理員安裝 Docker Compose v2.24 以上版本。",
        )
    return digest


def _default_cache_root(host: HostInfo) -> Path:
    if host.system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE")
        return Path(base) if base else host.home
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) if xdg else host.home / ".cache"


def _bundled_filename(host: HostInfo) -> str:
    return "docker-compose.exe" if host.system == "Windows" else "docker-compose"


def compose_cache_path(host: HostInfo, *, cache_root: Path | None = None) -> Path:
    root = cache_root if cache_root is not None else _default_cache_root(host)
    return (
        Path(root)
        / "ai-drawing"
        / "compose"
        / COMPOSE_BUNDLED_VERSION
        / _bundled_filename(host)
    )


Downloader = Callable[[str, Path], None]


def urlopen_download(url: str, dest: Path) -> None:
    with urlopen(url, timeout=60) as response:
        data = response.read()
    dest.write_bytes(data)


def _download_compose(
    url: str,
    dest: Path,
    expected_sha256: str,
    *,
    downloader: Downloader,
) -> None:
    partial = dest.with_name(dest.name + ".partial")
    partial.unlink(missing_ok=True)
    try:
        downloader(url, partial)
    except OSError as error:
        partial.unlink(missing_ok=True)
        raise DockerError(
            "COMPOSE_DOWNLOAD_FAILED",
            "自帶 Docker Compose 下載失敗。",
            "請確認網路與 github.com 可連線後重試；或安裝系統 Docker Compose v2.24 以上。",
        ) from error
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()
    if digest != expected_sha256:
        partial.unlink(missing_ok=True)
        raise DockerError(
            "COMPOSE_CHECKSUM_MISMATCH",
            "自帶 Docker Compose 的校驗碼不符，已刪除下載檔。",
            "請重試下載；若持續失敗，請改安裝系統 Docker Compose v2.24 以上。",
        )
    if os.name != "nt":
        partial.chmod(0o755)
    os.replace(partial, dest)


@dataclass(frozen=True)
class ComposeRuntime:
    invocation: tuple[str, ...]
    version: tuple[int, int, int]
    source: str


_SYSTEM_COMPOSE = ("docker", "compose")


def _compose_short_version(runner: Runner, invocation: tuple[str, ...]):
    result = _run(runner, [*invocation, "version", "--short"])
    if result.returncode != 0:
        return None
    return _parse_compose_version(result.stdout)


def resolve_compose_runtime(
    host: HostInfo,
    runner: Runner,
    *,
    allow_download: bool = True,
    downloader: Downloader | None = None,
    cache_root: Path | None = None,
) -> ComposeRuntime:
    system_version = _compose_short_version(runner, _SYSTEM_COMPOSE)
    if system_version is not None and system_version >= COMPOSE_MINIMUM:
        return ComposeRuntime(_SYSTEM_COMPOSE, system_version, "system")

    path = compose_cache_path(host, cache_root=cache_root)
    if not path.is_file():
        if not allow_download:
            raise DockerError(
                "COMPOSE_UNAVAILABLE",
                "無法使用 Docker Compose。",
                "請安裝 Docker Compose v2.24 以上，或執行 setup 以自動下載自帶版本。",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        _download_compose(
            compose_download_url(host),
            path,
            compose_expected_sha256(host),
            downloader=downloader or urlopen_download,
        )

    bundled_version = _compose_short_version(runner, (str(path),))
    if bundled_version is None:
        raise DockerError(
            "COMPOSE_BUNDLED_UNUSABLE",
            "自帶 Docker Compose 無法執行。",
            "請刪除 cache 目錄下的 compose 後重試，或安裝系統 Docker Compose v2.24 以上。",
        )
    return ComposeRuntime((str(path),), bundled_version, "bundled")


def preflight(
    runner: Runner,
    host: HostInfo,
    *,
    allow_download: bool = True,
    downloader: Downloader | None = None,
    cache_root: Path | None = None,
) -> DockerPreflight:
    daemon = _run(
        runner,
        ["docker", "version", "--format", "{{.Server.Version}}"],
    )
    docker_version = daemon.stdout.strip()
    if daemon.returncode != 0 or not docker_version:
        raise DockerError(
            "DOCKER_DAEMON_UNAVAILABLE",
            "Docker daemon 尚未就緒。",
            "請啟動 Docker Desktop 或 Docker Engine，確認 `docker version` 可用。",
        )
    runtime = resolve_compose_runtime(
        host,
        runner,
        allow_download=allow_download,
        downloader=downloader,
        cache_root=cache_root,
    )
    return DockerPreflight(docker_version=docker_version, compose=runtime)


def _validate_port(port: int) -> int:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be an integer from 1 to 65535")
    return port


def port_available(
    host: str,
    port: int,
    *,
    socket_factory: Callable[..., Any] = socket.socket,
) -> bool:
    _validate_port(port)
    probe = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def find_available_port(
    preferred: int,
    *,
    host: str = "127.0.0.1",
    max_attempts: int = 100,
    probe: Callable[[str, int], bool] = port_available,
) -> int:
    preferred = _validate_port(preferred)
    if type(max_attempts) is not int or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")
    for offset in range(max_attempts):
        candidate = preferred + offset
        if candidate > 65535:
            break
        if probe(host, candidate):
            return candidate
    raise DockerError(
        "PORT_UNAVAILABLE",
        f"找不到從 {preferred} 開始的可用本機連接埠。",
        "請關閉占用連接埠的服務，或使用 --backend-port/--frontend-port 指定其他連接埠。",
    )


def compose_command(
    project_root: Path,
    *arguments: str,
    env_file: Path | None = None,
    override_file: Path | None = None,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> list[str]:
    root = Path(project_root).resolve()
    env = Path(env_file).resolve() if env_file is not None else root / ".env"
    override = (
        Path(override_file).resolve()
        if override_file is not None
        else root / ".ai-drawing/compose.local.yaml"
    )
    return [
        *invocation,
        "--env-file",
        str(env),
        "-f",
        str(root / "docker-compose.yml"),
        "-f",
        str(override),
        *arguments,
    ]


def _compose_required(
    project_root: Path,
    runner: Runner,
    *arguments: str,
    code: str,
    message: str,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> None:
    root = Path(project_root).resolve()
    result = _run(runner, compose_command(root, *arguments, invocation=invocation), cwd=root)
    if result.returncode != 0:
        raise DockerError(
            code,
            message,
            "請執行 `setup.ps1 status` 或 `setup.sh status` 檢查服務，再查看 logs。",
        )


def validate_compose(
    project_root: Path,
    env_file: Path,
    override_file: Path,
    runner: Runner,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> bool:
    root = Path(project_root).resolve()
    result = _run(
        runner,
        compose_command(
            root,
            "config",
            "--quiet",
            env_file=env_file,
            override_file=override_file,
            invocation=invocation,
        ),
        cwd=root,
    )
    return result.returncode == 0


def compose_up(
    project_root: Path,
    runner: Runner,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> None:
    _compose_required(
        project_root,
        runner,
        "up",
        "-d",
        "--build",
        "--remove-orphans",
        code="COMPOSE_UP_FAILED",
        message="Docker 服務啟動失敗。",
        invocation=invocation,
    )


def compose_down(
    project_root: Path,
    runner: Runner,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> None:
    _compose_required(
        project_root,
        runner,
        "down",
        "--remove-orphans",
        "--timeout=10",
        code="COMPOSE_DOWN_FAILED",
        message="Docker 服務停止失敗。",
        invocation=invocation,
    )


def compose_service_states(
    project_root: Path,
    runner: Runner,
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> dict[str, str]:
    root = Path(project_root).resolve()
    result = _run(
        runner,
        compose_command(root, "ps", "--all", "--format", "json", invocation=invocation),
        cwd=root,
    )
    if result.returncode != 0:
        raise DockerError(
            "COMPOSE_STATUS_FAILED",
            "無法讀取 Docker Compose 服務狀態。",
            "請確認設定存在並執行 reconfigure。",
        )
    text = result.stdout.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        records = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        try:
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise DockerError(
                "COMPOSE_STATUS_INVALID",
                "Docker Compose 回傳無法解析的服務狀態。",
                "請更新 Docker Compose 至支援 JSON status 的版本。",
            ) from error
    states: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        service = record.get("Service")
        state = record.get("State")
        if isinstance(service, str) and service and isinstance(state, str):
            states[service] = state.lower()
    return states


def compose_up_services(
    project_root: Path,
    runner: Runner,
    services: frozenset[str],
    invocation: tuple[str, ...] = ("docker", "compose"),
) -> None:
    if not services:
        return
    _compose_required(
        project_root,
        runner,
        "up",
        "-d",
        "--no-deps",
        *sorted(services),
        code="COMPOSE_RESTORE_FAILED",
        message="無法還原先前的 Docker Compose 服務集合。",
        invocation=invocation,
    )


def docker_bridge_host(runner: Runner) -> str:
    result = _run(
        runner,
        [
            "docker",
            "network",
            "inspect",
            "bridge",
            "--format",
            "{{(index .IPAM.Config 0).Gateway}}",
        ],
    )
    address = result.stdout.strip()
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        parsed = None
        cause = error
    else:
        cause = None
    if (
        result.returncode != 0
        or not isinstance(parsed, ipaddress.IPv4Address)
        or not any(parsed in network for network in _RFC1918_NETWORKS)
        or parsed.is_loopback
        or parsed.is_unspecified
        or parsed.is_multicast
        or parsed.is_link_local
    ):
        raise DockerError(
            "DOCKER_BRIDGE_UNSAFE",
            "Docker bridge gateway 不存在或不是安全的私有 IPv4 位址。",
            "請確認預設 bridge network 可用；不會綁定 0.0.0.0 或公開位址。",
        ) from cause
    return str(parsed)


def _is_within(path: Path, roots: Iterable[Path]) -> bool:
    return any(path == root or path.is_relative_to(root) for root in roots)


def mount_probe(
    path: Path,
    runner: Runner,
    *,
    allowed_roots: Iterable[Path],
) -> None:
    try:
        resolved = Path(path).resolve(strict=True)
    except OSError as error:
        raise DockerError(
            "MOUNT_PATH_MISSING",
            "指定的 Docker 掛載路徑不存在。",
            "請確認專案資料路徑或 ComfyUI 路徑後重試。",
        ) from error
    if not resolved.is_dir():
        raise DockerError(
            "MOUNT_PATH_INVALID",
            "指定的 Docker 掛載路徑不是目錄。",
            "請選擇 ComfyUI 根目錄或專案資料目錄。",
        )
    try:
        allowed = tuple(Path(root).resolve(strict=True) for root in allowed_roots)
    except OSError as error:
        raise DockerError(
            "MOUNT_PATH_NOT_ALLOWED",
            "允許的掛載根目錄不存在。",
            "請重新執行 reconfigure 選擇有效路徑。",
        ) from error
    if not allowed or not _is_within(resolved, allowed):
        raise DockerError(
            "MOUNT_PATH_NOT_ALLOWED",
            "拒絕探測未明確允許的掛載路徑。",
            "只可使用專案資料目錄或已確認的 ComfyUI 目錄。",
        )
    command = [
        "docker",
        "run",
        "--rm",
        "--mount",
        f"type=bind,source={resolved},target=/probe,readonly",
        MOUNT_PROBE_IMAGE,
        "test",
        "-d",
        "/probe",
    ]
    result = _run(runner, command)
    if result.returncode != 0:
        raise DockerError(
            "MOUNT_PROBE_FAILED",
            f"Docker 無法讀取已選擇的掛載路徑：{resolved}",
            "請在 Docker Desktop 分享該路徑，並確認目錄權限。",
        )


def wait_http_ready(
    url: str,
    *,
    http_get: Callable[..., Any] = urlopen,
    timeout: float = 60.0,
    interval: float = 0.5,
    request_timeout: float = 2.0,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    if timeout <= 0 or interval <= 0 or request_timeout <= 0:
        raise ValueError("readiness timing values must be positive")
    deadline = monotonic() + timeout
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        try:
            response = http_get(url, timeout=min(request_timeout, remaining))
            if hasattr(response, "__enter__"):
                with response as opened:
                    status = getattr(opened, "status", 0)
            else:
                status = getattr(response, "status", 0)
            if monotonic() < deadline and 200 <= status < 300:
                return True
        except (OSError, TimeoutError, ValueError):
            pass
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        sleep(min(interval, remaining))
