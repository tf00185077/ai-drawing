from __future__ import annotations

import argparse
import re
import socket
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from . import docker
from .comfyui import (
    ComfyInstallError,
    discover_comfyui,
    install_comfyui,
    probe_comfyui,
    update_comfyui,
    validate_comfyui_root,
)
from .configuration import (
    ConfigurationError,
    atomic_write,
    load_state,
    parse_env,
    write_configuration,
)
from .constants import (
    COMFYUI_VERSION,
    DEFAULT_BACKEND_PORT,
    DEFAULT_COMFYUI_PORT,
    DEFAULT_FRONTEND_PORT,
    STATE_SCHEMA_VERSION,
)
from .models import (
    ComfyMode,
    ComfyPaths,
    DeviceMode,
    LauncherCommand,
    LauncherState,
    LocalSettings,
)
from .platforms import (
    choose_device,
    default_comfyui_root,
    detect_host,
    nvidia_available,
    read_process_identity,
)
from .processes import start_comfyui, stop_comfyui
from .relay import (
    RelayState,
    load_relay_state,
    start_relay,
    stop_relay,
)
from .runner import Runner, SubprocessRunner


class LauncherError(RuntimeError):
    def __init__(self, code: str, message: str, hint: str, *, exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code


_LOG_SECRET = re.compile(
    r"(?im)\b(authorization|token|secret|password|api[_-]?key)\b\s*[:=]\s*[^\r\n]*"
)


def _redact_log(value: str) -> str:
    return _LOG_SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


@dataclass(frozen=True)
class _ConfigurationSnapshot:
    values: tuple[tuple[Path, str | None], ...]


class DefaultServices:
    """Real host boundaries; tests inject a scripted object with the same methods."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        runner: Runner | None = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.runner = runner or SubprocessRunner()
        self.host = detect_host()
        self._input = input_fn
        self._output = output_fn

    def emit(self, message: str) -> None:
        self._output(message)

    def preflight(self) -> None:
        docker.preflight(self.runner)

    def load_state(self) -> LauncherState | None:
        return load_state(self.project_root / "data/bootstrap/state.json")

    def ask(self, message: str, default: bool = False) -> bool:
        suffix = "[Y/n]" if default else "[y/N]"
        answer = self._input(f"{message} {suffix} ").strip().lower()
        if not answer:
            return default
        return answer in {"y", "yes", "是"}

    def choose(
        self,
        message: str,
        options: Sequence[str],
        default: str | None = None,
    ) -> str:
        rendered = "/".join(options)
        answer = self._input(f"{message} ({rendered}) ").strip().lower()
        selected = answer or default
        if selected not in options:
            raise LauncherError(
                "INVALID_DECISION",
                "輸入的選項無效。",
                f"請選擇：{rendered}",
                exit_code=2,
            )
        return selected

    def detect_device(self) -> DeviceMode:
        return choose_device(self.host, nvidia_available(self.runner))

    def discover_comfyui(self, candidates: Sequence[Path]):
        return discover_comfyui(candidates, self.host)

    def probe_external(self, port: int) -> bool:
        return probe_comfyui(f"http://127.0.0.1:{port}").running

    def default_comfyui_root(self) -> Path:
        return default_comfyui_root(self.host)

    def install_comfyui(self, root: Path, device: DeviceMode):
        return install_comfyui(root, device, self.runner, self.host)

    def start_comfyui(self, planned: LauncherState) -> LauncherState:
        if planned.comfyui_root is None or planned.device is None:
            raise LauncherError(
                "COMFYUI_STATE_INVALID",
                "ComfyUI 啟動設定不完整。",
                "請重新執行 reconfigure。",
            )
        if planned.managed_pid is not None:
            identity = read_process_identity(self.host, planned.managed_pid, self.runner)
            if identity is not None and identity == planned.managed_identity:
                if self.probe_external(planned.comfyui_port):
                    return planned
                raise LauncherError(
                    "COMFYUI_MANAGED_NOT_READY",
                    "已知的 managed ComfyUI 程序仍在執行，但 API 尚未就緒。",
                    "請查看 data/logs/comfyui.log；啟動器不會重複建立程序。",
                )
            if self.probe_external(planned.comfyui_port):
                return replace(
                    planned,
                    comfy_mode=ComfyMode.EXTERNAL,
                    managed_pid=None,
                    managed_identity=None,
                )
        validation = validate_comfyui_root(planned.comfyui_root, self.host)
        if not validation.controllable or validation.python is None:
            raise LauncherError(
                "COMFYUI_NOT_CONTROLLABLE",
                "找不到可控制的 ComfyUI Python runtime。",
                "請確認路徑或重新安裝 ComfyUI。",
            )
        result = start_comfyui(
            root=validation.root,
            python=validation.python,
            device=planned.device,
            port=planned.comfyui_port,
            host=self.host,
            runner=self.runner,
            project_root=self.project_root,
        )
        if not result.started or result.state is None:
            raise LauncherError(
                "COMFYUI_START_FAILED",
                "ComfyUI 未能在時限內啟動。",
                "請查看 data/logs/comfyui.log，或 reconfigure 選擇 disabled。",
            )
        return replace(
            result.state,
            launcher_installed=planned.launcher_installed,
            installed_root=planned.installed_root,
            installed_commit=planned.installed_commit,
        )

    def stop_comfyui(self, current: LauncherState):
        return stop_comfyui(current, self.runner, self.host)

    def select_ports(self, backend_port: int, frontend_port: int) -> tuple[int, int]:
        backend = docker.find_available_port(backend_port)
        frontend = docker.find_available_port(
            frontend_port,
            max_attempts=100,
            probe=lambda host, port: port != backend and docker.port_available(host, port),
        )
        return backend, frontend

    def load_ports(self) -> tuple[int, int]:
        env_path = self.project_root / ".env"
        values = (
            parse_env(env_path.read_text(encoding="utf-8")) if env_path.is_file() else {}
        )
        try:
            backend = int(values.get("BACKEND_PORT", DEFAULT_BACKEND_PORT))
            frontend = int(values.get("FRONTEND_PORT", DEFAULT_FRONTEND_PORT))
        except ValueError as error:
            raise LauncherError(
                "CONFIG_PORT_INVALID",
                "既有設定中的連接埠無效。",
                "請重新執行 reconfigure。",
            ) from error
        if not _valid_port(backend) or not _valid_port(frontend):
            raise LauncherError(
                "CONFIG_PORT_INVALID",
                "既有設定中的連接埠超出有效範圍。",
                "連接埠必須是 1 到 65535 的整數；請重新執行 reconfigure。",
            )
        return backend, frontend

    def mount_probes(self, settings: LocalSettings) -> None:
        data = (self.project_root / "data").resolve()
        data.mkdir(parents=True, exist_ok=True)
        docker.mount_probe(
            self.project_root,
            self.runner,
            allowed_roots=(self.project_root,),
        )
        docker.mount_probe(data, self.runner, allowed_roots=(self.project_root,))
        if settings.comfy_paths is not None:
            docker.mount_probe(
                settings.comfy_paths.root,
                self.runner,
                allowed_roots=(settings.comfy_paths.root,),
            )

    def snapshot_configuration(self) -> _ConfigurationSnapshot:
        paths = (
            self.project_root / ".env",
            self.project_root / ".ai-drawing/compose.local.yaml",
            self.project_root / "data/bootstrap/state.json",
        )
        return _ConfigurationSnapshot(
            tuple(
                (path, path.read_text(encoding="utf-8") if path.is_file() else None)
                for path in paths
            )
        )

    def restore_configuration(self, snapshot: _ConfigurationSnapshot) -> None:
        try:
            for path, content in snapshot.values:
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, content)
        except OSError as error:
            raise LauncherError(
                "CONFIG_ROLLBACK_FAILED",
                "啟動失敗，且無法還原原設定。",
                "請保留 data/bootstrap 並人工檢查 .env 與 compose override。",
            ) from error

    def write_configuration(
        self,
        settings: LocalSettings,
        new_state: LauncherState,
    ) -> None:
        write_configuration(
            self.project_root,
            settings,
            new_state,
            validate=lambda env, override: docker.validate_compose(
                self.project_root,
                env,
                override,
                self.runner,
            ),
        )

    def validate_current_compose(self) -> None:
        if not docker.validate_compose(
            self.project_root,
            self.project_root / ".env",
            self.project_root / ".ai-drawing/compose.local.yaml",
            self.runner,
        ):
            raise LauncherError(
                "COMPOSE_CONFIG_INVALID",
                "Docker Compose 設定驗證失敗。",
                "請重新執行 reconfigure；不會套用無效設定。",
            )

    def compose_running_services(self) -> frozenset[str]:
        return frozenset(
            service
            for service, state in docker.compose_service_states(
                self.project_root, self.runner
            ).items()
            if state == "running"
        )

    def compose_up_services(self, services: frozenset[str]) -> None:
        docker.compose_up_services(self.project_root, self.runner, services)

    def compose_up(self) -> None:
        docker.compose_up(self.project_root, self.runner)

    def compose_down(self) -> None:
        docker.compose_down(self.project_root, self.runner)

    @staticmethod
    def _relay_ready(state: RelayState) -> bool:
        try:
            with socket.create_connection(
                (state.bind_host, state.bind_port), timeout=0.5
            ):
                return True
        except OSError:
            return False

    def ensure_relay(self, settings: LocalSettings):
        from .relay import RelayStartResult

        if self.host.system != "Linux" or settings.comfy_mode is ComfyMode.DISABLED:
            return RelayStartResult(False, "not_required", None)
        existing = load_relay_state(self.project_root)
        existing_was_stopped = False
        if existing is not None:
            identity = read_process_identity(
                self.host, existing.managed_pid, self.runner
            )
            if (
                identity == existing.managed_identity
                and existing.target_port == settings.comfyui_port
                and existing.bind_port == settings.comfyui_port
                and self._relay_ready(existing)
            ):
                return RelayStartResult(False, "already_ready", existing)
            stopped = stop_relay(
                existing,
                self.runner,
                self.host,
                project_root=self.project_root,
            )
            existing_was_stopped = stopped.stopped
            if not stopped.stopped and stopped.reason not in {
                "process_not_found",
                "process_identity_mismatch",
            }:
                raise LauncherError(
                    "RELAY_REPLACEMENT_FAILED",
                    "既有 launcher relay 無法安全替換。",
                    "請執行 status 並檢查 data/bootstrap/relay-state.json。",
                )
        bridge_host = docker.docker_bridge_host(self.runner)
        result = start_relay(
            project_root=self.project_root,
            python=Path(sys.executable),
            bind_host=bridge_host,
            bind_port=settings.comfyui_port,
            target_port=settings.comfyui_port,
            host=self.host,
            runner=self.runner,
        )
        if not result.started or result.state is None:
            if existing is not None and existing_was_stopped:
                try:
                    self.restore_relay(existing)
                except Exception as restore_error:
                    raise LauncherError(
                        "RELAY_REPLACEMENT_ROLLBACK_FAILED",
                        "新 relay 啟動失敗，且舊 relay 無法恢復。",
                        "請執行 status 並檢查 relay ownership/log。",
                    ) from restore_error
            raise LauncherError(
                "RELAY_START_FAILED",
                "Linux Docker bridge relay 未能安全啟動。",
                "請查看 data/logs/comfyui-relay.log，或停用 ComfyUI。",
            )
        return result

    def current_relay_state(self) -> RelayState | None:
        state = load_relay_state(self.project_root)
        if state is None:
            return None
        identity = read_process_identity(self.host, state.managed_pid, self.runner)
        return state if identity == state.managed_identity else None

    def restore_relay(self, state: RelayState) -> None:
        result = start_relay(
            project_root=self.project_root,
            python=Path(sys.executable),
            bind_host=state.bind_host,
            bind_port=state.bind_port,
            target_port=state.target_port,
            host=self.host,
            runner=self.runner,
        )
        if not result.started:
            raise LauncherError(
                "RELAY_RESTORE_FAILED",
                "無法恢復先前 launcher relay。",
                "請執行 status 並檢查 data/logs/comfyui-relay.log。",
            )

    def stop_relay(self, state: RelayState | None = None):
        return stop_relay(
            state,
            self.runner,
            self.host,
            project_root=self.project_root,
        )

    def wait_backend(self, port: int, *, timeout: float = 60.0) -> bool:
        return docker.wait_http_ready(
            f"http://127.0.0.1:{port}/health", timeout=timeout
        )

    def wait_frontend(self, port: int, *, timeout: float = 60.0) -> bool:
        return docker.wait_http_ready(f"http://127.0.0.1:{port}/", timeout=timeout)

    def save_state(self, new_state: LauncherState) -> None:
        atomic_write(
            self.project_root / "data/bootstrap/state.json",
            new_state.to_json() + "\n",
        )

    @staticmethod
    def _model_count(root: Path | None) -> int:
        if root is None:
            return 0
        extensions = {".safetensors", ".ckpt", ".pt", ".pth"}
        found: set[Path] = set()
        for relative in ("models/checkpoints", "models/diffusion_models"):
            directory = root / relative
            if directory.is_dir():
                found.update(
                    path.resolve()
                    for path in directory.iterdir()
                    if path.is_file() and path.suffix.lower() in extensions
                )
        return len(found)

    def status(self, current: LauncherState | None) -> dict[str, Any]:
        compose_files = (
            self.project_root / "docker-compose.yml",
            self.project_root / ".env",
            self.project_root / ".ai-drawing/compose.local.yaml",
        )
        services = (
            docker.compose_service_states(self.project_root, self.runner)
            if all(path.is_file() for path in compose_files)
            else {}
        )
        backend_port, frontend_port = self.load_ports()
        backend = (
            "reachable" if self.wait_backend(backend_port, timeout=1.0) else "unreachable"
        )
        frontend = (
            "reachable"
            if self.wait_frontend(frontend_port, timeout=1.0)
            else "unreachable"
        )
        comfy_state = "not_configured"
        ownership = "none"
        model_count = 0
        hint = "執行 reconfigure 可設定或安裝 ComfyUI。"
        if current is not None and current.comfy_mode is not ComfyMode.DISABLED:
            probe = probe_comfyui(f"http://127.0.0.1:{current.comfyui_port}")
            model_count = self._model_count(current.comfyui_root)
            if current.comfy_mode is ComfyMode.MANAGED:
                identity = (
                    read_process_identity(self.host, current.managed_pid, self.runner)
                    if current.managed_pid is not None
                    else None
                )
                ownership = (
                    "managed_verified"
                    if identity is not None and identity == current.managed_identity
                    else "managed_stale"
                )
            else:
                ownership = "external"
            if not probe.running:
                comfy_state = "unreachable"
                hint = "請啟動 ComfyUI 或執行 reconfigure 選擇 disabled。"
            elif model_count == 0:
                comfy_state = "no_models"
                hint = "ComfyUI 已連線；請自行放入 checkpoint 或 diffusion model。"
            else:
                comfy_state = "connected"
                hint = "ComfyUI 與模型已就緒。"

        relay_status = "not_required" if self.host.system != "Linux" else "not_running"
        if self.host.system == "Linux":
            relay_state = load_relay_state(self.project_root)
            if relay_state is not None:
                identity = read_process_identity(
                    self.host, relay_state.managed_pid, self.runner
                )
                relay_status = (
                    "running_verified"
                    if identity == relay_state.managed_identity
                    and self._relay_ready(relay_state)
                    else "stale"
                )
        return {
            "docker": "available",
            "services": services,
            "backend": backend,
            "frontend": frontend,
            "comfy": {
                "state": comfy_state,
                "ownership": ownership,
                "model_count": model_count,
                "hint": hint,
            },
            "relay": relay_status,
        }

    def compose_logs(self) -> None:
        for name in ("bootstrap.log", "comfyui.log", "comfyui-relay.log"):
            path = self.project_root / "data/logs" / name
            if not path.is_file():
                self.emit(f"--- {name}: missing ---")
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self.emit(f"--- {name}: unreadable ---")
                continue
            self.emit(f"--- {name} ---")
            self.emit(_redact_log(content))
        result = self.runner.run(
            docker.compose_command(self.project_root, "logs", "--tail", "200"),
            cwd=self.project_root,
        )
        self.emit("--- docker compose logs ---")
        if result.returncode == 0:
            self.emit(_redact_log(result.stdout))
        else:
            self.emit("Compose logs unavailable.")

    def update_comfyui(self, current: LauncherState) -> None:
        if (
            not current.launcher_installed
            or current.installed_root is None
            or current.device is None
        ):
            raise LauncherError(
                "COMFYUI_NOT_MANAGED",
                "目前沒有可更新的 managed ComfyUI。",
                "請先執行 reconfigure 並選擇由啟動器管理的 ComfyUI。",
            )
        try:
            update_comfyui(
                current.installed_root,
                current.device,
                self.runner,
                self.host,
            )
        except ComfyInstallError as error:
            raise LauncherError(
                "COMFYUI_UPDATE_FAILED",
                "ComfyUI 更新失敗，已嘗試還原。",
                "請查看終端前一個安全摘要與 ComfyUI 安裝狀態。",
            ) from error


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise LauncherError(
            "CLI_ARGUMENT_INVALID",
            "啟動參數無效。",
            f"請使用 --help 檢查參數格式（{message}）。",
            exit_code=2,
        )


def _port_argument(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be from 1 to 65535")
    return port


def _valid_port(value: object) -> bool:
    return type(value) is int and 1 <= value <= 65535


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="AI Drawing launcher")
    parser.add_argument(
        "command",
        nargs="?",
        choices=[command.value for command in LauncherCommand] + ["dry-run"],
        default=None,
    )
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--accept-alternate-ports", action="store_true")
    parser.add_argument(
        "--on-comfy-failure",
        choices=("abort", "retry", "cpu", "disabled"),
    )
    parser.add_argument(
        "--on-mount-failure",
        choices=("abort", "retry", "disabled"),
    )
    parser.add_argument("--comfyui-mode", choices=[mode.value for mode in ComfyMode])
    parser.add_argument("--comfyui-path", type=Path)
    parser.add_argument("--device", choices=[mode.value for mode in DeviceMode])
    parser.add_argument("--backend-port", type=_port_argument, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-port", type=_port_argument, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--comfyui-port", type=_port_argument, default=DEFAULT_COMFYUI_PORT)
    return parser


def _base_state(
    mode: ComfyMode,
    *,
    root: Path | None = None,
    device: DeviceMode | None = None,
    port: int = DEFAULT_COMFYUI_PORT,
    previous: LauncherState | None = None,
    launcher_installed: bool | None = None,
    installed_root: Path | None = None,
    installed_commit: str | None = None,
) -> LauncherState:
    same_root = (
        previous is not None
        and root is not None
        and previous.comfyui_root is not None
        and previous.comfyui_root.resolve() == root.resolve()
        and previous.comfyui_port == port
    )
    preserve_process = (
        same_root
        and mode is ComfyMode.MANAGED
        and previous is not None
        and previous.device == device
    )
    preserve_install = (
        previous is not None
        and previous.launcher_installed
        and previous.installed_root is not None
        and (
            (root is not None and previous.installed_root.resolve() == root.resolve())
            or (root is None and mode is ComfyMode.DISABLED)
        )
    )
    owned_install = preserve_install if launcher_installed is None else launcher_installed
    return LauncherState(
        schema_version=STATE_SCHEMA_VERSION,
        comfy_mode=mode,
        comfyui_root=root,
        device=device,
        comfyui_port=port,
        managed_pid=previous.managed_pid if preserve_process else None,
        managed_identity=previous.managed_identity if preserve_process else None,
        launcher_installed=owned_install,
        installed_root=(
            previous.installed_root
            if owned_install and installed_root is None and previous is not None
            else installed_root
        ),
        installed_commit=(
            previous.installed_commit
            if owned_install and installed_commit is None and previous is not None
            else installed_commit
        ),
    )


def _settings(
    planned: LauncherState,
    backend_port: int,
    frontend_port: int,
) -> LocalSettings:
    if planned.comfy_mode is ComfyMode.DISABLED:
        return LocalSettings.disabled(
            backend_port=backend_port,
            frontend_port=frontend_port,
        )
    return LocalSettings(
        comfy_mode=planned.comfy_mode,
        comfyui_port=planned.comfyui_port,
        comfy_paths=(
            ComfyPaths.from_root(planned.comfyui_root)
            if planned.comfyui_root is not None
            else None
        ),
        backend_port=backend_port,
        frontend_port=frontend_port,
    )


def _install_or_disable(
    args: argparse.Namespace,
    services: Any,
    root: Path,
    device: DeviceMode,
    previous: LauncherState | None,
) -> LauncherState:
    try:
        installed = services.install_comfyui(root, device)
    except Exception as first_error:
        choice = _recovery_choice(args, services, kind="comfy")
        if choice == "disabled":
            return _base_state(
                ComfyMode.DISABLED,
                port=args.comfyui_port,
                previous=previous,
            )
        if choice == "abort":
            raise LauncherError(
                "COMFYUI_INSTALL_FAILED",
                "ComfyUI 安裝未完成。",
                "可重新執行 setup，或選擇 --comfyui-mode disabled。",
            ) from first_error
        retry_device = DeviceMode.CPU if choice == "cpu" else device
        try:
            installed = services.install_comfyui(root, retry_device)
            device = retry_device
        except Exception as retry_error:
            raise LauncherError(
                "COMFYUI_INSTALL_RECOVERY_FAILED",
                "ComfyUI 安裝恢復嘗試仍未完成。",
                "請查看安裝環境，或重新執行並選擇 disabled。",
            ) from retry_error
    return _base_state(
        ComfyMode.MANAGED,
        root=installed.root,
        device=device,
        port=args.comfyui_port,
        launcher_installed=True,
        installed_root=installed.root,
        installed_commit=COMFYUI_VERSION,
    )


def _plan_comfyui(
    args: argparse.Namespace,
    services: Any,
    previous: LauncherState | None = None,
    *,
    dry_run: bool = False,
) -> LauncherState:
    explicit_mode = ComfyMode(args.comfyui_mode) if args.comfyui_mode else None
    if args.non_interactive and explicit_mode is None:
        raise LauncherError(
            "MISSING_DECISION",
            "非互動模式缺少 ComfyUI 決策。",
            "請指定 --comfyui-mode disabled、external 或 managed。",
            exit_code=2,
        )
    if explicit_mode is ComfyMode.DISABLED:
        return _base_state(
            ComfyMode.DISABLED,
            port=args.comfyui_port,
            previous=previous,
        )
    if explicit_mode is ComfyMode.EXTERNAL:
        if not services.probe_external(args.comfyui_port):
            raise LauncherError(
                "COMFYUI_UNREACHABLE",
                "指定的 external ComfyUI 尚未就緒。",
                "請先啟動 ComfyUI，確認 /system_stats 可連線，或選擇 disabled。",
            )
        return _base_state(
            ComfyMode.EXTERNAL,
            root=args.comfyui_path.resolve() if args.comfyui_path else None,
            port=args.comfyui_port,
            previous=previous,
        )
    if (
        args.non_interactive
        and explicit_mode is ComfyMode.MANAGED
        and not args.comfyui_path
        and not dry_run
    ):
        raise LauncherError(
            "MISSING_COMFYUI_PATH",
            "非互動 managed 模式缺少安裝或既有路徑。",
            "請指定 --comfyui-path。若不安裝，請使用 --comfyui-mode disabled。",
            exit_code=2,
        )

    if explicit_mode is None and not services.ask("是否設定 ComfyUI？", default=False):
        return _base_state(
            ComfyMode.DISABLED,
            port=args.comfyui_port,
            previous=previous,
        )
    if services.probe_external(args.comfyui_port):
        return _base_state(
            ComfyMode.EXTERNAL,
            port=args.comfyui_port,
            previous=previous,
        )

    root = args.comfyui_path.resolve() if args.comfyui_path else None
    candidates = tuple(path for path in (root, services.default_comfyui_root()) if path)
    found = services.discover_comfyui(candidates)
    if found and (explicit_mode is ComfyMode.MANAGED or services.ask(
        f"找到 ComfyUI：{found[0].root}，是否使用？", default=True
    )):
        device = DeviceMode(args.device) if args.device else services.detect_device()
        return _base_state(
            ComfyMode.MANAGED,
            root=found[0].root,
            device=device,
            port=args.comfyui_port,
            previous=previous,
        )

    if explicit_mode is None and not services.ask("是否自動安裝 ComfyUI？", default=True):
        return _base_state(
            ComfyMode.DISABLED,
            port=args.comfyui_port,
            previous=previous,
        )
    target = root or services.default_comfyui_root()
    device = DeviceMode(args.device) if args.device else services.detect_device()
    if dry_run:
        return _base_state(
            ComfyMode.MANAGED,
            root=target,
            device=device,
            port=args.comfyui_port,
            previous=previous,
        )
    return _install_or_disable(args, services, target, device, previous)


def _confirm_selected_ports(
    args: argparse.Namespace,
    services: Any,
    selected: tuple[int, int],
) -> tuple[int, int]:
    backend_port, frontend_port = selected
    if not _valid_port(backend_port) or not _valid_port(frontend_port):
        raise LauncherError(
            "CONFIG_PORT_INVALID",
            "選擇的連接埠無效。",
            "連接埠必須是 1 到 65535 的內建整數。",
        )
    alternate = (
        backend_port != args.backend_port or frontend_port != args.frontend_port
    )
    if not alternate:
        return selected
    description = f"Backend {backend_port}、Frontend {frontend_port}"
    if args.non_interactive and not args.accept_alternate_ports:
        raise LauncherError(
            "ALTERNATE_PORTS_NOT_ACCEPTED",
            f"預設連接埠已占用；可用替代為 {description}。",
            "非互動模式請加上 --accept-alternate-ports，或指定其他 ports。",
            exit_code=2,
        )
    if not args.non_interactive and not services.ask(
        f"預設連接埠已占用，是否使用 {description}？", default=False
    ):
        raise LauncherError(
            "ALTERNATE_PORTS_REJECTED",
            "使用者未接受替代連接埠。",
            "請釋放預設連接埠或指定其他 ports。",
            exit_code=2,
        )
    return selected


def _recovery_choice(
    args: argparse.Namespace,
    services: Any,
    *,
    kind: str,
) -> str:
    flag = args.on_comfy_failure if kind == "comfy" else args.on_mount_failure
    options = (
        ("retry", "cpu", "disabled", "abort")
        if kind == "comfy"
        else ("retry", "disabled", "abort")
    )
    if args.non_interactive:
        if flag is None:
            raise LauncherError(
                "MISSING_RECOVERY_DECISION",
                "非互動模式遇到可恢復錯誤，但沒有明確處理決策。",
                f"請指定 --on-{kind}-failure。",
                exit_code=2,
            )
        return flag
    return services.choose(
        "恢復方式",
        options,
        default="abort",
    )


def _start_comfy_with_recovery(
    args: argparse.Namespace,
    services: Any,
    planned: LauncherState,
) -> LauncherState:
    try:
        return services.start_comfyui(planned)
    except Exception as original:
        choice = _recovery_choice(args, services, kind="comfy")
        if choice == "disabled":
            return _base_state(
                ComfyMode.DISABLED,
                port=planned.comfyui_port,
                previous=planned,
            )
        retry_state = planned
        if choice == "cpu":
            retry_state = replace(
                planned,
                device=DeviceMode.CPU,
                managed_pid=None,
                managed_identity=None,
            )
        if choice in {"retry", "cpu"}:
            try:
                return services.start_comfyui(retry_state)
            except Exception as retry_error:
                raise LauncherError(
                    "COMFYUI_RECOVERY_FAILED",
                    "ComfyUI 恢復嘗試仍未成功。",
                    "請查看 ComfyUI log，或重新執行並選擇 disabled。",
                ) from retry_error
        raise LauncherError(
            "COMFYUI_START_ABORTED",
            "ComfyUI 啟動已中止。",
            "可重新執行並選擇 retry、cpu 或 disabled。",
        ) from original


def _mount_with_recovery(
    args: argparse.Namespace,
    services: Any,
    settings: LocalSettings,
    active: LauncherState,
) -> tuple[LocalSettings, LauncherState]:
    try:
        services.mount_probes(settings)
        return settings, active
    except Exception as original:
        choice = _recovery_choice(args, services, kind="mount")
        if choice == "retry":
            services.mount_probes(settings)
            return settings, active
        if choice == "disabled" and active.comfy_mode is not ComfyMode.DISABLED:
            disabled = _base_state(
                ComfyMode.DISABLED,
                port=active.comfyui_port,
                previous=active,
            )
            disabled_settings = _settings(
                disabled,
                settings.backend_port,
                settings.frontend_port,
            )
            services.mount_probes(disabled_settings)
            return disabled_settings, disabled
        raise LauncherError(
            "MOUNT_RECOVERY_ABORTED",
            "Docker 掛載檢查未通過。",
            "請修正 Docker 路徑分享，或選擇 disabled。",
        ) from original


def _safe_rollback(
    services: Any,
    *,
    snapshot: Any | None,
    compose_attempted: bool,
    prior_services: frozenset[str],
    started_state: LauncherState | None,
    started_relay: RelayState | None,
    prior_relay: RelayState | None,
    prior_relay_stopped: bool,
) -> None:
    rollback_errors: list[Exception] = []
    if compose_attempted:
        try:
            services.compose_down()
        except Exception as error:
            rollback_errors.append(error)
    if snapshot is not None:
        try:
            services.restore_configuration(snapshot)
        except Exception as error:
            rollback_errors.append(error)
    if started_relay is not None:
        try:
            stopped_relay = services.stop_relay(started_relay)
            if not stopped_relay.stopped:
                raise LauncherError(
                    "RELAY_ROLLBACK_STOP_FAILED",
                    "Rollback 無法停止本次啟動的 Linux relay。",
                    "請執行 status 並人工確認 relay PID。",
                )
        except Exception as error:
            rollback_errors.append(error)
    if prior_relay is not None and (
        prior_relay_stopped
        or (started_relay is not None and prior_relay != started_relay)
    ):
        try:
            services.restore_relay(prior_relay)
        except Exception as error:
            rollback_errors.append(error)
    if started_state is not None:
        try:
            stopped = services.stop_comfyui(started_state)
            if not stopped.stopped:
                raise LauncherError(
                    "COMFYUI_ROLLBACK_STOP_FAILED",
                    "Rollback 無法停止本次啟動的 ComfyUI。",
                    "請執行 status 並人工確認 managed PID。",
                )
        except Exception as error:
            rollback_errors.append(error)
    if prior_services:
        try:
            services.compose_up_services(prior_services)
        except Exception as error:
            rollback_errors.append(error)
    if rollback_errors:
        raise LauncherError(
            "ROLLBACK_INCOMPLETE",
            "啟動失敗，且部分還原動作未完成。",
            "請執行 status；檢查 Compose 與 data/bootstrap 狀態後再重試。",
        ) from rollback_errors[0]


def _start_application(
    args: argparse.Namespace,
    services: Any,
    current: LauncherState,
    *,
    backend_port: int,
    frontend_port: int,
) -> None:
    snapshot = services.snapshot_configuration()
    started_state: LauncherState | None = None
    started_relay: RelayState | None = None
    prior_relay = services.current_relay_state()
    prior_relay_stopped = False
    compose_attempted = False
    prior_services = services.compose_running_services()
    try:
        active = current
        if current.comfy_mode is ComfyMode.MANAGED:
            active = _start_comfy_with_recovery(args, services, current)
            if active.managed_pid != current.managed_pid:
                if active.comfy_mode is ComfyMode.MANAGED:
                    started_state = active
        settings = _settings(active, backend_port, frontend_port)
        settings, active = _mount_with_recovery(
            args, services, settings, active
        )
        if started_state is not None and active.comfy_mode is ComfyMode.DISABLED:
            stopped_new = services.stop_comfyui(started_state)
            if not stopped_new.stopped:
                raise LauncherError(
                    "COMFYUI_STOP_FAILED",
                    "切換 disabled 時無法停止本次啟動的 ComfyUI。",
                    "ownership 狀態已保留；請執行 status。",
                )
            started_state = None
        relay = services.ensure_relay(settings)
        if relay.started:
            started_relay = relay.state
        changed = (
            active.comfy_mode != current.comfy_mode
            or active.device != current.device
            or active.comfyui_root != current.comfyui_root
            or active.comfyui_port != current.comfyui_port
        )
        if changed:
            services.write_configuration(settings, active)
        elif active.managed_pid != current.managed_pid:
            services.save_state(active)
            services.validate_current_compose()
        else:
            services.validate_current_compose()
        compose_attempted = True
        services.compose_up()
        if not services.wait_backend(backend_port):
            raise LauncherError(
                "BACKEND_NOT_READY",
                "Backend 未能在時限內就緒。",
                "請執行 logs 查看容器診斷。",
            )
        if not services.wait_frontend(frontend_port):
            raise LauncherError(
                "FRONTEND_NOT_READY",
                "Frontend 未能在時限內就緒。",
                "請執行 logs 查看容器診斷。",
            )
        if active.comfy_mode is ComfyMode.DISABLED and prior_relay is not None:
            stopped_prior_relay = services.stop_relay(prior_relay)
            if stopped_prior_relay.stopped:
                prior_relay_stopped = True
            elif stopped_prior_relay.reason not in {
                "process_not_found",
                "process_identity_mismatch",
            }:
                raise LauncherError(
                    "RELAY_STOP_FAILED",
                    "切換 disabled 後無法安全停止舊 relay。",
                    "將回復舊設定；請執行 status。",
                )
        if (
            current.comfy_mode is ComfyMode.MANAGED
            and current.managed_pid is not None
            and current.managed_pid != active.managed_pid
        ):
            stopped_old = services.stop_comfyui(current)
            if not stopped_old.stopped and stopped_old.reason not in {
                "process_not_found",
                "process_identity_mismatch",
                "no_managed_process",
            }:
                raise LauncherError(
                    "COMFYUI_STOP_FAILED",
                    "舊 managed ComfyUI 無法在轉換完成後安全停止。",
                    "已回復舊設定；請執行 status。",
                )
    except Exception:
        _safe_rollback(
            services,
            snapshot=snapshot,
            compose_attempted=compose_attempted,
            prior_services=prior_services,
            started_state=started_state,
            started_relay=started_relay,
            prior_relay=prior_relay,
            prior_relay_stopped=prior_relay_stopped,
        )
        raise


def _configure(args: argparse.Namespace, services: Any, old: LauncherState | None) -> None:
    backend_port, frontend_port = _confirm_selected_ports(
        args,
        services,
        services.select_ports(args.backend_port, args.frontend_port),
    )
    planned = _plan_comfyui(args, services, old)
    snapshot = services.snapshot_configuration()
    prior_services = services.compose_running_services()
    started_state: LauncherState | None = None
    started_relay: RelayState | None = None
    prior_relay = services.current_relay_state()
    prior_relay_stopped = False
    compose_attempted = False
    try:
        active = planned
        if planned.comfy_mode is ComfyMode.MANAGED:
            active = _start_comfy_with_recovery(args, services, planned)
            if (
                active.comfy_mode is ComfyMode.MANAGED
                and (old is None or active.managed_pid != old.managed_pid)
            ):
                started_state = active
        settings = _settings(active, backend_port, frontend_port)
        settings, active = _mount_with_recovery(
            args, services, settings, active
        )
        if started_state is not None and active.comfy_mode is ComfyMode.DISABLED:
            stopped_new = services.stop_comfyui(started_state)
            if not stopped_new.stopped:
                raise LauncherError(
                    "COMFYUI_STOP_FAILED",
                    "切換 disabled 時無法停止本次啟動的 ComfyUI。",
                    "ownership 狀態已保留；請執行 status。",
                )
            started_state = None
        relay = services.ensure_relay(settings)
        if relay.started:
            started_relay = relay.state
        services.write_configuration(settings, active)
        compose_attempted = True
        services.compose_up()
        if not services.wait_backend(backend_port):
            raise LauncherError(
                "BACKEND_NOT_READY",
                "Backend 未能在時限內就緒。",
                "請執行 logs 查看容器診斷。",
            )
        if not services.wait_frontend(frontend_port):
            raise LauncherError(
                "FRONTEND_NOT_READY",
                "Frontend 未能在時限內就緒。",
                "請執行 logs 查看容器診斷。",
            )
        if active.comfy_mode is ComfyMode.DISABLED and prior_relay is not None:
            stopped_prior_relay = services.stop_relay(prior_relay)
            if stopped_prior_relay.stopped:
                prior_relay_stopped = True
            elif stopped_prior_relay.reason not in {
                "process_not_found",
                "process_identity_mismatch",
            }:
                raise LauncherError(
                    "RELAY_STOP_FAILED",
                    "切換 disabled 後無法安全停止舊 relay。",
                    "將回復舊設定；請執行 status。",
                )
        if (
            old is not None
            and old.comfy_mode is ComfyMode.MANAGED
            and old.managed_pid is not None
            and old.managed_pid != active.managed_pid
        ):
            stopped = services.stop_comfyui(old)
            if not stopped.stopped and stopped.reason not in {
                "process_not_found",
                "process_identity_mismatch",
                "no_managed_process",
            }:
                raise LauncherError(
                    "COMFYUI_STOP_FAILED",
                    "舊的 managed ComfyUI 無法安全停止。",
                    "已保留 ownership 狀態；請執行 status。",
                )
        services.emit(f"Frontend: http://127.0.0.1:{frontend_port}")
        services.emit(f"Backend: http://127.0.0.1:{backend_port}")
        services.emit(f"ComfyUI: {active.comfy_mode.value}")
    except Exception:
        _safe_rollback(
            services,
            snapshot=snapshot,
            compose_attempted=compose_attempted,
            prior_services=prior_services,
            started_state=started_state,
            started_relay=started_relay,
            prior_relay=prior_relay,
            prior_relay_stopped=prior_relay_stopped,
        )
        raise


def _run(args: argparse.Namespace, services: Any) -> int:
    services.preflight()
    current = services.load_state()
    command = args.command
    if command is None:
        command = "start" if current is not None else "setup"

    if command == "dry-run":
        planned = current
        if current is None:
            planned = _plan_comfyui(args, services, current, dry_run=True)
            if planned.comfy_mode is ComfyMode.MANAGED:
                services.emit(
                    f"Would install or use ComfyUI at: {planned.comfyui_root}"
                )
        if planned is not None:
            services.emit(f"Would configure ComfyUI mode: {planned.comfy_mode.value}")
        services.emit(
            "Would validate explicit project/data/ComfyUI mount paths and staged Compose config."
        )
        services.emit(
            "Would run Docker Compose with explicit .env, base compose, and local override paths."
        )
        services.emit("Dry run 完成：未寫入設定、未啟動或停止任何服務。")
        return 0
    if command == LauncherCommand.STATUS.value:
        status = services.status(current)
        services.emit(f"Docker: {status['docker']}")
        for service, state in sorted(status["services"].items()):
            services.emit(f"Compose {service}: {state}")
        services.emit(f"Backend: {status['backend']}")
        services.emit(f"Frontend: {status['frontend']}")
        comfy = status["comfy"]
        services.emit(
            f"ComfyUI: {comfy['state']} ({comfy['ownership']}), "
            f"models={comfy['model_count']}"
        )
        services.emit(f"Hint: {comfy['hint']}")
        services.emit(f"Relay: {status['relay']}")
        return 0
    if command == LauncherCommand.LOGS.value:
        services.compose_logs()
        return 0
    if command == LauncherCommand.UPDATE_COMFYUI.value:
        if (
            current is None
            or not current.launcher_installed
            or current.installed_root is None
            or current.device is None
        ):
            raise LauncherError(
                "COMFYUI_UPDATE_NOT_OWNED",
                "只有啟動器自動安裝的 ComfyUI 可以自動更新。",
                "使用者自有或 discovered 路徑請自行更新，啟動器不會修改。",
            )
        services.update_comfyui(current)
        return 0
    if command == LauncherCommand.STOP.value:
        stop_errors: list[LauncherError] = []
        try:
            services.compose_down()
        except docker.DockerError as error:
            stop_errors.append(
                LauncherError(error.code, error.message, error.hint)
            )
        except Exception:
            stop_errors.append(
                LauncherError(
                    "COMPOSE_DOWN_FAILED",
                    "Docker Compose 無法完整停止。",
                    "仍會嘗試安全停止 launcher-owned relay 與 ComfyUI。",
                )
            )
        stopped_relay = services.stop_relay()
        if not stopped_relay.stopped and stopped_relay.reason not in {
            "no_managed_process",
            "process_not_found",
            "process_identity_mismatch",
        }:
            stop_errors.append(
                LauncherError(
                    "RELAY_STOP_FAILED",
                    "launcher-owned Linux relay 無法安全停止。",
                    "relay ownership 已保留；請執行 status。",
                )
            )
        if current is not None and current.comfy_mode is ComfyMode.MANAGED:
            stopped = services.stop_comfyui(current)
            if stopped.stopped or stopped.reason in {
                "process_not_found",
                "process_identity_mismatch",
                "no_managed_process",
            }:
                services.save_state(stopped.state)
            else:
                stop_errors.append(
                    LauncherError(
                        "COMFYUI_STOP_FAILED",
                        "managed ComfyUI 無法安全停止。",
                        "ownership 狀態已保留；請執行 status 檢查程序。",
                    )
                )
        if stop_errors:
            raise stop_errors[0]
        return 0
    if command == LauncherCommand.START.value:
        if current is None:
            raise LauncherError(
                "SETUP_REQUIRED",
                "尚未完成啟動設定。",
                "請先執行 setup。",
                exit_code=2,
            )
        load_ports = getattr(services, "load_ports", None)
        backend_port, frontend_port = (
            load_ports()
            if load_ports is not None
            else (args.backend_port, args.frontend_port)
        )
        if not _valid_port(backend_port) or not _valid_port(frontend_port):
            raise LauncherError(
                "CONFIG_PORT_INVALID",
                "既有設定中的連接埠無效。",
                "連接埠必須是 1 到 65535 的內建整數；請執行 reconfigure。",
            )
        _start_application(
            args,
            services,
            current,
            backend_port=backend_port,
            frontend_port=frontend_port,
        )
        return 0
    if command in {LauncherCommand.SETUP.value, LauncherCommand.RECONFIGURE.value}:
        _configure(args, services, current)
        return 0
    raise LauncherError("UNKNOWN_COMMAND", "未知指令。", "請使用 --help。", exit_code=2)


def _emit_error(services: Any, error: LauncherError) -> None:
    services.emit(f"ERROR [{error.code}] {error.message}")
    services.emit(f"Hint: {error.hint}")


def main(
    argv: Sequence[str] | None = None,
    *,
    services: Any | None = None,
) -> int:
    active_services = services or DefaultServices()
    try:
        args = build_parser().parse_args(argv)
        return _run(args, active_services)
    except LauncherError as error:
        _emit_error(active_services, error)
        return error.exit_code
    except docker.DockerError as error:
        wrapped = LauncherError(error.code, error.message, error.hint)
        _emit_error(active_services, wrapped)
        return wrapped.exit_code
    except ConfigurationError:
        error = LauncherError(
            "CONFIGURATION_FAILED",
            "產生或驗證本機設定失敗，舊設定已保留。",
            "請確認 Docker Compose 設定與目錄權限後重試。",
        )
        _emit_error(active_services, error)
        return error.exit_code
    except Exception:
        error = LauncherError(
            "UNEXPECTED_ERROR",
            "啟動器遇到未預期錯誤；敏感細節已隱藏。",
            "請執行 status，並查看不含密鑰的 bootstrap/Compose logs。",
        )
        _emit_error(active_services, error)
        return error.exit_code
