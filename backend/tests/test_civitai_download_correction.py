"""Correction1: registered callers, actual commits and deterministic owner overlap.

HTTPX replaces external HTTP only; Settings/file credentials, operation deadlines,
ORM transactions and files remain real. Regressions fail when current failure or
admission ownership is bypassed, rather than when an internal helper is renamed.
"""
import hashlib
import json
import threading

import httpx
import pytest

from app.db import database
from app.db.models import DownloadedResource
from app.services import civitai_provider as provider
from app.services import civitai_resource_install as install
from app.services.resource_records import project_resource
from tests.test_civitai_download_callers import descriptor
from tests.test_resource_record_writers import boundary, acquire_http

_HTTPClient = httpx.AsyncClient


def retained(b):
    return b.client.post('/api/civitai-recipes/resource-install', json={
        'selected': descriptor(b), 'storage_root': 'loras'})


def state(b, rid):
    return b.client.get('/api/civitai/resources/status', params={
        'acquisition_id': rid}).json()['resources'][0]


def seed(b, *, final=False):
    selected = descriptor(b)
    target = b.tmp/'loras'/selected['name']
    if final:
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b.body)
    with database.SessionLocal() as db:
        row = DownloadedResource(provider='civitai', resource_type='lora',
            resource_name=selected['name'], status='planned',
            source_url=selected['download_url_identity'], model_id='10', version_id='21',
            civitai_file_id='32', sha256=b.sha, file_size=len(b.body),
            local_path=str(target), storage_root='loras', notes=' exact historical notes ')
        db.add(row); db.commit()
        return row.id, target


def columns(rid):
    with database.SessionLocal() as db:
        row = db.get(DownloadedResource, rid)
        return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@pytest.mark.parametrize('adverse', ['deadline', 'replacement'])
@pytest.mark.parametrize('existing', [False, True])
def test_adoption_current_failure_keeps_actual_reason_id_and_history(boundary, monkeypatch, adverse, existing):
    b = boundary
    if existing:
        rid, target = seed(b, final=True)
    else:
        rid = None; target = b.tmp/'loras'/descriptor(b)['name']
        target.parent.mkdir(); target.write_bytes(b.body)
    operations = []; original_init = provider.ProviderOperation.__init__
    def init(self, *args, **kw):
        original_init(self, *args, **kw); operations.append(self)
    monkeypatch.setattr(provider.ProviderOperation, '__init__', init)
    cls = database.SessionLocal.class_; commit = cls.commit; measured = []
    def committed(db):
        installed = [r for r in [*db.dirty, *db.new] if isinstance(r, DownloadedResource) and r.status == 'installed']
        commit(db)
        if installed and not measured:
            measured.append(json.loads(installed[0].metadata_json)['verification'])
            if adverse == 'deadline':
                for operation in operations: operation.deadline = -1
            else:
                target.rename(target.with_suffix('.original'))
                target.write_bytes(b'foreign replacement')
    monkeypatch.setattr(cls, 'commit', committed)
    response = retained(b)
    assert measured and response.status_code == 500, response.text
    with database.SessionLocal() as db:
        row = db.query(DownloadedResource).one()
        assert rid is None or row.id == rid
        rid = row.id
        assert row.status == 'failed'
        assert json.loads(row.metadata_json)['verification'] == measured[0]
        assert project_resource(row).sha256_verified is (True if adverse == 'deadline' else None)
        if existing: assert row.notes == ' exact historical notes '
    code = 'civitai_timeout' if adverse == 'deadline' else 'civitai_file_changed'
    diagnostic = response.json()['detail']['diagnostic']
    current = state(b, rid)
    assert diagnostic['resource_id'] == rid and diagnostic['code'] == code and diagnostic['hint']
    assert current['error']['code'] == code and current['error']['hint'] == diagnostic['hint']
    assert current['status'] == 'failed'
    assert target.read_bytes() == (b.body if adverse == 'deadline' else b'foreign replacement')
    if adverse == 'replacement': assert target.with_suffix('.original').read_bytes() == b.body
    assert not [p for p, _ in b.seen if '/api/download/' in p]
    print('CORRECTION_ADOPTION='+json.dumps({'adverse': adverse, 'existing': existing,
        'resource_id': rid, 'http': response.status_code, 'diagnostic': diagnostic,
        'status': current['status'], 'historical_measurement_retained': True}))


@pytest.mark.parametrize('phase', ['pending', 'running'])
@pytest.mark.parametrize('late_target', [False, True])
def test_active_acquire_refuses_retained_without_mutating_owner(boundary, monkeypatch, phase, late_target):
    b = boundary; rid, target = seed(b)
    first = acquire_http(b); assert first.json()['resource']['acquisition_id'] == rid
    owner = b.pending.pop(); before = columns(rid)
    def competitor():
        if late_target:
            target.parent.mkdir(exist_ok=True); target.write_bytes(b'late foreign target')
        prior = target.read_bytes() if target.exists() else None
        response = retained(b)
        assert response.status_code == 409, response.text
        diagnostic = response.json()['detail']['diagnostic']
        assert diagnostic['code'] == 'civitai_resource_active' and diagnostic['resource_id'] == rid and diagnostic['hint']
        assert columns(rid) == before
        assert (target.read_bytes() if target.exists() else None) == prior
        assert not list(b.tmp.rglob('*.part'))
    if phase == 'pending':
        competitor(); assert not [p for p, _ in b.seen if '/api/download/' in p]
    else:
        original = provider.ProviderDownloadTransport.get
        entered = []
        def get(self, *args, **kw):
            if not entered:
                entered.append(True)
                competitor()
            return original(self, *args, **kw)
        monkeypatch.setattr(provider.ProviderDownloadTransport, 'get', get)
    owner()
    after = state(b, rid)
    assert after['status'] == ('failed' if late_target else 'installed')
    if late_target:
        assert after['error']['code'] == 'civitai_target_exists'
        assert target.read_bytes() == b'late foreign target'
    else: assert target.read_bytes() == b.body
    assert columns(rid)['notes'] == before['notes']
    print('CORRECTION_ACTIVE='+json.dumps({'phase': phase, 'late_target': late_target,
        'resource_id': rid, 'after': after['status'], 'body_requests': len([p for p, _ in b.seen if '/api/download/' in p])}))


def test_active_ownership_rechecked_after_retained_preflight(boundary, monkeypatch):
    b = boundary; rid, target = seed(b)
    original = install.preflight_download; fired = []
    def preflight(*args, **kw):
        result = original(*args, **kw)
        if not fired:
            fired.append(True)
            first = acquire_http(b)
            assert first.json()['resource']['acquisition_id'] == rid
        return result
    monkeypatch.setattr(install, 'preflight_download', preflight)
    before = columns(rid)
    response = retained(b)
    assert fired and response.status_code == 409, response.text
    assert response.json()['detail']['diagnostic']['resource_id'] == rid
    during = columns(rid)
    assert during['status'] == 'downloading' and during['notes'] == before['notes']
    assert not [p for p, _ in b.seen if '/api/download/' in p]
    b.pending.pop()()
    assert state(b, rid)['status'] == 'installed'


def test_retained_owner_is_unchanged_by_active_acquire_and_retained_call(boundary, monkeypatch):
    b = boundary; rid, target = seed(b); original = provider.ProviderDownloadTransport.get; fired = []
    def get(self, *args, **kw):
        if not fired:
            fired.append(True); before = columns(rid)
            reused = acquire_http(b)
            assert reused.json()['resource']['acquisition_id'] == rid and not b.pending
            assert columns(rid) == before
            refused = retained(b)
            assert refused.status_code == 409, refused.text
            assert refused.json()['detail']['diagnostic']['resource_id'] == rid
            assert columns(rid) == before
        return original(self, *args, **kw)
    monkeypatch.setattr(provider.ProviderDownloadTransport, 'get', get)
    response = retained(b)
    assert response.status_code == 200 and response.json()['ledger_id'] == rid
    assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body
    assert len([p for p, _ in b.seen if '/api/download/' in p]) == 1


@pytest.mark.parametrize('entry', ['acquire', 'install'])
def test_failed_retry_and_inactive_verified_reuse_remain_useful(boundary, entry):
    b = boundary; rid, target = seed(b); b.failure[0] = True
    def submit():
        if entry == 'acquire':
            response = acquire_http(b)
            assert response.json()['resource']['acquisition_id'] == rid
            if b.pending: b.pending.pop()()
        else: response = retained(b)
        return response
    submit(); assert state(b, rid)['status'] == 'failed'
    b.failure[0] = False; submit()
    assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body
    count = len([p for p, _ in b.seen if '/api/download/' in p]); submit()
    assert len([p for p, _ in b.seen if '/api/download/' in p]) == count
    with database.SessionLocal() as db:
        assert db.query(DownloadedResource).count() == 1
        assert db.get(DownloadedResource, rid).notes == ' exact historical notes '


@pytest.mark.parametrize('fault', ['admission', 'publication', 'unavailable'])
@pytest.mark.parametrize('existing', [False, True])
def test_adoption_database_failure_controls_preserve_adopted_bytes(boundary, monkeypatch, fault, existing):
    b = boundary
    if existing: rid, target = seed(b, final=True)
    else:
        rid = None; target = b.tmp/'loras'/descriptor(b)['name']
        target.parent.mkdir(); target.write_bytes(b.body)
    before = columns(rid) if rid else None
    cls = database.SessionLocal.class_; commit = cls.commit; rejected = []; operations = []
    original_init = provider.ProviderOperation.__init__
    def init(self, *args, **kw):
        original_init(self, *args, **kw); operations.append(self)
    monkeypatch.setattr(provider.ProviderOperation, '__init__', init)
    def controlled(db):
        rows = [r for r in [*db.new, *db.dirty] if isinstance(r, DownloadedResource)]
        if fault == 'admission' or (fault == 'unavailable' and rejected):
            raise RuntimeError('synthetic unavailable database')
        if any(r.status == 'installed' for r in rows) and not rejected:
            rejected.append(True)
            if fault == 'publication': raise RuntimeError('synthetic rejected commit')
            commit(db)
            for operation in operations: operation.deadline = -1
            return
        commit(db)
    monkeypatch.setattr(cls, 'commit', controlled)
    response = retained(b)
    assert response.status_code == 500 and target.read_bytes() == b.body
    diagnostic = response.json()['detail']['diagnostic']
    if fault == 'admission':
        assert diagnostic['code'] == 'ledger_persistence_failed'
        if existing: assert columns(rid) == before
        else:
            with database.SessionLocal() as db: assert db.query(DownloadedResource).count() == 0
    else:
        with database.SessionLocal() as db:
            row = db.query(DownloadedResource).one()
            assert rid is None or row.id == rid
            assert diagnostic['resource_id'] == row.id
            assert diagnostic['code'] == ('civitai_timeout' if fault == 'unavailable' else 'ledger_persistence_failed')
            assert row.status == ('installed' if fault == 'unavailable' else 'failed')
            if existing: assert row.notes == before['notes']
    assert not [p for p, _ in b.seen if '/api/download/' in p]


def test_active_partial_and_metadata_survive_both_competing_callers(boundary, monkeypatch):
    b = boundary; b.body = b'x'*(2*1024*1024); b.sha = hashlib.sha256(b.body).hexdigest()
    b.file['sizeKB'] = 2048; b.file['hashes']['SHA256'] = b.sha
    rid, target = seed(b)
    # The fixture's original HTTP handler closes over its original short body;
    # substitute only external HTTP, still using production request machinery.
    def wire(request):
        b.seen.append((request.url.path, request.headers.get('authorization')))
        if '/api/v1/' in request.url.path:
            return httpx.Response(200, json=b.model if '/models/' in request.url.path else b.version)
        return httpx.Response(200, content=b.body)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: _HTTPClient(transport=httpx.MockTransport(wire), **kw))
    cls = database.SessionLocal.class_; commit = cls.commit; checked = []
    def committed(db):
        commit(db)
        part = target.with_name(target.name+'.part')
        if part.exists() and part.stat().st_size == 1024*1024 and not checked:
            checked.append(True); before = columns(rid); prefix = part.read_bytes(); stat = part.stat()
            response = retained(b)
            assert response.status_code == 409, response.text
            reused = acquire_http(b)
            assert reused.json()['resource']['acquisition_id'] == rid and not b.pending
            assert columns(rid) == before
            assert part.read_bytes() == prefix and part.stat() == stat
    monkeypatch.setattr(cls, 'commit', committed)
    assert acquire_http(b).json()['resource']['acquisition_id'] == rid
    b.pending.pop()()
    assert checked and state(b, rid)['status'] == 'installed'
    assert target.read_bytes() == b.body
    assert len([p for p, _ in b.seen if '/api/download/' in p]) == 1


def test_simultaneous_retained_admission_selects_one_owner(boundary, monkeypatch):
    b = boundary; rid, target = seed(b); entered = threading.Event(); release = threading.Event()
    original = provider.ProviderDownloadTransport.get; outcomes = []
    def get(self, *args, **kw):
        entered.set()
        assert release.wait(5), 'test must release the real admitted owner'
        return original(self, *args, **kw)
    monkeypatch.setattr(provider.ProviderDownloadTransport, 'get', get)
    def owner(): outcomes.append(retained(b))
    thread = threading.Thread(target=owner); thread.start()
    try:
        assert entered.wait(5), 'owner must reach body boundary'
        before = columns(rid); refused = retained(b)
        assert refused.status_code == 409, refused.text
        assert refused.json()['detail']['diagnostic']['resource_id'] == rid
        assert columns(rid) == before
        assert not [p for p, _ in b.seen if '/api/download/' in p]
    finally:
        release.set(); thread.join(5)
    assert not thread.is_alive() and outcomes[0].status_code == 200
    assert state(b, rid)['status'] == 'installed' and target.read_bytes() == b.body
    with database.SessionLocal() as db: assert db.query(DownloadedResource).count() == 1
