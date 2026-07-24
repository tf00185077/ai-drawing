"""自動記錄 Pipeline 單元測試"""
import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import GeneratedArtifact
from app.core.recording import save, save_artifact


@pytest.fixture
def db_session():
    """建立 in-memory SQLite 測試用 session"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_save_creates_record_with_full_params(db_session) -> None:
    """寫入完整參數時正確建立 GeneratedImage 記錄"""
    record = save(
        image_path="/outputs/gallery/2024-01/test.png",
        checkpoint="model.safetensors",
        lora="lora.safetensors",
        seed=12345,
        steps=20,
        cfg=7.0,
        prompt="1girl, solo",
        negative_prompt="lowres",
        db=db_session,
    )

    assert record.id is not None
    assert record.image_path == "/outputs/gallery/2024-01/test.png"
    assert record.checkpoint == "model.safetensors"
    assert record.lora == "lora.safetensors"
    assert record.seed == 12345
    assert record.steps == 20
    assert record.cfg == 7.0
    assert record.prompt == "1girl, solo"
    assert record.negative_prompt == "lowres"
    assert record.created_at is not None

    artifact = db_session.query(GeneratedArtifact).filter_by(job_id=record.job_id).one()
    assert artifact.artifact_type == "image"
    assert artifact.gallery_path == record.image_path
    assert artifact.mime_type == "image/png"


def test_save_creates_record_with_minimal_params(db_session) -> None:
    """僅傳入 image_path 時建立記錄，其他欄位為 None"""
    record = save(image_path="/outputs/gallery/minimal.png", db=db_session)

    assert record.id is not None
    assert record.image_path == "/outputs/gallery/minimal.png"
    assert record.checkpoint is None
    assert record.lora is None
    assert record.seed is None
    assert record.steps is None
    assert record.cfg is None
    assert record.prompt is None
    assert record.negative_prompt is None
    assert record.created_at is not None


def test_save_persists_independent_member_artifact_metadata(db_session) -> None:
    record = save(
        image_path="2026-07-25/member.png",
        job_id="parent-job",
        seed=987654,
        artifact_metadata={"batch_index": 2, "seed": 987654},
        artifact_source_node_id="9",
        artifact_source_node_type="SaveImage",
        db=db_session,
    )

    artifact = (
        db_session.query(GeneratedArtifact)
        .filter(GeneratedArtifact.job_id == "parent-job")
        .one()
    )
    assert record.job_id == "parent-job"
    assert record.seed == 987654
    assert json.loads(artifact.metadata_json) == {
        "batch_index": 2,
        "seed": 987654,
    }
    assert artifact.source_node_type == "SaveImage"


def test_save_artifact_persists_video_metadata(db_session) -> None:
    """Generic artifacts store delivery, source, workflow, and video metadata."""
    record = save_artifact(
        gallery_path="2026-06-22/video_job.mp4",
        artifact_type="video",
        mime_type="video/mp4",
        job_id="job-video",
        source_node_id="42",
        source_node_type="VHS_VideoCombine",
        file_size=1024,
        workflow_json={"42": {"class_type": "VHS_VideoCombine"}},
        prompt="slow pan",
        negative_prompt="blur",
        metadata={"output_key": "gifs"},
        fps=12.0,
        frame_count=24,
        duration=2.0,
        width=512,
        height=512,
        db=db_session,
    )

    assert record.id is not None
    assert record.job_id == "job-video"
    assert record.artifact_type == "video"
    assert record.gallery_path == "2026-06-22/video_job.mp4"
    assert record.mime_type == "video/mp4"
    assert record.source_node_id == "42"
    assert record.source_node_type == "VHS_VideoCombine"
    assert record.file_size == 1024
    assert record.workflow_json == '{"42": {"class_type": "VHS_VideoCombine"}}'
    assert record.prompt == "slow pan"
    assert record.negative_prompt == "blur"
    assert record.metadata_json == '{"output_key": "gifs"}'
    assert record.fps == 12.0
    assert record.frame_count == 24
    assert record.duration == 2.0
    assert record.width == 512
    assert record.height == 512
    assert record.created_at is not None
