from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import workers
from app.main import app
from app.services import nvidia_worker


def test_powershell_client_uses_open_command_routes_and_preserves_payload(
    monkeypatch,
) -> None:
    real_client = httpx.Client
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/powershell/commands":
            body = {"command_id": "cmd/任意", "state": "accepted"}
            return httpx.Response(202, json=body, request=request)
        body = {"command_id": "cmd/任意", "state": "running"}
        return httpx.Response(200, json=body, request=request)

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        nvidia_worker.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    client = nvidia_worker.NvidiaWorkerClient("http://worker", timeout=10)
    script = "$env:TEST='任意'; Get-ChildItem D:\\"
    working_directory = r"D:\code"

    accepted = client.submit_powershell(
        script,
        working_directory=working_directory,
    )
    status = client.powershell_status(accepted["command_id"])
    cancelled = client.cancel_powershell(accepted["command_id"])

    assert accepted == {"command_id": "cmd/任意", "state": "accepted"}
    assert status == {"command_id": "cmd/任意", "state": "running"}
    assert cancelled == {"command_id": "cmd/任意", "state": "running"}
    assert [(request.method, request.url.raw_path.decode()) for request in requests] == [
        ("POST", "/v1/powershell/commands"),
        ("GET", "/v1/powershell/commands/cmd/%E4%BB%BB%E6%84%8F"),
        ("POST", "/v1/powershell/commands/cmd/%E4%BB%BB%E6%84%8F/cancel"),
    ]
    assert json.loads(requests[0].content) == {
        "script": script,
        "working_directory": working_directory,
    }
    assert all("Authorization" not in request.headers for request in requests)


class FakePowerShellWorker:
    def __init__(self) -> None:
        self.submitted: tuple[str, str | None] | None = None
        self.status_command_id: str | None = None
        self.cancelled_command_id: str | None = None

    def submit_powershell(
        self, script: str, *, working_directory: str | None = None
    ) -> dict:
        self.submitted = (script, working_directory)
        return {"command_id": "command/1", "state": "accepted"}

    def powershell_status(self, command_id: str) -> dict:
        self.status_command_id = command_id
        return {"command_id": command_id, "state": "running"}

    def cancel_powershell(self, command_id: str) -> dict:
        self.cancelled_command_id = command_id
        return {"command_id": command_id, "state": "cancelled"}


def test_mac_api_submits_open_powershell_command_unchanged(monkeypatch) -> None:
    fake = FakePowerShellWorker()
    monkeypatch.setattr(workers, "get_worker_client", lambda: fake)

    response = TestClient(app).post(
        "/api/workers/powershell/commands",
        json={
            "script": "Restart-Service Spooler",
            "working_directory": r"C:\\",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"command_id": "command/1", "state": "accepted"}
    assert fake.submitted == ("Restart-Service Spooler", r"C:\\")


def test_mac_api_reads_open_powershell_command_status_unchanged(monkeypatch) -> None:
    fake = FakePowerShellWorker()
    monkeypatch.setattr(workers, "get_worker_client", lambda: fake)

    response = TestClient(app).get("/api/workers/powershell/commands/any/id")

    assert response.status_code == 200
    assert response.json() == {"command_id": "any/id", "state": "running"}
    assert fake.status_command_id == "any/id"


def test_mac_api_cancels_open_powershell_command_unchanged(monkeypatch) -> None:
    fake = FakePowerShellWorker()
    monkeypatch.setattr(workers, "get_worker_client", lambda: fake)

    response = TestClient(app).post("/api/workers/powershell/commands/any/id/cancel")

    assert response.status_code == 200
    assert response.json() == {"command_id": "any/id", "state": "cancelled"}
    assert fake.cancelled_command_id == "any/id"


@pytest.mark.parametrize(
    ("method", "path", "payload", "operation"),
    [
        (
            "post",
            "/api/workers/powershell/commands",
            {"script": "Get-Date"},
            "submit_powershell",
        ),
        (
            "get",
            "/api/workers/powershell/commands/unknown",
            None,
            "powershell_status",
        ),
        (
            "post",
            "/api/workers/powershell/commands/unknown/cancel",
            None,
            "cancel_powershell",
        ),
    ],
)
def test_mac_api_maps_worker_powershell_errors_to_unavailable(
    monkeypatch, method: str, path: str, payload: dict | None, operation: str
) -> None:
    fake = FakePowerShellWorker()
    monkeypatch.setattr(
        fake,
        operation,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(workers, "get_worker_client", lambda: fake)

    client = TestClient(app)
    response = (
        client.post(path, json=payload)
        if method == "post"
        else client.get(path)
    )

    assert response.status_code == 503


def test_worker_status_is_configured_with_only_worker_url(monkeypatch) -> None:
    monkeypatch.setattr(
        workers,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "nvidia_worker_url": "http://worker:8791",
                "nvidia_worker_auto_update": False,
            },
        )(),
    )
    monkeypatch.setattr(
        workers,
        "worker_update_status",
        lambda: {"state": "idle", "error_code": None},
    )
    monkeypatch.setattr(
        workers,
        "get_worker_client",
        lambda: type("Worker", (), {"health": lambda self: {"ready": True}})(),
    )

    response = TestClient(app).get("/api/workers/status")

    assert response.status_code == 200
    assert response.json()["configured"] is True
