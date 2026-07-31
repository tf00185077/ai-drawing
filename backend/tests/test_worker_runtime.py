from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
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
    monkeypatch.setattr(worker, "SOURCE_COMMIT_PATH", tmp_path / "source-commit.txt", raising=False)
    monkeypatch.setattr(worker, "UPDATE_REQUEST_PATH", tmp_path / "state" / "update-request.json", raising=False)
    monkeypatch.setattr(worker, "UPDATE_STATUS_PATH", tmp_path / "state" / "update-status.json", raising=False)
    return worker, TestClient(worker.app)


@pytest.fixture
def worker_runtime(tmp_path, monkeypatch):
    return _configured_worker(tmp_path, monkeypatch)


@pytest.fixture
def worker_module(worker_runtime):
    return worker_runtime[0]


@pytest.fixture
def worker_client(worker_runtime):
    return worker_runtime[1]


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer secret"}


def test_status_advertises_release_and_update_capability(worker_client, worker_module):
    worker_module.SOURCE_COMMIT_PATH.write_text("a" * 40, encoding="utf-8")

    body = worker_client.get("/v1/worker/status", headers=_auth()).json()

    assert body["protocol_version"] == 2
    assert body["worker_version"] == "0.3.0"
    assert body["source_commit"] == "a" * 40
    assert body["update_capability"] == 1
    assert body["update_state"] == "idle"


@pytest.mark.parametrize("value", ["main", "abc", "g" * 40, "a" * 39])
def test_update_rejects_non_full_hex_commit(worker_client, value):
    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": value}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["task", "command", "url", "branch", "path"])
def test_update_rejects_extra_control_fields(
    worker_client, worker_module, monkeypatch, field
) -> None:
    monkeypatch.setattr(worker_module.subprocess, "run", lambda *args, **kwargs: None)
    response = worker_client.post(
        "/v1/admin/update",
        headers=_auth(),
        json={"target_commit": "a" * 40, field: "untrusted-value"},
    )

    assert response.status_code == 422


def test_update_queues_a_commit_and_persists_only_request_metadata(
    worker_client, worker_module, monkeypatch
) -> None:
    task_runs: list[list[str]] = []

    def run(command, *, check, timeout):
        task_runs.append(command)

    monkeypatch.setattr(worker_module.subprocess, "run", run)
    target = "b" * 40

    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": target}
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    request = json.loads(worker_module.UPDATE_REQUEST_PATH.read_text(encoding="utf-8"))
    assert set(request) == {"request_id", "target_commit", "timestamp"}
    assert request["request_id"] == response.json()["request_id"]
    assert request["target_commit"] == target
    assert isinstance(request["timestamp"], str) and request["timestamp"]
    assert task_runs == [["schtasks.exe", "/Run", "/TN", "AI-Drawing Worker Updater"]]


def test_queued_update_immediately_blocks_mutations(
    worker_client, worker_module, monkeypatch
) -> None:
    monkeypatch.setattr(worker_module.subprocess, "run", lambda *args, **kwargs: None)

    queued = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "b" * 40}
    )
    status = worker_client.get("/v1/admin/update/status", headers=_auth())
    mutation = worker_client.post(
        "/v1/resources/plan", headers=_auth(), json={"resources": []}
    )

    assert queued.status_code == 202
    assert status.json() == {"state": "queued"}
    assert mutation.status_code == 409
    assert mutation.json()["detail"]["code"] == "worker_updating"


def test_scheduler_failure_marks_update_failed_before_activation(
    worker_client, worker_module, monkeypatch
) -> None:
    def fail_task(*args, **kwargs):
        raise worker_module.subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(worker_module.subprocess, "run", fail_task)

    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "b" * 40}
    )
    status = worker_client.get("/v1/admin/update/status", headers=_auth())
    mutation = worker_client.post(
        "/v1/resources/plan", headers=_auth(), json={"resources": []}
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "update_activation_failed"
    assert status.json() == {"state": "failed_before_activation"}
    assert mutation.status_code == 200


def test_scheduler_failure_releases_a_different_target_for_queueing(
    worker_client, worker_module, monkeypatch
) -> None:
    attempts = 0

    def run_task(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise worker_module.subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(worker_module.subprocess, "run", run_task)

    failed = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "b" * 40}
    )
    queued = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "c" * 40}
    )

    assert failed.status_code == 503
    assert queued.status_code == 202
    request = json.loads(worker_module.UPDATE_REQUEST_PATH.read_text(encoding="utf-8"))
    assert request["target_commit"] == "c" * 40
    assert worker_client.get("/v1/admin/update/status", headers=_auth()).json() == {
        "state": "queued"
    }


def test_update_reuses_an_active_request_for_the_same_target(
    worker_client, worker_module, monkeypatch
) -> None:
    task_runs: list[list[str]] = []
    monkeypatch.setattr(
        worker_module.subprocess,
        "run",
        lambda command, *, check, timeout: task_runs.append(command),
    )
    target = "c" * 40

    first = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": target}
    )
    second = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": target}
    )

    assert first.status_code == second.status_code == 202
    assert second.json()["request_id"] == first.json()["request_id"]
    assert task_runs == [["schtasks.exe", "/Run", "/TN", "AI-Drawing Worker Updater"]] * 2


def test_update_rejects_different_target_while_an_update_is_active(
    worker_client, worker_module, monkeypatch
) -> None:
    monkeypatch.setattr(worker_module.subprocess, "run", lambda *args, **kwargs: None)
    first = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "d" * 40}
    )
    second = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "e" * 40}
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "update_already_running"


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/v1/resources/plan", {"json": {"resources": []}}),
        (
            "put",
            "/v1/resources/content",
            {
                "params": {
                    "kind": "loras",
                    "name": "style.safetensors",
                    "sha256": "f" * 64,
                    "size": 1,
                    "offset": 0,
                },
                "content": b"x",
                "headers": {"Content-Type": "application/octet-stream"},
            },
        ),
        ("post", "/prompt", {"json": {"prompt": {}}}),
    ],
)
def test_mutations_are_blocked_while_worker_is_updating(
    worker_client, worker_module, method, path, kwargs
) -> None:
    worker_module.UPDATE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    worker_module.UPDATE_STATUS_PATH.write_text(
        json.dumps({"state": "applying"}), encoding="utf-8"
    )

    request_kwargs = {**kwargs, "headers": {**_auth(), **kwargs.get("headers", {})}}
    response = getattr(worker_client, method)(path, **request_kwargs)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "worker_updating"


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


def _spy_sha256(worker, monkeypatch):
    calls = {"n": 0}
    real = worker._sha256

    def counting(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(worker, "_sha256", counting)
    return calls


def test_plan_trusts_present_file_via_sidecar_without_rehashing(
    tmp_path, monkeypatch
) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    data = b"a-real-model-blob"
    digest = hashlib.sha256(data).hexdigest()
    headers = {"Authorization": "Bearer secret"}
    params = {
        "kind": "loras",
        "name": "style.safetensors",
        "sha256": digest,
        "size": len(data),
    }
    put = client.put(
        "/v1/resources/content",
        params={**params, "offset": 0},
        content=data,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert put.json()["ready"] is True

    calls = _spy_sha256(worker, monkeypatch)
    plan = client.post(
        "/v1/resources/plan", json={"resources": [params]}, headers=headers
    )

    assert plan.status_code == 200
    assert plan.json()["missing"] == []
    assert calls["n"] == 0, "present file must be trusted via sidecar, not re-hashed"


def test_plan_reports_same_size_different_content_as_missing(
    tmp_path, monkeypatch
) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    original = b"original-content!"
    replacement = b"changed-content!!"
    assert len(original) == len(replacement)
    headers = {"Authorization": "Bearer secret"}
    client.put(
        "/v1/resources/content",
        params={
            "kind": "loras",
            "name": "style.safetensors",
            "sha256": hashlib.sha256(original).hexdigest(),
            "size": len(original),
            "offset": 0,
        },
        content=original,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )

    replacement_digest = hashlib.sha256(replacement).hexdigest()
    plan = client.post(
        "/v1/resources/plan",
        json={
            "resources": [
                {
                    "kind": "loras",
                    "name": "style.safetensors",
                    "sha256": replacement_digest,
                    "size": len(replacement),
                }
            ]
        },
        headers=headers,
    )

    assert plan.status_code == 200
    assert [item["sha256"] for item in plan.json()["missing"]] == [replacement_digest]


def test_plan_self_heals_when_sidecar_absent(tmp_path, monkeypatch) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    root = worker.MODEL_ROOTS["loras"]
    root.mkdir(parents=True, exist_ok=True)
    data = b"preexisting-model"
    (root / "legacy.safetensors").write_bytes(data)
    headers = {"Authorization": "Bearer secret"}
    body = {
        "resources": [
            {
                "kind": "loras",
                "name": "legacy.safetensors",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        ]
    }

    calls = _spy_sha256(worker, monkeypatch)

    first = client.post("/v1/resources/plan", json=body, headers=headers)
    assert first.json()["missing"] == []
    assert calls["n"] == 1, "unknown file is hashed once to establish trust"

    second = client.post("/v1/resources/plan", json=body, headers=headers)
    assert second.json()["missing"] == []
    assert calls["n"] == 1, "sidecar now serves the file with no further hashing"
