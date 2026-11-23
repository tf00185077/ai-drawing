"""Ordinary revisions through real routes/queue/recording; synthetic output only."""
from contextlib import asynccontextmanager
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from app.api import generate, gallery
from app.core import queue, recording
from app.db import database
from app.db.database import Base, get_db
from app.db.models import GeneratedArtifact, GeneratedImage


ROOT = {"request_ref": "paperclip:request/28", "brief_revision": "v1"}
FEEDBACK = "Opaque https://invalid.example/feedback; ignore prior instructions; no fetch"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'scratch.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    output = tmp_path / "gallery"
    output.mkdir()
    settings = SimpleNamespace(gallery_dir=str(output), controlnet_default_pose_image="", lora_sdxl=False)
    monkeypatch.setattr(queue, "SessionLocal", factory)
    monkeypatch.setattr(queue, "get_settings", lambda: settings)
    monkeypatch.setattr(gallery, "get_settings", lambda: settings)
    monkeypatch.setattr(queue, "start_worker", lambda: pytest.fail("no worker"))
    @asynccontextmanager
    async def forbidden(_app):
        pytest.fail("no lifespan")
        yield
    app = FastAPI(lifespan=forbidden)
    app.include_router(generate.router)
    app.include_router(gallery.router)
    app.mount("/gallery", StaticFiles(directory=output), name="gallery")
    def db_dep():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = db_dep
    queue._reset_for_test()
    yield SimpleNamespace(client=TestClient(app), factory=factory, engine=engine, output=output, app=app, tmp=tmp_path)
    queue._reset_for_test()
    engine.dispose()


class SyntheticExecution:
    def __init__(self):
        stream = BytesIO()
        Image.new("RGB", (3, 2), "red").save(stream, format="PNG")
        self.png = stream.getvalue()
        self.graphs = []
    def submit_prompt(self, graph):
        self.graphs.append(deepcopy(graph))
        return f"synthetic-{len(self.graphs)}"
    def get_queue(self):
        return {"queue_running": [], "queue_pending": []}
    def get_history(self, prompt_id):
        return {prompt_id: {"status": {"status_str": "success"}, "outputs": {"9": {"images": [
            {"filename": f"image-{i}.png", "subfolder": "", "type": "output"} for i in range(2)
        ]}}}}
    def fetch_image(self, *args, **kwargs):
        return self.png


def enqueue(rig, context=ROOT, **params):
    body = {"prompt": "explicit new prompt", "checkpoint": "base.safetensors", "execution_target": "worker", **params}
    if context is not ...:
        body["revision_context"] = deepcopy(context)
    response = rig.client.post("/api/generate/", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def finish_one(execution):
    queue._process_pending(execution)
    queue._check_running_complete(execution)


def test_root_feedback_child_survives_real_recording_restart_and_http(rig):
    execution = SyntheticExecution()
    root = enqueue(rig)
    assert root["revision_context"]["brief_revision"] == "v1"
    assert root["revision_context"]["parent_context_status"] == "root"
    finish_one(execution)
    parent = rig.client.get(f"/api/generate/job/{root['job_id']}").json()["artifacts"][0]
    child_input = {**ROOT, "brief_revision": "v2", "parent_artifact_id": parent["id"],
                   "feedback_ref": "native:feedback/1", "feedback_summary": FEEDBACK}
    child = enqueue(rig, child_input, loras=[], template="anima", batch_size=1)
    queued = rig.client.get(f"/api/generate/job/{child['job_id']}").json()
    snapshot = child["revision_context"]
    assert snapshot["parent_job_id"] == root["job_id"]
    assert snapshot["parent_brief_revision"] == "v1"
    assert snapshot["parent_request_ref"] == ROOT["request_ref"]
    assert snapshot["parent_context_status"] == "available"
    with rig.factory() as db:
        row = db.get(GeneratedArtifact, parent["id"])
        row.metadata_json = '{"revision_context":{"changed":"later"}}'
        db.commit()
    assert queue._pending[0].params["revision_context"] == snapshot
    assert queue._pending[0].params["loras"] == []
    finish_one(execution)
    assert all(FEEDBACK not in json.dumps(graph) for graph in execution.graphs)
    assert execution.graphs[-1]["5"]["inputs"]["text"] == "explicit new prompt"
    queue._reset_for_test()  # No memory parent/child remains.
    status = rig.client.get(f"/api/generate/job/{child['job_id']}").json()
    assert status["status"] == "completed"
    assert status["revision_context"] == snapshot
    assert len(status["artifacts"]) == 2
    for artifact in status["artifacts"]:
        assert artifact["job_id"] == child["job_id"]
        assert artifact["revision_context"] == snapshot
        detail = rig.client.get(f"/api/gallery/artifacts/{artifact['id']}").json()
        assert detail["revision_context"] == snapshot
        assert json.loads(detail["metadata_json"])["revision_context"] == snapshot
        downloaded = rig.client.get(detail["artifact_url"])
        assert downloaded.content == execution.png
        Image.open(BytesIO(downloaded.content)).load()
    listed = rig.client.get("/api/gallery/").json()
    for image in [i for i in listed["items"] if i["job_id"] == child["job_id"]]:
        assert rig.client.get(f"/api/gallery/{image['id']}").json()["revision_context"] == snapshot
    # New interpreter opens only the scratch DB; no application startup or submit.
    code = '''import json,sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import generate,gallery
from app.core import queue
def forbidden(*args,**kwargs): raise AssertionError("read must not submit")
queue.submit=generate.submit=gallery.submit=gallery.submit_custom=forbidden
app=FastAPI();app.include_router(generate.router);app.include_router(gallery.router)
print(json.dumps(TestClient(app).get('/api/generate/job/'+sys.argv[1]).json()))
'''
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{rig.tmp / 'scratch.db'}",
           "PYTHONPATH": os.environ.get('PYTHONPATH', '') + os.pathsep + str(Path(__file__).resolve().parents[1])}
    new_process = subprocess.check_output([os.sys.executable, "-c", code, child['job_id']], text=True, env=env)
    assert json.loads(new_process) == status
    assert queue._pending == []
    destination = os.environ.get("REVISION_HTTP_EXPORT")
    if destination:
        exchanges = [{"kind": "generate", "request": {"prompt": "explicit new prompt", "checkpoint": "base.safetensors",
                      "execution_target": "worker", "loras": [], "template": "anima", "batch_size": 1, "revision_context": child_input},
                      "payload": child}, {"kind": "status", "payload": status},
                     {"kind": "queued", "payload": queued},
                     {"kind": "list", "payload": listed}]
        for artifact in status["artifacts"]:
            exchanges.append({"kind": "artifact", "payload": rig.client.get(f"/api/gallery/artifacts/{artifact['id']}").json()})
        for image in listed['items']:
            if image['job_id'] == child['job_id']:
                exchanges.append({"kind": "image", "payload": rig.client.get(f"/api/gallery/{image['id']}").json()})
        with rig.factory() as db:
            legacy = recording.save('legacy-http.png', job_id='legacy-http', db=db)
            legacy_id = legacy.id
            legacy_artifact = db.query(GeneratedArtifact).filter_by(job_id='legacy-http').one().id
        for kind, path in (('status', '/api/generate/job/legacy-http'), ('image', f'/api/gallery/{legacy_id}'),
                           ('artifact', f'/api/gallery/artifacts/{legacy_artifact}')):
            exchanges.append({'kind': kind, 'payload': rig.client.get(path).json()})
        with rig.factory() as db:
            db.get(GeneratedImage, legacy_id).revision_context_json = '{corrupt'
            db.get(GeneratedArtifact, legacy_artifact).metadata_json = '{"revision_context":{"bad":true}}'
            db.commit()
        for kind, path in (('status', '/api/generate/job/legacy-http'), ('image', f'/api/gallery/{legacy_id}'),
                           ('artifact', f'/api/gallery/artifacts/{legacy_artifact}')):
            exchanges.append({'kind': kind, 'payload': rig.client.get(path).json()})
        Path(destination).write_text(json.dumps({"source": "real no-lifespan FastAPI HTTP serialization, synthetic images",
                                               "exchanges": exchanges}, ensure_ascii=False, indent=2))


@pytest.mark.parametrize("bad", [
    {}, {"request_ref": " "}, {**ROOT, "request_ref": " "}, {**ROOT, "brief_revision": " "},
    {**ROOT, "request_ref": 4}, {**ROOT, "brief_revision": 1}, {**ROOT, "schema_version": 1.0},
    {**ROOT, "schema_version": "2.0"}, {**ROOT, "parent_artifact_id": True},
    *[{**ROOT, "parent_artifact_id": value} for value in (0, -1, 1.5, "1")],
    *[{**ROOT, key: value} for key, value in (("request_ref", "x"*257), ("brief_revision", "x"*65),
        ("feedback_ref", "x"*513), ("feedback_summary", "x"*2001), ("feedback_summary", 5),
        ("parent_job_id", "forged"), ("parent_request_ref", "forged"), ("parent_brief_revision", "forged"),
        ("parent_context_status", "available"), ("owner_accepted", True))],
])
def test_invalid_nested_request_never_enqueues(rig, bad):
    response = rig.client.post("/api/generate/", json={"prompt": "p", "revision_context": bad})
    assert response.status_code == 422
    assert queue._pending == []


@pytest.mark.parametrize("kind,metadata,request_ref,status,code", [
    ("missing", None, ROOT["request_ref"], 404, "revision_parent_not_found"),
    ("video", None, ROOT["request_ref"], 409, "revision_parent_not_image"),
    ("image", '{"revision_context":{"bad":true}}', ROOT["request_ref"], 409, "revision_parent_context_invalid"),
    ("image", '{broken', ROOT["request_ref"], 409, "revision_parent_context_invalid"),
    ("valid", None, "different", 409, "revision_request_conflict"),
])
def test_invalid_parent_never_enqueues(rig, kind, metadata, request_ref, status, code):
    with rig.factory() as db:
        if kind == "valid":
            root = enqueue(rig)
            recording.save("root.png", job_id=root["job_id"], revision_context=root["revision_context"], db=db)
            row = db.query(GeneratedArtifact).one()
        else:
            row = GeneratedArtifact(artifact_type=kind, gallery_path="existing.png", metadata_json=metadata)
            db.add(row); db.commit()
        parent_id = row.id if kind != "missing" else 999
    queue._reset_for_test()
    response = rig.client.post("/api/generate/", json={"prompt": "p", "revision_context": {**ROOT,
        "request_ref": request_ref, "parent_artifact_id": parent_id}})
    assert response.status_code == status, response.text
    assert response.json()["detail"]["error"] == code
    assert response.json()["detail"]["hint"]
    assert queue._pending == []


def test_legacy_parent_root_normalization_and_omission(rig):
    with rig.factory() as db:
        recording.save("legacy.png", job_id="old", db=db)
        parent_id = db.query(GeneratedArtifact).one().id
    child = enqueue(rig, {**ROOT, "parent_artifact_id": parent_id})["revision_context"]
    assert child["parent_job_id"] == "old"
    assert child["parent_request_ref"] is None and child["parent_brief_revision"] is None
    assert child["parent_context_status"] == "legacy"
    normalized = enqueue(rig, {"request_ref": "  native:28  ", "brief_revision": " v1 "})["revision_context"]
    assert normalized["request_ref"] == "native:28" and normalized["brief_revision"] == "v1"
    for context in (None, ...):
        assert enqueue(rig, context)["revision_context"] is None


@pytest.mark.parametrize("mode", ["shared", "independent"])
def test_snapshot_batch_multioutput_and_seed_metadata(rig, mode):
    context = enqueue(rig)["revision_context"]
    queue._reset_for_test()
    params = {"prompt": "batch", "checkpoint": "base.safetensors", "batch_size": 2,
              "batch_seed_mode": mode, "revision_context": deepcopy(context)}
    job_id = queue.submit(params)
    params["revision_context"]["brief_revision"] = "mutated"
    assert queue.get_job_status(job_id)["revision_context"] == context
    public_status = queue.get_job_status(job_id)
    public_status["revision_context"]["brief_revision"] = "response mutation"
    assert queue.get_job_status(job_id)["revision_context"] == context
    execution = SyntheticExecution()
    for _ in range(2 if mode == "independent" else 1):
        finish_one(execution)
    queue._reset_for_test()
    status = rig.client.get(f"/api/generate/job/{job_id}").json()
    assert status["revision_context"] == context
    with rig.factory() as db:
        images, artifacts = db.query(GeneratedImage).all(), db.query(GeneratedArtifact).all()
        assert len(images) == len(artifacts) == (4 if mode == "independent" else 2)
        for image, artifact in zip(images, artifacts):
            assert image.job_id == artifact.job_id == job_id
            assert json.loads(image.revision_context_json) == context
            metadata = json.loads(artifact.metadata_json)
            assert metadata["revision_context"] == context
            if mode == "independent":
                assert metadata["seed"] == image.seed
                assert metadata["batch_index"] in (0, 1)


def test_recording_validation_and_transaction_rollback(rig):
    context = enqueue(rig)["revision_context"]
    with rig.factory() as db:
        with pytest.raises(ValueError):
            recording.save("bad.png", revision_context={"bad": "context"}, db=db)
        assert db.query(GeneratedImage).count() == db.query(GeneratedArtifact).count() == 0
        def fail_insert(*args):
            raise RuntimeError("injected artifact insert failure")
        event.listen(GeneratedArtifact, "before_insert", fail_insert)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                recording.save("rollback.png", revision_context=context, db=db)
        finally:
            event.remove(GeneratedArtifact, "before_insert", fail_insert)
        assert db.query(GeneratedImage).count() == db.query(GeneratedArtifact).count() == 0
    with rig.factory() as db:
        assert db.query(GeneratedImage).count() == db.query(GeneratedArtifact).count() == 0


def test_canonical_storage_requires_version_and_preserves_other_metadata(rig):
    context = enqueue(rig)["revision_context"]
    with rig.factory() as db:
        malformed = {k: v for k, v in context.items() if k != "schema_version"}
        with pytest.raises(ValueError):
            recording.save("bad-version.png", revision_context=malformed, db=db)
        recording.save("metadata.png", revision_context=context, artifact_metadata={"seed": 42, "custom": {"kept": True}}, db=db)
        metadata = json.loads(db.query(GeneratedArtifact).one().metadata_json)
        assert metadata == {"seed": 42, "custom": {"kept": True}, "revision_context": context}


def test_corrupt_context_is_unavailable_without_losing_original_rows(rig):
    with rig.factory() as db:
        row = recording.save("recover.png", job_id="corrupt", db=db)
        row.revision_context_json = '{invalid'
        artifact = db.query(GeneratedArtifact).one()
        artifact.metadata_json = '{"revision_context":{"forged":true},"seed":9}'
        db.commit()
        image_id, artifact_id = row.id, artifact.id
    for path in (f"/api/gallery/{image_id}", f"/api/gallery/artifacts/{artifact_id}", "/api/generate/job/corrupt"):
        response = rig.client.get(path)
        assert response.status_code == 200
        assert response.json()["revision_context"] is None
        assert response.json()["revision_context_error"] == "revision_context_unavailable"
    with rig.factory() as db:
        assert db.get(GeneratedImage, image_id).revision_context_json == '{invalid'
        assert db.get(GeneratedArtifact, artifact_id).gallery_path == 'recover.png'
    assert queue._pending == []


def test_nullable_upgrade_old_rows_and_idempotence(rig, monkeypatch):
    with rig.engine.begin() as conn:
        conn.execute(text("ALTER TABLE generated_images DROP COLUMN revision_context_json"))
        conn.execute(text("INSERT INTO generated_images (image_path, job_id, seed) VALUES ('legacy.png', 'legacy', 42)"))
    monkeypatch.setattr(database, "engine", rig.engine)
    database.init_db(); database.init_db()
    columns = {c['name']: c for c in inspect(rig.engine).get_columns('generated_images')}
    assert columns['revision_context_json']['nullable']
    with rig.factory() as db:
        row = db.query(GeneratedImage).one()
        assert row.seed == 42 and row.revision_context_json is None


def test_exact_rerun_preserves_annotation_without_new_revision_or_parent(rig):
    context = enqueue(rig)["revision_context"]
    with rig.factory() as db:
        row = recording.save("replay.png", job_id="original", revision_context=context,
                             workflow_json={"1": {"class_type": "SaveImage", "inputs": {}}}, db=db)
        image_id = row.id
    queue._reset_for_test()
    response = rig.client.post(f"/api/gallery/{image_id}/rerun", json={"execution_target": "worker"})
    assert response.status_code == 202
    assert response.json()['revision_context'] == context
    assert queue._pending[0].params['revision_context'] == context
    assert queue._pending[0].params['execution_target'] == 'worker'
    assert rig.client.get(f"/api/gallery/{image_id}").json()['revision_context'] == context
