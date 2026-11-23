"""Agent-visible parent recovery is allowlisted; Backend text stays untrusted."""
import asyncio
import json
from unittest.mock import patch

import httpx
import pytest

from mcp_server.client import HttpBackendClient
from mcp_server.server import mcp
from mcp_server.tools import generate
from mcp_server.tools.responses import exception_error_json


CASES = [
    (404, "revision_parent_not_found", "Choose an existing canonical artifact ID."),
    (409, "revision_parent_not_image", "Choose an image artifact as the revision parent."),
    (409, "revision_request_conflict", "Use the parent's request_ref or choose a parent from this request."),
    (409, "revision_parent_context_invalid", "Recover the parent's stored context before using this anchor."),
]
# Synthetic markers only; no real credentials or private data.
MARKER = "/private/synthetic-only/FAKE_CREDENTIAL_AID30"
REQUEST = {"prompt": "explicit revision", "execution_target": "worker", "batch_size": 1,
           "revision_context": {"request_ref": "native:30", "brief_revision": "v2", "parent_artifact_id": 9}}


def invoke(response, *, tool=None, arguments=None, base_url="http://offline.invalid/api"):
    """Run the real client, replacing only its network transport."""
    real_client = httpx.Client
    requests = []
    errors = []

    def respond(request):
        requests.append({"method": request.method, "path": request.url.path,
                         "body": json.loads(request.content) if request.content else None})
        return response

    class CapturingClient(HttpBackendClient):
        def post(self, *args, **kwargs):
            try:
                return super().post(*args, **kwargs)
            except httpx.HTTPStatusError as exc:
                errors.append(exc)
                raise

    client = CapturingClient(base_url)
    with patch.object(generate, "_get_client", return_value=client), patch(
        "httpx.Client", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw)
    ):
        result = json.loads((tool or generate.generate_image)(**(REQUEST if arguments is None else arguments)))
    assert len(requests) == 1  # Domain rejection never retries or creates another job.
    return result, requests[0], errors


@pytest.mark.parametrize("status,code,hint", CASES)
@pytest.mark.parametrize("backend_hint", ["missing", "text", "object", "null"])
def test_known_parent_rejection_uses_only_canonical_recovery(status, code, hint, backend_hint):
    # Removing the allowlist or echoing the Backend hint/extra data must fail.
    detail = {"error": code, "nested": {"diagnostic": MARKER}}
    if backend_hint != "missing":
        detail["hint"] = {"text": MARKER, "object": {"secret": MARKER}, "null": None}[backend_hint]
    result, request, _ = invoke(httpx.Response(status, json={"detail": detail, "extra": MARKER}))
    assert request == {"method": "POST", "path": "/api/generate/", "body": REQUEST}
    assert result == {"ok": False, "tool": "generate_image", "error": {
        "code": code, "message": "Revision parent validation failed.",
        "details": {"where": "backend", "hint": hint}}}
    assert MARKER not in json.dumps(result)
    assert "job_id" not in result


@pytest.mark.parametrize("status,code,hint", CASES)
def test_known_parent_rejection_does_not_echo_exception_url(status, code, hint):
    result, _, errors = invoke(httpx.Response(status, json={"detail": {"error": code}}),
                               base_url="http://offline.invalid" + MARKER)
    assert MARKER in str(errors[0])  # Exercise actual HttpBackendClient exception text.
    assert MARKER not in json.dumps(result)
    assert result["error"]["details"]["hint"] == hint


@pytest.mark.parametrize("status,body", [
    (409, {"detail": {"error": "revision_parent_not_found"}}),
    (404, {"detail": {"error": "revision_parent_not_image"}}),
    (404, {"detail": {"error": "revision_request_conflict"}}),
    (404, {"detail": {"error": "revision_parent_context_invalid"}}),
    (422, {"detail": {"error": "revision_parent_not_found"}}),
    (500, {"detail": {"error": "revision_request_conflict"}}),
    (409, {"detail": {"error": "unknown_parent_error"}}),
    (409, {"detail": {"error": "revision_request_conflict "}}),
    (409, {"detail": {"error": ["revision_request_conflict"]}}),
    (409, {"detail": {"error": {"code": "revision_request_conflict"}}}),
    (409, {"detail": {"error": 1}}),
    (409, {"detail": {"error": True}}),
    (409, {"detail": {"error": None}}),
    (409, {"detail": {}}),
    (409, {"detail": []}),
    (409, {"detail": "revision_request_conflict"}),
    (409, {"detail": None}),
    (409, {}), (409, []), (409, None), (409, "revision_request_conflict"),
])
def test_unrecognized_shape_or_status_preserves_generic_fallback(status, body):
    # Any broader mapping or raw body projection would fail exact legacy comparison.
    response = httpx.Response(status, content=json.dumps(body).encode(), headers={"X-Synthetic": MARKER})
    result, _, errors = invoke(response)
    assert result == json.loads(exception_error_json("generate_image", errors[0], where="backend"))
    assert result["error"]["code"] == "HTTPStatusError"
    assert "job_id" not in result and MARKER not in json.dumps(result)


@pytest.mark.parametrize("content", [b"", b"{not-json", MARKER.encode(), b'null'])
def test_empty_or_non_json_body_stays_generic_without_body_echo(content):
    result, _, errors = invoke(httpx.Response(409, content=content))
    assert result == json.loads(exception_error_json("generate_image", errors[0], where="backend"))
    assert MARKER not in json.dumps(result)


def test_unknown_error_does_not_echo_injected_body():
    result, _, errors = invoke(httpx.Response(409, json={"detail": {"error": MARKER, "hint": MARKER}, "extra": MARKER}))
    assert result == json.loads(exception_error_json("generate_image", errors[0], where="backend"))
    assert MARKER not in json.dumps(result)


@pytest.mark.parametrize("exc", [RuntimeError("backend unavailable"), ValueError("invalid input"),
                                 httpx.ConnectError("offline connect failure")])
def test_non_http_status_exception_keeps_legacy_projection(exc):
    class OfflineClient:
        def post(self, path, json):
            raise exc
    with patch.object(generate, "_get_client", return_value=OfflineClient()):
        result = json.loads(generate.generate_image(**REQUEST))
    assert result == json.loads(exception_error_json("generate_image", exc, where="backend"))


@pytest.mark.parametrize("tool,arguments", [
    (generate.generate_image_custom_workflow, {"workflow": "{}", "execution_target": "worker"}),
    (generate.generate_video_custom_workflow, {"workflow": "{}", "execution_target": "worker"}),
])
def test_custom_callers_keep_generic_errors(tool, arguments):
    result, _, errors = invoke(httpx.Response(409, json={"detail": {"error": "revision_request_conflict", "hint": MARKER}}),
                               tool=tool, arguments=arguments)
    assert result == json.loads(exception_error_json(tool.__name__, errors[0], where="backend"))
    assert MARKER not in json.dumps(result)


@pytest.mark.parametrize("with_known_code", [False, True])
@pytest.mark.parametrize("boundary", ["direct", "sdk"])
def test_deep_json_decode_preserves_original_http_error(with_known_code, boundary):
    # Losing decoder containment must fail at both public calling boundaries.
    nested = b"[" * 1100 + b"0" + b"]" * 1100
    content = (b'{"detail":{"error":"revision_request_conflict"},"extra":'
               + nested + b"}") if with_known_code else nested

    def registered_tool(**arguments):
        result = asyncio.run(mcp.call_tool("generate_image", arguments))
        blocks = result[0] if isinstance(result, tuple) else result
        return next(block.text for block in blocks if hasattr(block, "text"))

    result, request, errors = invoke(
        httpx.Response(409, content=content),
        tool=registered_tool if boundary == "sdk" else generate.generate_image,
    )
    assert request == {"method": "POST", "path": "/api/generate/", "body": REQUEST}
    assert len(errors) == 1
    assert result == json.loads(exception_error_json("generate_image", errors[0], where="backend"))
    assert result["ok"] is False and result["error"]["code"] == "HTTPStatusError"
    assert "job_id" not in result and "revision_request_conflict" not in json.dumps(result)
