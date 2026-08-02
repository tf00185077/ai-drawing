from __future__ import annotations

import json

import httpx

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
