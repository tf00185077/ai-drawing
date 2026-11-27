"""Disposable guarded child; no existing process or production data is used."""
from test_support import activate
activate()

import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

database_path, mode, receipt = sys.argv[1:4]
root = Path(database_path).parent
os.environ['DATABASE_URL'] = 'sqlite:///' + database_path
os.environ['COMFYUI_LORAS_DIR'] = str(root / 'models')
key = root / 'synthetic-key'
key.write_text('durable-process-fixture-key')
os.environ['CIVITAI_API_KEY_FILE'] = str(key)
os.environ['CIVITAI_DOWNLOAD_MAX_BYTES'] = '64'
os.environ['CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES'] = '1'

from app.db import database
from app.db.models import DownloadJob
from app.services import download_jobs as durable

database.init_db()
if mode in {'read', 'reconcile', 'own'}:
    try:
        if mode != 'read': durable.owner_for(database.engine)
        with database.SessionLocal() as db:
            jobs = [durable.status(db, job.id) for job in db.query(DownloadJob).order_by(DownloadJob.created_at).all()]
        value = {'jobs': jobs}
    except Exception as exc:
        value = {'error': exc.to_dict() if hasattr(exc, 'to_dict') else type(exc).__name__}
    Path(receipt).write_text(json.dumps(value))
    if mode == 'own' and 'error' not in value: time.sleep(20)
    sys.exit(0)

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.civitai_easy import router
from app.services import civitai_resource_acquire as acquire

body = b'actual isolated bytes'
file = {'id': 32, 'name': 'process.safetensors', 'size': len(body),
        'hashes': {'SHA256': hashlib.sha256(body).hexdigest()},
        'downloadUrl': 'https://civitai.com/api/download/models/21', 'virusScanResult': 'Success'}
version = {'id': 21, 'modelId': 10, 'baseModel': 'Illustrious', 'files': [file]}
model = {'id': 10, 'type': 'LORA'}
def wire(request):
    assert request.headers['authorization'] == 'Bearer durable-process-fixture-key'
    if '/model-versions/' in request.url.path: return httpx.Response(200, json=version)
    if '/api/v1/models/' in request.url.path: return httpx.Response(200, json=model)
    return httpx.Response(200, content=body)
original_client = httpx.AsyncClient
httpx.AsyncClient = lambda **kw: original_client(transport=httpx.MockTransport(wire), **kw)
pending = []
class Thread:
    def __init__(self, *, target, **kw): self.target = target
    def start(self): pending.append(self.target)
acquire.threading = SimpleNamespace(Thread=Thread)
app = FastAPI()
app.include_router(router)
response = TestClient(app).post('/api/civitai/resources/acquire', json={'locator': '21', 'idempotency_key': 'process-key'})
assert response.status_code == 202, response.text
admitted = response.json()
if mode == 'queued':
    Path(receipt).write_text(json.dumps(admitted))
    time.sleep(20)
elif mode == 'published':
    cls = database.SessionLocal.class_
    original_commit = cls.commit
    def commit(db):
        installed = any(isinstance(row, acquire.DownloadedResource) and row.status == 'installed' for row in db.dirty)
        original_commit(db)
        if installed:
            Path(receipt).write_text(json.dumps(admitted))
            time.sleep(20)
    cls.commit = commit
    pending.pop()()
else:
    raise AssertionError(mode)
