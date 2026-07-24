from __future__ import annotations

from pathlib import Path

import pytest

import hashlib

from launcher import constants
from launcher.docker import (
    ComposeRuntime,
    DockerError,
    _download_compose,
    compose_asset_name,
    compose_cache_path,
    compose_command,
    compose_download_url,
    compose_expected_sha256,
    compose_down,
    compose_up,
    compose_up_services,
    compose_service_states,
    docker_bridge_host,
    find_available_port,
    mount_probe,
    normalize_arch,
    port_available,
    preflight,
    resolve_compose_runtime,
    validate_compose,
    wait_http_ready,
)
from launcher.platforms import detect_host
from launcher.runner import CommandResult

LINUX = detect_host(system="Linux", machine="x86_64", home=Path("/home/x"))


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


def test_preflight_requires_running_daemon_and_returns_system_runtime():
    runner = FakeRunner((result(stdout="27.0.0\n"), result(stdout="2.24.7\n")))
    report = preflight(runner, LINUX)
    assert report.docker_version == "27.0.0"
    assert report.compose_version == (2, 24, 7)
    assert report.invocation == ("docker", "compose")
    assert [call[0] for call in runner.commands] == [
        ["docker", "version", "--format", "{{.Server.Version}}"],
        ["docker", "compose", "version", "--short"],
    ]


def test_preflight_rejects_unavailable_daemon():
    with pytest.raises(DockerError) as raised:
        preflight(FakeRunner((result(1, stderr="daemon unavailable"),)), LINUX)
    assert raised.value.code == "DOCKER_DAEMON_UNAVAILABLE"
    assert raised.value.hint


@pytest.mark.parametrize(
    ("machine", "expected"),
    [("x86_64", "x86_64"), ("AMD64", "x86_64"), ("arm64", "aarch64"), ("aarch64", "aarch64")],
)
def test_normalize_arch_maps_known_machines(machine, expected):
    assert normalize_arch(machine) == expected


def test_normalize_arch_rejects_unknown():
    with pytest.raises(DockerError) as raised:
        normalize_arch("mips")
    assert raised.value.code == "COMPOSE_BUNDLED_UNSUPPORTED_ARCH"
    assert raised.value.hint


def test_compose_asset_name_and_url_for_windows():
    host = detect_host(system="Windows", machine="AMD64", home=Path("C:/Users/x"))
    assert compose_asset_name(host) == "docker-compose-windows-x86_64.exe"
    assert compose_download_url(host) == (
        f"{constants.COMPOSE_RELEASE_URL}/v{constants.COMPOSE_BUNDLED_VERSION}"
        "/docker-compose-windows-x86_64.exe"
    )


def test_compose_asset_name_for_linux_arm():
    host = detect_host(system="Linux", machine="aarch64", home=Path("/home/x"))
    assert compose_asset_name(host) == "docker-compose-linux-aarch64"


def test_compose_cache_path_is_private_and_versioned(tmp_path):
    path = compose_cache_path(LINUX, cache_root=tmp_path)
    assert path == (
        tmp_path / "ai-drawing" / "compose" / constants.COMPOSE_BUNDLED_VERSION / "docker-compose"
    )
    win = detect_host(system="Windows", machine="AMD64", home=Path("C:/Users/x"))
    assert compose_cache_path(win, cache_root=tmp_path).name == "docker-compose.exe"


def test_compose_expected_sha256_present_for_supported_asset():
    assert len(compose_expected_sha256(LINUX)) == 64


def test_download_compose_verifies_checksum_and_replaces(tmp_path):
    dest = tmp_path / "docker-compose"
    payload = b"#!/bin/sh\necho compose\n"
    digest = hashlib.sha256(payload).hexdigest()

    def fake_downloader(url, path):
        path.write_bytes(payload)

    _download_compose("https://example/compose", dest, digest, downloader=fake_downloader)
    assert dest.read_bytes() == payload
    assert not dest.with_name("docker-compose.partial").exists()


def test_download_compose_rejects_bad_checksum_and_cleans_up(tmp_path):
    dest = tmp_path / "docker-compose"

    def fake_downloader(url, path):
        path.write_bytes(b"tampered")

    with pytest.raises(DockerError) as raised:
        _download_compose("https://example/compose", dest, "0" * 64, downloader=fake_downloader)
    assert raised.value.code == "COMPOSE_CHECKSUM_MISMATCH"
    assert not dest.exists()
    assert not dest.with_name("docker-compose.partial").exists()


def test_download_compose_reports_download_failure(tmp_path):
    dest = tmp_path / "docker-compose"

    def failing_downloader(url, path):
        raise OSError("network down")

    with pytest.raises(DockerError) as raised:
        _download_compose("https://example/compose", dest, "0" * 64, downloader=failing_downloader)
    assert raised.value.code == "COMPOSE_DOWNLOAD_FAILED"
    assert not dest.with_name("docker-compose.partial").exists()


def test_resolve_uses_system_compose_when_new_enough(tmp_path):
    runner = FakeRunner((result(stdout="2.29.7\n"),))
    downloads = []
    runtime = resolve_compose_runtime(
        LINUX, runner, cache_root=tmp_path,
        downloader=lambda url, path: downloads.append(url),
    )
    assert runtime == ComposeRuntime(("docker", "compose"), (2, 29, 7), "system")
    assert downloads == []


def test_resolve_downloads_bundled_when_system_too_old(tmp_path):
    payload = b"bundled-compose"
    digest = hashlib.sha256(payload).hexdigest()
    runner = FakeRunner((result(stdout="2.20.2\n"), result(stdout="2.32.4\n")))
    seen = {}

    def fake_downloader(url, path):
        seen["url"] = url
        path.write_bytes(payload)

    import launcher.docker as dockermod
    original = dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"]
    dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = digest
    try:
        runtime = resolve_compose_runtime(
            LINUX, runner, cache_root=tmp_path, downloader=fake_downloader
        )
    finally:
        dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = original
    assert runtime.source == "bundled"
    assert runtime.version == (2, 32, 4)
    assert runtime.invocation == (str(compose_cache_path(LINUX, cache_root=tmp_path)),)
    assert "docker-compose-linux-x86_64" in seen["url"]


def test_resolve_uses_cached_bundled_without_download(tmp_path):
    path = compose_cache_path(LINUX, cache_root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"cached")
    runner = FakeRunner((result(stdout="2.10.0\n"), result(stdout="2.32.4\n")))

    def forbidden(url, p):
        raise AssertionError("must not download when cache is present")

    runtime = resolve_compose_runtime(
        LINUX, runner, cache_root=tmp_path, downloader=forbidden
    )
    assert runtime.source == "bundled"
    assert runtime.invocation == (str(path),)


def test_resolve_read_only_never_downloads(tmp_path):
    runner = FakeRunner((result(stdout="2.10.0\n"),))

    def forbidden(url, p):
        raise AssertionError("read-only must not download")

    with pytest.raises(DockerError) as raised:
        resolve_compose_runtime(
            LINUX, runner, allow_download=False, cache_root=tmp_path, downloader=forbidden
        )
    assert raised.value.code == "COMPOSE_UNAVAILABLE"


def test_resolve_handles_missing_system_compose(tmp_path):
    payload = b"bundled"
    digest = hashlib.sha256(payload).hexdigest()
    runner = FakeRunner((result(1, stderr="unknown command"), result(stdout="2.32.4\n")))
    import launcher.docker as dockermod
    original = dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"]
    dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = digest
    try:
        runtime = resolve_compose_runtime(
            LINUX, runner, cache_root=tmp_path,
            downloader=lambda url, path: path.write_bytes(payload),
        )
    finally:
        dockermod.COMPOSE_ASSET_SHA256["docker-compose-linux-x86_64"] = original
    assert runtime.source == "bundled"


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


def test_compose_command_accepts_bundled_invocation(tmp_path):
    root = tmp_path.resolve()
    command = compose_command(root, "up", "-d", invocation=("/cache/docker-compose",))
    assert command[:1] == ["/cache/docker-compose"]
    assert command[1:3] == ["--env-file", str(root / ".env")]
    assert command[-2:] == ["up", "-d"]


def test_compose_up_uses_supplied_invocation(tmp_path):
    runner = FakeRunner((result(),))
    compose_up(tmp_path, runner, invocation=("/cache/docker-compose",))
    assert runner.commands[0][0][0] == "/cache/docker-compose"
    assert runner.commands[0][0][-4:] == ["up", "-d", "--build", "--remove-orphans"]


def test_compose_operations_are_structured_lists(tmp_path):
    runner = FakeRunner((result(), result()))
    compose_up(tmp_path, runner)
    compose_down(tmp_path, runner)
    assert runner.commands[0][0][-4:] == ["up", "-d", "--build", "--remove-orphans"]
    assert runner.commands[1][0][-3:] == ["down", "--remove-orphans", "--timeout=10"]


def test_partial_compose_restore_is_exact_and_has_no_dependencies(tmp_path):
    runner = FakeRunner((result(),))
    compose_up_services(tmp_path, runner, frozenset({"backend"}))
    assert runner.commands[0][0][-4:] == ["up", "-d", "--no-deps", "backend"]


def test_compose_service_states_are_parsed_without_shell(tmp_path):
    payload = (
        '{"Service":"backend","State":"running"}\n'
        '{"Service":"frontend","State":"exited"}\n'
    )
    runner = FakeRunner((result(stdout=payload),))
    assert compose_service_states(tmp_path, runner) == {
        "backend": "running",
        "frontend": "exited",
    }
    assert runner.commands[0][0][-4:] == ["ps", "--all", "--format", "json"]


def test_linux_bridge_host_comes_from_structured_docker_inspection():
    runner = FakeRunner((result(stdout="172.17.0.1\n"),))
    assert docker_bridge_host(runner) == "172.17.0.1"
    assert runner.commands[0][0] == [
        "docker",
        "network",
        "inspect",
        "bridge",
        "--format",
        "{{(index .IPAM.Config 0).Gateway}}",
    ]


@pytest.mark.parametrize(
    "address",
    ["0.0.0.0", "127.0.0.1", "8.8.8.8", "192.0.2.1", "not-an-ip"],
)
def test_linux_bridge_host_rejects_unsafe_address(address):
    with pytest.raises(DockerError) as raised:
        docker_bridge_host(FakeRunner((result(stdout=address),)))
    assert raised.value.code == "DOCKER_BRIDGE_UNSAFE"


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
