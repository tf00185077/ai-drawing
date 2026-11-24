"""Registered MCP -> real adapters/client -> mocked HTTP, with real deadlines."""
import asyncio
import json
import time
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import quote

import httpx
import pytest

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp


JOB = '25e4b0ee-dfac-4e48-916b-158368f72978'
GEN = '/api/generate/job/' + JOB
TRAIN = '/api/lora-train/jobs/' + JOB
GALLERY = Path('/fixture/gallery').resolve()
CONTEXT = {'request_ref': 'cup', 'brief_revision': 'v2', 'parent_artifact_id': 7}


@contextmanager
def backend(monkeypatch, handler, gallery=GALLERY):
    monkeypatch.setenv('MCP_BACKEND_API_URL', 'http://backend.invalid')
    monkeypatch.setenv('MCP_GALLERY_DIR', str(gallery))
    get_mcp_settings.cache_clear()
    requests = []
    async def respond(request):
        requests.append(request)
        assert request.method == 'GET', 'wait must never submit or cancel'
        value = handler(request)
        if hasattr(value, '__await__'):
            value = await value
        if isinstance(value, httpx.Response):
            return value
        status, body = value if isinstance(value, tuple) else (200, value)
        return httpx.Response(status, json=body)
    real = httpx.AsyncClient
    with patch('httpx.AsyncClient', side_effect=lambda **kw: real(transport=httpx.MockTransport(respond), **kw)):
        try:
            yield requests
        finally:
            get_mcp_settings.cache_clear()


async def call(timeout=1):
    blocks, structured = await mcp.call_tool('wait_for_job', {'job_id': JOB, 'timeout_seconds': timeout})
    assert json.loads(blocks[0].text) == structured
    return structured


def completed(artifacts=None, **extra):
    return {'job_id': JOB, 'status': 'completed', 'artifacts': artifacts or [], 'revision_context': CONTEXT, **extra}


def artifact(identity, path='nested/旅 人.png', kind='image', **extra):
    return {'id': identity, 'artifact_type': kind, 'gallery_path': path,
            'source_node_id': str(identity), 'source_node_type': 'SaveImage',
            'revision_context': {**CONTEXT, 'artifact_id': identity}, **extra}


async def test_discovery_is_one_read_intent_with_bounded_schema():
    tools = {t.name: t for t in await mcp.list_tools()}
    assert len(tools) == 31
    tool = tools['wait_for_job']
    assert tool.description.startswith('Risk: read.')
    assert tool.inputSchema['required'] == ['job_id']
    assert tool.inputSchema['properties']['timeout_seconds']['default'] == 50.0


async def test_mixed_media_all_identities_order_lineage_and_nested_unicode(monkeypatch):
    rows = [artifact(12), artifact(3, 'clips/a b.mp4', 'video'), artifact(18, 'last.png')]
    def respond(req):
        if req.url.path == GEN:
            return completed(rows, image_id=901, image_path='nested/旅 人.png')
        if req.url.path == '/api/gallery/901':
            return {'id': 901, 'image_path': 'nested/旅 人.png', 'image_url': '/gallery/nested/%E6%97%85%20%E4%BA%BA.png'}
        return next(row for row in rows if req.url.path.endswith('/' + str(row['id'])))
    with backend(monkeypatch, respond) as requests:
        result = await call()
    assert result['ok'] is True, result
    data = result['data']
    assert (data['job_id'], data['job_domain'], data['status']) == (JOB, 'generation', 'completed')
    assert [a['artifact_id'] for a in data['artifacts']] == [12, 3, 18]
    assert [a['kind'] for a in data['artifacts']] == ['image', 'video', 'image']
    assert data['revision_context'] == CONTEXT
    for expected, actual in zip(rows, data['artifacts']):
        assert actual['local_path'] == str(GALLERY / expected['gallery_path'])
        assert actual['artifact_url'] == 'http://backend.invalid/gallery/' + quote(expected['gallery_path'], safe='/')
        assert actual['revision_context'] == expected['revision_context']
        assert actual['source_node_id'] == expected['source_node_id']
    assert data['images'][0]['image_id'] == 901
    assert data['images'][0]['artifact_id'] is None
    assert len(requests) == 5


@pytest.mark.parametrize('row', [
    artifact(1, None, artifact_url='/gallery/a/%E6%97%85%20%E4%BA%BA.png'),
    artifact(1, str(GALLERY / 'a/旅 人.png')),
    artifact(1, 'a/旅 人.png', artifact_url='/gallery/a/%E6%97%85%20%E4%BA%BA.png'),
    artifact(1, 'a/旅 人.png', artifact_url='http://backend.invalid/gallery/a/%E6%97%85%20%E4%BA%BA.png'),
])
async def test_supported_relative_url_or_proven_absolute_path(monkeypatch, row):
    with backend(monkeypatch, lambda req: completed([row]) if req.url.path == GEN else row):
        result = await call()
    assert result['ok'] is True, result
    assert result['data']['artifacts'][0]['local_path'] == str(GALLERY / 'a/旅 人.png')
    assert result['data']['artifacts'][0]['artifact_url'] == 'http://backend.invalid/gallery/a/%E6%97%85%20%E4%BA%BA.png'


async def test_no_arbitrary_result_cap(monkeypatch):
    rows = [artifact(i, f'{i}.png') for i in range(1, 107)]
    with backend(monkeypatch, lambda req: completed(rows) if req.url.path == GEN else rows[int(req.url.path.rsplit('/', 1)[1])-1]):
        result = await call(3)
    assert [a['artifact_id'] for a in result['data']['artifacts']] == list(range(1, 107))


async def test_legacy_image_only_has_separate_namespace_and_no_artifact(monkeypatch):
    def respond(req):
        return completed(image_id=901, image_path='old/旅 人.png') if req.url.path == GEN else {'id': 901, 'image_path': 'old/旅 人.png', 'image_url': '/gallery/old/%E6%97%85%20%E4%BA%BA.png'}
    with backend(monkeypatch, respond) as requests:
        result = await call()
    assert result['ok'] is True
    data = result['data']
    assert data['artifacts'] == []
    assert data['images'] == [{'image_id': 901, 'artifact_id': None, 'kind': 'image', 'image_path': 'old/旅 人.png', 'local_path': str(GALLERY / 'old/旅 人.png'), 'image_url': 'http://backend.invalid/gallery/old/%E6%97%85%20%E4%BA%BA.png'}]
    assert [r.url.path for r in requests] == [GEN, '/api/gallery/901']


@pytest.mark.parametrize('bad', [
    {'gallery_path': None}, {'gallery_path': ''},
    {'gallery_path': '/outside/gallery/result.png'},
    {'gallery_path': '/app/data/gallery/result.png'},
    {'gallery_path': 'C:\\container\\gallery\\result.png'},
    {'gallery_path': '../result.png'}, {'gallery_path': 'safe/../../result.png'},
    {'gallery_path': 'safe\\..\\result.png'},
    {'gallery_path': None, 'artifact_url': '/gallery/%2e%2e/secret.png'},
    {'gallery_path': None, 'artifact_url': '/gallery/%252e%252e/secret.png'},
    {'gallery_path': None, 'artifact_url': '//evil.invalid/gallery/result.png'},
    {'gallery_path': None, 'artifact_url': 'https://evil.invalid/gallery/result.png'},
    {'gallery_path': None, 'artifact_url': 'http://backend.invalid/other/result.png'},
    {'gallery_path': 'safe.png', 'artifact_url': '/gallery/other.png'},
    {'gallery_path': 'safe.png', 'artifact_url': '/gallery/safe.png?token=secret'},
    {'gallery_path': 'a\x00.png'},
    {'gallery_path': str(GALLERY / 'nested/../result.png')},
    {'gallery_path': None, 'artifact_url': '/gallery/a%2fb.png'},
    {'gallery_path': None, 'artifact_url': '\n/gallery/result.png'},
    {'gallery_path': None, 'artifact_url': {'invalid': 'type'}},
])
async def test_unsafe_or_unavailable_locator_keeps_completed_and_entire_identity_set(monkeypatch, bad):
    rows = [artifact(10, 'good.png'), artifact(20, **bad), artifact(30, 'last.mp4', 'video')]
    with backend(monkeypatch, lambda req: completed(rows) if req.url.path == GEN else next(r for r in rows if req.url.path.endswith('/'+str(r['id'])))):
        result = await call()
    assert result['ok'] is False
    assert result['error']['code'] == 'artifact_locator_unavailable'
    detail = result['error']['details']
    assert (detail['job_id'], detail['job_domain'], detail['status']) == (JOB, 'generation', 'completed')
    assert [a['artifact_id'] for a in detail['artifacts']] == [10, 20, 30]
    assert detail['artifacts'][0]['local_path'] == str(GALLERY / 'good.png')
    assert detail['artifacts'][2]['artifact_url'] == 'http://backend.invalid/gallery/last.mp4'
    assert detail['artifacts'][1]['local_path'] == (str(GALLERY / 'safe.png') if '?' in str(bad.get('artifact_url')) else None)
    assert detail['artifacts'][1]['artifact_url'] is None
    assert detail['unavailable_locators'][0]['artifact_id'] == 20
    assert detail['unavailable_locators'][0]['reason']
    assert JOB in result['error']['hint'] and 'Gallery' in result['error']['hint']


async def test_symlink_escape_is_not_a_host_locator_and_no_file_is_copied(monkeypatch, tmp_path):
    root = tmp_path/'gallery'; root.mkdir()
    outside = tmp_path/'outside'; outside.mkdir()
    try:
        (root/'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Host cannot create symlinks; p1-03 host containment needs symlink privileges')
    row = artifact(2, 'link/missing.png')
    before = sorted(str(p) for p in tmp_path.rglob('*'))
    with backend(monkeypatch, lambda req: completed([row]) if req.url.path == GEN else row, root):
        result = await call()
    assert result['error']['code'] == 'artifact_locator_unavailable'
    assert result['error']['details']['artifacts'][0]['local_path'] is None
    assert sorted(str(p) for p in tmp_path.rglob('*')) == before


@pytest.mark.parametrize('domain', ['generation', 'training'])
@pytest.mark.parametrize('status', ['failed', 'cancelled'])
async def test_terminal_failure_cancellation_and_safe_training_projection(monkeypatch, domain, status):
    payload = {'ok': True, 'status': status, 'error': 'worker offline', 'failure_code': 'worker_unavailable',
               'node_errors': [{'node_id': '8', 'message': 'missing model'}], 'recording_error': 'not recorded',
               'revision_context': CONTEXT, 'error_code': 'lora_registration_failed',
               'error_message': '/private/SECRET token=SECRET', 'output_path': '/private/output.safetensors',
               'registration_status': 'failed', 'registered_lora_name': 'products/Cup.safetensors'}
    with backend(monkeypatch, lambda req: (404, {'detail': 'Job not found'}) if domain == 'training' and req.url.path == GEN else payload) as requests:
        result = await call()
    assert result['ok'] is False
    detail = result['error']['details']
    assert (detail['job_id'], detail['job_domain'], detail['status']) == (JOB, domain, status)
    if domain == 'generation':
        assert result['error']['message'] == 'worker offline'
        assert detail['node_errors'] == payload['node_errors']
        assert detail['recording_error'] == payload['recording_error']
        assert detail['failure_code'] == payload['failure_code']
    else:
        assert 'SECRET' not in json.dumps(result)
        assert detail['registration_status'] == 'failed'
        assert detail['registered_lora_name'] == payload['registered_lora_name']
        assert detail['output_path'] == '<redacted private path>'
    assert result['error']['code'] == ('job_cancelled' if status == 'cancelled' else 'worker_unavailable' if domain == 'generation' else 'lora_registration_failed')
    assert len(requests) == (2 if domain == 'training' else 1)


@pytest.mark.parametrize('smoke', [None, 'completed', 'legacy', 'queued', 'running', 'failed', 'cancelled', 'artifact_unavailable'])
async def test_training_output_and_independent_smoke_never_wait_or_submit(monkeypatch, smoke):
    raw = {'ok': True, 'job_id': JOB, 'status': 'completed', 'output_path': 'runs/Cup.safetensors',
           'output_sha256': 'abc', 'registration_status': 'registered', 'registered_lora_name': 'Cup.safetensors'}
    if smoke:
        raw.update(smoke_test_job_id='independent-smoke', smoke_test_status='completed' if smoke == 'legacy' else smoke,
                   smoke_test_artifact_id=None if smoke == 'legacy' else 71,
                   smoke_test_image_id=901, smoke_test_artifact='smoke/旅 人.png',
                   smoke_test_artifact_url='/gallery/smoke/%E6%97%85%20%E4%BA%BA.png')
        if smoke in {'failed', 'cancelled', 'artifact_unavailable'}:
            raw.update(smoke_test_error='SECRET', smoke_test_error_code='smoke_artifact_unavailable' if smoke == 'artifact_unavailable' else 'smoke_generation_'+smoke)
    with backend(monkeypatch, lambda req: (404, {'detail': 'not found'}) if req.url.path == GEN else raw) as requests:
        result = await call()
    assert result['ok'] is True, result
    data = result['data']
    assert data['status'] == 'completed' and data['job_domain'] == 'training'
    assert data['artifacts'] == [] and data['images'] == []
    for field in ('output_path', 'output_sha256', 'registration_status', 'registered_lora_name'):
        assert data[field] == raw[field]
    if smoke:
        for field in ('smoke_test_job_id', 'smoke_test_status', 'smoke_test_artifact_id', 'smoke_test_image_id', 'smoke_test_artifact', 'smoke_test_artifact_url'):
            assert data[field] == raw[field]
        assert 'SECRET' not in json.dumps(data)
        if smoke in {'failed', 'cancelled', 'artifact_unavailable'}:
            assert data['smoke_test_error_code'] == raw['smoke_test_error_code']
            assert data['smoke_test_hint']
    assert [r.url.path for r in requests] == [GEN, TRAIN]


@pytest.mark.parametrize('failure', ['connection', 'server'])
async def test_read_failure_is_not_not_found_or_domain_fallback(monkeypatch, failure):
    def respond(req):
        if failure == 'connection':
            raise httpx.ConnectError('unavailable', request=req)
        return 503, {'detail': {'code': 'read_unavailable', 'message': 'Try later', 'hint': 'Inspect same job.', 'details': {'phase': 'read'}}}
    with backend(monkeypatch, respond) as requests:
        result = await call()
    assert result['ok'] is False
    assert result['error']['details']['job_id'] == JOB
    assert result['error']['details']['status'] == 'unknown'
    assert len(requests) == 1
    if failure == 'server':
        assert result['error']['code'] == 'read_unavailable'
        assert result['error']['hint'] == 'Inspect same job.'


async def test_only_two_actual_not_found_reads_return_job_not_found(monkeypatch):
    with backend(monkeypatch, lambda req: (404, {'detail': {'code': 'job_not_found'}})) as requests:
        result = await call()
    assert result['error']['code'] == 'job_not_found'
    assert [r.url.path for r in requests] == [GEN, TRAIN]


class SlowBody(httpx.AsyncByteStream):
    def __init__(self):
        self.closed = False
    async def __aiter__(self):
        for _ in range(40):
            await asyncio.sleep(.01)
            yield b' '
        yield b'{"status":"completed"}'
    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize('stage', ['first', 'body', 'fallback', 'enrichment', 'last_known'])
async def test_overall_deadline_aborts_reads_and_reports_last_known_truth(monkeypatch, stage):
    body = SlowBody()
    count = 0
    async def respond(req):
        nonlocal count
        count += 1
        if stage == 'body':
            return httpx.Response(200, stream=body)
        if stage == 'fallback' and req.url.path == GEN:
            await asyncio.sleep(.025)
            return 404, {'detail': 'not found'}
        if stage == 'enrichment' and req.url.path == GEN:
            await asyncio.sleep(.025)
            return completed([artifact(1)])
        if stage == 'last_known' and count == 1:
            return {'status': 'running'}
        await asyncio.sleep(.4)
        return completed([artifact(1)])
    start = time.monotonic()
    with backend(monkeypatch, respond) as requests:
        result = await call(.07)
    elapsed = time.monotonic() - start
    assert .05 <= elapsed < .3, elapsed
    assert result['ok'] is False and result['error']['code'] == 'timeout', result
    detail = result['error']['details']
    assert detail['status'] == ('completed' if stage == 'enrichment' else 'running' if stage == 'last_known' else 'unknown')
    assert detail['job_id'] == JOB
    assert JOB in result['error']['hint'] and 'again' in result['error']['hint']
    assert len(requests) == (2 if stage in {'fallback', 'enrichment'} else 1)
    if stage == 'body':
        assert body.closed
    print(json.dumps({'stage': stage, 'budget': .07, 'elapsed': elapsed, 'requests': len(requests)}))


@pytest.mark.parametrize('domain', ['generation', 'training'])
@pytest.mark.parametrize('pending', ['queued', 'running'])
async def test_pending_timeout_then_same_id_recovery_without_mutations(monkeypatch, domain, pending):
    done = False
    def respond(req):
        if domain == 'training' and req.url.path == GEN:
            return 404, {'detail': 'not found'}
        return completed(image_id=901, image_path='a.png') if done and domain == 'generation' and req.url.path == GEN else {'id': 901, 'image_path': 'a.png'} if done and domain == 'generation' else {'ok': True, 'status': 'completed' if done else pending}
    with backend(monkeypatch, respond) as requests:
        first = await call(.025)
        done = True
        second = await call()
    assert first['error']['code'] == 'timeout'
    assert first['error']['details']['status'] == pending
    assert second['ok'] is True
    assert second['data']['job_domain'] == domain
    assert second['data']['job_id'] == JOB
    assert len(requests) == (3 if domain == 'generation' else 4)


async def test_high_timeout_is_clamped_to_overall_policy(monkeypatch):
    from mcp_server.tools import wait_for_job as wait
    assert wait.MAX_WAIT_SECONDS == 50.0
    monkeypatch.setattr(wait, 'MAX_WAIT_SECONDS', .04)
    async def respond(req):
        await asyncio.sleep(.4)
        return {'status': 'queued'}
    start = time.monotonic()
    with backend(monkeypatch, respond) as requests:
        result = await call(999999)
    assert time.monotonic()-start < .25
    assert result['error']['code'] == 'timeout'
    assert result['error']['details']['timeout_seconds'] == .04
    assert len(requests) == 1


@pytest.mark.parametrize('timeout', [0, -1, float('inf'), float('nan')])
async def test_invalid_timeout_rejected_before_http(monkeypatch, timeout):
    with backend(monkeypatch, lambda req: pytest.fail('must validate first')) as requests:
        result = await call(timeout)
    assert result['error']['code'] == 'request_validation_failed'
    assert requests == []


async def test_training_http_failure_uses_existing_safe_projection(monkeypatch):
    def respond(req):
        if req.url.path == GEN:
            return 404, {'detail': 'absent'}
        return 503, {'detail': {'code': 'unexpected_error', 'message': 'SECRET private diagnostic', 'hint': 'SECRET', 'details': {'private': 'SECRET'}}}
    with backend(monkeypatch, respond) as requests:
        result = await call()
    assert result['ok'] is False
    assert 'SECRET' not in json.dumps(result)
    assert result['error']['details']['job_id'] == JOB
    assert len(requests) == 2


async def test_deadline_consumed_by_non_yielding_status_prevents_enrichment(monkeypatch):
    def respond(req):
        time.sleep(.035)  # CPU/non-yielding transport work also consumes budget.
        return completed([artifact(1)])
    with backend(monkeypatch, respond) as requests:
        result = await call(.02)
    assert result['error']['code'] == 'timeout'
    assert result['error']['details']['status'] == 'completed'
    assert len(requests) == 1


async def test_deadline_includes_response_preparation(monkeypatch):
    from mcp_server.tools import wait_for_job as wait
    real = wait.envelope
    def slow_prepare(value):
        time.sleep(.03)
        return real(value)
    monkeypatch.setattr(wait, 'envelope', slow_prepare)
    with backend(monkeypatch, lambda req: (404, {'detail': 'absent'}) if req.url.path == GEN else {'ok': True, 'status': 'completed'}):
        result = await call(.02)
    assert result['error']['code'] == 'timeout'
    assert result['error']['details']['status'] == 'completed'


async def test_metadata_read_failure_keeps_all_identities_and_backend_recovery(monkeypatch):
    rows = [artifact(10, 'good.png'), artifact(20, 'later.png')]
    def respond(req):
        if req.url.path == GEN:
            return completed(rows)
        return 503, {'detail': {'code': 'metadata_busy', 'message': 'Metadata read busy', 'hint': 'Read same job later.', 'details': {'phase': 'gallery'}}}
    with backend(monkeypatch, respond) as requests:
        result = await call()
    assert result['error']['code'] == 'metadata_busy'
    assert result['error']['hint'] == 'Read same job later.'
    assert result['error']['details']['status'] == 'completed'
    assert [a['artifact_id'] for a in result['error']['details']['artifacts']] == [10, 20]
    assert len(requests) == 2


async def test_unavailable_legacy_image_keeps_full_separate_identity_set(monkeypatch):
    row = artifact(12, 'available.png')
    def respond(req):
        if req.url.path == GEN:
            return completed([row], image_id=901, image_path='/container/outside.png')
        return row if '/artifacts/' in req.url.path else {'id': 901, 'image_path': '/container/outside.png', 'image_url': None}
    with backend(monkeypatch, respond):
        result = await call()
    detail = result['error']['details']
    assert result['error']['code'] == 'artifact_locator_unavailable'
    assert detail['status'] == 'completed'
    assert detail['artifacts'][0]['artifact_id'] == 12
    assert detail['artifacts'][0]['local_path'] == str(GALLERY / 'available.png')
    assert detail['images'][0]['image_id'] == 901 and detail['images'][0]['artifact_id'] is None
    assert detail['images'][0]['local_path'] is None and detail['images'][0]['image_url'] is None
    assert detail['unavailable_locators'][0]['image_id'] == 901


async def test_detail_lookup_must_not_replace_known_artifact_identity(monkeypatch):
    row = artifact(12, 'known.png')
    with backend(monkeypatch, lambda req: completed([row]) if req.url.path == GEN else artifact(99, 'other.png')):
        result = await call()
    assert result['error']['code'] == 'artifact_locator_unavailable'
    assert result['error']['details']['artifacts'][0]['artifact_id'] == 12
    assert result['error']['details']['artifacts'][0]['local_path'] is None


async def test_supported_host_locator_survives_an_unavailable_url(monkeypatch):
    row = artifact(12, 'known.png', artifact_url='https://evil.invalid/remote.png')
    with backend(monkeypatch, lambda req: completed([row]) if req.url.path == GEN else row):
        result = await call()
    assert result['error']['code'] == 'artifact_locator_unavailable'
    result = result['error']['details']['artifacts'][0]
    assert result['local_path'] == str(GALLERY / 'known.png')
    assert result['artifact_url'] is None


@pytest.mark.parametrize('job', ['legacy-image-only', 'mixed-media', 'absolute-media', 'train-completed', 'train-failed', 'train-cancelled', 'train-smoke', 'train-smoke-legacy', 'train-smoke-pending', 'train-smoke-failed', 'train-smoke-cancelled', 'train-smoke-unavailable'])
async def test_fresh_real_backend_route_exports_through_registered_wait(monkeypatch, tmp_path, job):
    """Pinned route/SQLite export; only HTTP transport is replaced in this reader.

    Producer/reproducer: delivery-1-evidence/backend-shape-export.py.txt.
    Fixture files are synthetic; this test performs no product service read.
    """
    exported = json.loads((Path(__file__).parent/'fixtures/wait_http_export.json').read_text(encoding='utf-8'))
    responses = exported['responses']
    def respond(req):
        return responses.get(req.url.path, (404, {'detail': 'Job not found'}))
    with backend(monkeypatch, respond, tmp_path/'gallery') as requests:
        blocks, result = await mcp.call_tool('wait_for_job', {'job_id': job, 'timeout_seconds': 1})
    assert json.loads(blocks[0].text) == result
    if job in {'absolute-media', 'train-failed', 'train-cancelled'}:
        assert result['ok'] is False
        data = result['error']['details']
        assert data['status'] == {'absolute-media': 'completed', 'train-failed': 'failed', 'train-cancelled': 'cancelled'}[job]
    else:
        assert result['ok'] is True, result
        data = result['data']
        assert data['status'] == 'completed'
    assert data['job_id'] == job
    if job.startswith('train-'):
        assert data['artifacts'] == []
        original = responses['/api/lora-train/jobs/'+job]
        for key in ('output_path', 'registration_status', 'smoke_test_status', 'smoke_test_job_id', 'smoke_test_artifact_id', 'smoke_test_image_id', 'smoke_test_artifact', 'smoke_test_artifact_url', 'smoke_test_error_code'):
            assert data[key] == original[key]
        assert len(requests) == 2  # never read or submit independent smoke
    elif job == 'mixed-media':
        assert [a['artifact_id'] for a in data['artifacts']] == [41, 42]
        assert data['artifacts'][0]['artifact_url'] == 'http://backend.invalid/gallery/run/%E6%97%85%20%E4%BA%BA.png'
    elif job == 'legacy-image-only':
        assert data['artifacts'] == [] and data['images'][0]['image_id'] == 901
