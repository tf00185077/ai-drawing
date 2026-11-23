"""Real durable state / HTTP admission regressions. No runner is executed."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from app.db import database
from app.db.models import LoraTrainingJob
from app.services import lora_trainer as t, lora_dataset
from tests import test_lora_trainer as original

@pytest.fixture(autouse=True)
def reset(monkeypatch):
    t._reset_for_test()
    monkeypatch.setattr(t, '_ensure_worker', lambda: None)
    yield
    t._reset_for_test()

def seed(job_id, status):
    with database.SessionLocal() as db:
        db.add(LoraTrainingJob(job_id=job_id,folder='PRIVATE_SENTINEL',status=status,stage=status))
        db.commit()

def test_idle_http_exposes_durable_pending_and_tracking_without_writes(client):
    for job,status in [('q','queued'),('r','running'),('done','completed')]: seed(job,status)
    before = database.engine.raw_connection().total_changes
    st=client.get('/api/lora-train/status').json()
    assert st['status']=='idle'
    d=st['durable'];assert d['availability']=='available'
    assert (d['nonterminal_total'],d['tracked_total'],d['untracked_total'])==(2,0,2)
    assert d['jobs']==[{'job_id':'q','status':'queued','memory_tracked':False},{'job_id':'r','status':'running','memory_tracked':False}]
    assert 'PRIVATE_SENTINEL' not in json.dumps(d)
    t._queue.append(SimpleNamespace(job_id='q',folder='x',output_name=None,resolved_output_name=None,output_serial=None,run_locator=None,output_config_hash=None))
    d=client.get('/api/lora-train/status').json()['durable']
    assert (d['tracked_total'],d['untracked_total'])==(1,1)
    assert database.engine.raw_connection().total_changes==before

def test_bounded_fixed_order_and_unknown_status(client):
    for n in range(55):seed(f'job-{n:03}', 'queued')
    seed('unknown','new_future_state')
    d=client.get('/api/lora-train/status').json()['durable']
    assert d['nonterminal_total']==56 and d['truncated'] is True
    assert d['limit']==50 and len(d['jobs'])==50
    assert [j['job_id'] for j in d['jobs']]==[f'job-{n:03}' for n in range(50)]

@pytest.mark.parametrize('kind',['missing','table','column','corrupt'])
def test_unavailable_never_creates_or_migrates(kind,tmp_path,monkeypatch,client):
    import sqlite3
    file=tmp_path/'observe.db'
    if kind=='corrupt':file.write_bytes(b'not sqlite')
    elif kind in ('table','column'):
        with sqlite3.connect(file) as db:
            if kind=='column':db.execute('CREATE TABLE lora_training_jobs (job_id TEXT)')
    before=file.read_bytes() if file.exists() else None
    monkeypatch.setattr(database,'engine',create_engine('sqlite:///'+str(file)))
    monkeypatch.setattr(database,'init_db',lambda:pytest.fail('migration forbidden'))
    monkeypatch.setattr(t,'_with_db',lambda *a:pytest.fail('lazy DB forbidden'))
    d=client.get('/api/lora-train/status').json()['durable']
    assert d['availability']=='unavailable' and d['nonterminal_total'] is None
    assert (file.read_bytes() if file.exists() else None)==before

def test_terminal_only_is_zero(client):
    for state in ('completed','failed','cancelled'):seed(state,state)
    d=client.get('/api/lora-train/status').json()['durable']
    assert d['availability']=='available' and d['nonterminal_total']==0

@pytest.fixture
def admission(tmp_path,monkeypatch):
    root=original.valid_train_dir.__wrapped__(tmp_path)
    mock=MagicMock(); original._set_common_enqueue_settings(mock,root)
    monkeypatch.setattr(t,'get_settings',mock)
    monkeypatch.setattr(lora_dataset,'get_settings',lambda:t.get_settings())
    dataset,profile=original._approval_hashes(root/'lora_train/my_lora')
    return dict(folder='my_lora',output_name='test-product',expected_dataset_hash=dataset,expected_profile_hash=profile,recipe=original._canonical_recipe())

@pytest.mark.parametrize('fault',['append','worker','prepare'])
def test_postcommit_http_retains_canonical_identity(fault,admission,monkeypatch,client):
    def fail(*a,**kw):raise RuntimeError('/private/SECRET_SENTINEL token=SECRET_SENTINEL')
    if fault=='append':
        class Broken(list):
            append=fail
        monkeypatch.setattr(t,'_queue',Broken())
    elif fault=='worker':monkeypatch.setattr(t,'_ensure_worker',fail)
    else:monkeypatch.setattr(t.delivery,'create_run',fail)
    response=client.post('/api/lora-train/start',json=admission)
    with database.SessionLocal() as db:rows=db.query(LoraTrainingJob).all()
    assert len(rows)==1
    assert response.status_code==503
    detail=response.json()['detail']
    assert detail['job_id']==rows[0].job_id
    assert detail['code']=='admission_uncertain'
    assert 'do not resubmit' in detail['hint']
    assert 'SECRET_SENTINEL' not in response.text
    import os
    from pathlib import Path
    file=Path(os.environ['AI_DRAWING_TEST_ROOT'])/'http-export.json'
    exported=json.loads(file.read_text()) if file.exists() else []
    exported.append({'fault':fault,'http_status':response.status_code,'body':response.json()})
    file.write_text(json.dumps(exported,indent=2))
    assert rows[0].status=='queued'
    # The read-only aggregate can find an untracked committed row; no second POST.
    assert client.get('/api/lora-train/status').json()['durable']['nonterminal_total']==1

def test_queued_log_failure_still_acknowledges_and_schedules(admission,monkeypatch,client):
    def fail(*a,**kw):raise OSError('/private/SECRET_SENTINEL')
    calls=[]
    monkeypatch.setattr(t,'_append_log',fail)
    monkeypatch.setattr(t,'_ensure_worker',lambda:calls.append('ensure'))
    response=client.post('/api/lora-train/start',json=admission)
    assert response.status_code==202 and len(calls)==1
    with database.SessionLocal() as db:
        rows=db.query(LoraTrainingJob).all()
        assert len(rows)==1 and rows[0].job_id==response.json()['job_id']
    assert 'SECRET_SENTINEL' not in response.text


def test_file_observation_uses_readonly_selects_preserves_rows_names_and_bytes(tmp_path,monkeypatch,client):
    import sqlite3
    file=tmp_path/'persisted.db'
    with sqlite3.connect(file) as db:
        db.executescript("CREATE TABLE lora_training_jobs(job_id TEXT,status TEXT); INSERT INTO lora_training_jobs VALUES('legacy','running'); CREATE TABLE reservations(name TEXT,serial INTEGER); INSERT INTO reservations VALUES('preserve',7);")
    original=sqlite3.connect;sql=[];uris=[]
    def connect(location,*a,**kw):
        uris.append(location);conn=original(location,*a,**kw);conn.set_trace_callback(sql.append);return conn
    before=file.read_bytes();files=sorted(p.name for p in tmp_path.iterdir())
    monkeypatch.setattr(database,'engine',create_engine('sqlite:///'+str(file)))
    monkeypatch.setattr(sqlite3,'connect',connect)
    d=client.get('/api/lora-train/status').json()['durable']
    assert d['availability']=='available' and d['jobs'][0]['job_id']=='legacy', (d,uris,sql)
    assert all('mode=ro' in uri for uri in uris)
    assert all(stmt.startswith(('SELECT','BEGIN')) for stmt in sql)
    assert file.read_bytes()==before and sorted(p.name for p in tmp_path.iterdir())==files


def test_wal_is_unknown_without_sidecar_writes(tmp_path,monkeypatch,client):
    import sqlite3
    file=tmp_path/'wal.db'
    with sqlite3.connect(file) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE lora_training_jobs(job_id TEXT,status TEXT)')
        db.execute("INSERT INTO lora_training_jobs VALUES('pending','queued')")
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(database,'engine',create_engine('sqlite:///'+str(file)))
    assert client.get('/api/lora-train/status').json()['durable']['availability']=='unavailable'
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before


def test_precommit_rejection_has_no_false_acknowledgement(admission,monkeypatch,client):
    def fail(*a,**kw):raise t.TrainerServiceError('dataset_locked','SECRET_SENTINEL')
    monkeypatch.setattr(t,'_create_persistent_job',fail)
    response=client.post('/api/lora-train/start',json=admission)
    assert response.status_code==409
    assert 'job_id' not in response.json()['detail']
    with database.SessionLocal() as db:assert db.query(LoraTrainingJob).count()==0


def test_unknown_state_and_connection_failure_are_not_false_zero(monkeypatch,client,tmp_path):
    import sqlite3
    seed('future','new-state')
    d=client.get('/api/lora-train/status').json()['durable']
    assert d['nonterminal_total']==1 and d['jobs'][0]['status']=='unknown'
    file=tmp_path/'unavailable.db';file.write_bytes(b'SQLite format 3\0'+b'\0'*100)
    monkeypatch.setattr(database,'engine',create_engine('sqlite:///'+str(file)))
    def fail(*a,**kw):raise OSError('/private/SECRET_SENTINEL')
    monkeypatch.setattr(sqlite3,'connect',fail)
    response=client.get('/api/lora-train/status')
    assert response.json()['durable']['availability']=='unavailable' and 'SECRET_SENTINEL' not in response.text


def test_fresh_module_observes_existing_row_without_recovery(client):
    import importlib.util,sys
    seed('old-queued','queued')
    spec=importlib.util.spec_from_file_location('fresh_lifecycle_trainer',t.__file__)
    fresh=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fresh
    try:
        spec.loader.exec_module(fresh)
        status=fresh.get_status()
        assert status['status']=='idle' and status['durable']['untracked_total']==1
        with database.SessionLocal() as db:assert db.query(LoraTrainingJob).one().status=='queued'
    finally:sys.modules.pop(spec.name,None)


def test_commit_succeeds_but_persistence_return_fails_keeps_same_id(admission,monkeypatch,client):
    original_create=t._create_persistent_job
    def fail_after_commit(job):
        original_create(job)
        raise RuntimeError('SECRET_SENTINEL commit returned ambiguously')
    monkeypatch.setattr(t,'_create_persistent_job',fail_after_commit)
    response=client.post('/api/lora-train/start',json=admission)
    with database.SessionLocal() as db:row=db.query(LoraTrainingJob).one()
    assert response.status_code==503
    assert response.json()['detail']['job_id']==row.job_id
    assert response.json()['detail']['code']=='admission_uncertain'
    assert 'SECRET_SENTINEL' not in response.text
    assert row.status=='queued' and t.get_status()['status']=='idle'


def test_journal_mode_change_at_open_stays_unknown_without_new_sidecars(tmp_path,monkeypatch,client):
    import sqlite3
    file=tmp_path/'transition.db'
    with sqlite3.connect(file) as db:
        db.executescript("CREATE TABLE lora_training_jobs(job_id TEXT,status TEXT); INSERT INTO lora_training_jobs VALUES('old','queued');")
    monkeypatch.setattr(database,'engine',create_engine('sqlite:///'+str(file)))
    original=sqlite3.connect
    def transition(location,*a,**kw):
        content=bytearray(file.read_bytes());content[18:20]=b'\x02\x02';file.write_bytes(content)
        return original(location,*a,**kw)
    monkeypatch.setattr(sqlite3,'connect',transition)
    files=sorted(p.name for p in tmp_path.iterdir())
    d=client.get('/api/lora-train/status').json()['durable']
    assert d['availability']=='unavailable'
    assert sorted(p.name for p in tmp_path.iterdir())==files
