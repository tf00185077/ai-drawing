"""Durable operation outcomes through registered callers and real SQLite.

Only external HTTP and thread scheduling use the established synthetic fixture.
Removing durable admission, replay or DB-only reads breaks public assertions.
"""
import json
import pytest
from app.db import database
from tests.test_resource_record_writers import boundary


def submit(b, key=None):
    body = {'locator': 'https://civitai.com/models/10?modelVersionId=21'}
    if key is not None:
        body['idempotency_key'] = key
    return b.client.post('/api/civitai/resources/acquire', json=body)


def job(b, identity):
    response = b.client.get('/api/civitai/download-jobs/' + identity)
    assert response.status_code == 200, response.text
    return response.json()


def test_registered_admission_commits_job_and_owner_before_launch(boundary):
    b = boundary
    response = submit(b, 'admission-1')
    assert response.status_code == 202, response.text
    value = response.json()
    assert value.get('job_id', '').startswith('dl_'), value
    persisted = job(b, value['job_id'])
    assert persisted['job_domain'] == 'download'
    assert persisted['status'] == 'queued'
    assert persisted['resource_ids'] == [value['resource']['acquisition_id']]
    assert persisted['components'][0]['downloaded_bytes'] == 0
    assert persisted['updated_at']
    assert len(b.pending) == 1
    assert not [p for p, _ in b.seen if '/api/download/' in p]


@pytest.mark.parametrize('failed', [False, True])
def test_same_key_replays_terminal_history_and_new_key_is_new_operation(boundary, failed):
    b = boundary
    first = submit(b, 'same-key').json()
    assert first.get('job_id'), first
    b.failure[0] = failed
    b.pending.pop()()
    before = job(b, first['job_id'])
    assert before['status'] == ('failed' if failed else 'completed')
    calls = len(b.seen)
    replay = submit(b, 'same-key').json()
    assert replay['job_id'] == first['job_id'] and not b.pending
    assert job(b, first['job_id']) == before
    assert not [p for p, _ in b.seen[calls:] if '/api/download/' in p]
    if failed:
        b.failure[0] = False
        retry = submit(b, 'new-key').json()
        assert retry['job_id'] != first['job_id']
        assert retry['resource']['acquisition_id'] == first['resource']['acquisition_id']
        b.pending.pop()()
        assert job(b, retry['job_id'])['status'] == 'completed'
        assert job(b, first['job_id']) == before


def test_conflicting_key_and_active_replay_do_not_mutate_or_launch(boundary):
    b = boundary
    first = submit(b, 'binding').json()
    assert first.get('job_id'), first
    before = job(b, first['job_id'])
    assert submit(b).json()['job_id'] == first['job_id']
    b.file['hashes']['SHA256'] = 'f' * 64
    response = submit(b, 'binding')
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'download_idempotency_conflict'
    assert 'binding' not in response.text
    assert job(b, first['job_id']) == before and len(b.pending) == 1


@pytest.mark.parametrize('key', ['', 'a b', 'é', 'x' * 129, True])
def test_invalid_key_refuses_before_provider_or_admission(boundary, key):
    b = boundary
    response = submit(b, key)
    assert response.status_code == 422
    assert not b.seen and not b.pending


def test_status_uses_stored_measurements_without_model_stat(boundary, monkeypatch):
    b = boundary
    first = submit(b).json()
    assert first.get('job_id'), first
    b.pending.pop()()
    before = job(b, first['job_id'])
    from pathlib import Path
    original = Path.stat
    def stat(path, *args, **kwargs):
        assert not str(path).endswith(('.safetensors', '.part')), str(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    assert job(b, first['job_id']) == before
    status = b.client.get('/api/civitai/resources/status', params={
        'acquisition_id': first['resource']['acquisition_id']}).json()['resources'][0]
    assert status['job_id'] == first['job_id']
    assert before['components'][0]['downloaded_bytes'] == len(b.body)
    assert before['components'][0]['status'] == 'completed'
    assert 'SIGNED' not in json.dumps(before)


def test_retained_install_creates_and_finishes_the_same_durable_domain(boundary):
    from tests.test_civitai_download_callers import descriptor
    b = boundary
    response = b.client.post('/api/civitai-recipes/resource-install', json={
        'selected': descriptor(b), 'storage_root': 'loras'})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value.get('job_id', '').startswith('dl_'), value
    persisted = job(b, value['job_id'])
    assert persisted['status'] == 'completed'
    assert persisted['resource_ids'] == [value['ledger_id']]
    assert persisted['components'][0]['downloaded_bytes'] == len(b.body)


def test_repeated_completed_callback_cannot_change_history_or_submit(boundary):
    b = boundary
    first = submit(b).json()
    callback = b.pending.pop()
    callback()
    before = job(b, first['job_id'])
    calls = len(b.seen)
    callback()
    assert job(b, first['job_id']) == before
    assert len(b.seen) == calls


def test_invalid_key_is_not_echoed_in_validation_diagnostics(boundary):
    raw = 'invalid key private diagnostic value'
    response = submit(boundary, raw)
    assert response.status_code == 422
    assert raw not in response.text


def test_independent_connections_claim_once_without_process_admission_lock(boundary, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import nullcontext
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services import civitai_resource_acquire as acquire
    b = boundary
    engine = create_engine('sqlite:///' + str(b.tmp / 'independent.db'), connect_args={'check_same_thread': False})
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(acquire, 'SessionLocal', factory)
    monkeypatch.setattr(acquire, 'bounded_resource_admission', lambda operation: nullcontext())
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: submit(b, 'simultaneous'), range(2)))
        assert all(r.status_code == 202 for r in responses), [r.text for r in responses]
        identities = {r.json()['job_id'] for r in responses}
        assert len(identities) == 1 and len(b.pending) == 1
        from app.db.models import DownloadJob, DownloadClaim, DownloadedResource
        with factory() as db:
            assert db.query(DownloadJob).count() == db.query(DownloadedResource).count() == 1
            assert db.query(DownloadClaim).count() == 2
        b.pending.pop()()
        assert job(b, identities.pop())['status'] == 'completed'
    finally:
        engine.dispose()


def test_admission_commit_failure_cannot_launch_an_unrecorded_body(boundary, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from app.db.models import DownloadJob, DownloadedResource
    b = boundary
    cls = database.SessionLocal.class_
    original = cls.commit
    def reject(db):
        if any(isinstance(row, DownloadJob) and row.status == 'queued' for row in db.identity_map.values()):
            raise SQLAlchemyError('synthetic admission commit failure')
        return original(db)
    monkeypatch.setattr(cls, 'commit', reject)
    response = submit(b)
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'download_persistence_unavailable'
    assert not b.pending and not [p for p, _ in b.seen if '/api/download/' in p]
    with database.SessionLocal() as db:
        assert db.query(DownloadJob).count() == db.query(DownloadedResource).count() == 0


def test_package_failure_retains_successful_component_without_whole_success(boundary, monkeypatch):
    import httpx
    from app.config import get_settings
    b = boundary
    b.model['type'] = 'Checkpoint'
    b.version['baseModel'] = 'Anima'
    monkeypatch.setenv('COMFYUI_DIFFUSION_MODELS_DIR', str(b.tmp / 'diffusion'))
    get_settings.cache_clear()
    b.version['files'][0]['downloadUrl'] = 'https://civitai.com/api/download/models/20'
    # The fixture has already replaced the client constructor. Capture the
    # actual class from the request module for a separate external HTTP fixture.
    original = httpx._client.AsyncClient
    bodies = []
    def wire(request):
        if '/model-versions/' in request.url.path: return httpx.Response(200, json=b.version)
        if '/api/v1/models/' in request.url.path: return httpx.Response(200, json=b.model)
        bodies.append(request.url.path)
        return httpx.Response(403 if request.url.path.endswith('/21') else 200, content=b.body)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(wire), **kw))
    response = submit(b)
    assert response.status_code == 202, response.text
    identity = response.json()['job_id']
    b.pending.pop()()
    value = job(b, identity)
    assert value['status'] == 'failed'
    assert [c['status'] for c in value['components']] == ['completed', 'failed']
    assert value['components'][0]['result']['sha256'] == b.sha
    assert (b.tmp / 'diffusion' / 'first.safetensors').read_bytes() == b.body
    assert len(bodies) == 2


def test_stale_previous_attempt_cannot_change_new_owner(boundary):
    b = boundary
    first = submit(b, 'old').json()
    old_callback = b.pending.pop()
    b.failure[0] = True
    old_callback()
    terminal = job(b, first['job_id'])
    b.failure[0] = False
    second = submit(b, 'new').json()
    pending = job(b, second['job_id'])
    calls = len(b.seen)
    old_callback()
    assert job(b, second['job_id']) == pending
    assert job(b, first['job_id']) == terminal
    assert len(b.seen) == calls
    b.pending.pop()()
    assert job(b, second['job_id'])['status'] == 'completed'


def test_initial_lifecycle_database_contention_consumes_callers_deadline(boundary, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services import civitai_provider as provider
    from app.services import civitai_resource_acquire as acquire
    import time
    b = boundary
    engine = create_engine('sqlite:///' + str(b.tmp / 'locked.db'), connect_args={'check_same_thread': False})
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(acquire, 'SessionLocal', factory)
    original = provider.ProviderOperation.__init__
    def shortened(self, kind, **kw):
        original(self, kind, **kw)
        if kind == 'download': self.deadline = time.monotonic() + 0.02
    monkeypatch.setattr(provider.ProviderOperation, '__init__', shortened)
    try:
        with engine.connect() as held:
            held.exec_driver_sql('BEGIN EXCLUSIVE')
            response = submit(b)
            assert response.status_code == 422, response.text
            assert response.json()['detail']['code'] == 'civitai_timeout'
            assert not b.pending
            held.rollback()
    finally:
        engine.dispose()
