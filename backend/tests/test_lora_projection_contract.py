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
