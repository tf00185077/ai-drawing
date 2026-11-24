"""Real HttpBackendClient consumes Backend HTTP/compiled exports in MCP's venv.

Regenerate with test_multi_lora_boundaries and MULTI_LORA_HTTP_EXPORT; the frozen
export is a standalone fallback, never evidence of a live backend or generation.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from mcp_server.character_style import DefaultCharacterStyleResolver
from mcp_server.client import HttpBackendClient
from mcp_server.tools import generate

ROOT = Path(__file__).resolve().parents[2]
EXPORT = Path(os.environ.get("MULTI_LORA_HTTP_EXPORT", Path(__file__).parent / "fixtures" / "multi_lora_http_export.json"))


def test_http_compiled_export_through_real_client_and_tools():
    """Catches dropped [], list reordering, lost locators and false success on failure."""
    evidence = json.loads(EXPORT.read_text())
    fixture = ROOT / "backend/tests/fixtures/multi_lora_connected.json"
    assert evidence["fixture_sha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    exchanges = evidence["exchanges"]
    assert len(exchanges) == 14
    assert {entry["case"] for entry in exchanges} == {"omitted", "null", "legacy", "empty", "short", "exact", "excess"}
    real_client = httpx.Client
    resolver = DefaultCharacterStyleResolver()
    resolver._styles["offline style"] = ("mapped style", "ignored.safetensors")
    for entry in exchanges:
        received = []
        request_body = deepcopy(entry["request"])
        # Tools omit None fields, Backend treats explicit null as omission.
        expected_body = {key: value for key, value in request_body.items() if value is not None}

        def respond(request):
            received.append(request)
            if request.method == "POST":
                assert request.url.path == entry["path"]
                assert json.loads(request.content) == expected_body
                return httpx.Response(entry["post_status"], json=entry["post"])
            assert request.method == "GET"
            assert request.url.path == "/api/generate/job/" + entry["post"]["job_id"]
            return httpx.Response(entry["get_status"], json=entry["get"])

        transport = httpx.MockTransport(respond)
        with patch.object(generate, "_get_client", return_value=HttpBackendClient("http://offline.invalid/api")), \
             patch("httpx.Client", side_effect=lambda **kw: real_client(transport=transport, **kw)), \
             patch("mcp_server.character_style.get_resolver", return_value=resolver):
            arguments = deepcopy(request_body)
            if entry["case"] in ("short", "empty"):
                # Exercise actual style resolution; complete list still owns active set.
                arguments.pop("lora")
                arguments["prompt"] = "contract"
                arguments["style"] = "offline style"
            if entry["path"].endswith("custom"):
                arguments["workflow"] = json.dumps(arguments["workflow"])
                submitted = json.loads(generate.generate_image_custom_workflow(**arguments))
            else:
                submitted = json.loads(generate.generate_image(**arguments))
            assert submitted["ok"] is True and submitted["status"] == "queued"
            status = json.loads(generate.get_generation_status(submitted["job_id"]))
        assert len(received) == 2
        if entry["case"] == "excess":
            assert entry["compiled"] is None
            assert status["ok"] is False and status["status"] == "failed"
            assert status["error"]["code"] == "generation_failed"
            assert "defines 4 LoRAs but workflow has 3 loader" in status["error"]["message"]
        else:
            assert status["ok"] is True and status["status"] == "running"
            names = [node["inputs"]["lora_name"] for node in entry["compiled"].values()
                     if node["class_type"] in ("LoraLoader", "LoraLoaderModelOnly")]
            if entry["case"] == "empty":
                assert names == []
            elif entry["case"] in ("short", "exact"):
                assert names == [spec["name"] for spec in expected_body["loras"]]
                assert names[0] == "AI-Drawing/run-004/Readable Name_002.safetensors"


def test_backend_http_error_is_structured_failure():
    """A transport-level rejection cannot become a queued success."""
    real_client = httpx.Client
    def reject(request):
        assert json.loads(request.content)["loras"] == []
        return httpx.Response(422, json={"detail": "invalid request"})
    with patch.object(generate, "_get_client", return_value=HttpBackendClient("http://offline.invalid/api")), \
         patch("httpx.Client", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(reject), **kw)):
        result = json.loads(generate.generate_image(prompt="contract", loras=[]))
    assert result["ok"] is False
    assert result["error"]["code"] == "backend_http_error"
    assert "job_id" not in result
