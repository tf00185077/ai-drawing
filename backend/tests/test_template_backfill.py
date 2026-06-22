"""#5 回填/自我擴充模板庫：形狀剝離、去重、版本化、DB 閘門"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import workflow_manifest as wm
from app.core.recording import save
from app.core.workflow_manifest import (
    CapabilityRequest,
    LoadedManifest,
    WorkflowManifest,
    backfill_template,
    consolidate_templates,
    find_matching_templates,
    strip_workflow_to_shape,
)
from app.db.database import Base, get_db
from app.db.models import GeneratedArtifact
from app.main import app


def _sample_wf():
    return {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a girl in a red raincoat", "clip": ["4", 1]}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad", "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": 12345, "steps": 20, "cfg": 7.0,
            "positive": ["1", 0], "negative": ["2", 0], "latent_image": ["5", 0], "model": ["4", 0]}},
    }


def _write_meta(wf_dir, tid, **fields):
    (wf_dir / f"{tid}.json").write_text("{}", encoding="utf-8")
    (wf_dir / f"{tid}.meta.json").write_text(json.dumps({"id": tid, **fields}), encoding="utf-8")


# --- 形狀剝離 -------------------------------------------------------------


def test_strip_removes_seed_and_prompt() -> None:
    shape = strip_workflow_to_shape(_sample_wf())
    assert shape["3"]["inputs"]["seed"] == 0
    assert shape["1"]["inputs"]["text"] == ""  # positive 清空
    assert shape["2"]["inputs"]["text"] == ""  # negative 清空


# --- 去重 / 建立 / 版本化（用 tmp 目錄）----------------------------------


def test_backfill_creates_family_filed_template(tmp_path) -> None:
    r = backfill_template(
        _sample_wf(), modality="img2img", model_family="sdxl",
        conditioning=["controlnet_pose"], io=["text", "image_ref"],
        description="pose img2img", workflows_dir=tmp_path,
    )
    assert r["ok"] and r["created"]
    tid = r["template_id"]
    assert tid.startswith("gen_img2img_sdxl")  # 家族（modality+family）編入命名
    # 形狀有寫、且已剝 seed
    saved = json.loads((tmp_path / f"{tid}.json").read_text())
    assert saved["3"]["inputs"]["seed"] == 0
    meta = json.loads((tmp_path / f"{tid}.meta.json").read_text())
    assert meta["modality"] == "img2img" and "controlnet_pose" in meta["conditioning"]


def test_backfill_dedupes_on_capability_key(tmp_path) -> None:
    _write_meta(tmp_path, "existing", modality="txt2img", model_family="sdxl",
                conditioning=[], io=["text"])
    r = backfill_template(
        _sample_wf(), modality="txt2img", model_family="sdxl",
        conditioning=[], io=["text"], workflows_dir=tmp_path,
    )
    assert r["ok"] and r["created"] is False
    assert r["reused"] == "existing"
    # 不應新增任何 gen_* 檔
    assert not list(tmp_path.glob("gen_*.json"))


def test_backfill_versions_and_deprecates_broken_same_key(tmp_path) -> None:
    # 既有同 key 模板但「壞」：meta 缺對應 .json（workflow_exists=False → invalid）
    (tmp_path / "broken.meta.json").write_text(json.dumps({
        "id": "broken", "modality": "inpaint", "model_family": "sdxl",
        "conditioning": [], "io": ["text", "mask"]}), encoding="utf-8")
    r = backfill_template(
        _sample_wf(), modality="inpaint", model_family="sdxl",
        conditioning=[], io=["text", "mask"], workflows_dir=tmp_path,
    )
    assert r["ok"] and r["created"]
    assert r["deprecated"] == "broken"
    # 舊的被標 deprecated（只動 meta，未刪）
    old_meta = json.loads((tmp_path / "broken.meta.json").read_text())
    assert old_meta["deprecated"] is True


def test_backfill_rejects_out_of_vocabulary_tags(tmp_path) -> None:
    r = backfill_template(
        _sample_wf(), modality="txt2img", model_family="sdxl",
        conditioning=["pose_control"], io=["text"], workflows_dir=tmp_path,
    )
    assert r["ok"] is False
    assert r["error"] == "invalid_tags"


def test_consolidate_removes_deprecated_only(tmp_path) -> None:
    # 一個正常、一個 deprecated
    _write_meta(tmp_path, "keep", modality="txt2img", model_family="sdxl", io=["text"])
    _write_meta(tmp_path, "old", modality="txt2img", model_family="sdxl", io=["text"], deprecated=True)
    r = consolidate_templates(workflows_dir=tmp_path)
    assert r["removed"] == ["old"]
    assert not (tmp_path / "old.meta.json").exists()
    assert not (tmp_path / "old.json").exists()
    assert (tmp_path / "keep.meta.json").exists()  # 正常的保留


def test_matching_skips_deprecated() -> None:
    dep = LoadedManifest(manifest=WorkflowManifest(
        id="d", modality="txt2img", model_family="sdxl", io=("text",), deprecated=True))
    req = CapabilityRequest(modality="txt2img")
    assert find_matching_templates([dep], req) == []


# --- DB 閘門（endpoint）--------------------------------------------------


@pytest.fixture
def client_db(tmp_path, monkeypatch):
    monkeypatch.setattr(wm, "WORKFLOWS_DIR", tmp_path)  # 寫入導向 tmp，不汙染真 workflows/
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SL = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override():
        db = SL()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with SL() as db:
        save(image_path="d/a.png", job_id="ok-job", prompt="p", workflow_json=_sample_wf(), db=db)
        save(image_path="d/b.png", job_id="legacy-job", prompt="p", db=db)  # 無 workflow_json
        db.add(GeneratedArtifact(
            job_id="video-job",
            artifact_type="video",
            gallery_path="d/a.mp4",
            mime_type="video/mp4",
            workflow_json=json.dumps(_sample_wf()),
            prompt="p",
        ))
        db.commit()
    try:
        yield TestClient(app), tmp_path
    finally:
        app.dependency_overrides.clear()


def test_backfill_endpoint_success(client_db) -> None:
    client, tmp_path = client_db
    r = client.post("/api/workflow-catalog/backfill", json={
        "job_id": "ok-job", "modality": "txt2img", "model_family": "sdxl",
        "conditioning": [], "io": ["text"], "description": "basic"})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] is True
    assert (tmp_path / f"{body['template_id']}.json").exists()


def test_backfill_endpoint_promotes_video_artifact(client_db) -> None:
    client, tmp_path = client_db
    r = client.post("/api/workflow-catalog/backfill", json={
        "job_id": "video-job", "modality": "img2video", "model_family": "wan",
        "conditioning": [], "io": ["text", "first_frame"], "description": "i2v"})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] is True
    meta = json.loads((tmp_path / f"{body['template_id']}.meta.json").read_text())
    assert meta["modality"] == "img2video"
    assert meta["model_family"] == "wan"
    assert "first_frame" in meta["io"]


def test_backfill_endpoint_gate_unknown_job(client_db) -> None:
    client, _ = client_db
    r = client.post("/api/workflow-catalog/backfill", json={
        "job_id": "nope", "modality": "txt2img", "model_family": "sdxl"})
    assert r.status_code == 404


def test_backfill_endpoint_gate_no_workflow_json(client_db) -> None:
    client, _ = client_db
    r = client.post("/api/workflow-catalog/backfill", json={
        "job_id": "legacy-job", "modality": "txt2img", "model_family": "sdxl"})
    assert r.status_code == 409
