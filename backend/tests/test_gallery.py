"""圖庫 API 單元測試"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.db.models import GeneratedArtifact, GeneratedImage
from app.core.recording import save
from app.main import app


@pytest.fixture
def client():
    """使用 in-memory DB 覆寫 get_db（StaticPool 確保單一連線共用同一 DB）"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestSessionLocal() as session:
        session.add(
            GeneratedArtifact(
                job_id="job-video",
                artifact_type="video",
                gallery_path="2024-01/video.mp4",
                mime_type="video/mp4",
                file_size=1234,
                source_node_id="42",
                source_node_type="VHS_VideoCombine",
                workflow_json='{"42": {"class_type": "VHS_VideoCombine"}}',
                prompt="slow pan",
                negative_prompt="blur",
                metadata_json='{"output_key": "gifs"}',
                fps=12.0,
                frame_count=24,
                duration=2.0,
                width=512,
                height=512,
            )
        )
        session.commit()
        save(image_path="2024-01/test1.png", job_id="job-1", checkpoint="model.safetensors", prompt="1girl", db=session)
        save(image_path="2024-01/test2.png", lora="lora.safetensors", seed=999, db=session)

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_list_images_returns_items(client) -> None:
    """GET /api/gallery/ 回傳圖庫列表"""
    res = client.get("/api/gallery/")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_list_images_exposes_job_identity(client) -> None:
    data = client.get("/api/gallery/", params={"image_id": 1}).json()
    assert data["items"][0]["job_id"] == "job-1"


def test_list_images_filter_by_image_id(client) -> None:
    """GET /api/gallery/?image_id=1 回傳該 ID 圖片"""
    res = client.get("/api/gallery/", params={"image_id": 1})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == 1


def test_list_images_filter_by_image_name(client) -> None:
    """GET /api/gallery/?image_name=test1 依路徑關鍵字模糊查詢"""
    res = client.get("/api/gallery/", params={"image_name": "test1"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any("test1" in (it.get("image_path") or "") for it in data["items"])


def test_get_image_detail_returns_404_for_invalid_id(client) -> None:
    """GET /api/gallery/99999 回傳 404"""
    res = client.get("/api/gallery/99999")
    assert res.status_code == 404


def test_get_artifact_detail_returns_video_metadata(client) -> None:
    """GET /api/gallery/artifacts/{id} 回傳影片 artifact metadata"""
    res = client.get("/api/gallery/artifacts/1")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["job_id"] == "job-video"
    assert data["artifact_type"] == "video"
    assert data["mime_type"] == "video/mp4"
    assert data["gallery_path"] == "2024-01/video.mp4"
    assert data["artifact_url"] == "/gallery/2024-01/video.mp4"
    assert Path(data["local_path"]).parts[-2:] == ("2024-01", "video.mp4")
    assert data["file_size"] == 1234
    assert data["source_node_id"] == "42"
    assert data["source_node_type"] == "VHS_VideoCombine"
    assert data["workflow_json"] == '{"42": {"class_type": "VHS_VideoCombine"}}'
    assert data["prompt"] == "slow pan"
    assert data["negative_prompt"] == "blur"
    assert data["metadata_json"] == '{"output_key": "gifs"}'
    assert data["fps"] == 12.0
    assert data["frame_count"] == 24
    assert data["duration"] == 2.0
    assert data["width"] == 512
    assert data["height"] == 512


def test_get_artifact_detail_returns_structured_404(client) -> None:
    """GET /api/gallery/artifacts/{id} 對未知 artifact 回傳結構化錯誤"""
    res = client.get("/api/gallery/artifacts/9999")
    assert res.status_code == 404
    assert res.json()["detail"] == {"error": "artifact_not_found", "artifact_id": 9999}


def test_rerun_returns_202_with_job_id(client) -> None:
    """POST /api/gallery/1/rerun 一鍵重現回傳 202 與 job_id"""
    res = client.post("/api/gallery/1/rerun")
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "已加入生圖佇列" in (data.get("message") or "")


def test_rerun_returns_404_for_invalid_id(client) -> None:
    """POST /api/gallery/99999/rerun 回傳 404"""
    res = client.post("/api/gallery/99999/rerun")
    assert res.status_code == 404


# Slack 相關測試已移除，因為 Slack 功能已從系統中移除


def test_export_json_returns_image_detail(client) -> None:
    """GET /api/gallery/1/export?format=json 回傳與 GET /{id} 同構"""
    res = client.get("/api/gallery/1/export?format=json")
    assert res.status_code == 200
    assert res.headers.get("content-type", "").startswith("application/json")
    data = res.json()
    assert data["id"] == 1
    assert "image_path" in data
    assert data["prompt"] == "1girl"


def test_export_csv_returns_csv_content(client) -> None:
    """GET /api/gallery/1/export?format=csv 回傳 CSV"""
    res = client.get("/api/gallery/1/export?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    text = res.text
    assert "id,image_path,checkpoint" in text or "id" in text
    assert "1girl" in text
