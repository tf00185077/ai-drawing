from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import nvidia_worker


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
