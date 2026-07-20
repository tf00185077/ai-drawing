from __future__ import annotations

import argparse
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
from .runner import Runner, SubprocessRunner


class LauncherError(RuntimeError):
    def __init__(self, code: str, message: str, hint: str, *, exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code


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
        return result.state

    def stop_comfyui(self, current: LauncherState) -> LauncherState:
        return stop_comfyui(current, self.runner, self.host).state

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

    def compose_running(self) -> bool:
        result = self.runner.run(
            docker.compose_command(
                self.project_root,
                "ps",
                "--services",
                "--filter",
                "status=running",
            ),
            cwd=self.project_root,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def compose_up(self) -> None:
        docker.compose_up(self.project_root, self.runner)

    def compose_down(self) -> None:
        docker.compose_down(self.project_root, self.runner)

    def wait_backend(self, port: int) -> bool:
        return docker.wait_http_ready(f"http://127.0.0.1:{port}/health")

    def wait_frontend(self, port: int) -> bool:
        return docker.wait_http_ready(f"http://127.0.0.1:{port}/")

    def save_state(self, new_state: LauncherState) -> None:
        atomic_write(
            self.project_root / "data/bootstrap/state.json",
            new_state.to_json() + "\n",
        )

    def status(self, current: LauncherState | None) -> dict[str, str]:
        running = self.compose_running()
        return {
            "application": "running" if running else "stopped",
            "comfy_mode": current.comfy_mode.value if current else "not_configured",
        }

    def compose_logs(self) -> None:
        self.runner.run(
            docker.compose_command(self.project_root, "logs", "--tail", "200"),
            cwd=self.project_root,
            capture=False,
        )

    def update_comfyui(self, current: LauncherState) -> None:
        if current.comfyui_root is None or current.device is None:
            raise LauncherError(
                "COMFYUI_NOT_MANAGED",
                "目前沒有可更新的 managed ComfyUI。",
                "請先執行 reconfigure 並選擇由啟動器管理的 ComfyUI。",
            )
        try:
            update_comfyui(
                current.comfyui_root,
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


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="AI Drawing launcher")
    parser.add_argument(
        "command",
        nargs="?",
        choices=[command.value for command in LauncherCommand] + ["dry-run"],
        default=None,
    )
    parser.add_argument("--non-interactive", action="store_true")
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
) -> LauncherState:
    return LauncherState(
        schema_version=STATE_SCHEMA_VERSION,
        comfy_mode=mode,
        comfyui_root=root,
        device=device,
        comfyui_port=port,
        managed_pid=None,
        managed_identity=None,
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
) -> LauncherState:
    try:
        installed = services.install_comfyui(root, device)
    except Exception as first_error:
        if device is not DeviceMode.CPU and not args.non_interactive:
            if services.ask("GPU/MPS 驗證失敗，是否明確改用 CPU？", default=False):
                try:
                    installed = services.install_comfyui(root, DeviceMode.CPU)
                    device = DeviceMode.CPU
                except Exception:
                    installed = None
            else:
                installed = None
        else:
            installed = None
        if installed is None:
            if not args.non_interactive and services.ask(
                "ComfyUI 安裝失敗，是否以停用 ComfyUI 繼續？",
                default=True,
            ):
                return _base_state(ComfyMode.DISABLED, port=args.comfyui_port)
            raise LauncherError(
                "COMFYUI_INSTALL_FAILED",
                "ComfyUI 安裝未完成。",
                "可重新執行 setup，或選擇 --comfyui-mode disabled。",
            ) from first_error
    return _base_state(
        ComfyMode.MANAGED,
        root=installed.root,
        device=device,
        port=args.comfyui_port,
    )


def _plan_comfyui(args: argparse.Namespace, services: Any) -> LauncherState:
    explicit_mode = ComfyMode(args.comfyui_mode) if args.comfyui_mode else None
    if args.non_interactive and explicit_mode is None:
        raise LauncherError(
            "MISSING_DECISION",
            "非互動模式缺少 ComfyUI 決策。",
            "請指定 --comfyui-mode disabled、external 或 managed。",
            exit_code=2,
        )
    if explicit_mode is ComfyMode.DISABLED:
        return _base_state(ComfyMode.DISABLED, port=args.comfyui_port)
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
        )
    if args.non_interactive and explicit_mode is ComfyMode.MANAGED and not args.comfyui_path:
        raise LauncherError(
            "MISSING_COMFYUI_PATH",
            "非互動 managed 模式缺少安裝或既有路徑。",
            "請指定 --comfyui-path。若不安裝，請使用 --comfyui-mode disabled。",
            exit_code=2,
        )

    if explicit_mode is None and not services.ask("是否設定 ComfyUI？", default=False):
        return _base_state(ComfyMode.DISABLED, port=args.comfyui_port)
    if services.probe_external(args.comfyui_port):
        return _base_state(ComfyMode.EXTERNAL, port=args.comfyui_port)

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
        )

    if explicit_mode is None and not services.ask("是否自動安裝 ComfyUI？", default=True):
        return _base_state(ComfyMode.DISABLED, port=args.comfyui_port)
    target = root or services.default_comfyui_root()
    device = DeviceMode(args.device) if args.device else services.detect_device()
    return _install_or_disable(args, services, target, device)


def _safe_rollback(
    services: Any,
    *,
    snapshot: Any | None,
    compose_attempted: bool,
    compose_was_running: bool,
    started_state: LauncherState | None,
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
    if started_state is not None:
        try:
            services.stop_comfyui(started_state)
        except Exception as error:
            rollback_errors.append(error)
    if compose_was_running:
        try:
            services.compose_up()
        except Exception as error:
            rollback_errors.append(error)
    if rollback_errors:
        raise LauncherError(
            "ROLLBACK_INCOMPLETE",
            "啟動失敗，且部分還原動作未完成。",
            "請執行 status；檢查 Compose 與 data/bootstrap 狀態後再重試。",
        ) from rollback_errors[0]


def _start_application(
    services: Any,
    current: LauncherState,
    *,
    backend_port: int,
    frontend_port: int,
) -> None:
    snapshot = services.snapshot_configuration()
    started_state: LauncherState | None = None
    compose_attempted = False
    compose_was_running = services.compose_running()
    try:
        active = current
        if current.comfy_mode is ComfyMode.MANAGED:
            active = services.start_comfyui(current)
            if active.managed_pid != current.managed_pid:
                started_state = active
                services.save_state(active)
        services.mount_probes(_settings(active, backend_port, frontend_port))
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
    except Exception:
        _safe_rollback(
            services,
            snapshot=snapshot,
            compose_attempted=compose_attempted,
            compose_was_running=compose_was_running,
            started_state=started_state,
        )
        raise


def _configure(args: argparse.Namespace, services: Any, old: LauncherState | None) -> None:
    backend_port, frontend_port = services.select_ports(
        args.backend_port,
        args.frontend_port,
    )
    planned = _plan_comfyui(args, services)
    snapshot = services.snapshot_configuration()
    compose_was_running = services.compose_running()
    started_state: LauncherState | None = None
    compose_attempted = False
    try:
        active = planned
        if planned.comfy_mode is ComfyMode.MANAGED:
            active = services.start_comfyui(planned)
            started_state = active
        settings = _settings(active, backend_port, frontend_port)
        services.mount_probes(settings)
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
        if (
            old is not None
            and old.comfy_mode is ComfyMode.MANAGED
            and old.managed_pid is not None
            and old.managed_pid != active.managed_pid
        ):
            services.stop_comfyui(old)
        services.emit(f"Frontend: http://127.0.0.1:{frontend_port}")
        services.emit(f"Backend: http://127.0.0.1:{backend_port}")
        services.emit(f"ComfyUI: {active.comfy_mode.value}")
    except Exception:
        _safe_rollback(
            services,
            snapshot=snapshot,
            compose_attempted=compose_attempted,
            compose_was_running=compose_was_running,
            started_state=started_state,
        )
        raise


def _run(args: argparse.Namespace, services: Any) -> int:
    services.preflight()
    current = services.load_state()
    command = args.command
    if command is None:
        command = "start" if current is not None else "setup"

    if command == "dry-run":
        if current is None:
            _plan_comfyui(args, services)
        services.emit("Dry run 完成：未寫入設定、未啟動或停止任何服務。")
        return 0
    if command == LauncherCommand.STATUS.value:
        status = services.status(current)
        services.emit(f"Application: {status['application']}")
        services.emit(f"ComfyUI: {status['comfy_mode']}")
        return 0
    if command == LauncherCommand.LOGS.value:
        services.compose_logs()
        return 0
    if command == LauncherCommand.UPDATE_COMFYUI.value:
        if current is None or current.comfy_mode is not ComfyMode.MANAGED:
            raise LauncherError(
                "COMFYUI_NOT_MANAGED",
                "目前沒有可更新的 managed ComfyUI。",
                "請先執行 reconfigure。",
            )
        services.update_comfyui(current)
        return 0
    if command == LauncherCommand.STOP.value:
        services.compose_down()
        if current is not None and current.comfy_mode is ComfyMode.MANAGED:
            services.save_state(services.stop_comfyui(current))
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
        _start_application(
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
