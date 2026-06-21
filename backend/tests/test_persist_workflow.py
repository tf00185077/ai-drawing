"""persist-full-workflow-for-rerun：recording 持久化 workflow/來源、rerun 忠實重現"""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.recording import save
from app.db.database import Base, get_db
from app.main import app


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# --- recording 持久化 -----------------------------------------------------


def test_recording_persists_workflow_and_sources(session_factory) -> None:
    wf = {"3": {"class_type": "KSampler", "inputs": {"seed": 123}}}
    with session_factory() as db:
        rec = save(
            image_path="2026-06-20/a.png",
            prompt="1girl",
            workflow_json=wf,
            source_image="2026-06-20/subject.png",
            source_mask="2026-06-20/mask.png",
            db=db,
        )
        # dict 會被序列化為 JSON 字串，且可還原
        assert json.loads(rec.workflow_json) == wf
        assert rec.source_image == "2026-06-20/subject.png"
        assert rec.source_mask == "2026-06-20/mask.png"
        # 既有欄位仍寫入
        assert rec.prompt == "1girl"


def test_recording_txt2img_leaves_sources_null(session_factory) -> None:
    with session_factory() as db:
        rec = save(image_path="2026-06-20/b.png", prompt="x", db=db)
        assert rec.workflow_json is None
        assert rec.source_image is None
        assert rec.source_mask is None


# --- rerun 分支 -----------------------------------------------------------


@pytest.fixture
def client_with_rows(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with session_factory() as db:
        # id=1：有 workflow_json（custom），無來源圖（txt2img custom）
        save(
            image_path="d/custom.png",
            prompt="p",
            workflow_json={"3": {"class_type": "KSampler", "inputs": {"seed": 42}}},
            db=db,
        )
        # id=2：legacy，無 workflow_json
        save(image_path="d/legacy.png", checkpoint="m.safetensors", seed=7, db=db)
        # id=3：custom 但來源圖不存在於 gallery
        save(
            image_path="d/needs_src.png",
            prompt="p",
            workflow_json={"3": {"class_type": "KSampler", "inputs": {"seed": 42}}},
            source_image="nope/missing.png",
            db=db,
        )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_rerun_custom_uses_custom_path_and_reuses_seed(client_with_rows) -> None:
    with patch("app.api.gallery.submit_custom", return_value="job-custom") as m_custom, \
         patch("app.api.gallery.submit") as m_template:
        r = client_with_rows.post("/api/gallery/1/rerun")
    assert r.status_code == 202
    m_custom.assert_called_once()
    m_template.assert_not_called()
    params = m_custom.call_args[0][0]
    assert "workflow" in params
    # 不重新隨機 seed：custom 路徑省略 seed，沿用 workflow 內 baked 值
    assert "seed" not in params


def test_rerun_legacy_uses_template_path(client_with_rows) -> None:
    with patch("app.api.gallery.submit", return_value="job-legacy") as m_template, \
         patch("app.api.gallery.submit_custom") as m_custom:
        r = client_with_rows.post("/api/gallery/2/rerun")
    assert r.status_code == 202
    m_template.assert_called_once()
    m_custom.assert_not_called()
    params = m_template.call_args[0][0]
    assert "workflow" not in params
    assert params["checkpoint"] == "m.safetensors"


def test_rerun_missing_source_returns_error(client_with_rows) -> None:
    with patch("app.api.gallery.submit_custom") as m_custom:
        r = client_with_rows.post("/api/gallery/3/rerun")
    assert r.status_code == 409
    m_custom.assert_not_called()
