"""生成統計分析單元測試"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.db.models import GeneratedImage
from app.core.recording import save
from app.main import app
from app.services.analytics import get_stats, _parse_date


@pytest.fixture
def db_session():
    """In-memory DB with sample data"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    save(image_path="2024-01/a.png", checkpoint="model_a.safetensors", prompt="1girl", steps=20, cfg=7.0, seed=111, db=session)
    save(image_path="2024-01/b.png", checkpoint="model_a.safetensors", prompt="2girl", steps=25, cfg=7.5, seed=111, db=session)
    save(image_path="2024-01/c.png", checkpoint="model_b.safetensors", lora="lora_x", prompt="solo", steps=30, cfg=8.0, seed=222, db=session)

    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """TestClient with overridden get_db"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestParseDate:
    """_parse_date 測試"""

    def test_parses_iso_date(self) -> None:
        """解析 YYYY-MM-DD"""
        d = _parse_date("2024-01-15")
        assert d.year == 2024 and d.month == 1 and d.day == 15

    def test_raises_on_invalid(self) -> None:
        """無效格式拋出 ValueError"""
        with pytest.raises(ValueError):
            _parse_date("not-a-date")
        with pytest.raises(ValueError):
            _parse_date("2024-13-45")


class TestGetStats:
    """get_stats 服務層測試"""

    def test_empty_db_returns_zero_counts(self, db_session) -> None:
        """空 DB 回傳全零結構"""
        empty_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=empty_engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=empty_engine)
        empty_db = SessionLocal()
        try:
            r = get_stats(empty_db)
            assert r["total_count"] == 0
            assert r["checkpoint_usage"] == []
            assert r["steps_stats"]["count"] == 0
        finally:
            empty_db.close()

    def test_aggregates_checkpoint_and_seed_usage(self, db_session) -> None:
        """正確聚合 checkpoint、lora、seed 使用頻率"""
        r = get_stats(db_session)
        assert r["total_count"] == 3
        assert len(r["checkpoint_usage"]) >= 1
        model_a = next((u for u in r["checkpoint_usage"] if "model_a" in u["name"]), None)
        assert model_a is not None
        assert model_a["count"] == 2
        assert r["steps_stats"]["min"] == 20 and r["steps_stats"]["max"] == 30
        assert any(s["seed"] == 111 and s["count"] == 2 for s in r["top_seeds"])


class TestAnalyticsAPI:
    """API 端點測試"""

    def test_summary_returns_200_with_structure(self, client) -> None:
        """GET /api/analytics/summary 回傳正確結構"""
        res = client.get("/api/analytics/summary")
        assert res.status_code == 200
        data = res.json()
        assert "total_count" in data
        assert "checkpoint_usage" in data
        assert "lora_usage" in data
        assert "steps_stats" in data
        assert "cfg_stats" in data
        assert "top_seeds" in data

    def test_summary_returns_400_for_invalid_date(self, client) -> None:
        """無效日期回傳 400"""
        res = client.get("/api/analytics/summary?from_date=invalid")
        assert res.status_code == 400
