"""Output-only option contract at durable HTTP -> independent MCP boundaries.

Removing semantic option projection must expose these invented private values.
No trainer or product service runs; SQLite and HttpBackendClient are real.
"""
import json
import os
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import lora_trainer
from tests.test_lora_delivery import isolated_worker

UNSAFE = [
    'cache_dir=/private/PRIVATE_OPTION_16/cache',
    r'trace_dir=C:\Private\PRIVATE_OPTION_16\trace',
    r'other_dir=\\server\PRIVATE_OPTION_16\cache',
    'directory="/private/PRIVATE_OPTION_16/space here"',
    r'directory="C:\Private\PRIVATE_OPTION_16\space here"',
    'weight_decay=/private/PRIVATE_OPTION_16',
    'weight_decay = "/private/PRIVATE_OPTION_16"',
    'betas=0.9,PRIVATE_OPTION_16',
    'decouple=PRIVATE_OPTION_16',
    'unknown=PRIVATE_OPTION_16',
    'PRIVATE_OPTION_16',
]
SAFE = ['weight_decay=0.01', 'decouple=true', 'betas=0.9,0.99', 'num_cycles=2', 'power=1.0', 'mode=min', 'decay_rate=-0.8', 'eps=1e-8', 'relative_step=False', 'weight_decay = "0.01"']

@pytest.mark.parametrize('legacy', [True, False])
@pytest.mark.parametrize('field', ['optimizer_args', 'lr_scheduler_args'])
@pytest.mark.parametrize('unsafe', UNSAFE)
def test_durable_options_are_public_only_and_internal_bytes_survive(isolated_worker, tmp_path, legacy, field, unsafe):
    w=isolated_worker
    envelope=json.loads(lora_trainer._recipe_envelope_json(w.job.recipe))
    for side in ('requested','effective'):
        envelope[side]['optimization'][field]=[unsafe, *SAFE]
    encoded=json.dumps(envelope,ensure_ascii=False)
    evidence={'argv':['fake-python', unsafe], 'dataset_config_content':'# '+unsafe, 'dataset_config_sha256':'a'*64, 'status':'unverified','capability':envelope['capability']}
    lora_trainer._update_persistent_job(w.job.job_id, recipe_json=encoded, execution_evidence_json=json.dumps(evidence), **({'run_locator':None,'output_name':None,'resolved_output_name':None,'output_serial':None} if legacy else {}))
    from app.db import database, models
    def raw():
        with database.SessionLocal() as db:
            row=db.query(models.LoraTrainingJob).filter_by(job_id=w.job.job_id).one()
            return (row.recipe_json,row.execution_evidence_json,row.recipe_hash,row.output_config_hash)
    before=raw(); internal=lora_trainer.get_job_status(w.job.job_id)
    response=TestClient(app).get('/api/lora-train/jobs/'+w.job.job_id)
    assert response.status_code==200
    public=response.json()
    assert 'PRIVATE_OPTION_16' not in response.text
    for side in ('requested_recipe','effective_recipe'):
        values=public[side]['optimization'][field]
        assert 'redacted' in values[0]
        assert values[1:]==SAFE
    assert public['recipe_hash']==internal['recipe_hash']
    if legacy:
        assert public['run_locator'] is public['output_name'] is public['resolved_output_name'] is public['output_serial'] is None
    else:
        assert public['output_name']=='旅人' and public['output_serial']==1 and public['run_locator']==w.job.run_locator
    # Actual HTTP serialization, and independently unsafe older Backend serialization.
    # MCP's own interpreter cannot import Backend as a dependency.
    payloads=tmp_path/'http-and-older.json';payloads.write_text(json.dumps([public,internal]))
    script=r'''
import json,sys
from unittest.mock import patch
import httpx
from mcp_server.client import HttpBackendClient
from mcp_server.tools import lora_train
for payload in json.load(open(sys.argv[1])):
    transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload)); original=httpx.Client
    with patch.object(lora_train,'_get_client',return_value=HttpBackendClient('http://fixture.invalid/api')),patch('httpx.Client',side_effect=lambda **kw:original(transport=transport,**kw)):
        result=lora_train.lora_train_job_status('fixture')
    assert result['ok'] is True
    assert 'PRIVATE_OPTION_16' not in json.dumps(result)
    assert result['run_locator']==payload['run_locator']
    for side in ('requested_recipe','effective_recipe'):
        assert result[side]['optimization'][sys.argv[2]][1:]==json.loads(sys.argv[3])
'''
    from test_support import run_script
    r=run_script(script,scratch=tmp_path,python=os.environ['MCP_TEST_PYTHON'],args=[str(payloads),field,json.dumps(SAFE)])
    assert r.returncode==0,r.stdout+r.stderr
    assert raw()==before and before[0]==encoded
    assert lora_trainer.get_job_status(w.job.job_id)==internal


def test_preflight_report_projection_does_not_rewrite_canonical_start_input(isolated_worker, monkeypatch):
    from app.schemas.lora_train import TrainingDecisionPreflightResponse, TrainingStartPayload
    from app.services import lora_training_decision
    w=isolated_worker
    requested=w.job.recipe.requested.model_copy(update={'optimization':w.job.recipe.requested.optimization.model_copy(update={'optimizer_args':('unknown=PRIVATE_INPUT_16',)})})
    start=TrainingStartPayload(folder='fixture',output_name='旅人',expected_dataset_hash='a'*64,expected_profile_hash='b'*64,recipe=requested)
    result=TrainingDecisionPreflightResponse(folder='fixture',decision='train',output_name='旅人',requested_recipe=requested,start_payload=start)
    monkeypatch.setattr(lora_training_decision,'decide_training_preflight',lambda *a,**kw:result)
    response=TestClient(app).post('/api/lora-train/datasets/training-decision-preflight',json={'folder':'fixture','output_name':'旅人'})
    assert response.status_code==200
    public=response.json()
    assert public['start_payload']==start.model_dump(mode='json')
    assert 'PRIVATE_INPUT_16' not in json.dumps(public['requested_recipe'])
    assert result.requested_recipe==requested and start.recipe==requested
