"""生圖 API 端點測試"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.queue import _reset_for_test
from app.core.recording import save
from app.db.database import Base, get_db
from app.db.models import GeneratedArtifact
from app.main import app


def setup_function() -> None:
    _reset_for_test()


def test_post_generate_returns_201_with_job_id(client) -> None:
    """POST /api/generate/ 回傳 201 與 job_id"""
    r = client.post(
        "/api/generate/",
        json={"prompt": "1girl, solo"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "已加入" in (data.get("message") or "")


def test_post_generate_returns_503_when_queue_full(client) -> None:
    """佇列已滿時 POST 回傳 503"""
    from app.core.queue import QueueFullError

    with patch("app.api.generate.submit", side_effect=QueueFullError("full")):
        r = client.post(
            "/api/generate/",
            json={"prompt": "test"},
        )
    assert r.status_code == 503


def test_get_queue_returns_valid_structure(client) -> None:
    """GET /api/generate/queue 回傳正確結構"""
    r = client.get("/api/generate/queue")
    assert r.status_code == 200
    data = r.json()
    assert "queue_running" in data
    assert "queue_pending" in data
    assert isinstance(data["queue_running"], list)
    assert isinstance(data["queue_pending"], list)


def test_available_resources_includes_empty_video_categories(client) -> None:
    r = client.get("/api/generate/available-resources")
    assert r.status_code == 200
    data = r.json()
    assert data["video_models"] == []
    assert data["video_loras"] == []
    assert data["video_inputs"] == []


def test_available_resources_exposes_loras_from_inventory(client, tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    lora_dir = tmp_path / "loras"
    checkpoint_dir.mkdir()
    lora_dir.mkdir()
    (checkpoint_dir / "base.safetensors").write_text("x", encoding="utf-8")
    (lora_dir / "artist.safetensors").write_text("x", encoding="utf-8")
    (lora_dir / "character.ckpt").write_text("x", encoding="utf-8")
    (lora_dir / "ignore.txt").write_text("x", encoding="utf-8")
    settings = SimpleNamespace(
        comfyui_checkpoints_dir=str(checkpoint_dir),
        comfyui_loras_dir=str(lora_dir),
        comfyui_diffusion_models_dir="",
        comfyui_text_encoders_dir="",
        comfyui_vae_dir="",
        lora_default_checkpoint="fallback.safetensors",
    )

    with patch("app.api.generate.get_settings", return_value=settings):
        r = client.get("/api/generate/available-resources")

    assert r.status_code == 200
    data = r.json()
    assert data["checkpoints"] == ["base.safetensors"]
    assert data["loras"] == ["artist.safetensors", "character.ckpt"]
    assert isinstance(data["loras"], list)


def test_post_generate_custom_returns_201(client) -> None:
    """POST /api/generate/custom 接受 workflow 回傳 201"""
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {"class_type": "KSampler", "inputs": {"positive": ["6", 0], "negative": ["7", 0]}},
    }
    r = client.post(
        "/api/generate/custom",
        json={"workflow": wf, "prompt": "1girl, solo"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "job_id" in data
    assert "自訂" in (data.get("message") or "")


def test_post_generate_video_custom_returns_201(client) -> None:
    """POST /api/generate/video/custom accepts supplied workflow and queues a job."""
    wf = {
        "20": {"class_type": "VHS_VideoCombine", "inputs": {}},
    }
    r = client.post(
        "/api/generate/video/custom",
        json={"workflow": wf, "prompt": "slow pan"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "影片" in (data.get("message") or "")


def test_post_generate_video_custom_forwards_optional_refs(client) -> None:
    wf = {"20": {"class_type": "VHS_VideoCombine", "inputs": {}}}
    with patch("app.api.generate.submit_custom", return_value="video-job") as mock_submit:
        r = client.post(
            "/api/generate/video/custom",
            json={
                "workflow": wf,
                "prompt": "slow pan",
                "first_frame": "2026-06-22/start.png",
                "last_frame": "2026-06-22/end.png",
                "video_ref": "2026-06-22/ref.mp4",
            },
        )

    assert r.status_code == 201
    params = mock_submit.call_args[0][0]
    assert params["first_frame"] == "2026-06-22/start.png"
    assert params["last_frame"] == "2026-06-22/end.png"
    assert params["video_ref"] == "2026-06-22/ref.mp4"


def test_post_generate_video_custom_forwards_lora_payloads(client) -> None:
    wf = {"20": {"class_type": "VHS_VideoCombine", "inputs": {}}}
    loras = [{"name": "motion.safetensors", "strength_model": 0.7}]
    with patch("app.api.generate.submit_custom", return_value="video-lora") as mock_submit:
        r = client.post(
            "/api/generate/video/custom",
            json={
                "workflow": wf,
                "prompt": "slow pan",
                "checkpoint": "wan.safetensors",
                "lora": "style.safetensors",
                "lora_strength": 0.45,
                "loras": loras,
            },
        )

    assert r.status_code == 201
    params = mock_submit.call_args[0][0]
    assert params["checkpoint"] == "wan.safetensors"
    assert params["lora"] == "style.safetensors"
    assert params["lora_strength"] == 0.45
    assert params["loras"] == loras


def test_get_job_status_returns_completed_video_artifacts() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    with session_factory() as db:
        db.add(
            GeneratedArtifact(
                job_id="job-video",
                artifact_type="video",
                gallery_path="2026-06-22/video.mp4",
                mime_type="video/mp4",
                file_size=2048,
                source_node_id="42",
                source_node_type="VHS_VideoCombine",
            )
        )
        db.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = TestClient(app).get("/api/generate/job/job-video")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {
        "status": "completed",
        "job_id": "job-video",
        "artifacts": [
            {
                "id": 1,
                "artifact_type": "video",
                "mime_type": "video/mp4",
                "gallery_path": "2026-06-22/video.mp4",
                "file_size": 2048,
                "job_id": "job-video",
                "source_node_id": "42",
                "source_node_type": "VHS_VideoCombine",
            }
        ],
    }


def test_get_job_status_preserves_legacy_image_fields() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    with session_factory() as db:
        save(
            image_path="2026-06-22/image.png",
            job_id="job-image",
            prompt="1girl",
            db=db,
        )

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = TestClient(app).get("/api/generate/job/job-image")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["job_id"] == "job-image"
    assert data["image_id"] == 1
    assert data["image_path"] == "2026-06-22/image.png"
    assert data["artifacts"] == [
        {
            "id": 1,
            "artifact_type": "image",
            "mime_type": "image/png",
            "gallery_path": "2026-06-22/image.png",
            "file_size": None,
            "job_id": "job-image",
            "source_node_id": None,
            "source_node_type": None,
        }
    ]


def test_get_workflow_templates_returns_list(client) -> None:
    """GET /api/generate/workflow-templates 回傳模板列表"""
    r = client.get("/api/generate/workflow-templates")
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)
    assert "default" in data["templates"]
