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
