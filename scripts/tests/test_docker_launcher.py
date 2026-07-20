from __future__ import annotations

from pathlib import Path

import pytest

from launcher.docker import (
    DockerError,
    compose_command,
    compose_down,
    compose_up,
    find_available_port,
    mount_probe,
    port_available,
    preflight,
    validate_compose,
    wait_http_ready,
)
from launcher.runner import CommandResult


class FakeRunner:
    def __init__(self, results=()):
        self.results = iter(results)
        self.commands: list[tuple[list[str], Path | None]] = []

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append((command, cwd))
        try:
            return next(self.results)
        except StopIteration:
            return CommandResult(tuple(command), 0, "", "")


def result(code=0, stdout="", stderr=""):
    return CommandResult((), code, stdout, stderr)


def test_preflight_requires_running_daemon_and_compose_224():
    runner = FakeRunner((result(stdout="27.0.0\n"), result(stdout="2.24.7\n")))
    report = preflight(runner)
    assert report.docker_version == "27.0.0"
    assert report.compose_version == (2, 24, 7)
    assert [call[0] for call in runner.commands] == [
        ["docker", "version", "--format", "{{.Server.Version}}"],
        ["docker", "compose", "version", "--short"],
    ]


@pytest.mark.parametrize(
    ("results", "code"),
    [
        ((result(1, stderr="daemon unavailable"),), "DOCKER_DAEMON_UNAVAILABLE"),
        (
            (result(stdout="27.0.0"), result(stdout="v2.23.3")),
            "COMPOSE_VERSION_UNSUPPORTED",
        ),
    ],
)
def test_preflight_returns_actionable_failures(results, code):
    with pytest.raises(DockerError) as raised:
        preflight(FakeRunner(results))
    assert raised.value.code == code
    assert raised.value.hint


def test_compose_command_uses_explicit_env_base_and_override(tmp_path):
    root = tmp_path.resolve()
    assert compose_command(root, "up", "-d", "--build") == [
        "docker",
        "compose",
        "--env-file",
        str(root / ".env"),
        "-f",
        str(root / "docker-compose.yml"),
        "-f",
        str(root / ".ai-drawing/compose.local.yaml"),
        "up",
        "-d",
        "--build",
    ]


def test_compose_operations_are_structured_lists(tmp_path):
    runner = FakeRunner((result(), result()))
    compose_up(tmp_path, runner)
    compose_down(tmp_path, runner)
    assert runner.commands[0][0][-4:] == ["up", "-d", "--build", "--remove-orphans"]
    assert runner.commands[1][0][-3:] == ["down", "--remove-orphans", "--timeout=10"]


def test_validate_compose_uses_staged_paths(tmp_path):
    env = tmp_path / ".env.stage"
    override = tmp_path / ".compose.stage.yaml"
    runner = FakeRunner((result(),))
    assert validate_compose(tmp_path, env, override, runner) is True
    command = runner.commands[0][0]
    assert command[command.index("--env-file") + 1] == str(env.resolve())
    assert command[command.index("-f", command.index("-f") + 1) + 1] == str(
        override.resolve()
    )
    assert command[-2:] == ["config", "--quiet"]


def test_occupied_port_is_never_terminated_and_alternate_is_selected():
    calls: list[tuple[str, int]] = []

    def probe(host, port):
        calls.append((host, port))
        return port == 8002

    assert find_available_port(8001, probe=probe) == 8002
    assert calls == [("127.0.0.1", 8001), ("127.0.0.1", 8002)]


def test_port_available_closes_probe_socket():
    events = []

    class Socket:
        def __init__(self, *_args):
            pass

        def bind(self, address):
            events.append(("bind", address))

        def close(self):
            events.append(("close",))

    assert port_available("127.0.0.1", 8001, socket_factory=Socket) is True
    assert events == [("bind", ("127.0.0.1", 8001)), ("close",)]


def test_mount_probe_resolves_only_explicit_allowed_path(tmp_path):
    allowed = tmp_path / "data"
    allowed.mkdir()
    runner = FakeRunner((result(),))
    mount_probe(allowed / ".", runner, allowed_roots=(tmp_path,))
    command = runner.commands[0][0]
    assert command[:3] == ["docker", "run", "--rm"]
    assert str(allowed.resolve()) in " ".join(command)
    assert "busybox:1.36.1" in command
    assert all("shell=True" not in item for item in command)


def test_mount_probe_rejects_path_outside_allowed_roots(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    with pytest.raises(DockerError) as raised:
        mount_probe(outside, FakeRunner(), allowed_roots=(tmp_path,))
    assert raised.value.code == "MOUNT_PATH_NOT_ALLOWED"


def test_mount_probe_reports_missing_explicit_path(tmp_path):
    with pytest.raises(DockerError) as raised:
        mount_probe(tmp_path / "missing", FakeRunner(), allowed_roots=(tmp_path,))
    assert raised.value.code == "MOUNT_PATH_MISSING"


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


def test_readiness_is_bounded_by_monotonic_deadline():
    clock = FakeClock()
    timeouts = []

    def http_get(_url, *, timeout):
        timeouts.append(timeout)
        raise OSError("not ready")

    assert (
        wait_http_ready(
            "http://127.0.0.1:8001/health",
            http_get=http_get,
            timeout=2.5,
            interval=1.0,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        is False
    )
    assert timeouts == [2.0, 1.5, 0.5]
    assert clock.sleeps == [1.0, 1.0, 0.5]
    assert clock.now == 2.5


def test_readiness_accepts_only_success_response_before_deadline():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    assert wait_http_ready("http://127.0.0.1:5173", http_get=lambda *_a, **_k: Response())
