from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import worker.windows.updater.request_lock as request_lock
from worker.windows.updater.runtime import WindowsJunctionOps
from worker.windows.updater.request_lock import RequestLockTimeout


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


def _set_worker_root_env(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    root = tmp_path / "deployed"
    release = root
    config = root / "config" / "worker.json"
    state = root
    comfy = release / "runtime" / "ComfyUI"
    partial = root / "cache" / ".partial"
    verification = root / "cache" / "verified"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps({"token": "secret", "cache_gb": 70, "minimum_free_gb": 0}),
        encoding="utf-8",
    )
    (comfy / "models").mkdir(parents=True)
    partial.mkdir(parents=True)
    verification.mkdir()
    for name, value in {
        "AI_DRAWING_WORKER_ROOT": root,
        "AI_DRAWING_WORKER_RELEASE_ROOT": release,
        "AI_DRAWING_WORKER_CONFIG_PATH": config,
        "AI_DRAWING_WORKER_UPDATE_STATE_ROOT": state,
        "AI_DRAWING_COMFYUI_ROOT": comfy,
        "AI_DRAWING_WORKER_PARTIAL_ROOT": partial,
        "AI_DRAWING_WORKER_VERIFICATION_ROOT": verification,
    }.items():
        monkeypatch.setenv(name, str(value))
    return {
        "root": root,
        "release": release,
        "config": config,
        "state": state,
        "comfy": comfy,
        "partial": partial,
        "verification": verification,
    }


def _configured_worker(tmp_path, monkeypatch):
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    worker = _load_worker()
    assert worker.ROOT == paths["root"].resolve(strict=True)
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


def test_comfyui_url_defaults_to_the_exact_production_loopback(tmp_path, monkeypatch) -> None:
    """Changing the no-env production endpoint must make this test fail."""
    monkeypatch.delenv("AI_DRAWING_COMFYUI_URL", raising=False)
    _set_worker_root_env(tmp_path, monkeypatch)

    worker = _load_worker()

    assert worker.COMFYUI_URL == "http://127.0.0.1:8188"


def test_partial_root_defaults_to_the_existing_worker_cache_contract(
    tmp_path: Path, monkeypatch
) -> None:
    """Changing the non-versioned default away from ROOT/cache must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    monkeypatch.delenv("AI_DRAWING_WORKER_PARTIAL_ROOT")
    monkeypatch.delenv("AI_DRAWING_WORKER_VERIFICATION_ROOT")

    worker = _load_worker()

    assert worker.PARTIAL_ROOT == paths["root"].resolve(strict=True) / "cache" / ".partial"
    assert worker.VERIFICATION_ROOT == paths["root"].resolve(strict=True) / "cache" / "verified"


def test_loopback_comfyui_override_is_used_by_status_preflight_and_proxy(
    tmp_path, monkeypatch
) -> None:
    """Leaving any ComfyUI call on port 8188 must make this test fail."""
    override = "http://127.0.0.1:49152"
    monkeypatch.setenv("AI_DRAWING_COMFYUI_URL", override)
    worker, _client = _configured_worker(tmp_path, monkeypatch)
    worker.SOURCE_COMMIT_PATH.write_text("a" * 40, encoding="utf-8")
    seen: list[str] = []

    class Response:
        content = b"{}"
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {"ExampleNode": {}}

        def raise_for_status(self):
            return None

    def get(url, **_kwargs):
        seen.append(url)
        return Response()

    def request(_method, url, **_kwargs):
        seen.append(url)
        return Response()

    monkeypatch.setattr(worker.httpx, "get", get)
    monkeypatch.setattr(worker.httpx, "request", request)

    worker.status()
    assert worker.workflow_preflight({"node_types": ["ExampleNode"]}) == {
        "ready": True,
        "missing_node_types": [],
    }
    worker._proxy("POST", "/prompt", json={"prompt": {}})

    assert seen == [
        f"{override}/system_stats",
        f"{override}/object_info",
        f"{override}/prompt",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1:8188",
        "http://0.0.0.0:8188",
        "http://example.test:8188",
        "http://user@127.0.0.1:8188",
        "http://127.0.0.1:8188/path",
        "http://127.0.0.1:8188?query=1",
        "http://127.0.0.1:8188#fragment",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
    ],
)
def test_invalid_comfyui_override_fails_worker_startup(tmp_path, monkeypatch, value: str) -> None:
    """Falling back after an unsafe staged endpoint must make this test fail."""
    monkeypatch.setenv("AI_DRAWING_COMFYUI_URL", value)
    _set_worker_root_env(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="AI_DRAWING_COMFYUI_URL"):
        _load_worker()


def test_staged_worker_uses_explicit_release_config_state_and_comfy_roots(
    tmp_path: Path, monkeypatch
) -> None:
    """Collapsing staged immutable and mutable roots must make this test fail."""
    root = tmp_path / "deployed"
    release = root / "releases" / ("a" * 40)
    config = root / "config" / "worker.json"
    state = root / "staging" / "validation-state"
    comfy = release / "ComfyUI"
    shared_partial = root / "shared" / "partial"
    shared_cache = root / "shared" / "cache"
    partial = release / "cache" / ".partial"
    verification = shared_cache / "verified"
    for directory in (
        release,
        config.parent,
        state,
        comfy / "models" / "loras",
        shared_partial,
        shared_cache,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    partial.parent.mkdir(parents=True)
    WindowsJunctionOps().create(partial, shared_partial)
    config.write_text(
        json.dumps({"token": "staged-secret", "cache_gb": 70, "minimum_free_gb": 0}),
        encoding="utf-8",
    )
    (release / "source-commit.txt").write_text("a" * 40, encoding="utf-8")
    model = comfy / "models" / "loras" / "staged.safetensors"
    model_bytes = b"staged-model"
    model.write_bytes(model_bytes)
    (root / "source-commit.txt").write_text("b" * 40, encoding="utf-8")
    (root / "state").mkdir()
    (root / "state" / "update-status.json").write_text(
        json.dumps({"state": "recovery_required"}), encoding="utf-8"
    )
    (state / "state").mkdir()
    (state / "state" / "update-status.json").write_text(
        json.dumps({"state": "ready"}), encoding="utf-8"
    )
    comfy_url = "http://127.0.0.1:49152"
    values = {
        "AI_DRAWING_WORKER_ROOT": root,
        "AI_DRAWING_WORKER_RELEASE_ROOT": release,
        "AI_DRAWING_WORKER_CONFIG_PATH": config,
        "AI_DRAWING_WORKER_UPDATE_STATE_ROOT": state,
        "AI_DRAWING_COMFYUI_ROOT": comfy,
        "AI_DRAWING_WORKER_PARTIAL_ROOT": partial,
        "AI_DRAWING_WORKER_VERIFICATION_ROOT": verification,
        "AI_DRAWING_COMFYUI_URL": comfy_url,
    }
    for name, value in values.items():
        monkeypatch.setenv(name, str(value))
    worker = _load_worker()
    worker._record_verified(model, hashlib.sha256(model_bytes).hexdigest())
    client = TestClient(worker.app)
    seen: list[str] = []

    class Response:
        def __init__(self, value):
            self.value = value

        def json(self):
            return self.value

        def raise_for_status(self):
            return None

    def get(url, **_kwargs):
        seen.append(url)
        if url.endswith("/system_stats"):
            return Response({"devices": [{"name": "NVIDIA Test GPU"}]})
        return Response({"ExampleNode": {}})

    monkeypatch.setattr(worker.httpx, "get", get)
    headers = {"Authorization": "Bearer staged-secret"}

    status = client.get("/v1/worker/status", headers=headers)
    plan = client.post(
        "/v1/resources/plan",
        headers=headers,
        json={
            "resources": [
                {
                    "kind": "loras",
                    "name": model.name,
                    "sha256": hashlib.sha256(model_bytes).hexdigest(),
                    "size": len(model_bytes),
                }
            ]
        },
    )
    preflight = client.post(
        "/v1/workflows/preflight", headers=headers, json={"node_types": ["ExampleNode"]}
    )
    upload_data = b"shared-partial-upload"
    upload_digest = hashlib.sha256(upload_data).hexdigest()
    uploaded_prefix = upload_data[:7]
    content = client.put(
        "/v1/resources/content",
        headers={**headers, "Content-Type": "application/octet-stream"},
        params={
            "kind": "loras",
            "name": "uploaded.safetensors",
            "sha256": upload_digest,
            "size": len(upload_data),
            "offset": 0,
        },
        content=uploaded_prefix,
    )
    resume_plan = client.post(
        "/v1/resources/plan",
        headers=headers,
        json={
            "resources": [
                {
                    "kind": "loras",
                    "name": "uploaded.safetensors",
                    "sha256": upload_digest,
                    "size": len(upload_data),
                }
            ]
        },
    )
    partial_bytes = (shared_partial / f"{upload_digest}.part").read_bytes()
    completed = client.put(
        "/v1/resources/content",
        headers={**headers, "Content-Type": "application/octet-stream"},
        params={
            "kind": "loras",
            "name": "uploaded.safetensors",
            "sha256": upload_digest,
            "size": len(upload_data),
            "offset": len(uploaded_prefix),
        },
        content=upload_data[len(uploaded_prefix):],
    )

    assert status.status_code == plan.status_code == preflight.status_code == 200
    assert content.status_code == resume_plan.status_code == completed.status_code == 200
    assert status.json()["source_commit"] == "a" * 40
    assert status.json()["update_state"] == "ready"
    assert plan.json() == {"missing": []}
    assert preflight.json() == {"ready": True, "missing_node_types": []}
    assert worker.ROOT == root.resolve(strict=True)
    assert worker.RELEASE_ROOT == release.resolve(strict=True)
    assert worker.CONFIG_PATH == config.resolve(strict=True)
    assert worker.UPDATE_STATE_ROOT == state.resolve(strict=True)
    assert worker.COMFYUI_ROOT == comfy.resolve(strict=True)
    assert worker.MODEL_ROOTS["loras"] == comfy.resolve(strict=True) / "models" / "loras"
    assert worker.PARTIAL_ROOT == partial
    assert worker.VERIFICATION_ROOT == verification.resolve(strict=True)
    assert content.json() == {"ready": False, "offset": len(uploaded_prefix)}
    assert resume_plan.json()["missing"][0]["offset"] == len(uploaded_prefix)
    assert partial_bytes == uploaded_prefix
    assert completed.json()["ready"] is True
    sidecars = list(verification.glob("*.json"))
    assert len(sidecars) == 2
    assert any(json.loads(path.read_text(encoding="utf-8"))["sha256"] == upload_digest for path in sidecars)
    assert not (state / "cache").exists()
    assert not (root / "cache" / "verified").exists()
    assert not (release / "cache" / "verified").exists()
    assert seen == [f"{comfy_url}/system_stats", f"{comfy_url}/object_info"]


@pytest.mark.parametrize(
    "invalid_name",
    [
        "AI_DRAWING_WORKER_ROOT",
        "AI_DRAWING_WORKER_RELEASE_ROOT",
        "AI_DRAWING_WORKER_CONFIG_PATH",
        "AI_DRAWING_WORKER_UPDATE_STATE_ROOT",
        "AI_DRAWING_COMFYUI_ROOT",
        "AI_DRAWING_WORKER_PARTIAL_ROOT",
        "AI_DRAWING_WORKER_VERIFICATION_ROOT",
    ],
)
def test_worker_rejects_missing_or_out_of_root_explicit_paths(
    tmp_path: Path, monkeypatch, invalid_name: str
) -> None:
    """Accepting missing or escaping explicit runtime roots must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    if invalid_name == "AI_DRAWING_WORKER_ROOT":
        invalid = tmp_path / "missing-root"
    elif invalid_name == "AI_DRAWING_WORKER_CONFIG_PATH":
        invalid = outside / "worker.json"
        invalid.write_text('{"token":"outside"}', encoding="utf-8")
    elif invalid_name == "AI_DRAWING_COMFYUI_ROOT":
        invalid = outside
    elif invalid_name == "AI_DRAWING_WORKER_RELEASE_ROOT":
        invalid = outside
    else:
        invalid = outside
    monkeypatch.setenv(invalid_name, str(invalid))

    with pytest.raises(ValueError, match=invalid_name):
        _load_worker()


def test_worker_rejects_managed_partial_junction_with_external_target(
    tmp_path: Path, monkeypatch
) -> None:
    """Accepting a partial junction outside shared/partial must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    root = paths["root"]
    release = root / "releases" / ("a" * 40)
    comfy = release / "ComfyUI"
    partial = release / "cache" / ".partial"
    outside = tmp_path / "outside-partial"
    comfy.mkdir(parents=True)
    partial.parent.mkdir(parents=True)
    outside.mkdir()
    WindowsJunctionOps().create(partial, outside)
    monkeypatch.setenv("AI_DRAWING_WORKER_RELEASE_ROOT", str(release))
    monkeypatch.setenv("AI_DRAWING_COMFYUI_ROOT", str(comfy))
    monkeypatch.setenv("AI_DRAWING_WORKER_PARTIAL_ROOT", str(partial))

    with pytest.raises(ValueError, match="AI_DRAWING_WORKER_PARTIAL_ROOT"):
        _load_worker()


def test_worker_rejects_reparsed_shared_partial_before_touching_external_target(
    tmp_path: Path, monkeypatch
) -> None:
    """Resolving shared/partial before no-follow validation must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    root = paths["root"]
    release = root / "releases" / ("a" * 40)
    comfy = release / "ComfyUI"
    partial = release / "cache" / ".partial"
    shared_partial = root / "shared" / "partial"
    external = tmp_path / "external-shared-partial"
    sentinel = external / "keep.txt"
    comfy.mkdir(parents=True)
    partial.parent.mkdir(parents=True)
    shared_partial.parent.mkdir(parents=True)
    external.mkdir()
    sentinel.write_text("keep", encoding="utf-8")
    junctions = WindowsJunctionOps()
    junctions.create(shared_partial, external)
    junctions.create(partial, shared_partial)
    monkeypatch.setenv("AI_DRAWING_WORKER_RELEASE_ROOT", str(release))
    monkeypatch.setenv("AI_DRAWING_COMFYUI_ROOT", str(comfy))
    monkeypatch.setenv("AI_DRAWING_WORKER_PARTIAL_ROOT", str(partial))

    try:
        with pytest.raises(ValueError, match="AI_DRAWING_WORKER_PARTIAL_ROOT"):
            _load_worker()

        assert junctions.read_target(shared_partial) == external.resolve(strict=True)
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        junctions.remove(partial)
        junctions.remove(shared_partial)


def test_worker_rejects_reparsed_managed_verification_root_before_external_write(
    tmp_path: Path, monkeypatch
) -> None:
    """Allowing verification sidecars through a reparse point must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    root = paths["root"]
    release = root / "releases" / ("a" * 40)
    comfy = release / "ComfyUI"
    shared_partial = root / "shared" / "partial"
    partial = release / "cache" / ".partial"
    verification = root / "shared" / "cache" / "verified"
    external = tmp_path / "external-verification"
    sentinel = external / "keep.txt"
    comfy.mkdir(parents=True)
    shared_partial.mkdir(parents=True)
    partial.parent.mkdir(parents=True)
    verification.parent.mkdir(parents=True)
    external.mkdir()
    sentinel.write_text("keep", encoding="utf-8")
    junctions = WindowsJunctionOps()
    junctions.create(partial, shared_partial)
    junctions.create(verification, external)
    monkeypatch.setenv("AI_DRAWING_WORKER_RELEASE_ROOT", str(release))
    monkeypatch.setenv("AI_DRAWING_COMFYUI_ROOT", str(comfy))
    monkeypatch.setenv("AI_DRAWING_WORKER_PARTIAL_ROOT", str(partial))
    monkeypatch.setenv("AI_DRAWING_WORKER_VERIFICATION_ROOT", str(verification))

    try:
        with pytest.raises(ValueError, match="AI_DRAWING_WORKER_VERIFICATION_ROOT"):
            _load_worker()

        assert junctions.read_target(verification) == external.resolve(strict=True)
        assert sentinel.read_text(encoding="utf-8") == "keep"
    finally:
        junctions.remove(verification)
        junctions.remove(partial)


def test_worker_rejects_versioned_release_outside_releases_namespace(
    tmp_path: Path, monkeypatch
) -> None:
    """Allowing a candidate under an arbitrary mutable subdirectory must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    root = paths["root"]
    release = root / "operator-data" / ("a" * 40)
    comfy = release / "ComfyUI"
    comfy.mkdir(parents=True)
    monkeypatch.setenv("AI_DRAWING_WORKER_RELEASE_ROOT", str(release))
    monkeypatch.setenv("AI_DRAWING_COMFYUI_ROOT", str(comfy))

    with pytest.raises(ValueError, match="AI_DRAWING_WORKER_RELEASE_ROOT"):
        _load_worker()


def test_worker_rejects_update_state_inside_shared_models(tmp_path: Path, monkeypatch) -> None:
    """Using model storage for request/cache state must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    shared_models = paths["root"] / "shared" / "models"
    shared_models.mkdir(parents=True)
    monkeypatch.setenv("AI_DRAWING_WORKER_UPDATE_STATE_ROOT", str(shared_models))

    with pytest.raises(ValueError, match="AI_DRAWING_WORKER_UPDATE_STATE_ROOT"):
        _load_worker()


def test_worker_rejects_nested_candidate_comfy_root(tmp_path: Path, monkeypatch) -> None:
    """Accepting a nested substitute for release/ComfyUI must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    release = paths["root"] / "releases" / ("a" * 40)
    comfy = release / "nested" / "ComfyUI"
    comfy.mkdir(parents=True)
    monkeypatch.setenv("AI_DRAWING_WORKER_RELEASE_ROOT", str(release))
    monkeypatch.setenv("AI_DRAWING_COMFYUI_ROOT", str(comfy))

    with pytest.raises(ValueError, match="AI_DRAWING_COMFYUI_ROOT"):
        _load_worker()


@pytest.mark.parametrize("reparse_part", ["parent", "leaf"])
def test_worker_rejects_config_reparse_components(
    tmp_path: Path, monkeypatch, reparse_part: str
) -> None:
    """Resolving through a config reparse point must make this test fail."""
    paths = _set_worker_root_env(tmp_path, monkeypatch)
    reported = paths["config"].parent if reparse_part == "parent" else paths["config"]
    original_is_symlink = Path.is_symlink

    def is_symlink(path: Path) -> bool:
        return path == reported or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", is_symlink)

    with pytest.raises(ValueError, match="AI_DRAWING_WORKER_CONFIG_PATH"):
        _load_worker()


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


def test_update_request_lock_timeout_maps_to_safe_503(
    worker_client, worker_module, monkeypatch
) -> None:
    def time_out(*_args, **_kwargs):
        raise RequestLockTimeout()

    monkeypatch.setattr(worker_module, "queue_update", time_out)
    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "a" * 40}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "update_lock_unavailable"}


def test_update_unlock_failure_maps_to_safe_503(
    worker_client, worker_module, monkeypatch
) -> None:
    def fail_unlock(_lock_file):
        raise OSError("TOKEN=unlock-secret")

    monkeypatch.setattr(request_lock, "_unlock", fail_unlock)
    monkeypatch.setattr(worker_module.subprocess, "run", lambda *args, **kwargs: None)

    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "a" * 40}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "update_lock_unavailable"}
    assert "unlock-secret" not in response.text


def test_update_status_lock_timeout_maps_to_safe_503(
    worker_client, worker_module, monkeypatch
) -> None:
    def time_out(*_args, **_kwargs):
        raise RequestLockTimeout()

    monkeypatch.setattr(worker_module, "read_public_update_status", time_out)
    response = worker_client.get("/v1/admin/update/status", headers=_auth())

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "update_lock_unavailable"}


def test_scheduler_failure_status_lock_timeout_maps_to_safe_503(
    worker_client, worker_module, monkeypatch
) -> None:
    def fail_task(*args, **_kwargs):
        raise worker_module.subprocess.CalledProcessError(1, args[0])

    def time_out(*_args, **_kwargs):
        raise RequestLockTimeout()

    monkeypatch.setattr(worker_module.subprocess, "run", fail_task)
    monkeypatch.setattr(worker_module, "write_update_status", time_out)
    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": "a" * 40}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "update_lock_unavailable"}


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


def test_restart_uses_only_the_fixed_task_and_correlated_status(
    worker_client, worker_module, monkeypatch
) -> None:
    task_runs: list[list[str]] = []
    monkeypatch.setattr(
        worker_module.subprocess,
        "run",
        lambda command, *, check, timeout: task_runs.append(command),
    )

    queued = worker_client.post("/v1/admin/restart", headers=_auth(), json={})
    request_id = queued.json()["request_id"]
    status = worker_client.get(
        "/v1/admin/restart/status",
        headers=_auth(),
        params={"request_id": request_id},
    )

    assert queued.status_code == 202
    assert status.status_code == 200
    assert status.json()["request_id"] == request_id
    assert status.json()["state"] == "queued"
    assert isinstance(status.json()["timestamp"], str) and status.json()["timestamp"]
    assert task_runs == [["schtasks.exe", "/Run", "/TN", "AI-Drawing NVIDIA Worker Restart"]]


def test_restart_rejects_control_fields(worker_client) -> None:
    response = worker_client.post(
        "/v1/admin/restart", headers=_auth(), json={"command": "untrusted"}
    )
    assert response.status_code == 422


def test_restart_scheduler_failure_is_durable_and_retryable(
    worker_client, worker_module, monkeypatch
) -> None:
    def fail_task(*args, **kwargs):
        raise worker_module.subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(worker_module.subprocess, "run", fail_task)
    failed = worker_client.post("/v1/admin/restart", headers=_auth(), json={})
    request_id = json.loads(
        worker_module.RESTART_REQUEST_PATH.read_text(encoding="utf-8")
    )["request_id"]
    status = worker_client.get(
        "/v1/admin/restart/status",
        headers=_auth(),
        params={"request_id": request_id},
    )

    assert failed.status_code == 503
    assert failed.json()["detail"] == {"code": "restart_activation_failed"}
    assert status.json()["state"] == "failed"
    assert status.json()["error_code"] == "RESTART_ACTIVATION_FAILED"

    monkeypatch.setattr(worker_module.subprocess, "run", lambda *args, **kwargs: None)
    retried = worker_client.post("/v1/admin/restart", headers=_auth(), json={})
    assert retried.status_code == 202
    assert retried.json()["request_id"] != request_id


def test_restart_status_lock_timeout_maps_to_safe_503(
    worker_client, worker_module, monkeypatch
) -> None:
    monkeypatch.setattr(
        worker_module,
        "read_restart_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RequestLockTimeout()),
    )
    response = worker_client.get(
        "/v1/admin/restart/status",
        headers=_auth(),
        params={"request_id": "request-1"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "restart_lock_unavailable"}


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
    assert status.json()["state"] == "queued"
    assert status.json()["request_id"] == queued.json()["request_id"]
    assert status.json()["target_commit"] == "b" * 40
    assert isinstance(status.json()["timestamp"], str) and status.json()["timestamp"]
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
    assert status.json()["state"] == "failed_before_activation"
    assert status.json()["target_commit"] == "b" * 40
    assert isinstance(status.json()["request_id"], str)
    assert isinstance(status.json()["timestamp"], str)
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
    status = worker_client.get("/v1/admin/update/status", headers=_auth()).json()
    assert status["state"] == "queued"
    assert status["request_id"] == queued.json()["request_id"]
    assert status["target_commit"] == "c" * 40
    assert isinstance(status["timestamp"], str) and status["timestamp"]


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


def test_plan_does_not_self_heal_missing_verification_sidecar(tmp_path, monkeypatch) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    root = worker.MODEL_ROOTS["loras"]
    root.mkdir(parents=True, exist_ok=True)
    data = b"preexisting-model"
    destination = root / "legacy.safetensors"
    destination.write_bytes(data)
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
    assert first.json()["missing"] == [{**body["resources"][0], "offset": 0}]
    assert calls["n"] == 0, "planning must never hash an unverified destination"
    assert not worker._sidecar_path(destination).exists()

    worker._sidecar_path(destination).write_text("[]", encoding="utf-8")
    malformed = client.post("/v1/resources/plan", json=body, headers=headers)
    assert malformed.json()["missing"] == [{**body["resources"][0], "offset": 0}]
    assert calls["n"] == 0


def test_plan_requires_retransfer_for_non_hex_sidecar_digest(tmp_path, monkeypatch) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    data = b"preexisting-model"
    invalid_digest = "z" * 64
    destination = worker.MODEL_ROOTS["loras"] / "legacy.safetensors"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(data)
    stat = destination.stat()
    sidecar = worker._sidecar_path(destination)
    sidecar.write_text(
        json.dumps(
            {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": invalid_digest,
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "kind": "loras",
        "name": destination.name,
        "sha256": invalid_digest,
        "size": len(data),
    }

    plan = client.post("/v1/resources/plan", headers=_auth(), json={"resources": [manifest]})

    assert plan.json()["missing"] == [{**manifest, "offset": 0}]


def test_plan_removes_stale_sidecar_when_destination_is_missing(
    tmp_path, monkeypatch
) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    data = b"verified-model"
    digest = hashlib.sha256(data).hexdigest()
    destination = worker.MODEL_ROOTS["loras"] / "style.safetensors"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(data)
    worker._record_verified(destination, digest)
    sidecar = worker._sidecar_path(destination)
    destination.unlink()

    plan = client.post(
        "/v1/resources/plan",
        headers=_auth(),
        json={
            "resources": [
                {
                    "kind": "loras",
                    "name": destination.name,
                    "sha256": digest,
                    "size": len(data),
                }
            ]
        },
    )

    assert plan.json()["missing"] == [
        {
            "kind": "loras",
            "name": destination.name,
            "sha256": digest,
            "size": len(data),
            "offset": 0,
        }
    ]
    assert not sidecar.exists()


def test_plan_requires_retransfer_when_size_or_mtime_changes(tmp_path, monkeypatch) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    data = b"verified-model"
    digest = hashlib.sha256(data).hexdigest()
    headers = _auth()
    params = {
        "kind": "loras",
        "name": "style.safetensors",
        "sha256": digest,
        "size": len(data),
    }
    uploaded = client.put(
        "/v1/resources/content",
        params={**params, "offset": 0},
        content=data,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert uploaded.json()["ready"] is True
    destination = worker.MODEL_ROOTS["loras"] / params["name"]

    destination.write_bytes(data + b"!")
    changed_size = client.post(
        "/v1/resources/plan", headers=headers, json={"resources": [params]}
    )
    assert changed_size.json()["missing"] == [{**params, "offset": 0}]

    destination.write_bytes(data)
    worker._record_verified(destination, digest)
    stat = destination.stat()
    os.utime(destination, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert destination.stat().st_mtime_ns != stat.st_mtime_ns
    changed_mtime = client.post(
        "/v1/resources/plan", headers=headers, json={"resources": [params]}
    )
    assert changed_mtime.json()["missing"] == [{**params, "offset": 0}]


def test_cache_eviction_removes_destination_verification_sidecar(tmp_path, monkeypatch) -> None:
    worker, _client = _configured_worker(tmp_path, monkeypatch)
    data = b"verified-model"
    destination = worker.MODEL_ROOTS["loras"] / "style.safetensors"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(data)
    worker._record_verified(destination, hashlib.sha256(data).hexdigest())
    sidecar = worker._sidecar_path(destination)
    worker._config = lambda: {"cache_gb": 0, "minimum_free_gb": 0}

    worker._enforce_cache(incoming_bytes=0, protected=set())

    assert not destination.exists()
    assert not sidecar.exists()


def test_digest_mismatch_leaves_no_destination_or_sidecar(tmp_path, monkeypatch) -> None:
    worker, client = _configured_worker(tmp_path, monkeypatch)
    destination = worker.MODEL_ROOTS["loras"] / "style.safetensors"
    previous = b"previous-model"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(previous)
    worker._record_verified(destination, hashlib.sha256(previous).hexdigest())
    sidecar = worker._sidecar_path(destination)
    response = client.put(
        "/v1/resources/content",
        params={
            "kind": "loras",
            "name": destination.name,
            "sha256": hashlib.sha256(b"expected-model").hexdigest(),
            "size": len(b"wrong-model!!"),
            "offset": 0,
        },
        content=b"wrong-model!!",
        headers={**_auth(), "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 422
    assert not destination.exists()
    assert not sidecar.exists()
