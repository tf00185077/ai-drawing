from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.api import workers
from app.config import Settings
from app.services import nvidia_worker


@pytest.fixture(autouse=True)
def _isolate_runtime_worker_url_cache():
    nvidia_worker.clear_runtime_worker_urls()
    yield
    nvidia_worker.clear_runtime_worker_urls()


def test_worker_target_fails_closed_when_not_paired(monkeypatch) -> None:
    monkeypatch.setattr(
        nvidia_worker,
        "get_settings",
        lambda: SimpleNamespace(
            nvidia_worker_url="",
            nvidia_worker_token="",
            nvidia_worker_timeout=60,
        ),
    )

    with pytest.raises(
        nvidia_worker.WorkerConfigurationError,
        match="not paired",
    ):
        nvidia_worker.get_generation_client("worker")


def test_local_target_uses_local_client(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(nvidia_worker, "get_comfy_client", lambda: sentinel)

    assert nvidia_worker.get_generation_client("local") is sentinel


def test_unknown_target_is_rejected() -> None:
    with pytest.raises(
        nvidia_worker.WorkerConfigurationError,
        match="unsupported execution target",
    ):
        nvidia_worker.get_generation_client("auto")


def _paired_settings(**overrides):
    values = {
        "nvidia_worker_url": "http://192.168.1.106:8791",
        "nvidia_worker_timeout": 60,
        "nvidia_worker_hostname": "DESKTOP-AV90PQ4",
        "nvidia_worker_protocol_version": 2,
        "nvidia_worker_discovery_enabled": True,
        "nvidia_worker_discovery_cidr": "192.168.1.0/24",
        "nvidia_worker_discovery_timeout": 0.1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_recording_transport(monkeypatch, handler):
    real_client = httpx.Client
    requests = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(record)
    monkeypatch.setattr(
        nvidia_worker.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    return requests


def test_probe_worker_status_is_url_only(monkeypatch) -> None:
    requests = _install_recording_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"protocol_version": 2, "hostname": "DESKTOP-AV90PQ4"},
            request=request,
        ),
    )

    status = nvidia_worker._probe_worker_status(
        "http://192.168.1.120:8791",
        timeout=0.1,
    )

    assert status == {"protocol_version": 2, "hostname": "DESKTOP-AV90PQ4"}
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/worker/status"
    assert "Authorization" not in requests[0].headers


def test_worker_retry_scans_cidr_and_adopts_protocol_2_worker_without_auth(
    monkeypatch,
) -> None:
    settings = _paired_settings()
    remembered_url = "http://192.168.1.110:8791"
    reachable_url = "http://192.168.1.120:8791"
    nvidia_worker.remember_runtime_worker_url(
        settings.nvidia_worker_url,
        settings.nvidia_worker_hostname,
        settings.nvidia_worker_protocol_version,
        remembered_url,
    )
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: settings)
    scans = []

    def candidates(**kwargs):
        scans.append(kwargs)
        return [reachable_url]

    monkeypatch.setattr(nvidia_worker, "_open_worker_candidates", candidates)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "192.168.1.110":
            raise httpx.ConnectError("remembered address refused", request=request)
        return httpx.Response(
            200,
            json={"protocol_version": 2, "hostname": "DESKTOP-AV90PQ4"},
            request=request,
        )

    requests = _install_recording_transport(monkeypatch, respond)
    client = nvidia_worker.get_worker_client()

    assert client.health() == {
        "protocol_version": 2,
        "hostname": "DESKTOP-AV90PQ4",
    }
    assert scans == [
        {
            "failed_url": remembered_url,
            "discovery_cidr": "192.168.1.0/24",
            "timeout": 0.1,
        }
    ]
    assert client.base_url == reachable_url
    assert [request.url.host for request in requests] == [
        "192.168.1.110",
        "192.168.1.120",
        "192.168.1.120",
    ]
    assert all("Authorization" not in request.headers for request in requests)
    assert nvidia_worker.get_worker_client().base_url == reachable_url


def test_get_worker_client_requires_only_configured_url(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_WORKER_TOKEN", raising=False)
    settings = Settings(
        _env_file=None,
        nvidia_worker_url="http://192.168.1.106:8791",
    )
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: settings)

    client = nvidia_worker.get_worker_client()

    assert isinstance(client, nvidia_worker.NvidiaWorkerClient)
    assert client.base_url == "http://192.168.1.106:8791"


def test_discovery_rejects_wrong_hostname_and_protocol(monkeypatch) -> None:
    candidates = [
        "http://192.168.1.110:8791",
        "http://192.168.1.111:8791",
        "http://192.168.1.120:8791",
    ]
    statuses = {
        candidates[0]: {"protocol_version": 1, "hostname": "OTHER-PC"},
        candidates[1]: {"protocol_version": 2, "hostname": "DESKTOP-AV90PQ4"},
        candidates[2]: {"protocol_version": 1, "hostname": "DESKTOP-AV90PQ4"},
    }
    monkeypatch.setattr(
        nvidia_worker,
        "_open_worker_candidates",
        lambda **kwargs: candidates,
    )
    monkeypatch.setattr(
        nvidia_worker,
        "_probe_worker_status",
        lambda url, **kwargs: statuses[url],
    )

    assert nvidia_worker.discover_worker_url(
        failed_url="http://192.168.1.106:8791",
        expected_hostname="DESKTOP-AV90PQ4",
        expected_protocol_version=1,
        discovery_cidr="192.168.1.0/24",
        discovery_timeout=0.1,
    ) == "http://192.168.1.120:8791"


@pytest.mark.parametrize(
    "status",
    [
        {"protocol_version": 1, "hostname": "OTHER-PC"},
        {"protocol_version": 2, "hostname": "DESKTOP-AV90PQ4"},
    ],
)
def test_discovery_refuses_when_identity_does_not_match(monkeypatch, status) -> None:
    monkeypatch.setattr(
        nvidia_worker,
        "_open_worker_candidates",
        lambda **kwargs: ["http://192.168.1.120:8791"],
    )
    monkeypatch.setattr(
        nvidia_worker,
        "_probe_worker_status",
        lambda url, **kwargs: status,
    )

    with pytest.raises(nvidia_worker.WorkerConfigurationError, match="not found"):
        nvidia_worker.discover_worker_url(
            failed_url="http://192.168.1.106:8791",
            expected_hostname="DESKTOP-AV90PQ4",
            expected_protocol_version=1,
            discovery_cidr="192.168.1.0/24",
            discovery_timeout=0.1,
        )


def test_generation_client_reuses_runtime_discovered_url(monkeypatch) -> None:
    settings = _paired_settings()
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: settings)
    nvidia_worker.clear_runtime_worker_urls()
    nvidia_worker.remember_runtime_worker_url(
        settings.nvidia_worker_url,
        settings.nvidia_worker_hostname,
        settings.nvidia_worker_protocol_version,
        "http://192.168.1.120:8791",
    )

    client = nvidia_worker.get_generation_client("worker")

    assert isinstance(client, nvidia_worker.NvidiaWorkerClient)
    assert client.base_url == "http://192.168.1.120:8791"


@pytest.mark.parametrize(
    ("failed_url", "cidr"),
    [
        ("http://worker.local:8791", "192.168.1.0/24"),
        ("http://[2001:db8::1]:8791", "192.168.1.0/24"),
        ("http://192.168.1.106:8791", "192.168.2.0/24"),
        ("http://192.168.1.106:8791", "192.168.0.0/16"),
        ("http://192.168.1.106:8080", "192.168.1.0/24"),
    ],
)
def test_discovery_is_restricted_to_configured_ipv4_same_24(failed_url, cidr) -> None:
    with pytest.raises(nvidia_worker.WorkerConfigurationError):
        nvidia_worker._discovery_target(failed_url, cidr)


def test_discovery_requires_exactly_one_identity_match(monkeypatch) -> None:
    candidates = ["http://192.168.1.110:8791", "http://192.168.1.120:8791"]
    monkeypatch.setattr(nvidia_worker, "_open_worker_candidates", lambda **kwargs: candidates)
    monkeypatch.setattr(
        nvidia_worker,
        "_probe_worker_status",
        lambda url, **kwargs: {"protocol_version": 1, "hostname": "DESKTOP-AV90PQ4"},
    )

    with pytest.raises(nvidia_worker.WorkerConfigurationError, match="ambiguous"):
        nvidia_worker.discover_worker_url(
            failed_url="http://192.168.1.106:8791",
            expected_hostname="DESKTOP-AV90PQ4",
            expected_protocol_version=1,
            discovery_cidr="192.168.1.0/24",
            discovery_timeout=0.1,
        )


def test_discovery_disabled_does_not_scan(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient(
        "http://192.168.1.106:8791", discovery_enabled=False
    )
    monkeypatch.setattr(
        client,
        "_request_once",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("refused")),
    )
    discover = MagicMock()
    monkeypatch.setattr(nvidia_worker, "discover_worker_url", discover)

    with pytest.raises(httpx.ConnectError):
        client.health()
    discover.assert_not_called()


def test_non_connection_error_does_not_scan(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient(
        "http://192.168.1.106:8791", discovery_enabled=True
    )
    monkeypatch.setattr(
        client,
        "_request_once",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ReadTimeout("slow response")),
    )
    discover = MagicMock()
    monkeypatch.setattr(nvidia_worker, "discover_worker_url", discover)

    with pytest.raises(httpx.ReadTimeout):
        client.health()
    discover.assert_not_called()


def test_worker_status_uses_discovery_aware_factory(monkeypatch) -> None:
    # The Mac API's legacy configuration gate is removed in Task 5. This task
    # changes only the Worker client, so keep this route-focused test isolated.
    settings = _paired_settings(nvidia_worker_token="legacy")
    client = MagicMock()
    client.health.return_value = {"protocol_version": 1, "hostname": "DESKTOP-AV90PQ4"}
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(workers, "get_settings", lambda: settings)
    monkeypatch.setattr(workers, "get_worker_client", factory)

    result = workers.worker_status()

    factory.assert_called_once_with()
    assert result["reachable"] is True


def test_worker_discovery_settings_defaults(monkeypatch) -> None:
    # app.config loads the repository .env at import time. A defaults test must
    # not inherit deployment-specific values copied into os.environ.
    for name in (
        "NVIDIA_WORKER_DISCOVERY_ENABLED",
        "NVIDIA_WORKER_DISCOVERY_CIDR",
        "NVIDIA_WORKER_DISCOVERY_TIMEOUT",
        "NVIDIA_WORKER_HOSTNAME",
        "NVIDIA_WORKER_PROTOCOL_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)

    assert settings.nvidia_worker_discovery_enabled is False
    assert settings.nvidia_worker_discovery_cidr == ""
    assert settings.nvidia_worker_discovery_timeout > 0
    assert settings.nvidia_worker_hostname == ""
    assert settings.nvidia_worker_protocol_version == 2
