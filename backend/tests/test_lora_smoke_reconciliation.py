"""Real scratch SQLite/Gallery/queue/HTTP; no worker, network or trainer runs.

These regressions catch submission-only status, cross-job image inference,
unsafe diagnostics, duplicate submissions and lost terminal projections.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import gallery, lora_train
from app.core import queue, recording
from app.db import database
from app.db.models import GeneratedArtifact, GeneratedImage, LoraTrainingJob
from app.schemas.lora_train import LoraSmokeTestRequest
from app.services import lora_trainer


@pytest.fixture
def smoke(tmp_path, monkeypatch):
    def denied(*a, **kw):
        raise AssertionError("offline smoke fixture forbids network/process/worker")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(lora_trainer.subprocess, "Popen", denied)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", denied)
    monkeypatch.setattr(queue, "start_worker", denied)
    engine = create_engine(f"sqlite:///{tmp_path / 'scratch.db'}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine)
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(queue, "SessionLocal", sessions)
    root = tmp_path / "gallery"
    root.mkdir()
    settings = SimpleNamespace(gallery_dir=str(root), lora_train_dir=str(tmp_path / 'train'))
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(gallery, "get_settings", lambda: settings)
    queue._reset_for_test()
    lora_trainer._reset_for_test()
    monkeypatch.setattr(lora_trainer, "submit_generation", denied)
    api = FastAPI()
    api.include_router(lora_train.router)
    api.include_router(gallery.router)
    api.mount('/gallery', StaticFiles(directory=root))
    def get_db():
        with sessions() as db:
            yield db
    api.dependency_overrides[database.get_db] = get_db
    client = TestClient(api)
    with sessions() as db:
        db.add(LoraTrainingJob(job_id='train-1', folder='portraits', status='completed', stage='completed',
            output_name='旅人', resolved_output_name='旅人_002', output_serial=2,
            run_locator='旅人_002__run', output_config_hash='a'*64, output_sha256='b'*64,
            validation_status='validated', registration_status='registered',
            registered_lora_name='products/旅人_002.safetensors',
            params_json=json.dumps({'model_family':'sdxl','checkpoint':'base.safetensors'}),
            smoke_test_status='submitted', smoke_test_job_id='gen-1'))
        db.commit()
    def update(**fields):
        with sessions() as db:
            db.query(LoraTrainingJob).filter_by(job_id='train-1').update(fields)
            db.commit()
    def image(path='run/smoke.png', job='gen-1'):
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (2, 2), 'red').save(file)
        with sessions() as db:
            row = recording.save(path, job_id=job, lora='products/旅人_002.safetensors', db=db)
            return row.id, db.query(GeneratedArtifact).filter_by(job_id=job, gallery_path=path).one().id
    fixture = SimpleNamespace(client=client, sessions=sessions, root=root, update=update, image=image)
    yield fixture
    queue._reset_for_test()
    lora_trainer._reset_for_test()
    engine.dispose()


def status(w):
    response = w.client.get('/api/lora-train/jobs/train-1')
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == result['stage'] == 'completed'
    assert result['output_name'] == '旅人' and result['output_serial'] == 2
    assert result['registered_lora_name'] == 'products/旅人_002.safetensors'
    assert result['output_sha256'] == 'b'*64 and result['output_config_hash'] == 'a'*64
    return result


def test_completed_image_reconciles_after_queue_restart_and_is_retrievable(smoke):
    image_id, artifact_id = smoke.image()
    # The real queue has no state after reset; durable output is sufficient.
    queue._reset_for_test()
    result = status(smoke)
    assert result['smoke_test_status'] == 'completed'
    assert result['smoke_test_artifact'] == 'run/smoke.png'
    assert result['smoke_test_artifact_id'] == artifact_id
    assert result['smoke_test_image_id'] == image_id
    assert result['smoke_test_artifact_url'] == '/gallery/run/smoke.png'
    assert smoke.client.get(result['smoke_test_artifact_url']).content == (smoke.root/'run/smoke.png').read_bytes()
    detail = smoke.client.get(f'/api/gallery/artifacts/{artifact_id}').json()
    assert detail['job_id'] == 'gen-1' and detail['gallery_path'] == 'run/smoke.png'
    assert smoke.client.get(f'/api/gallery/{image_id}').json()['job_id'] == 'gen-1'
    with smoke.sessions() as db:
        row = db.query(LoraTrainingJob).one()
        assert row.smoke_test_status == 'completed' and row.smoke_test_artifact == 'run/smoke.png'
    assert status(smoke) == result


@pytest.mark.parametrize('state', ['queued','running','failed','cancelled'])
def test_queue_states_never_promote_partial_image_or_echo_private_error(smoke, monkeypatch, state):
    smoke.image()
    monkeypatch.setattr(queue, 'get_job_status', lambda job: {'job_id':job, 'status':state,'error':'SECRET_MARKER /private/token'})
    result = status(smoke)
    assert result['smoke_test_status'] == state
    assert result['smoke_test_artifact'] is None
    assert 'SECRET_MARKER' not in json.dumps(result)
    if state in {'failed','cancelled'}:
        assert result['smoke_test_error_code'] == 'smoke_generation_'+state
        assert result['smoke_test_hint']
        monkeypatch.setattr(queue, 'get_job_status', lambda _: None)
        assert status(smoke)['smoke_test_status'] == state


@pytest.mark.parametrize('queue_status,want_code', [(None,'smoke_job_missing'), ('completed','smoke_artifact_unavailable'), ('unrecognized','smoke_job_unknown')])
def test_missing_and_completed_without_images_are_recoverable(smoke, monkeypatch, queue_status, want_code):
    smoke.image('other.png', 'other-job')
    monkeypatch.setattr(queue, 'get_job_status', lambda job: {'job_id':job,'status':queue_status} if queue_status else None)
    result = status(smoke)
    assert result['smoke_test_status'] in {'unknown','artifact_unavailable'}
    assert result['smoke_test_artifact'] is None
    assert result['smoke_test_error_code'] == want_code
    assert result['smoke_test_hint']
    monkeypatch.setattr(queue, 'get_job_status', lambda _: None)
    smoke.image()
    assert status(smoke)['smoke_test_status'] == 'completed'


@pytest.mark.parametrize('bad', ['missing','escape','absolute','symlink','invalid-image','video','wrong-job','conflicting-owner'])
def test_unusable_artifacts_are_not_success(smoke, tmp_path, bad):
    path = 'missing.png'
    job, kind = 'gen-1', 'image'
    if bad in {'escape','absolute','symlink'}:
        outside = tmp_path/'outside.png'
        Image.new('RGB',(2,2)).save(outside)
        if bad == 'escape': path = '../outside.png'
        if bad == 'absolute': path = str(outside)
        if bad == 'symlink':
            path = 'linked.png'; (smoke.root/path).symlink_to(outside)
    if bad == 'invalid-image':
        path = 'invalid.png'; (smoke.root/path).write_bytes(b'not an image')
    if bad in {'video','wrong-job','conflicting-owner'}:
        path='available.png'; Image.new('RGB',(2,2)).save(smoke.root/path)
        if bad == 'video': kind = 'video'
        if bad == 'wrong-job': job = 'other'
    with smoke.sessions() as db:
        db.add(GeneratedArtifact(job_id=job, artifact_type=kind, gallery_path=path))
        if bad == 'conflicting-owner':
            db.add(GeneratedImage(job_id='other',image_path=path))
        db.commit()
    result = status(smoke)
    assert result['smoke_test_status'] != 'completed'
    assert result['smoke_test_artifact'] is None
    assert str(tmp_path) not in json.dumps(result)


def test_deterministic_multiple_artifacts_and_deleted_file_recovery(smoke):
    _, first = smoke.image('first.png')
    smoke.image('second.png')
    assert status(smoke)['smoke_test_artifact_id'] == first
    (smoke.root/'first.png').unlink()
    assert status(smoke)['smoke_test_artifact'] == 'second.png'
    (smoke.root/'second.png').unlink()
    assert status(smoke)['smoke_test_status'] == 'artifact_unavailable'
    smoke.image('restored.png')
    assert status(smoke)['smoke_test_artifact'] == 'restored.png'


def test_legacy_image_without_generic_artifact_is_recoverable(smoke):
    image_id, _ = smoke.image()
    with smoke.sessions() as db:
        db.query(GeneratedArtifact).delete(); db.commit()
    result=status(smoke)
    assert result['smoke_test_status']=='completed'
    assert result['smoke_test_image_id']==image_id
    assert result['smoke_test_artifact_id'] is None


def test_concurrent_smoke_requests_claim_once_and_repeat_reads_never_submit(smoke, monkeypatch):
    smoke.update(smoke_test_status=None, smoke_test_job_id=None)
    entered, release = threading.Event(), threading.Event()
    calls=[]
    def submit(params):
        calls.append(params); entered.set()
        assert release.wait(5)
        return queue.submit(params)
    monkeypatch.setattr(lora_trainer, 'submit_generation', submit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(lora_trainer.smoke_test_job,'train-1',LoraSmokeTestRequest(execution_target='worker'))
        assert entered.wait(5)
        try:
            second=pool.submit(lora_trainer.smoke_test_job,'train-1',LoraSmokeTestRequest()).result(timeout=5)
            assert second['smoke_test_status']=='submitting'
        finally:
            release.set()
        submitted=first.result(timeout=5)
    assert len(calls)==1 and calls[0]['execution_target']=='worker'
    assert calls[0]['lora']=='products/旅人_002.safetensors'
    repeated=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={'prompt':'changed'}).json()
    assert repeated['generation_job_id']==submitted['generation_job_id']
    assert repeated['smoke_test_status']=='queued'
    assert len(calls)==1 and len(queue.get_status()['queue_pending'])==1
    assert status(smoke)['smoke_test_status']=='queued'


def test_uncertain_submit_is_not_retried_even_after_restart(smoke, monkeypatch):
    smoke.update(smoke_test_status=None, smoke_test_job_id=None)
    calls=[]
    def uncertain(params):
        calls.append(params); queue.submit(params)
        raise TimeoutError('SECRET_MARKER /private/token')
    monkeypatch.setattr(lora_trainer,'submit_generation',uncertain)
    response=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
    assert response.status_code==200
    assert response.json()['smoke_test_status']=='submission_unknown'
    assert response.json()['error_code']=='smoke_submission_unknown'
    assert 'SECRET_MARKER' not in response.text
    lora_trainer._reset_for_test()
    again=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
    assert again.json()['smoke_test_status']=='submission_unknown'
    assert len(calls)==1 and len(queue.get_status()['queue_pending'])==1


def test_real_queue_cancellation_is_reconciled_and_persisted(smoke, monkeypatch):
    smoke.update(smoke_test_status=None, smoke_test_job_id=None)
    monkeypatch.setattr(lora_trainer,'submit_generation',queue.submit)
    submitted=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={}).json()
    assert queue.cancel(submitted['generation_job_id']) is True
    assert status(smoke)['smoke_test_status']=='cancelled'
    queue._reset_for_test()
    assert status(smoke)['smoke_test_status']=='cancelled'


def test_stale_status_read_cannot_overwrite_a_newer_terminal_projection(smoke, monkeypatch):
    def stale(job):
        smoke.update(smoke_test_status='failed',smoke_test_error='smoke_generation_failed')
        return {'job_id':job,'status':'running'}
    monkeypatch.setattr(queue,'get_job_status',stale)
    assert status(smoke)['smoke_test_status']=='failed'


def test_same_training_job_with_bound_smoke_cannot_submit_again_after_failure(smoke, monkeypatch):
    smoke.update(smoke_test_status='failed',smoke_test_error='smoke_generation_failed')
    result=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
    assert result.status_code==200
    assert result.json()['generation_job_id']=='gen-1'
    assert result.json()['smoke_test_status']=='failed'


def test_http_payloads_for_independent_mcp(smoke, monkeypatch):
    smoke.image()
    records=[]
    for state, code in [('completed',None),('failed','smoke_generation_failed'),('cancelled','smoke_generation_cancelled')]:
        smoke.update(smoke_test_status='submitted',smoke_test_error=None)
        monkeypatch.setattr(queue,'get_job_status', lambda job: None if state=='completed' else {'job_id':job,'status':state})
        payload=status(smoke)
        assert payload['smoke_test_status']==state
        records.append({'kind':'status','state':state,'code':code,'payload':payload})
        response=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
        assert response.status_code==200
        assert response.json()['smoke_test_status']==state
        records.append({'kind':'smoke','state':state,'code':code,'payload':response.json()})
    if os.environ.get('SMOKE_HTTP_FIXTURE_OUT'):
        Path(os.environ['SMOKE_HTTP_FIXTURE_OUT']).write_text(json.dumps(records,ensure_ascii=False))


def test_queue_full_is_a_definite_rejection_that_allows_explicit_retry(smoke, monkeypatch):
    smoke.update(smoke_test_status=None,smoke_test_job_id=None)
    def full(params):
        raise queue.QueueFullError('SECRET_MARKER')
    monkeypatch.setattr(lora_trainer,'submit_generation',full)
    rejected=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
    # Preserve the existing LoRA operation-error HTTP contract.
    assert rejected.status_code==400
    assert 'SECRET_MARKER' not in rejected.text
    assert status(smoke)['smoke_test_error_code']=='generation_queue_full'
    monkeypatch.setattr(lora_trainer,'submit_generation',queue.submit)
    assert smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={}).json()['smoke_test_status']=='submitted'
    assert len(queue.get_status()['queue_pending'])==1


@pytest.mark.parametrize('returned',[None, '', '/private/SECRET_MARKER', {'error':'SECRET_MARKER'}])
def test_malformed_submit_receipt_retains_uncertainty_without_retry(smoke, monkeypatch, returned):
    smoke.update(smoke_test_status=None,smoke_test_job_id=None)
    monkeypatch.setattr(lora_trainer,'submit_generation',lambda params: returned)
    response=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
    assert response.status_code==200
    assert response.json()['smoke_test_status']=='submission_unknown'
    assert response.json()['generation_job_id'] is None
    assert response.json()['error_code']=='smoke_submission_unknown'
    assert 'SECRET_MARKER' not in response.text


def test_interrupted_claim_has_actionable_diagnostic_and_never_resubmits(smoke):
    smoke.update(smoke_test_status='submitting',smoke_test_job_id=None)
    lora_trainer._reset_for_test()
    result=status(smoke)
    assert result['smoke_test_status']=='submitting'
    assert result['smoke_test_error_code']=='smoke_submission_unknown'
    assert result['smoke_test_hint']
    response=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={})
    assert response.json()['smoke_test_status']=='submitting'


def test_late_submission_receipt_cannot_overwrite_an_already_reconciled_binding(smoke, monkeypatch):
    smoke.update(smoke_test_status=None,smoke_test_job_id=None)
    def late(params):
        smoke.update(smoke_test_status='cancelled',smoke_test_job_id='newer-binding',smoke_test_error='smoke_generation_cancelled')
        return 'older-receipt'
    monkeypatch.setattr(lora_trainer,'submit_generation',late)
    result=smoke.client.post('/api/lora-train/jobs/train-1/smoke-test',json={}).json()
    assert result['generation_job_id']=='newer-binding'
    assert result['smoke_test_status']=='cancelled'


def test_fresh_interpreter_recovers_persisted_image_without_queue_or_submission(tmp_path):
    """A new Python process has no inherited queue; DB/Gallery alone close smoke."""
    root=tmp_path/'gallery';root.mkdir()
    Image.new('RGB',(2,2),'blue').save(root/'smoke.png')
    db_path=tmp_path/'restart.db'
    engine=create_engine('sqlite:///'+str(db_path))
    database.Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    with sessions() as db:
        db.add(LoraTrainingJob(job_id='train-restart',folder='portraits',status='completed',stage='completed',
            registered_lora_name='products/final.safetensors',output_name='旅人',output_serial=2,
            smoke_test_status='submitted',smoke_test_job_id='gen-restart'))
        recording.save('smoke.png',job_id='gen-restart',db=db)
    engine.dispose()
    script='''
import json,socket,subprocess
from app.services import lora_trainer
from app.core import queue
def denied(*a,**kw): raise AssertionError('restart probe forbids submission/network/process')
lora_trainer.submit_generation=denied
queue.submit=denied
socket.socket.connect=denied
subprocess.Popen=denied
assert queue.get_job_status('gen-restart') is None
result=lora_trainer.get_job_status('train-restart')
assert result['smoke_test_status']=='completed'
assert result['smoke_test_artifact']=='smoke.png'
assert result['smoke_test_artifact_id']==result['smoke_test_image_id']==1
assert result['registered_lora_name']=='products/final.safetensors'
assert result==lora_trainer.get_job_status('train-restart')
print(json.dumps(result))
'''
    from test_support import run_script
    result=run_script(script,scratch=tmp_path,overrides={'DATABASE_URL':'sqlite:///'+str(db_path),'GALLERY_DIR':str(root)})
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)['smoke_test_status']=='completed'
    with sessions() as db:
        row=db.query(LoraTrainingJob).one()
        assert row.smoke_test_status=='completed' and row.smoke_test_artifact=='smoke.png'
        assert row.output_name=='旅人' and row.output_serial==2
    engine.dispose()
