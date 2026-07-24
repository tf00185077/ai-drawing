"""生圖 API 端點測試"""
import json
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
from app.db.models import GeneratedArtifact, GeneratedImage
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


def test_post_generate_omitted_batch_seed_mode_preserves_legacy_queue_payload(client) -> None:
    with patch("app.api.generate.submit", return_value="job-shared") as mock_submit:
        response = client.post(
            "/api/generate/",
            json={"prompt": "legacy batch", "batch_size": 4},
        )

    assert response.status_code == 201
    params = mock_submit.call_args.args[0]
    assert params["batch_size"] == 4
    assert "batch_seed_mode" not in params


def test_post_generate_forwards_independent_random_batch_mode(client) -> None:
    with patch("app.api.generate.submit", return_value="job-independent") as mock_submit:
        response = client.post(
            "/api/generate/",
            json={
                "prompt": "independent batch",
                "batch_size": 4,
                "batch_seed_mode": "independent",
            },
        )

    assert response.status_code == 201
    params = mock_submit.call_args.args[0]
    assert params["batch_size"] == 4
    assert params["batch_seed_mode"] == "independent"
    assert "seed" not in params


def test_post_generate_forwards_explicit_shared_batch_mode(client) -> None:
    with patch("app.api.generate.submit", return_value="job-shared") as mock_submit:
        response = client.post(
            "/api/generate/",
            json={
                "prompt": "shared batch",
                "batch_size": 4,
                "batch_seed_mode": "shared",
                "seed_mode": "fixed",
                "seed": 123,
            },
        )

    assert response.status_code == 201
    params = mock_submit.call_args.args[0]
    assert params["batch_seed_mode"] == "shared"
    assert params["seed_mode"] == "fixed"
    assert params["seed"] == 123


def test_post_generate_rejects_independent_fixed_seed_mode(client) -> None:
    response = client.post(
        "/api/generate/",
        json={
            "prompt": "invalid independent batch",
            "batch_seed_mode": "independent",
            "seed_mode": "fixed",
            "seed": 123,
        },
    )

    assert response.status_code == 422


def test_post_generate_rejects_independent_workflow_default_seed_mode(client) -> None:
    response = client.post(
        "/api/generate/",
        json={
            "prompt": "invalid independent batch",
            "batch_seed_mode": "independent",
            "use_workflow_defaults": True,
            "seed_mode": "workflow_default",
        },
    )

    assert response.status_code == 422


def test_post_generate_rejects_independent_explicit_seed(client) -> None:
    response = client.post(
        "/api/generate/",
        json={
            "prompt": "invalid independent batch",
            "batch_seed_mode": "independent",
            "seed": 123,
        },
    )

    assert response.status_code == 422


def test_get_queue_returns_valid_structure(client) -> None:
    """GET /api/generate/queue 回傳正確結構"""
    r = client.get("/api/generate/queue")
    assert r.status_code == 200
    data = r.json()
    assert "queue_running" in data
    assert "queue_pending" in data
    assert isinstance(data["queue_running"], list)
    assert isinstance(data["queue_pending"], list)


def test_get_queue_preserves_additive_independent_batch_progress(client) -> None:
    aggregate = {
        "job_id": "parent-queue",
        "status": "running",
        "submitted_at": "2026-07-25T01:02:03Z",
        "prompt_id": "prompt-2",
        "batch_total": 4,
        "batch_completed": 1,
        "batch_failed": 1,
        "current_batch_index": 2,
        "failed_members": [
            {
                "batch_index": 1,
                "seed": 22,
                "code": "comfyui_execution_error",
                "message": "failed",
            }
        ],
    }
    with patch(
        "app.api.generate.get_status",
        return_value={"queue_running": [aggregate], "queue_pending": []},
    ):
        response = client.get("/api/generate/queue")

    assert response.status_code == 200
    assert response.json()["queue_running"] == [aggregate]


def test_get_queue_preserves_legacy_shared_item_shape(client) -> None:
    legacy = {
        "job_id": "shared-job",
        "status": "queued",
        "submitted_at": "2026-07-25T01:02:03Z",
        "prompt_id": None,
    }
    queue_item = {key: value for key, value in legacy.items() if key != "prompt_id"}
    with patch(
        "app.api.generate.get_status",
        return_value={"queue_running": [], "queue_pending": [queue_item]},
    ):
        response = client.get("/api/generate/queue")

    assert response.status_code == 200
    assert response.json()["queue_pending"] == [legacy]


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


def test_post_generate_custom_rejects_independent_batch_seed_mode(client) -> None:
    response = client.post(
        "/api/generate/custom",
        json={
            "workflow": {"3": {"class_type": "KSampler", "inputs": {}}},
            "prompt": "immutable custom graph",
            "batch_seed_mode": "independent",
        },
    )

    assert response.status_code == 422


def test_post_generate_forwards_loras_to_queue(client) -> None:
    """POST /api/generate/ forwards ordered multi-LoRA payloads without dropping single-LoRA compatibility fields."""
    loras = [
        {"name": "style.safetensors", "strength_model": 0.8},
        {"name": "character.safetensors", "strength_model": 0.6, "strength_clip": 0.4},
    ]
    with patch("app.api.generate.submit", return_value="job-loras") as mock_submit:
        r = client.post(
            "/api/generate/",
            json={
                "prompt": "1girl",
                "template": "multi_lora",
                "lora": "legacy.safetensors",
                "lora_strength": 0.7,
                "loras": loras,
            },
        )

    assert r.status_code == 201
    params = mock_submit.call_args[0][0]
    assert params["template"] == "multi_lora"
    assert params["lora"] == "legacy.safetensors"
    assert params["lora_strength"] == 0.7
    assert params["loras"] == loras


def test_post_generate_custom_forwards_loras_to_queue(client) -> None:
    """POST /api/generate/custom forwards ordered multi-LoRA payloads to the custom queue path."""
    wf = {
        "10": {"class_type": "LoraLoader", "inputs": {}},
        "11": {"class_type": "LoraLoaderModelOnly", "inputs": {}},
    }
    loras = [
        {"name": "detail.safetensors", "strength_model": 0.5},
        {"name": "motion.safetensors", "strength_model": 0.9, "strength_clip": 0.2},
    ]
    with patch("app.api.generate.submit_custom", return_value="custom-loras") as mock_submit:
        r = client.post(
            "/api/generate/custom",
            json={
                "workflow": wf,
                "prompt": "1girl",
                "lora": "legacy.safetensors",
                "lora_strength": 0.4,
                "loras": loras,
            },
        )

    assert r.status_code == 201
    params = mock_submit.call_args[0][0]
    assert params["workflow"] == wf
    assert params["lora"] == "legacy.safetensors"
    assert params["lora_strength"] == 0.4
    assert params["loras"] == loras


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


def test_get_job_status_returns_only_completed_saveimage_artifacts() -> None:
    from app.core.generation_batches import create_batch, mark_member_terminal

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    with session_factory() as db:
        create_batch(
            db,
            public_job_id="parent-mixed-api",
            execution_ids=("a", "b", "c", "d"),
            seeds=(10, 20, 30, 40),
            submitted_at="2026-07-25T01:02:03Z",
        )
        for batch_index in (0, 1, 2):
            mark_member_terminal(
                db,
                public_job_id="parent-mixed-api",
                batch_index=batch_index,
                succeeded=True,
            )
        mark_member_terminal(
            db,
            public_job_id="parent-mixed-api",
            batch_index=3,
            succeeded=False,
            failure_code="comfyui_execution_error",
            failure_message="sampler failed",
        )
        db.add_all(
            [
                GeneratedArtifact(
                    job_id="parent-mixed-api",
                    artifact_type="image",
                    gallery_path="2026-07-25/member-2.png",
                    mime_type="image/png",
                    source_node_type="SaveImage",
                    metadata_json=json.dumps(
                        {"batch_index": 2, "seed": 30}
                    ),
                ),
                GeneratedArtifact(
                    job_id="parent-mixed-api",
                    artifact_type="image",
                    gallery_path="2026-07-25/preview-0.png",
                    mime_type="image/png",
                    source_node_type="PreviewImage",
                    metadata_json=json.dumps(
                        {"batch_index": 0, "seed": 10}
                    ),
                ),
                GeneratedArtifact(
                    job_id="parent-mixed-api",
                    artifact_type="image",
                    gallery_path="2026-07-25/member-0.png",
                    mime_type="image/png",
                    source_node_type="SaveImage",
                    metadata_json=json.dumps(
                        {"batch_index": 0, "seed": 10}
                    ),
                ),
                GeneratedArtifact(
                    job_id="parent-mixed-api",
                    artifact_type="image",
                    gallery_path="2026-07-25/member-1.png",
                    mime_type="image/png",
                    source_node_type="SaveImage",
                    metadata_json=json.dumps(
                        {"batch_index": 1, "seed": 20}
                    ),
                ),
                GeneratedArtifact(
                    job_id="parent-mixed-api",
                    artifact_type="image",
                    gallery_path="2026-07-25/leaked-failed-member.png",
                    mime_type="image/png",
                    source_node_type="SaveImage",
                    metadata_json=json.dumps(
                        {"batch_index": 3, "seed": 40}
                    ),
                ),
            ]
        )
        db.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get(
            "/api/generate/job/parent-mixed-api"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["batch_total"] == 4
    assert data["batch_completed"] == 3
    assert data["batch_failed"] == 1
    assert data["failed_members"] == [
        {
            "batch_index": 3,
            "seed": 40,
            "code": "comfyui_execution_error",
            "message": "sampler failed",
        }
    ]
    assert [item["gallery_path"] for item in data["artifacts"]] == [
        "2026-07-25/member-0.png",
        "2026-07-25/member-1.png",
        "2026-07-25/member-2.png",
    ]
    assert [item["batch_index"] for item in data["artifacts"]] == [0, 1, 2]
    assert [item["seed"] for item in data["artifacts"]] == [10, 20, 30]


def test_get_job_status_persisted_all_failed_batch_returns_no_artifacts() -> None:
    from app.core.generation_batches import create_batch, mark_member_terminal

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    with session_factory() as db:
        create_batch(
            db,
            public_job_id="parent-all-failed",
            execution_ids=("a", "b"),
            seeds=(10, 20),
            submitted_at="2026-07-25T01:02:03Z",
        )
        for batch_index in (0, 1):
            mark_member_terminal(
                db,
                public_job_id="parent-all-failed",
                batch_index=batch_index,
                succeeded=False,
                failure_code="comfyui_execution_error",
                failure_message=f"member {batch_index} failed",
            )
        db.add(
            GeneratedArtifact(
                job_id="parent-all-failed",
                artifact_type="image",
                gallery_path="2026-07-25/leaked-partial-recording.png",
                mime_type="image/png",
                source_node_type="SaveImage",
                metadata_json=json.dumps(
                    {"batch_index": 0, "seed": 10}
                ),
            )
        )
        db.add(
            GeneratedImage(
                job_id="parent-all-failed",
                image_path="2026-07-25/leaked-partial-recording.png",
                seed=10,
            )
        )
        db.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get(
            "/api/generate/job/parent-all-failed"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["batch_total"] == 2
    assert data["batch_completed"] == 0
    assert data["batch_failed"] == 2
    assert data["artifacts"] == []
    assert "image_id" not in data
    assert "image_path" not in data
def test_get_workflow_templates_returns_list(client) -> None:
    """GET /api/generate/workflow-templates 回傳模板列表"""
    r = client.get("/api/generate/workflow-templates")
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)
    assert "default" in data["templates"]
