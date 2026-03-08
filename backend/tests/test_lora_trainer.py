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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

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
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

    client = TestClient(app)
    res = client.post("/api/lora-train/trigger-check")

    assert res.status_code == 200
    data = res.json()
    assert "should_trigger" in data
    assert "candidates" in data
    assert data["should_trigger"] is True


@patch("app.services.lora_trainer.get_settings")
def test_list_folders_returns_trainable_folders_with_count(
    mock_settings: MagicMock, valid_train_dir: Path
) -> None:
    """list_folders 回傳含可訓練圖片的資料夾與圖片數"""
    base = valid_train_dir / "lora_train"
    (base / "other").mkdir()
    (base / "other" / "x.png").write_bytes(b"x")
    (base / "other" / "x.txt").write_text("x", encoding="utf-8")
    mock_settings.return_value.lora_train_dir = str(base)

    result = lora_trainer.list_folders()

    assert len(result) >= 2  # my_lora, other
    folders = {r["folder"]: r["image_count"] for r in result}
    assert "my_lora" in folders
    assert folders["my_lora"] == 2
    assert "other" in folders
    assert folders["other"] == 1


@patch("app.services.lora_trainer.get_settings")
def test_list_folders_returns_empty_when_no_valid_folders(
    mock_settings: MagicMock, tmp_path: Path
) -> None:
    """list_folders 無可訓練資料夾時回傳空陣列"""
    empty = tmp_path / "empty"
    empty.mkdir()
    mock_settings.return_value.lora_train_dir = str(empty)

    result = lora_trainer.list_folders()

    assert result == []


@patch("app.services.lora_trainer.get_settings")
def test_api_folders_returns_list(mock_settings: MagicMock, valid_train_dir: Path) -> None:
    """GET /api/lora-train/folders 回傳可訓練資料夾列表"""
    from fastapi.testclient import TestClient
    from app.main import app

    base = valid_train_dir / "lora_train"
    mock_settings.return_value.lora_train_dir = str(base)

    client = TestClient(app)
    res = client.get("/api/lora-train/folders")

    assert res.status_code == 200
    data = res.json()
    assert "folders" in data
    assert len(data["folders"]) >= 1
    assert any(f["folder"] == "my_lora" for f in data["folders"])
    assert all("image_count" in f for f in data["folders"])


@patch("app.main.queue_submit")
@patch("app.main.get_settings")
def test_on_lora_complete_submits_to_queue(
    mock_settings: MagicMock, mock_queue_submit: MagicMock
) -> None:
    """LoRA 訓練完成 callback 會提交產圖至 queue"""
    mock_settings.return_value.lora_auto_prompt = "1girl"
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"

    from app.main import _on_lora_complete

    _on_lora_complete("/path/to/lora.safetensors", "my_lora")

    mock_queue_submit.assert_called_once()
    call_args = mock_queue_submit.call_args[0][0]
    assert call_args["lora"] == "lora.safetensors"  # ComfyUI 用檔名，依 extra_model_paths 解析
    assert call_args["prompt"] == "1girl"
    assert call_args["checkpoint"] == "model.ckpt"
