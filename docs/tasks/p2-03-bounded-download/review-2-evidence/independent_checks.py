"""QA2 checks: actual registered callers and commits, synthetic external I/O only."""
import asyncio
import hashlib
import json
import threading
from datetime import datetime

import httpx
import pytest

from tests.conftest import client, isolated_database, isolated_worker_admission
from tests.test_resource_record_writers import boundary, acquire_http
from tests.test_civitai_download_callers import descriptor
from app.db import database
from app.db.models import DownloadedResource
from app.services import civitai_provider as provider
from app.services import civitai_resource_install as install
from app.services.resource_records import project_resource
from mcp_server.server import mcp as server

HTTP_CLIENT = httpx.AsyncClient


def retained(b):
    return b.client.post('/api/civitai-recipes/resource-install', json={
        'selected': descriptor(b), 'storage_root': 'loras'})


def columns(rid):
    with database.SessionLocal() as db:
        row = db.get(DownloadedResource, rid)
        return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def state(b, rid):
    response = b.client.get('/api/civitai/resources/status', params={'acquisition_id': rid})
    assert response.status_code == 200
    return response.json()['resources'][0]


def seed(b, final=False):
    selected = descriptor(b)
    target = b.tmp/'loras'/selected['name']
    if final:
        target.parent.mkdir(); target.write_bytes(b.body)
    with database.SessionLocal() as db:
        row = DownloadedResource(provider='civitai', resource_type='lora',
            resource_name=selected['name'], status='failed',
            source_url=selected['download_url_identity'], model_id='10', version_id='21',
            civitai_file_id='32', sha256=b.sha, file_size=len(b.body),
            local_path=str(target), storage_root='loras',
            downloaded_at=datetime(2020, 1, 2),
            notes=' retained notes Authorization: Bearer old-private-value ')
        db.add(row); db.commit()
        return row.id, target


@pytest.mark.parametrize('adverse', ['deadline', 'same_bytes_replacement', 'deleted'])
def test_committed_adoption_reports_actual_current_reason_and_keeps_history(boundary, monkeypatch, adverse):
    b = boundary; rid, target = seed(b, final=True); before = columns(rid)
    operations = []; init = provider.ProviderOperation.__init__
    def capture(self, *a, **kw):
        init(self, *a, **kw); operations.append(self)
    monkeypatch.setattr(provider.ProviderOperation, '__init__', capture)
    cls = database.SessionLocal.class_; commit = cls.commit; committed = []
    def after_commit(db):
        installed = [r for r in db.dirty if isinstance(r, DownloadedResource) and r.status == 'installed']
        commit(db)
        if installed and not committed:
            with database.SessionLocal() as reader:
                actual = reader.get(DownloadedResource, rid)
                assert actual.status == 'installed'
                committed.append(json.loads(actual.metadata_json)['verification'])
            if adverse == 'deadline':
                operations[-1].deadline = -1
            else:
                target.rename(target.with_suffix('.preserved'))
                if adverse == 'same_bytes_replacement': target.write_bytes(b.body)
    monkeypatch.setattr(cls, 'commit', after_commit)
    response = retained(b); current = state(b, rid); after = columns(rid)
    expected = 'civitai_timeout' if adverse == 'deadline' else 'civitai_file_changed'
    print('QA2_ADOPTION='+json.dumps({'adverse': adverse, 'http': response.status_code,
        'response': response.json(), 'current': current, 'committed': bool(committed)}))
    assert committed and response.status_code == 500
    assert current['status'] == 'failed' and after['status'] == 'failed'
    diagnostic = response.json()['detail']['diagnostic']
    assert diagnostic['resource_id'] == rid and diagnostic['code'] == expected and diagnostic['hint']
    assert current['error']['code'] == expected and current['error']['hint'] == diagnostic['hint']
    assert after['notes'] == before['notes'] and after['downloaded_at'] == before['downloaded_at']
    for key in ['id', 'sha256', 'file_size', 'model_id', 'version_id', 'civitai_file_id', 'local_path']:
        assert after[key] == before[key]
    assert json.loads(after['metadata_json'])['verification'] == committed[0]
    with database.SessionLocal() as db:
        assert db.query(DownloadedResource).count() == 1
        assert project_resource(db.get(DownloadedResource, rid)).sha256_verified is (True if adverse == 'deadline' else None)
    if adverse == 'deleted': assert not target.exists()
    else: assert target.read_bytes() == b.body
    if adverse != 'deadline': assert target.with_suffix('.preserved').read_bytes() == b.body
    assert not [p for p, _ in b.seen if '/api/download/' in p]
    assert 'old-private-value' not in response.text


@pytest.fixture
def mcp_boundary(boundary, monkeypatch):
    # Bridge only the MCP adapter's HTTP channel into the actual ASGI test app.
    b = boundary; cls = httpx.Client
    class BackendClient(cls):
        def __init__(self, **kw): super().__init__(transport=b.client._transport, **kw)
    monkeypatch.setattr(httpx, 'Client', BackendClient)
    return b


def mcp(name, args):
    outcomes = []; errors = []
    def invoke():
        try: outcomes.append(asyncio.run(server.call_tool(name, args))[1])
        except BaseException as exc: errors.append(exc)
    worker = threading.Thread(target=invoke); worker.start(); worker.join(10)
    assert not worker.is_alive(), 'registered MCP fixture must complete'
    if errors: raise errors[0]
    result = outcomes[0]
    assert result['ok'], result
    return result['data']


@pytest.mark.parametrize('phase', ['pending', 'streaming'])
@pytest.mark.parametrize('late_target', [False, True])
def test_registered_mcp_owner_survives_competing_retained_and_acquire(mcp_boundary, monkeypatch, phase, late_target):
    b = mcp_boundary
    if phase == 'streaming':
        b.body = b'q' * (1024*1024+5); b.sha = hashlib.sha256(b.body).hexdigest()
        b.file['sizeKB'] = len(b.body)/1024; b.file['hashes']['SHA256'] = b.sha
    rid, target = seed(b)
    admitted = mcp('civitai_resource_acquire', {'source': 'https://civitai.com/models/10?modelVersionId=21'})
    assert admitted['resource']['acquisition_id'] == rid and len(b.pending) == 1
    invoked = []; closed = []
    def competitors():
        invoked.append(True)
        if late_target:
            target.parent.mkdir(exist_ok=True); target.write_bytes(b'late foreign bytes')
        before = columns(rid)
        part = target.with_name(target.name+'.part')
        part_before = (part.read_bytes(), part.stat()) if part.exists() else None
        if phase == 'streaming':
            assert part_before is not None and len(part_before[0]) == 1024*1024
        body_count = len([p for p, _ in b.seen if '/api/download/' in p])
        refused = retained(b)
        reused = mcp('civitai_resource_acquire', {'source': 'https://civitai.com/models/10?modelVersionId=21'})
        print('QA2_OWNER='+json.dumps({'phase':phase, 'late_target':late_target,
            'http':refused.status_code, 'body':refused.json(), 'resource_id':rid}))
        assert refused.status_code == 409
        diagnostic = refused.json()['detail']['diagnostic']
        assert diagnostic['code'] == 'civitai_resource_active' and diagnostic['resource_id'] == rid and diagnostic['hint']
        assert reused['resource']['acquisition_id'] == rid and reused['status'] == 'downloading'
        assert columns(rid) == before
        assert len([p for p, _ in b.seen if '/api/download/' in p]) == body_count
        assert ((part.read_bytes(), part.stat()) if part.exists() else None) == part_before
        if late_target: assert target.read_bytes() == b'late foreign bytes'
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b.body[:1024*1024]
            competitors()
            yield b.body[1024*1024:]
        async def aclose(self): closed.append(True)
    def wire(request):
        b.seen.append((request.url.path, request.headers.get('authorization')))
        if '/api/v1/' in request.url.path:
            return httpx.Response(200,json=b.model if '/models/' in request.url.path else b.version)
        return httpx.Response(200,stream=Body())
    if phase == 'pending': competitors()
    else: monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: HTTP_CLIENT(transport=httpx.MockTransport(wire), **kw))
    b.pending.pop()()
    current = mcp('civitai_resource_status', {'acquisition_id': rid})['resources'][0]
    assert invoked and not b.pending
    assert current['status'] == ('failed' if late_target else 'installed')
    if late_target:
        assert current['error']['code'] == 'civitai_target_exists' and target.read_bytes() == b'late foreign bytes'
    else: assert target.read_bytes() == b.body
    if phase == 'streaming': assert closed
    assert columns(rid)['notes'] == ' retained notes Authorization: Bearer old-private-value '


@pytest.mark.parametrize('adoption', [False, True])
def test_late_owner_claim_during_preflight_is_rechecked_at_admission(mcp_boundary, monkeypatch, adoption):
    b = mcp_boundary; rid, target = seed(b, final=adoption)
    hook = 'verified_existing' if adoption else 'preflight_download'
    original = getattr(install, hook); claims = []
    def competing_claim(*a, **kw):
        result = original(*a, **kw)
        if not claims:
            claims.append(mcp('civitai_resource_acquire', {'source': 'https://civitai.com/models/10?modelVersionId=21'}))
        return result
    monkeypatch.setattr(install, hook, competing_claim)
    before = columns(rid); response = retained(b)
    assert claims and response.status_code == 409, response.text
    assert response.json()['detail']['diagnostic']['resource_id'] == rid
    assert columns(rid)['status'] == 'downloading' and columns(rid)['notes'] == before['notes']
    assert not [p for p, _ in b.seen if '/api/download/' in p]
    b.pending.pop()()
    assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body


def test_registered_inactive_reuse_and_failed_retry_remain_useful(mcp_boundary):
    b = mcp_boundary; rid, target = seed(b)
    b.failure[0] = True
    assert retained(b).status_code == 500 and state(b, rid)['status'] == 'failed'
    b.failure[0] = False
    assert retained(b).json()['ledger_id'] == rid and state(b, rid)['status'] == 'installed'
    calls = len([p for p, _ in b.seen if '/api/download/' in p])
    assert retained(b).json()['ledger_id'] == rid
    reused = mcp('civitai_resource_acquire', {'source': 'https://civitai.com/models/10?modelVersionId=21'})
    assert reused['resource']['acquisition_id'] == rid and not b.pending
    assert len([p for p, _ in b.seen if '/api/download/' in p]) == calls
    assert target.read_bytes() == b.body
