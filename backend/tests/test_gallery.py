"""圖庫 API 單元測試"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.db.models import GeneratedImage
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
        save(image_path="2024-01/test1.png", checkpoint="model.safetensors", prompt="1girl", db=session)
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


def test_get_image_detail_returns_404_for_invalid_id(client) -> None:
    """GET /api/gallery/99999 回傳 404"""
    res = client.get("/api/gallery/99999")
    assert res.status_code == 404


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


def test_rerun_accepts_slack_body(client) -> None:
    """POST /api/gallery/1/rerun 可帶入 slack_channel_id、slack_thread_ts（Slack 回傳用）"""
    res = client.post(
        "/api/gallery/1/rerun",
        json={"slack_channel_id": "C123", "slack_thread_ts": "123.456"},
    )
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data


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
