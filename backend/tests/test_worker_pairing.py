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
        "nvidia_worker_token": "tok",
        "nvidia_worker_timeout": 60,
        "nvidia_worker_hostname": "DESKTOP-AV90PQ4",
        "nvidia_worker_protocol_version": 1,
        "nvidia_worker_discovery_enabled": True,
        "nvidia_worker_discovery_cidr": "192.168.1.0/24",
        "nvidia_worker_discovery_timeout": 0.1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_worker_request_discovers_changed_ip_and_retries(monkeypatch) -> None:
    nvidia_worker.clear_runtime_worker_urls()
    client = nvidia_worker.NvidiaWorkerClient(
        "http://192.168.1.106:8791",
        "tok",
        5.0,
        expected_hostname="DESKTOP-AV90PQ4",
        expected_protocol_version=1,
        discovery_enabled=True,
        discovery_cidr="192.168.1.0/24",
        discovery_timeout=0.1,
    )
    calls = []
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"protocol_version": 1, "hostname": "DESKTOP-AV90PQ4"}

    def request_once(method, path, **kwargs):
        calls.append((client.base_url, method, path))
        if client.base_url.endswith(".106:8791"):
            raise httpx.ConnectError("old address refused")
        return response

    monkeypatch.setattr(client, "_request_once", request_once)
    monkeypatch.setattr(
        nvidia_worker,
        "discover_worker_url",
        lambda **kwargs: "http://192.168.1.120:8791",
    )

    assert client.health()["hostname"] == "DESKTOP-AV90PQ4"
    assert calls == [
        ("http://192.168.1.106:8791", "GET", "/v1/worker/status"),
        ("http://192.168.1.120:8791", "GET", "/v1/worker/status"),
    ]
    assert client.base_url == "http://192.168.1.120:8791"


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
        token="tok",
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
            token="tok",
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


def test_discovery_requires_exactly_one_authenticated_match(monkeypatch) -> None:
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
            token="tok",
            expected_hostname="DESKTOP-AV90PQ4",
            expected_protocol_version=1,
            discovery_cidr="192.168.1.0/24",
            discovery_timeout=0.1,
        )


def test_discovery_disabled_does_not_scan(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient(
        "http://192.168.1.106:8791", "tok", discovery_enabled=False
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
        "http://192.168.1.106:8791", "tok", discovery_enabled=True
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
    settings = _paired_settings()
    client = MagicMock()
    client.health.return_value = {"protocol_version": 1, "hostname": "DESKTOP-AV90PQ4"}
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(workers, "get_settings", lambda: settings)
    monkeypatch.setattr(workers, "get_worker_client", factory)

    result = workers.worker_status()

    factory.assert_called_once_with()
    assert result["reachable"] is True


def test_worker_discovery_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.nvidia_worker_discovery_enabled is False
    assert settings.nvidia_worker_discovery_cidr == ""
    assert settings.nvidia_worker_discovery_timeout > 0
    assert settings.nvidia_worker_hostname == ""
    assert settings.nvidia_worker_protocol_version == 1
