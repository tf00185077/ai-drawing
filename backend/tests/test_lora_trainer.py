"""LoRA 訓練執行器單元測試"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import lora_trainer


@pytest.fixture(autouse=True)
def reset_trainer():
    """每個測試前清空佇列"""
    lora_trainer._reset_for_test()
    yield


@pytest.fixture(autouse=True)
def mock_worker():
    """不啟動 worker 線程，測試僅驗證 enqueue/get_status"""
    with patch("app.services.lora_trainer._ensure_worker"):
        yield


@pytest.fixture
def valid_train_dir(tmp_path: Path):
    """建立含圖片+txt 的訓練資料夾"""
    folder = tmp_path / "lora_train" / "my_lora"
    folder.mkdir(parents=True)
    (folder / "a.png").write_bytes(b"fake")
    (folder / "a.txt").write_text("1girl", encoding="utf-8")
    (folder / "b.jpg").write_bytes(b"fake")
    (folder / "b.txt").write_text("solo", encoding="utf-8")
    return tmp_path


@patch("app.services.lora_trainer.get_settings")
def test_enqueue_valid_folder_returns_job_id_and_queued(
    mock_settings: MagicMock, valid_train_dir: Path
) -> None:
    """enqueue 有效資料夾時回傳 job_id，get_status 顯示 queued"""
    mock_settings.return_value.lora_train_dir = str(valid_train_dir / "lora_train")
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"
    mock_settings.return_value.lora_train_threshold = 10
    mock_settings.return_value.sd_scripts_path = str(valid_train_dir)

    job_id = lora_trainer.enqueue("my_lora", checkpoint="model.ckpt", epochs=5)

    assert job_id
    assert len(job_id) == 36  # uuid format
    st = lora_trainer.get_status()
    assert st["status"] == "queued"
    assert len(st["queue"]) == 1
    assert st["queue"][0]["job_id"] == job_id
    assert st["queue"][0]["folder"] == "my_lora"


@patch("app.services.lora_trainer.get_settings")
def test_enqueue_nonexistent_folder_raises_value_error(
    mock_settings: MagicMock, tmp_path: Path
) -> None:
    """enqueue 不存在的資料夾時拋出 ValueError"""
    mock_settings.return_value.lora_train_dir = str(tmp_path / "lora_train")
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"

    with pytest.raises(ValueError, match="資料夾不存在"):
        lora_trainer.enqueue("not_exists")


@patch("app.services.lora_trainer.get_settings")
def test_enqueue_folder_without_caption_txt_raises(
    mock_settings: MagicMock, tmp_path: Path
) -> None:
    """enqueue 資料夾無 .txt caption 時拋出 ValueError"""
    folder = tmp_path / "lora_train" / "no_txt"
    folder.mkdir(parents=True)
    (folder / "a.png").write_bytes(b"fake")
    # 無 a.txt

    mock_settings.return_value.lora_train_dir = str(tmp_path / "lora_train")
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"

    with pytest.raises(ValueError, match="圖片數不足"):
        lora_trainer.enqueue("no_txt")


@patch("app.services.lora_trainer.get_settings")
def test_get_status_idle_when_empty(mock_settings: MagicMock) -> None:
    """佇列空時 get_status 回傳 idle"""
    mock_settings.return_value.lora_train_dir = "/tmp"
    st = lora_trainer.get_status()
    assert st["status"] == "idle"
    assert st["current_job"] is None
    assert st["queue"] == []


@patch("app.services.lora_trainer.get_settings")
def test_api_start_returns_202_and_job_id(
    mock_settings: MagicMock, valid_train_dir: Path
) -> None:
    """POST /api/lora-train/start 有效請求回傳 202 與 job_id"""
    from fastapi.testclient import TestClient
    from app.main import app

    mock_settings.return_value.lora_train_dir = str(valid_train_dir / "lora_train")
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"
    mock_settings.return_value.sd_scripts_path = str(valid_train_dir)

    client = TestClient(app)
    res = client.post(
        "/api/lora-train/start",
        json={"folder": "my_lora", "checkpoint": "model.ckpt", "epochs": 5},
    )

    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "queued"


@patch("app.services.lora_trainer.get_settings")
def test_trigger_check_returns_candidates_when_folder_meets_threshold(
    mock_settings: MagicMock, valid_train_dir: Path
) -> None:
    """trigger_check 達門檻時回傳 candidates 並 enqueue"""
    base = valid_train_dir / "lora_train"
    mock_settings.return_value.lora_train_dir = str(base)
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"
    mock_settings.return_value.lora_train_threshold = 2
    mock_settings.return_value.sd_scripts_path = str(valid_train_dir)

    result = lora_trainer.trigger_check()

    assert result["should_trigger"] is True
    assert len(result["candidates"]) >= 1
    assert any(c["folder"] == "my_lora" for c in result["candidates"])
    assert any(c["image_count"] >= 2 for c in result["candidates"])
    st = lora_trainer.get_status()
    assert st["status"] == "queued"


@patch("app.services.lora_trainer.get_settings")
def test_trigger_check_returns_empty_when_below_threshold(
    mock_settings: MagicMock, tmp_path: Path
) -> None:
    """trigger_check 未達門檻時回傳空 candidates"""
    folder = tmp_path / "lora_train" / "few"
    folder.mkdir(parents=True)
    (folder / "a.png").write_bytes(b"x")
    (folder / "a.txt").write_text("x", encoding="utf-8")
    mock_settings.return_value.lora_train_dir = str(tmp_path / "lora_train")
    mock_settings.return_value.lora_train_threshold = 10

    result = lora_trainer.trigger_check()

    assert result["should_trigger"] is False
    assert result["candidates"] == []


@patch("app.services.lora_trainer.get_settings")
def test_api_trigger_check_returns_candidates(
    mock_settings: MagicMock, valid_train_dir: Path
) -> None:
    """POST /api/lora-train/trigger-check 回傳 should_trigger 與 candidates"""
    from fastapi.testclient import TestClient
    from app.main import app

    base = valid_train_dir / "lora_train"
    mock_settings.return_value.lora_train_dir = str(base)
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"
    mock_settings.return_value.lora_train_threshold = 2

    client = TestClient(app)
    res = client.post("/api/lora-train/trigger-check")

    assert res.status_code == 200
    data = res.json()
    assert "should_trigger" in data
    assert "candidates" in data
    assert data["should_trigger"] is True
