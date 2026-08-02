from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.comfyui import ComfyUIError
from app.services import nvidia_worker


def test_worker_submission_sends_resource_references_directly_to_comfyui(
    monkeypatch,
) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 5.0)
    requests: list[tuple[str, str, dict[str, Any]]] = []
    digest_calls = []

    class Response:
        is_success = True
        text = ""
        reason_phrase = "OK"

        def __init__(self, body: dict[str, Any]) -> None:
            self._body = body

        def json(self) -> dict[str, Any]:
            return self._body

        def raise_for_status(self) -> None:
            return None

    def request(method: str, path: str, **kwargs: Any) -> Response:
        requests.append((method, path, kwargs["json"]))
        if path == "/v1/workflows/preflight":
            return Response({"ready": True, "missing_node_types": []})
        if path == "/v1/resources/plan":
            return Response({"missing": []})
        return Response({"prompt_id": "prompt-1"})

    def read_and_hash(path) -> str:
        digest_calls.append(path)
        return "0" * 64

    monkeypatch.setattr(client, "_request_raw", request)
    monkeypatch.setattr(
        nvidia_worker,
        "_read_and_hash",
        read_and_hash,
        raising=False,
    )
    prompt = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "style.safetensors"},
        },
        "3": {
            "class_type": "LoadImage",
            "inputs": {"image": "reference.png"},
        },
    }

    assert client.submit_prompt(prompt) == "prompt-1"

    assert requests == [
        ("POST", "/prompt", {"prompt": prompt}),
    ]
    assert digest_calls == []


def test_worker_submit_prompt_surfaces_node_errors(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 5.0)

    response = MagicMock()
    response.is_success = False
    response.status_code = 400
    response.text = ""
    response.json.return_value = {
        "error": "invalid prompt",
        "node_errors": {"6": "checkpoint not found"},
    }
    instance = MagicMock()
    instance.request.return_value = response
    fake = MagicMock()
    fake.__enter__.return_value = instance
    fake.__exit__.return_value = None
    monkeypatch.setattr(nvidia_worker.httpx, "Client", lambda *a, **k: fake)

    with pytest.raises(ComfyUIError) as exc:
        client.submit_prompt(
            {"6": {"class_type": "CheckpointLoaderSimple", "inputs": {}}}
        )

    assert exc.value.args[0] == "invalid prompt"
    assert exc.value.node_errors == {"6": "checkpoint not found"}
