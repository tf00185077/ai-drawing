from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from . import docker
from .comfyui import (
    ComfyInstallError,
    InstallTargetInsideProject,
    UnsupportedComfyArchitecture,
    UvBinaryError,
    discover_comfyui,
    install_comfyui,
    probe_comfyui,
    resolve_uv_binary,
    smoke_comfyui_runtime,
    update_comfyui,
    validate_install_target as validate_comfyui_install_target,
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
    UnsupportedNativeArchitecture,
    default_comfyui_root,
    detect_device as detect_device_mode,
    detect_host,
    read_process_identity,
)
from .processes import start_comfyui, stop_comfyui
from .relay import (
    RelayState,
    load_relay_state,
    peek_relay_state,
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
    r"(?i)(authorization|bearer|api[_-]?key|token|password|secret)"
)
_BOOTSTRAP_LOG_LIMIT = 256 * 1024


def _redact_log(value: str) -> str:
    rendered: list[str] = []
    for line in value.splitlines(keepends=True):
        ending = "\n" if line.endswith(("\n", "\r")) else ""
        rendered.append("[REDACTED]" + ending if _LOG_SECRET.search(line) else line)
    return "".join(rendered)


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

    def log_bootstrap(self, message: str) -> None:
        path = self.project_root / "data/logs/bootstrap.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.stat().st_size >= _BOOTSTRAP_LOG_LIMIT:
            rotated = path.with_suffix(".log.1")
            rotated.unlink(missing_ok=True)
            path.replace(rotated)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_redact_log(message.rstrip("\r\n")) + "\n")

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

    def ask_path(self, message: str) -> Path | None:
        answer = self._input(f"{message}: ").strip()
        return Path(answer).expanduser().resolve() if answer else None

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
        try:
            return detect_device_mode(self.host, self.runner)
        except UnsupportedNativeArchitecture as error:
            raise LauncherError(
                UnsupportedNativeArchitecture.code,
                UnsupportedNativeArchitecture.message,
                UnsupportedNativeArchitecture.hint,
                exit_code=2,
            ) from error

    def discover_comfyui(self, candidates: Sequence[Path]):
        safe_candidates = []
        for candidate in candidates:
            try:
                safe_candidates.append(
                    validate_comfyui_install_target(candidate, self.project_root)
                )
            except InstallTargetInsideProject:
                continue
        return discover_comfyui(safe_candidates, self.host)

    def candidate_roots(
        self, explicit: Path | None = None, previous: Path | None = None
    ) -> tuple[Path, ...]:
        home = self.host.home
        common = {
            "Windows": (
                home / "ComfyUI",
                home / "Desktop/ComfyUI",
                home / "Documents/ComfyUI",
            ),
            "Darwin": (home / "ComfyUI", home / "Applications/ComfyUI"),
            "Linux": (
                home / "ComfyUI",
                home / "Applications/ComfyUI",
                home / ".local/share/ComfyUI",
            ),
        }.get(self.host.system, (home / "ComfyUI",))
        ordered = (explicit, previous, self.default_comfyui_root(), *common)
        safe: list[Path] = []
        for path in ordered:
            if path is None:
                continue
            try:
                safe.append(validate_comfyui_install_target(path, self.project_root))
            except InstallTargetInsideProject:
                continue
        return tuple(dict.fromkeys(safe))

    def probe_external(self, port: int) -> bool:
        return probe_comfyui(f"http://127.0.0.1:{port}").running

    def managed_state_is_verified(self, state: LauncherState) -> bool:
        if (
            state.comfy_mode is not ComfyMode.MANAGED
            or state.comfyui_root is None
            or state.managed_pid is None
            or state.managed_identity is None
        ):
            return False
        identity = read_process_identity(self.host, state.managed_pid, self.runner)
        return (
            identity == state.managed_identity
            and self.probe_external(state.comfyui_port)
        )

    def default_comfyui_root(self) -> Path:
        return default_comfyui_root(self.host)

    def validate_install_target(self, root: Path) -> Path:
        try:
            return validate_comfyui_install_target(root, self.project_root)
        except InstallTargetInsideProject as error:
            raise LauncherError(
                "COMFYUI_TARGET_IN_PROJECT",
                "ComfyUI managed 安裝位置不能位於專案目錄內。",
                "請選擇 repository 外的空目錄後重試。",
                exit_code=2,
            ) from error

    def install_comfyui(self, root: Path, device: DeviceMode):
        return install_comfyui(
            root,
            device,
            self.runner,
            self.host,
            project_root=self.project_root,
            uv_bin=resolve_uv_binary(),
        )

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
        try:
            smoke_comfyui_runtime(validation.python, planned.device, self.runner)
        except ComfyInstallError as error:
            raise LauncherError(
                "COMFYUI_DEVICE_SMOKE_FAILED",
                "ComfyUI Python runtime does not support the selected device.",
                "Retry, choose CPU, disable ComfyUI, or stop it before reconfiguring.",
            ) from error
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

    def select_ports_for_running(
        self,
        desired: tuple[int, int],
        configured: tuple[int, int],
        running_services: frozenset[str],
    ) -> tuple[int, int]:
        """Treat this project's verified live ports as owned, not foreign conflicts."""
        owned = frozenset(
            port
            for service, port in zip(("backend", "frontend"), configured, strict=True)
            if service in running_services
        )
        selected: list[int] = []
        for requested in desired:
            if requested in owned and requested not in selected:
                selected.append(requested)
                continue
            chosen = docker.find_available_port(
                requested,
                max_attempts=100,
                probe=lambda host, port: (
                    port not in selected
                    and (port in owned or docker.port_available(host, port))
                ),
            )
            selected.append(chosen)
        return selected[0], selected[1]

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
        base = self.project_root / "docker-compose.yml"
        generated = (
            self.project_root / ".env",
            self.project_root / ".ai-drawing/compose.local.yaml",
        )
        if base.is_file() and not all(path.is_file() for path in generated):
            return frozenset()
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

    @staticmethod
    def query_comfy_model_count(port: int) -> int | None:
        """Query bounded ComfyUI metadata when no local model root is known."""
        try:
            with urlopen(
                f"http://127.0.0.1:{port}/object_info", timeout=1.0
            ) as response:
                payload = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        models: set[str] = set()
        inventory_seen = False
        for node_name in ("CheckpointLoaderSimple", "UNETLoader"):
            node = payload.get(node_name)
            try:
                required = node["input"]["required"]
            except (KeyError, TypeError):
                continue
            if not isinstance(required, dict):
                continue
            for value in required.values():
                if (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], list)
                ):
                    inventory_seen = True
                    models.update(str(item) for item in value[0])
        return len(models) if inventory_seen else None

    def status(
        self,
        current: LauncherState | None,
        *,
        docker_available: bool = True,
    ) -> dict[str, Any]:
        compose_files = (
            self.project_root / "docker-compose.yml",
            self.project_root / ".env",
            self.project_root / ".ai-drawing/compose.local.yaml",
        )
        services = (
            docker.compose_service_states(self.project_root, self.runner)
            if docker_available and all(path.is_file() for path in compose_files)
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
        model_count: int | None = None
        model_state = "unknown"
        hint = "執行 reconfigure 可設定或安裝 ComfyUI。"
        if current is not None and current.comfy_mode is not ComfyMode.DISABLED:
            probe = probe_comfyui(f"http://127.0.0.1:{current.comfyui_port}")
            if current.comfyui_root is not None:
                model_count = self._model_count(current.comfyui_root)
                model_state = "confirmed"
            elif probe.running:
                model_count = self.query_comfy_model_count(current.comfyui_port)
                model_state = "confirmed" if model_count is not None else "unknown"
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
            elif model_count is None:
                comfy_state = "connected"
                hint = "ComfyUI is reachable; model inventory could not be confirmed."
            else:
                comfy_state = "connected"
                hint = "ComfyUI 與模型已就緒。"

        relay_status = "not_required" if self.host.system != "Linux" else "not_running"
        if self.host.system == "Linux":
            relay_file = self.project_root / "data/bootstrap/relay-state.json"
            relay_state = peek_relay_state(self.project_root)
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
            elif relay_file.is_file():
                relay_status = "stale"
        return {
            "docker": "available" if docker_available else "unavailable",
            "services": services,
            "backend": backend,
            "frontend": frontend,
            "comfy": {
                "state": comfy_state,
                "ownership": ownership,
                "model_count": model_count,
                "model_state": model_state,
                "device": (
                    current.device.value
                    if current is not None and current.device is not None
                    else None
                ),
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
        self.emit("--- docker compose logs ---")
        try:
            result = self.runner.run(
                docker.compose_command(self.project_root, "logs", "--tail", "200"),
                cwd=self.project_root,
            )
        except OSError:
            self.emit("Compose logs unavailable (Docker CLI/daemon unavailable).")
            return
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
                uv_bin=resolve_uv_binary(),
            )
        except UnsupportedComfyArchitecture as error:
            raise LauncherError(
                UnsupportedNativeArchitecture.code,
                UnsupportedNativeArchitecture.message,
                UnsupportedNativeArchitecture.hint,
                exit_code=2,
            ) from error
        except UvBinaryError as error:
            raise LauncherError(
                error.code,
                error.message,
                error.hint,
                exit_code=2,
            ) from error
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


class _StorePort(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, values)
        setattr(namespace, f"_{self.dest}_specified", True)


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
    parser.set_defaults(
        _backend_port_specified=False,
        _frontend_port_specified=False,
        _comfyui_port_specified=False,
    )
    parser.add_argument(
        "--backend-port", type=_port_argument, action=_StorePort,
        default=DEFAULT_BACKEND_PORT,
    )
    parser.add_argument(
        "--frontend-port", type=_port_argument, action=_StorePort,
        default=DEFAULT_FRONTEND_PORT,
    )
    parser.add_argument(
        "--comfyui-port", type=_port_argument, action=_StorePort,
        default=DEFAULT_COMFYUI_PORT,
    )
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
    retain_disabled_install = (
        mode is ComfyMode.DISABLED
        and launcher_installed is not False
        and previous is not None
        and previous.launcher_installed
        and previous.comfyui_root is not None
        and previous.installed_root is not None
        and previous.installed_commit is not None
        and previous.device is not None
        and previous.comfyui_root.resolve() == previous.installed_root.resolve()
    )
    state_root = previous.comfyui_root if retain_disabled_install else root
    state_device = previous.device if retain_disabled_install else device
    same_root = (
        previous is not None
        and state_root is not None
        and previous.comfyui_root is not None
        and previous.comfyui_root.resolve() == state_root.resolve()
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
            state_root is not None
            and previous.installed_root.resolve() == state_root.resolve()
        )
    )
    owned_install = preserve_install if launcher_installed is None else launcher_installed
    return LauncherState(
        schema_version=STATE_SCHEMA_VERSION,
        comfy_mode=mode,
        comfyui_root=state_root,
        device=state_device,
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
    except (UnsupportedNativeArchitecture, UnsupportedComfyArchitecture) as error:
        raise LauncherError(
            UnsupportedNativeArchitecture.code,
            UnsupportedNativeArchitecture.message,
            UnsupportedNativeArchitecture.hint,
            exit_code=2,
        ) from error
    except InstallTargetInsideProject as error:
        raise LauncherError(
            "COMFYUI_TARGET_IN_PROJECT",
            "ComfyUI managed 安裝位置不能位於專案目錄內。",
            "請選擇 repository 外的空目錄後重試。",
            exit_code=2,
        ) from error
    except UvBinaryError as error:
        raise LauncherError(
            error.code,
            error.message,
            error.hint,
            exit_code=2,
        ) from error
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
        except UvBinaryError as error:
            raise LauncherError(
                error.code,
                error.message,
                error.hint,
                exit_code=2,
            ) from error
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
    requested_root = args.comfyui_path.resolve() if args.comfyui_path else None
    requested_device = DeviceMode(args.device) if args.device else None
    previous_managed_verified = (
        previous is not None
        and previous.comfy_mode is ComfyMode.MANAGED
        and previous.comfyui_root is not None
        and services.managed_state_is_verified(previous)
    )
    if previous_managed_verified and explicit_mode is not ComfyMode.DISABLED:
        same_runtime = (
            explicit_mode is not ComfyMode.EXTERNAL
            and (requested_root is None or requested_root == previous.comfyui_root.resolve())
            and (requested_device is None or requested_device == previous.device)
            and args.comfyui_port == previous.comfyui_port
        )
        if same_runtime:
            return previous
        raise LauncherError(
            "COMFYUI_RECONFIGURE_REQUIRES_STOP",
            "A verified managed ComfyUI is still running with different settings.",
            "Run stop first, then run reconfigure with the new path, device, or port.",
        )

    discovery_cache: tuple[tuple[Any, ...], tuple[Path, ...]] | None = None

    def bounded_discovery() -> tuple[tuple[Any, ...], tuple[Path, ...]]:
        nonlocal discovery_cache
        if discovery_cache is not None:
            return discovery_cache
        previous_root = previous.comfyui_root if previous is not None else None
        candidate_builder = getattr(services, "candidate_roots", None)
        candidates = (
            candidate_builder(requested_root, previous_root)
            if candidate_builder is not None
            else tuple(
                dict.fromkeys(
                    path.resolve()
                    for path in (
                        requested_root,
                        previous_root,
                        services.default_comfyui_root(),
                    )
                    if path is not None
                )
            )
        )
        discovery_cache = (tuple(services.discover_comfyui(candidates)), candidates)
        return discovery_cache

    if explicit_mode is ComfyMode.DISABLED:
        return _base_state(
            ComfyMode.DISABLED,
            port=args.comfyui_port,
            previous=previous,
        )
    if explicit_mode is ComfyMode.EXTERNAL:
        found, _candidates = bounded_discovery()
        if not services.probe_external(args.comfyui_port):
            raise LauncherError(
                "COMFYUI_UNREACHABLE",
                "指定的 external ComfyUI 尚未就緒。",
                "請先啟動 ComfyUI，確認 /system_stats 可連線，或選擇 disabled。",
            )
        return _base_state(
            ComfyMode.EXTERNAL,
            root=found[0].root if found else None,
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
    root = requested_root
    found, _candidates = bounded_discovery()
    if services.probe_external(args.comfyui_port):
        return _base_state(
            ComfyMode.EXTERNAL,
            root=found[0].root if found else None,
            port=args.comfyui_port,
            previous=previous,
        )
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

    if not args.non_interactive and root is None:
        entered = services.ask_path("輸入其他既有 ComfyUI 路徑（留白跳過）")
        if entered is not None:
            entered_found = services.discover_comfyui((entered.resolve(),))
            if entered_found:
                device = DeviceMode(args.device) if args.device else services.detect_device()
                return _base_state(
                    ComfyMode.MANAGED,
                    root=entered_found[0].root,
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
    default_target = services.default_comfyui_root().resolve()
    target = root
    if target is None and not args.non_interactive and not dry_run:
        target = services.ask_path(
            f"ComfyUI 安裝位置（留白使用預設 {default_target}）"
        )
    target = target or default_target
    target_validator = getattr(services, "validate_install_target", None)
    if target_validator is not None:
        target = target_validator(target)
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
    desired: tuple[int, int],
    selected: tuple[int, int],
) -> tuple[int, int]:
    backend_port, frontend_port = selected
    if not _valid_port(backend_port) or not _valid_port(frontend_port):
        raise LauncherError(
            "CONFIG_PORT_INVALID",
            "選擇的連接埠無效。",
            "連接埠必須是 1 到 65535 的內建整數。",
        )
    alternate = selected != desired
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


def _prepare_configuration(
    args: argparse.Namespace,
    services: Any,
    old: LauncherState | None,
) -> tuple[frozenset[str], int, int, LauncherState]:
    if old is not None and not args._comfyui_port_specified:
        args.comfyui_port = old.comfyui_port
    prior_services = services.compose_running_services()
    project_running = old is not None and bool(prior_services)
    if project_running:
        configured_backend, configured_frontend = services.load_ports()
        desired = (
            args.backend_port
            if args._backend_port_specified
            else configured_backend,
            args.frontend_port
            if args._frontend_port_specified
            else configured_frontend,
        )
    else:
        desired = (args.backend_port, args.frontend_port)
    if not all(_valid_port(port) for port in desired):
        raise LauncherError(
            "CONFIG_PORT_INVALID",
            "Configured project ports are invalid.",
            "Choose ports from 1 to 65535 and run reconfigure.",
        )
    if project_running:
        selector = getattr(services, "select_ports_for_running", None)
        selected = (
            selector(
                desired,
                (configured_backend, configured_frontend),
                prior_services,
            )
            if selector is not None
            else desired
        )
    else:
        selected = services.select_ports(*desired)
    backend_port, frontend_port = _confirm_selected_ports(
        args, services, desired, selected
    )
    planned = _plan_comfyui(args, services, old)
    return prior_services, backend_port, frontend_port, planned


def _begin_bootstrap_audit(
    args: argparse.Namespace,
    services: Any,
    command: str,
) -> None:
    if getattr(args, "_audit_started", False):
        return
    args._audit_started = True
    _try_bootstrap_log(services, f"command={command} begin")


def _configure(args: argparse.Namespace, services: Any, old: LauncherState | None) -> None:
    command = getattr(args, "_resolved_command", args.command or "setup")
    try:
        prior_services, backend_port, frontend_port, planned = _prepare_configuration(
            args,
            services,
            old,
        )
    except LauncherError as error:
        if error.code != "COMFYUI_RECONFIGURE_REQUIRES_STOP":
            _begin_bootstrap_audit(args, services, command)
        raise
    except Exception:
        _begin_bootstrap_audit(args, services, command)
        raise
    _begin_bootstrap_audit(args, services, command)
    snapshot = services.snapshot_configuration()
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
    current = services.load_state()
    command = args.command
    if command is None:
        command = "start" if current is not None else "setup"
    args._resolved_command = command
    deferred_audit = command in {
        LauncherCommand.SETUP.value,
        LauncherCommand.RECONFIGURE.value,
    }
    if command not in {"status", "logs", "dry-run"} and not deferred_audit:
        _begin_bootstrap_audit(args, services, command)

    docker_available = True
    if command in {
        LauncherCommand.SETUP.value,
        LauncherCommand.START.value,
        LauncherCommand.RECONFIGURE.value,
    }:
        try:
            services.preflight()
        except Exception:
            if deferred_audit:
                _begin_bootstrap_audit(args, services, command)
            raise
    elif command in {LauncherCommand.STATUS.value, "dry-run"}:
        try:
            services.preflight()
        except (docker.DockerError, LauncherError):
            docker_available = False

    if command == "dry-run":
        if not docker_available:
            services.emit("Docker preflight: unavailable (plan continues read-only).")
        reconfiguration_requested = any(
            (
                args.comfyui_mode is not None,
                args.comfyui_path is not None,
                args.device is not None,
                args._comfyui_port_specified,
            )
        )
        if current is not None and not args._comfyui_port_specified:
            args.comfyui_port = current.comfyui_port
        planned = current
        if current is None or reconfiguration_requested:
            planned = _plan_comfyui(args, services, current, dry_run=True)
            if planned.comfy_mode is ComfyMode.MANAGED:
                services.emit(
                    f"Would install or use ComfyUI at: {planned.comfyui_root}"
                )
        if planned is not None:
            services.emit(f"Would configure ComfyUI mode: {planned.comfy_mode.value}")
            services.emit(f"Would use ComfyUI port: {planned.comfyui_port}")
            if planned.device is not None:
                services.emit(f"Would use ComfyUI device: {planned.device.value}")
        configured_ports = (
            services.load_ports()
            if current is not None
            else (DEFAULT_BACKEND_PORT, DEFAULT_FRONTEND_PORT)
        )
        planned_backend = (
            args.backend_port
            if args._backend_port_specified
            else configured_ports[0]
        )
        planned_frontend = (
            args.frontend_port
            if args._frontend_port_specified
            else configured_ports[1]
        )
        services.emit(
            f"Would use project ports: backend={planned_backend}, "
            f"frontend={planned_frontend}"
        )
        services.emit(
            "Would validate explicit project/data/ComfyUI mount paths and staged Compose config."
        )
        services.emit(
            "Would run Docker Compose with explicit .env, base compose, and local override paths."
        )
        services.emit("Dry run 完成：未寫入設定、未啟動或停止任何服務。")
        return 0
    if command == LauncherCommand.STATUS.value:
        status = services.status(current, docker_available=docker_available)
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
        if comfy.get("device") is not None:
            services.emit(f"ComfyUI device: {comfy['device']}")
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


def _try_bootstrap_log(services: Any, message: str) -> None:
    """Write an audit event without ever changing launcher behaviour."""
    logger = getattr(services, "log_bootstrap", None)
    if logger is None:
        return
    try:
        logger(message)
    except Exception:
        pass


def _should_write_audit(args: argparse.Namespace | None, mutating: bool) -> bool:
    return mutating and (args is None or getattr(args, "_audit_started", False))


def main(
    argv: Sequence[str] | None = None,
    *,
    services: Any | None = None,
) -> int:
    active_services = services or DefaultServices()
    command = "setup"
    mutating = True
    args: argparse.Namespace | None = None
    try:
        args = build_parser().parse_args(argv)
        command = args.command or "setup"
        mutating = command not in {"status", "logs", "dry-run"}
        result = _run(args, active_services)
        command = getattr(args, "_resolved_command", command)
        mutating = command not in {"status", "logs", "dry-run"}
        if _should_write_audit(args, mutating):
            _try_bootstrap_log(active_services, f"command={command} complete")
        return result
    except LauncherError as error:
        command = getattr(args, "_resolved_command", command)
        mutating = command not in {"status", "logs", "dry-run"}
        if _should_write_audit(args, mutating):
            _try_bootstrap_log(
                active_services, f"command={command} error code={error.code}"
            )
        _emit_error(active_services, error)
        return error.exit_code
    except docker.DockerError as error:
        wrapped = LauncherError(error.code, error.message, error.hint)
        command = getattr(args, "_resolved_command", command)
        mutating = command not in {"status", "logs", "dry-run"}
        if _should_write_audit(args, mutating):
            _try_bootstrap_log(
                active_services, f"command={command} error code={wrapped.code}"
            )
        _emit_error(active_services, wrapped)
        return wrapped.exit_code
    except ConfigurationError:
        error = LauncherError(
            "CONFIGURATION_FAILED",
            "產生或驗證本機設定失敗，舊設定已保留。",
            "請確認 Docker Compose 設定與目錄權限後重試。",
        )
        command = getattr(args, "_resolved_command", command)
        mutating = command not in {"status", "logs", "dry-run"}
        if _should_write_audit(args, mutating):
            _try_bootstrap_log(
                active_services, f"command={command} error code={error.code}"
            )
        _emit_error(active_services, error)
        return error.exit_code
    except Exception:
        error = LauncherError(
            "UNEXPECTED_ERROR",
            "啟動器遇到未預期錯誤；敏感細節已隱藏。",
            "請執行 status，並查看不含密鑰的 bootstrap/Compose logs。",
        )
        command = getattr(args, "_resolved_command", command)
        mutating = command not in {"status", "logs", "dry-run"}
        if _should_write_audit(args, mutating):
            _try_bootstrap_log(
                active_services, f"command={command} error code={error.code}"
            )
        _emit_error(active_services, error)
        return error.exit_code
