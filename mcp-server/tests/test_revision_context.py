"""Actual Backend HTTP export -> separate MCP interpreter / HttpBackendClient."""
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from mcp_server.client import HttpBackendClient
from mcp_server.server import mcp
from mcp_server.tools import generate, gallery


def test_registered_generate_schema_exposes_optional_revision_context():
    tools = asyncio.run(mcp.list_tools())
    tool = next(t for t in tools if t.name == 'generate_image')
    assert 'revision_context' in tool.inputSchema['properties']
    assert 'revision_context' not in tool.inputSchema.get('required', [])


def test_actual_backend_http_serialization_survives_mcp_projection():
    source = os.environ.get('REVISION_HTTP_EXPORT')
    if not source:
        pytest.skip('run Backend HTTP export first; set REVISION_HTTP_EXPORT in the MCP interpreter')
    records = json.loads(Path(source).read_text())['exchanges']
    assert {'generate', 'status', 'image', 'artifact', 'list'} <= {r['kind'] for r in records}
    for record in records:
        payload, kind = record['payload'], record['kind']
        requests = []
        def respond(request):
            requests.append(request)
            assert request.method == ('POST' if kind == 'generate' else 'GET')
            if kind == 'generate':
                assert json.loads(request.content) == record['request']
            return httpx.Response(201 if kind == 'generate' else 200, json=payload)
        original = httpx.Client
        client = HttpBackendClient('http://fixture.invalid/api')
        with patch.object(generate, '_get_client', return_value=client), patch.object(gallery, '_get_client', return_value=client), \
             patch('httpx.Client', side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw)):
            if kind == 'generate':
                result = json.loads(generate.generate_image(**record['request']))
            elif kind in ('status', 'queued'):
                result = json.loads(generate.get_generation_status(payload['job_id']))
            elif kind == 'image':
                result = json.loads(gallery.get_gallery_image(payload['id']))
            elif kind == 'artifact':
                result = json.loads(gallery.get_gallery_artifact(payload['id']))
            else:
                result = json.loads(gallery.gallery_list())
        assert result['ok'] is True
        assert len(requests) == 1  # All reads cause zero POSTs.
        if kind == 'list':
            assert result['data'] == payload
        else:
            assert result['revision_context'] == payload['revision_context']
            assert result['revision_context_error'] == payload.get('revision_context_error')
            if result['revision_context'] is not None:
                assert result['revision_context']['parent_brief_revision'] == 'v1'
                assert result['revision_context']['brief_revision'] == 'v2'
                assert result['revision_context']['parent_job_id']
        if kind == 'status':
            assert result['artifacts'] == payload['artifacts']


@pytest.mark.parametrize('payload', [{'revision_context': None}, {'revision_context': None, 'revision_context_error': 'revision_context_unavailable'}])
def test_legacy_and_unavailable_context_is_not_invented(payload):
    backend = HttpBackendClient('http://fixture.invalid/api')
    original = httpx.Client
    def respond(request):
        assert request.method == 'GET'
        return httpx.Response(200, json={'status': 'completed', 'job_id': 'old', **payload})
    with patch.object(generate, '_get_client', return_value=backend), patch.object(gallery, '_get_client', return_value=backend), \
         patch('httpx.Client', side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw)):
        for raw in (generate.get_generation_status('old'), gallery.get_gallery_image(1), gallery.get_gallery_artifact(1)):
            result = json.loads(raw)
            assert result['revision_context'] is None
            assert result['revision_context_error'] == payload.get('revision_context_error')
