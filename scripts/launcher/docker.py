from __future__ import annotations

import re
import socket
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .constants import COMPOSE_MINIMUM
from .runner import Runner


MOUNT_PROBE_IMAGE = "busybox:1.36.1"


class DockerError(RuntimeError):
    def __init__(self, code: str, message: str, hint: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class DockerPreflight:
    docker_version: str
    compose_version: tuple[int, int, int]


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


def preflight(runner: Runner) -> DockerPreflight:
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

    compose = _run(runner, ["docker", "compose", "version", "--short"])
    version = _parse_compose_version(compose.stdout)
    if compose.returncode != 0 or version is None:
        raise DockerError(
            "COMPOSE_UNAVAILABLE",
            "無法讀取 Docker Compose 版本。",
            "請安裝 Docker Compose v2.24 以上版本。",
        )
    if version < COMPOSE_MINIMUM:
        minimum = ".".join(str(item) for item in COMPOSE_MINIMUM)
        raise DockerError(
            "COMPOSE_VERSION_UNSUPPORTED",
            f"Docker Compose 版本過舊，需要 {minimum} 以上。",
            "請更新 Docker Desktop 或 Docker Compose plugin。",
        )
    return DockerPreflight(docker_version=docker_version, compose_version=version)


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
) -> list[str]:
    root = Path(project_root).resolve()
    env = Path(env_file).resolve() if env_file is not None else root / ".env"
    override = (
        Path(override_file).resolve()
        if override_file is not None
        else root / ".ai-drawing/compose.local.yaml"
    )
    return [
        "docker",
        "compose",
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
) -> None:
    root = Path(project_root).resolve()
    result = _run(runner, compose_command(root, *arguments), cwd=root)
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
        ),
        cwd=root,
    )
    return result.returncode == 0


def compose_up(project_root: Path, runner: Runner) -> None:
    _compose_required(
        project_root,
        runner,
        "up",
        "-d",
        "--build",
        "--remove-orphans",
        code="COMPOSE_UP_FAILED",
        message="Docker 服務啟動失敗。",
    )


def compose_down(project_root: Path, runner: Runner) -> None:
    _compose_required(
        project_root,
        runner,
        "down",
        "--remove-orphans",
        "--timeout=10",
        code="COMPOSE_DOWN_FAILED",
        message="Docker 服務停止失敗。",
    )


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
