"""自動記錄 Pipeline 單元測試"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import GeneratedImage
from app.core.recording import save


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
