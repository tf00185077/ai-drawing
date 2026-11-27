"""Existing registered wait reads only the authoritative download domain."""
import json
import httpx
import pytest
from contextlib import contextmanager
from unittest.mock import patch
from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp

JOB = 'dl_' + 'a' * 32
ROUTE = '/api/civitai/download-jobs/' + JOB


@contextmanager
def backend(monkeypatch, handler):
    monkeypatch.setenv('MCP_BACKEND_API_URL', 'http://backend.invalid')
    get_mcp_settings.cache_clear()
    requests = []
    async def respond(request):
        requests.append(request)
        assert request.method == 'GET'
        value = handler(request)
        if hasattr(value, '__await__'): value = await value
        if isinstance(value, httpx.Response): return value
        code, body = value if isinstance(value, tuple) else (200, value)
        return httpx.Response(code, json=body)
    original = httpx.AsyncClient
    with patch('httpx.AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw)):
        try: yield requests
        finally: get_mcp_settings.cache_clear()


async def call(identity=JOB, timeout=1):
    blocks, result = await mcp.call_tool('wait_for_job', {'job_id': identity, 'timeout_seconds': timeout})
    assert json.loads(blocks[0].text) == result
    return result


@pytest.mark.parametrize('status', ['completed', 'failed'])
async def test_registered_wait_routes_download_without_gallery(monkeypatch, status):
    value = {'job_id': JOB, 'job_domain': 'download', 'status': status, 'resource_ids': [42],
        'components': [{'resource_id': 42, 'status': status, 'downloaded_bytes': 20}],
        'error': {'code': 'download_interrupted', 'message': 'Previous Backend exited', 'hint': 'Read the same job.'} if status == 'failed' else None}
    with backend(monkeypatch, lambda req: value) as requests:
        result = await call()
    assert [r.url.path for r in requests] == [ROUTE]
    state = result['data'] if status == 'completed' else result['error']['details']
    assert result['ok'] is (status == 'completed')
    assert state['job_id'] == JOB and state['job_domain'] == 'download'
    assert state['resource_ids'] == [42] and state.get('artifacts', []) == []
    if status == 'failed': assert result['error']['code'] == 'download_interrupted'


@pytest.mark.parametrize('code', [404, 503])
async def test_known_download_error_never_falls_through(monkeypatch, code):
    with backend(monkeypatch, lambda req: (code, {'detail': {'code': 'download_job_not_found', 'message': 'Unknown download', 'hint': 'Read the same ID.'}})) as requests:
        result = await call()
    assert result['ok'] is False
    assert [r.url.path for r in requests] == [ROUTE]
    assert result['error']['details']['job_domain'] == 'download'


async def test_download_identity_mismatch_is_not_certified(monkeypatch):
    with backend(monkeypatch, lambda req: {'job_id': 'dl_' + 'b' * 32, 'job_domain': 'download', 'status': 'completed', 'resource_ids': [42]}):
        result = await call()
    assert result['ok'] is False and result['error']['code'] == 'download_status_invalid'
    assert result['error']['details']['job_id'] == JOB


async def test_download_timeout_retains_last_known_state_and_same_job(monkeypatch):
    value = {'job_id': JOB, 'job_domain': 'download', 'status': 'running', 'resource_ids': [42], 'components': []}
    with backend(monkeypatch, lambda req: value) as requests:
        result = await call(timeout=0.02)
    assert result['error']['code'] == 'timeout'
    assert result['error']['details']['status'] == 'running'
    assert result['error']['details']['resource_ids'] == [42]
    assert JOB in result['error']['hint']
    assert all(r.url.path == ROUTE for r in requests)
