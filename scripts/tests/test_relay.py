from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from launcher.models import HostInfo
from launcher.relay import (
    RelayAddressError,
    RelayState,
    build_relay_command,
    forward_connection,
    relay_log_path,
    relay_state_path,
    run_relay,
    save_relay_state,
    start_relay,
    stop_relay,
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

    def poll(self):
        return None


class FakeRelayPopen:
    def __init__(self):
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(([str(arg) for arg in args], kwargs))
        return FakeRelayProcess()


class FakeRelayRunner:
    def __init__(self, identity: str | None):
        self.identity = identity
        self.commands: list[list[str]] = []

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append(command)
        if command[0] == "ps":
            return CommandResult(
                args=tuple(command),
                returncode=0 if self.identity else 1,
                stdout=f"{self.identity}\n" if self.identity else "",
                stderr="",
            )
        return CommandResult(tuple(command), 0, "", "")


class SequencedRelayRunner(FakeRelayRunner):
    def __init__(self, identities: list[str | None]):
        super().__init__(None)
        self.identities = iter(identities)

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append(command)
        if command[0] == "ps":
            identity = next(self.identities)
            return CommandResult(
                tuple(command),
                0 if identity else 1,
                f"{identity}\n" if identity else "",
                "",
            )
        return CommandResult(tuple(command), 0, "", "")


def test_ready_relay_records_separate_owned_state(tmp_path):
    popen = FakeRelayPopen()
    identity = "python scripts/comfyui_relay.py --bind-host 172.17.0.1"
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
    runner = FakeRelayRunner("python scripts/comfyui_relay.py")
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
    assert runner.commands == [
        ["ps", "-p", "7331", "-o", "command="],
        ["ps", "-p", "7331", "-o", "command="],
        ["kill", "-TERM", "-7331"],
    ]
    assert relay_state_path(tmp_path).exists() is False


def test_relay_pid_identity_mismatch_is_not_terminated(tmp_path):
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity="python scripts/comfyui_relay.py",
    )
    runner = FakeRelayRunner("unrelated --server")
    save_relay_state(tmp_path, state)

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert runner.commands == [["ps", "-p", "7331", "-o", "command="]]
    assert result.state is None
    assert relay_state_path(tmp_path).exists() is False


def test_relay_stop_terminates_only_exact_identity_and_clears_state(tmp_path):
    identity = "python scripts/comfyui_relay.py"
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


def test_relay_stop_rechecks_identity_immediately_before_signal(tmp_path):
    identity = "python scripts/comfyui_relay.py"
    state = RelayState(
        bind_host="172.17.0.1",
        bind_port=18188,
        target_port=8188,
        managed_pid=7331,
        managed_identity=identity,
    )
    save_relay_state(tmp_path, state)
    runner = SequencedRelayRunner([identity, "unrelated --server"])

    result = stop_relay(
        state,
        runner,
        HostInfo("Linux", "x86_64", Path("/home/test")),
        project_root=tmp_path,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert all(command[0] == "ps" for command in runner.commands)
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
