from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from launcher.models import HostInfo, ProcessIdentity
from launcher.relay import (
    RelayAddressError,
    RelayStartResult,
    RelayStateLockError,
    RelayStateLockTimeout,
    RelayState,
    RelayStopResult,
    build_relay_command,
    clear_relay_state,
    forward_connection,
    relay_log_path,
    relay_invalid_state_path,
    relay_lock_path,
    relay_state_path,
    load_relay_state,
    peek_relay_state,
    run_relay,
    save_relay_state,
    start_relay,
    stop_relay,
    relay_state_lock,
    validate_relay_bind,
)
from launcher.runner import CommandResult


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",
        "127.0.0.1",
        "224.0.0.1",
        "8.8.8.8",
        "169.254.1.1",
        "192.0.2.10",
        "::1",
        "not-an-address",
    ],
)
def test_relay_rejects_non_private_docker_bridge_addresses(address):
    with pytest.raises(RelayAddressError):
        validate_relay_bind(address)


@pytest.mark.parametrize("address", ["10.0.0.1", "172.17.0.1", "192.168.65.1"])
def test_relay_accepts_rfc1918_docker_bridge_addresses(address):
    assert validate_relay_bind(address) == address


def test_relay_command_uses_argument_list_and_loopback_target(tmp_path):
    command = build_relay_command(
        project_root=tmp_path,
        python=tmp_path / ".runtime" / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
    )

    assert command == [
        str(tmp_path / ".runtime" / "python"),
        str(tmp_path / "scripts" / "comfyui_relay.py"),
        "--bind-host",
        "172.17.0.1",
        "--bind-port",
        "18188",
        "--target-host",
        "127.0.0.1",
        "--target-port",
        "8188",
    ]


def test_relay_uses_separate_state_and_log_files(tmp_path):
    assert relay_state_path(tmp_path) == tmp_path / "data/bootstrap/relay-state.json"
    assert relay_log_path(tmp_path) == tmp_path / "data/logs/comfyui-relay.log"
    assert relay_state_path(tmp_path).name != "state.json"
    assert relay_log_path(tmp_path).name != "comfyui.log"


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "[]",
        '{"bind_host":"172.17.0.1"}',
        (
            '{"bind_host":"172.17.0.1","bind_port":18188,'
            '"target_port":8188,"managed_pid":"7331",'
            '"managed_identity":"python relay.py"}'
        ),
        (
            '{"bind_host":"8.8.8.8","bind_port":18188,'
            '"target_port":8188,"managed_pid":7331,'
            '"managed_identity":{'
            '"executable":"python","started_at":"1",'
            '"command_line":"python relay.py"}}'
        ),
    ],
)
def test_malformed_relay_state_is_quarantined_and_degrades_to_none(tmp_path, raw):
    path = relay_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(raw, encoding="utf-8")

    assert load_relay_state(tmp_path) is None
    assert path.exists() is False
    assert relay_invalid_state_path(tmp_path).read_text(encoding="utf-8") == raw


def test_non_utf8_relay_state_is_quarantined_without_exception(tmp_path):
    path = relay_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfeinvalid")

    assert load_relay_state(tmp_path) is None
    assert path.exists() is False
    assert relay_invalid_state_path(tmp_path).read_bytes() == b"\xff\xfeinvalid"


def test_peek_invalid_relay_state_is_strictly_read_only(tmp_path):
    path = relay_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    original = b"\xff\xfeinvalid"
    path.write_bytes(original)
    before = path.stat().st_mtime_ns

    assert peek_relay_state(tmp_path) is None

    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == before
    assert not relay_invalid_state_path(tmp_path).exists()
    assert not relay_lock_path(tmp_path).exists()


def test_invalid_bind_is_rejected_before_asyncio_server_starts():
    called = False

    async def fake_start_server(*_args, **_kwargs):
        nonlocal called
        called = True

    with pytest.raises(RelayAddressError):
        asyncio.run(
            run_relay(
                "0.0.0.0",
                18188,
                "127.0.0.1",
                8188,
                start_server=fake_start_server,
            )
        )

    assert called is False


def test_relay_starts_only_on_validated_bind_and_loopback_target():
    captured: dict[str, object] = {}

    class FakeServer:
        async def __aenter__(self):
            captured["entered"] = True
            return self

        async def __aexit__(self, *_args):
            return None

        async def serve_forever(self):
            captured["served"] = True

    async def fake_start_server(handler, host, port):
        captured.update(handler=handler, host=host, port=port)
        return FakeServer()

    asyncio.run(
        run_relay(
            "172.17.0.1",
            18188,
            "127.0.0.1",
            8188,
            start_server=fake_start_server,
        )
    )

    assert captured["host"] == "172.17.0.1"
    assert captured["port"] == 18188
    assert captured["entered"] is True
    assert captured["served"] is True


def test_relay_refuses_non_loopback_target():
    with pytest.raises(RelayAddressError, match="target"):
        asyncio.run(
            run_relay(
                "172.17.0.1",
                18188,
                "192.168.1.20",
                8188,
            )
        )


def test_relay_forwards_bytes_in_both_directions():
    async def scenario():
        async def echo(reader, writer):
            data = await reader.readexactly(5)
            writer.write(data.upper())
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        target = await asyncio.start_server(echo, "127.0.0.1", 0)
        target_port = target.sockets[0].getsockname()[1]
        proxy = await asyncio.start_server(
            lambda reader, writer: forward_connection(
                reader,
                writer,
                target_host="127.0.0.1",
                target_port=target_port,
            ),
            "127.0.0.1",
            0,
        )
        proxy_port = proxy.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
            writer.write(b"hello")
            await writer.drain()
            assert await asyncio.wait_for(reader.readexactly(5), timeout=1) == b"HELLO"
            writer.close()
            await writer.wait_closed()
        finally:
            proxy.close()
            target.close()
            await proxy.wait_closed()
            await target.wait_closed()

    asyncio.run(scenario())


def test_target_eof_cancels_client_pump_and_finishes_handler():
    async def scenario():
        completed = asyncio.Event()

        async def target_once(reader, writer):
            await reader.readexactly(1)
            writer.close()
            await writer.wait_closed()

        target = await asyncio.start_server(target_once, "127.0.0.1", 0)
        target_port = target.sockets[0].getsockname()[1]

        async def proxy_handler(reader, writer):
            try:
                await forward_connection(
                    reader,
                    writer,
                    target_host="127.0.0.1",
                    target_port=target_port,
                )
            finally:
                completed.set()

        proxy = await asyncio.start_server(proxy_handler, "127.0.0.1", 0)
        proxy_port = proxy.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        try:
            writer.write(b"x")
            await writer.drain()
            await asyncio.wait_for(completed.wait(), timeout=0.5)
            assert await asyncio.wait_for(reader.read(), timeout=0.5) == b""
        finally:
            writer.close()
            await writer.wait_closed()
            proxy.close()
            target.close()
            await proxy.wait_closed()
            await target.wait_closed()

    asyncio.run(scenario())


def test_relay_lifecycle_is_linux_only(tmp_path):
    host = HostInfo("Windows", "AMD64", Path("C:/Users/test"))
    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=host,
        runner=object(),
        popen=lambda *_args, **_kwargs: pytest.fail("must not spawn"),
    )

    assert result.started is False
    assert result.reason == "unsupported_platform"
    assert result.state is None


class FakeRelayProcess:
    pid = 7331

    def __init__(self, mode: str = "terminated"):
        self.mode = mode
        self.returncode = None
        self.cleanup_calls: list[object] = []
        self.wait_count = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.cleanup_calls.append("terminate")
        if self.mode == "failed":
            raise OSError("terminate failed")

    def wait(self, timeout):
        self.cleanup_calls.append(("wait", timeout))
        self.wait_count += 1
        if self.mode == "killed" and self.wait_count == 1:
            raise subprocess.TimeoutExpired("fake-relay", timeout)
        if self.mode == "failed":
            raise subprocess.TimeoutExpired("fake-relay", timeout)
        self.returncode = 0
        return 0

    def kill(self):
        self.cleanup_calls.append("kill")
        if self.mode == "failed":
            raise OSError("kill failed")


class FakeRelayPopen:
    def __init__(self, process: FakeRelayProcess | None = None):
        self.calls: list[tuple[list[str], dict[str, object]]] = []
        self.process = process or FakeRelayProcess()

    def __call__(self, args, **kwargs):
        self.calls.append(([str(arg) for arg in args], kwargs))
        return self.process


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, duration: float) -> None:
        self.sleeps.append(duration)
        self.now += duration


class FakeRelayRunner:
    def __init__(self, identity: ProcessIdentity | None):
        self.identity = identity
        self.commands: list[list[str]] = []

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append(command)
        if command[0] not in {"kill", "taskkill"}:
            return CommandResult(
                args=tuple(command),
                returncode=0 if self.identity else 1,
                stdout=json.dumps(asdict(self.identity)) + "\n" if self.identity else "",
                stderr="",
            )
        return CommandResult(tuple(command), 0, "", "")


class SequencedRelayRunner(FakeRelayRunner):
    def __init__(self, identities: list[ProcessIdentity | None]):
        super().__init__(None)
        self.identities = iter(identities)

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append(command)
        if command[0] not in {"kill", "taskkill"}:
            identity = next(self.identities)
            return CommandResult(
                tuple(command),
                0 if identity else 1,
                json.dumps(asdict(identity)) + "\n" if identity else "",
                "",
            )
        return CommandResult(tuple(command), 0, "", "")


def _identity(
    command_line: str = "python scripts/comfyui_relay.py",
    *,
    executable: str = "/usr/bin/python",
    started_at: str = "123456",
) -> ProcessIdentity:
    return ProcessIdentity(executable, started_at, command_line)


def test_ready_relay_records_separate_owned_state(tmp_path):
    popen = FakeRelayPopen()
    identity = _identity(
        "python scripts/comfyui_relay.py --bind-host 172.17.0.1"
    )
    runner = FakeRelayRunner(identity)
    probes: list[tuple[str, int]] = []

    def probe(host: str, port: int, timeout: float):
        probes.append((host, port))
        return len(probes) == 2

    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=popen,
        probe=probe,
        sleep=lambda _: None,
        readiness_timeout=1,
        poll_interval=0.1,
        bind_probe=lambda *_args: True,
    )

    assert result.started is True
    assert result.reason == "ready"
    assert result.state == RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=identity,
    )
    args, options = popen.calls[0]
    assert args[1] == str(tmp_path / "scripts/comfyui_relay.py")
    assert options["start_new_session"] is True
    assert RelayState.from_json(relay_state_path(tmp_path).read_text("utf-8")) == result.state


def test_relay_timeout_does_not_record_state_and_terminates_child(tmp_path):
    runner = FakeRelayRunner(_identity())
    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=FakeRelayPopen(),
        probe=lambda *_args, **_kwargs: False,
        sleep=lambda _: None,
        readiness_timeout=0.2,
        poll_interval=0.1,
        bind_probe=lambda *_args: True,
    )

    assert result.started is False
    assert result.reason == "readiness_timeout"
    assert result.state is None
    assert len(runner.commands) == 3
    assert runner.commands[-1] == ["kill", "-TERM", "-7331"]
    assert relay_state_path(tmp_path).exists() is False


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (RelayStateLockTimeout("busy"), "state_lock_timeout"),
        (RelayStateLockError("broken"), "state_lock_error"),
        (OSError("disk"), "state_write_failed"),
    ],
)
def test_ready_relay_persistence_failure_cleans_owned_process(
    tmp_path,
    monkeypatch,
    error,
    reason,
):
    identity = _identity()
    runner = FakeRelayRunner(identity)

    def fail_save(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("launcher.relay.save_relay_state", fail_save)

    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=FakeRelayPopen(),
        probe=lambda *_args: True,
        bind_probe=lambda *_args: True,
    )

    assert result == RelayStartResult(False, reason, None)
    assert runner.commands[-1] == ["kill", "-TERM", "-7331"]


def test_ready_relay_lock_failure_does_not_kill_replaced_process(
    tmp_path,
    monkeypatch,
):
    identity = _identity()
    replacement = _identity(started_at="replacement")
    runner = SequencedRelayRunner([identity, identity, replacement])

    def fail_save(*_args, **_kwargs):
        raise RelayStateLockTimeout("busy")

    monkeypatch.setattr("launcher.relay.save_relay_state", fail_save)

    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=FakeRelayPopen(),
        probe=lambda *_args: True,
        bind_probe=lambda *_args: True,
    )

    assert result == RelayStartResult(
        False,
        "state_lock_timeout_cleanup_identity_mismatch",
        None,
    )
    assert all(command[0] != "kill" for command in runner.commands)


def test_relay_pid_identity_mismatch_is_not_terminated(tmp_path):
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=_identity(),
    )
    runner = FakeRelayRunner(_identity("unrelated --server"))
    save_relay_state(tmp_path, state)

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert len(runner.commands) == 1
    assert result.state is None
    assert relay_state_path(tmp_path).exists() is False


def test_relay_stop_terminates_only_exact_identity_and_clears_state(tmp_path):
    identity = _identity()
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=identity,
    )
    save_relay_state(tmp_path, state)
    runner = FakeRelayRunner(identity)

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is True
    assert result.reason == "stopped"
    assert runner.commands[-1] == ["kill", "-TERM", "-7331"]
    assert relay_state_path(tmp_path).exists() is False


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (RelayStateLockTimeout("busy"), "state_lock_timeout"),
        (RelayStateLockError("broken"), "state_lock_error"),
    ],
)
def test_stop_translates_load_or_quarantine_lock_failure_before_signal(
    tmp_path,
    monkeypatch,
    error,
    reason,
):
    runner = FakeRelayRunner(_identity())

    def fail_load(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("launcher.relay.load_relay_state", fail_load)

    result = stop_relay(
        None,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result == RelayStopResult(False, reason, None)
    assert runner.commands == []


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (RelayStateLockTimeout("busy"), "stopped_state_lock_timeout"),
        (RelayStateLockError("broken"), "stopped_state_lock_error"),
    ],
)
def test_stop_retains_state_when_clear_lock_fails_after_termination(
    tmp_path,
    monkeypatch,
    error,
    reason,
):
    identity = _identity()
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=identity,
    )
    runner = FakeRelayRunner(identity)
    calls = 0

    def fail_clear(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise error

    monkeypatch.setattr("launcher.relay.clear_relay_state", fail_clear)

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result == RelayStopResult(True, reason, state)
    assert runner.commands[-1] == ["kill", "-TERM", "-7331"]
    assert calls == 1


def test_relay_stop_rechecks_identity_immediately_before_signal(tmp_path):
    identity = _identity()
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=identity,
    )
    save_relay_state(tmp_path, state)
    runner = SequencedRelayRunner([identity, _identity("unrelated --server")])

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert all(command[0] != "kill" for command in runner.commands)
    assert relay_state_path(tmp_path).exists() is False


def test_stopping_old_relay_does_not_delete_atomically_replaced_new_state(
    tmp_path,
    monkeypatch,
):
    old = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=_identity(started_at="old"),
    )
    new = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=8442,
        managed_identity=_identity(started_at="new"),
    )
    save_relay_state(tmp_path, old)

    def replace_during_termination(*_args, **_kwargs):
        save_relay_state(tmp_path, new)
        return "terminated"

    monkeypatch.setattr(
        "launcher.relay.terminate_if_identity_matches",
        replace_during_termination,
    )

    result = stop_relay(
        old,
        FakeRelayRunner(old.managed_identity),
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is True
    assert load_relay_state(tmp_path) == new


def test_compare_delete_serializes_writer_after_comparison_before_unlink(
    tmp_path,
    monkeypatch,
):
    old = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=_identity(started_at="old"),
    )
    new = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=8442,
        managed_identity=_identity(started_at="new"),
    )
    save_relay_state(tmp_path, old)
    state_path = relay_state_path(tmp_path)
    comparison_reached = threading.Event()
    writer_attempted = threading.Event()
    writer_done = threading.Event()
    original_unlink = Path.unlink

    def controlled_unlink(path, *args, **kwargs):
        if path == state_path:
            comparison_reached.set()
            assert writer_attempted.wait(timeout=1)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", controlled_unlink)

    def writer():
        assert comparison_reached.wait(timeout=1)
        writer_attempted.set()
        save_relay_state(tmp_path, new)
        writer_done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    assert clear_relay_state(tmp_path, old) is True
    thread.join(timeout=1)

    assert writer_done.is_set()
    assert load_relay_state(tmp_path) == new


def test_malformed_quarantine_serializes_writer_and_load_retries_new_state(
    tmp_path,
    monkeypatch,
):
    raw = b"not-json"
    new = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=8442,
        managed_identity=_identity(started_at="new"),
    )
    state_path = relay_state_path(tmp_path)
    state_path.parent.mkdir(parents=True)
    state_path.write_bytes(raw)
    comparison_reached = threading.Event()
    writer_attempted = threading.Event()
    writer_done = threading.Event()
    original_unlink = Path.unlink

    def controlled_unlink(path, *args, **kwargs):
        if path == state_path:
            comparison_reached.set()
            assert writer_attempted.wait(timeout=1)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", controlled_unlink)

    def writer():
        assert comparison_reached.wait(timeout=1)
        writer_attempted.set()
        save_relay_state(tmp_path, new)
        writer_done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    loaded = load_relay_state(tmp_path, replacement_timeout=0.5)
    thread.join(timeout=1)

    assert writer_done.is_set()
    assert loaded == new
    assert relay_state_path(tmp_path).is_file()
    assert relay_invalid_state_path(tmp_path).read_bytes() == raw


def test_relay_state_lock_is_interprocess_bounded_and_stale_file_is_harmless(
    tmp_path,
    project_root,
):
    code = (
        "import sys; "
        "sys.path.insert(0, 'scripts'); "
        "from pathlib import Path; "
        "from launcher.relay import relay_state_lock, RelayStateLockTimeout; "
        "root=Path(sys.argv[1]); "
        "\ntry:\n"
        "  with relay_state_lock(root, timeout=0.1): pass\n"
        "except RelayStateLockTimeout:\n"
        "  print('timeout')\n"
        "else:\n"
        "  print('acquired')\n"
    )

    with relay_state_lock(tmp_path, timeout=1):
        result = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

    assert result.stdout.strip() == "timeout"
    assert relay_lock_path(tmp_path).is_file()
    with relay_state_lock(tmp_path, timeout=0.1):
        pass


def test_relay_state_lock_is_same_thread_reentrant(tmp_path):
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=_identity(),
    )

    with relay_state_lock(tmp_path, timeout=0.5):
        save_relay_state(tmp_path, state, lock_timeout=0.5)
        assert load_relay_state(tmp_path, lock_timeout=0.5) == state


def test_unlock_error_releases_process_local_lock_for_other_threads(
    tmp_path,
    monkeypatch,
):
    import launcher.relay as relay_module

    original_release = relay_module._release_os_lock

    def fail_release(_handle):
        raise RelayStateLockError("injected unlock failure")

    monkeypatch.setattr(relay_module, "_release_os_lock", fail_release)
    with pytest.raises(RelayStateLockError, match="injected"):
        with relay_state_lock(tmp_path, timeout=0.2):
            pass
    monkeypatch.setattr(relay_module, "_release_os_lock", original_release)

    acquired = threading.Event()

    def acquire_after_error():
        with relay_state_lock(tmp_path, timeout=0.2):
            acquired.set()

    thread = threading.Thread(target=acquire_after_error)
    thread.start()
    thread.join(timeout=1)

    assert acquired.is_set()


@pytest.mark.parametrize("timeout", [0, -1])
def test_relay_state_lock_rejects_unbounded_timeout_values(tmp_path, timeout):
    with pytest.raises(ValueError, match="positive"):
        with relay_state_lock(tmp_path, timeout=timeout):
            pass


def test_stop_does_not_delete_or_raise_for_non_utf8_replacement(tmp_path):
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=_identity(),
    )
    path = relay_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xffnew-owner")

    result = stop_relay(
        state,
        FakeRelayRunner(state.managed_identity),
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is True
    assert path.read_bytes() == b"\xffnew-owner"


@pytest.mark.parametrize(
    "replacement",
    [
        _identity(started_at="654321"),
        _identity(executable="/different/python"),
    ],
)
def test_relay_identical_command_line_different_instance_is_not_terminated(
    tmp_path,
    replacement,
):
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=_identity(),
    )
    save_relay_state(tmp_path, state)
    runner = FakeRelayRunner(replacement)

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert len(runner.commands) == 1


def test_relay_initial_identity_failure_terminates_exact_handle_without_state(tmp_path):
    probes: list[tuple[str, int]] = []
    runner = FakeRelayRunner(None)
    process = FakeRelayProcess("terminated")

    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=FakeRelayPopen(process),
        probe=lambda host, port, _timeout: probes.append((host, port)) or True,
        bind_probe=lambda *_args: True,
    )

    assert result.started is False
    assert result.reason == "initial_identity_unavailable_cleanup_terminated"
    assert result.state is None
    assert result.pid == 7331
    assert probes == []
    assert len(runner.commands) == 1
    assert process.cleanup_calls == ["terminate", ("wait", 2.0)]
    assert relay_state_path(tmp_path).exists() is False


@pytest.mark.parametrize(
    ("mode", "reason", "calls"),
    [
        (
            "killed",
            "initial_identity_unavailable_cleanup_killed",
            ["terminate", ("wait", 2.0), "kill", ("wait", 2.0)],
        ),
        (
            "failed",
            "initial_identity_unavailable_cleanup_failed",
            ["terminate", "kill"],
        ),
    ],
)
def test_relay_initial_identity_cleanup_outcome_is_structured_and_never_saved(
    tmp_path,
    mode,
    reason,
    calls,
):
    process = FakeRelayProcess(mode)
    runner = FakeRelayRunner(None)

    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=FakeRelayPopen(process),
        probe=lambda *_args: True,
        bind_probe=lambda *_args: True,
    )

    assert result == RelayStartResult(False, reason, None, 7331)
    assert process.cleanup_calls == calls
    assert relay_state_path(tmp_path).exists() is False
    assert all(command[0] not in {"kill", "taskkill"} for command in runner.commands)


def test_relay_readiness_uses_real_monotonic_deadline(tmp_path):
    clock = FakeClock()
    probe_timeouts: list[float] = []
    runner = FakeRelayRunner(_identity())

    def probe(_host: str, _port: int, timeout: float):
        probe_timeouts.append(timeout)
        if len(probe_timeouts) == 2:
            clock.now += timeout
            return True
        return False

    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=runner,
        popen=FakeRelayPopen(),
        probe=probe,
        bind_probe=lambda *_args: True,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        readiness_timeout=1.5,
        poll_interval=0.75,
    )

    assert result.started is False
    assert result.reason == "readiness_timeout"
    assert result.state is None
    assert probe_timeouts == [1.0, 0.75]
    assert clock.sleeps == [0.75]
    assert clock.now == 1.5
    assert relay_state_path(tmp_path).exists() is False


def test_relay_rejects_private_address_not_bound_on_local_host(tmp_path):
    result = start_relay(
        project_root=tmp_path,
        python=tmp_path / "python",
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        host=HostInfo("Linux", "x86_64", Path("/home/test")),
        runner=FakeRelayRunner(None),
        popen=lambda *_args, **_kwargs: pytest.fail("must not spawn"),
        bind_probe=lambda host, port: False,
    )

    assert result.started is False
    assert result.reason == "bind_not_local"
    assert result.state is None
