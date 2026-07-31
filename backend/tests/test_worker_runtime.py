from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient


def _load_worker():
    path = (
        Path(__file__).resolve().parents[2]
        / "worker"
        / "windows"
        / "worker.py"
    )
    spec = importlib.util.spec_from_file_location("windows_worker_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configured_worker(tmp_path, monkeypatch):
    worker = _load_worker()
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"token": "secret", "cache_gb": 70, "minimum_free_gb": 0}),
        encoding="utf-8",
    )
    roots = {
        kind: tmp_path / kind
        for kind in worker.MODEL_ROOTS
    }
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    monkeypatch.setattr(worker, "CONFIG_PATH", config)
    monkeypatch.setattr(worker, "PARTIAL_ROOT", tmp_path / ".partial")
    monkeypatch.setattr(worker, "MODEL_ROOTS", roots)
    return worker, TestClient(worker.app)


def test_worker_rejects_missing_token(tmp_path, monkeypatch) -> None:
    _worker, client = _configured_worker(tmp_path, monkeypatch)

    response = client.post("/v1/resources/plan", json={"resources": []})

    assert response.status_code == 401


def test_worker_promotes_only_complete_verified_resource(
    tmp_path, monkeypatch
) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    data = b"verified-model"
    digest = hashlib.sha256(data).hexdigest()
    headers = {"Authorization": "Bearer secret"}
    params = {
        "kind": "loras",
        "name": "style.safetensors",
        "sha256": digest,
        "size": len(data),
    }

    first = client.put(
        "/v1/resources/content",
        params={**params, "offset": 0},
        content=data[:4],
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    destination = worker.MODEL_ROOTS["loras"] / "style.safetensors"

    assert first.status_code == 200
    assert first.json()["ready"] is False
    assert not destination.exists()

    second = client.put(
        "/v1/resources/content",
        params={**params, "offset": 4},
        content=data[4:],
        headers={**headers, "Content-Type": "application/octet-stream"},
    )

    assert second.status_code == 200
    assert second.json()["ready"] is True
    assert destination.read_bytes() == data
