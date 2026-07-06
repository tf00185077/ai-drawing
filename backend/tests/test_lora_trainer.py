"""LoRA 訓練執行器單元測試"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import lora_trainer


def test_resolve_checkpoint_path_windows_absolute() -> None:
    """本機 Windows 路徑應解析為絕對路徑"""
    result = lora_trainer._resolve_checkpoint_path(
        r"D:\AI\ComfyUI\models\checkpoints\incursiosMemeDiffusion_v16PDXL.safetensors"
    )
    assert "D:" in result or "d:" in result
    assert "incursiosMemeDiffusion" in result
    assert result.endswith(".safetensors")


def test_resolve_checkpoint_path_huggingface_id_unchanged() -> None:
    """HuggingFace 模型 ID 應原樣回傳"""
    hf_id = "stabilityai/stable-diffusion-xl-base-1.0"
    result = lora_trainer._resolve_checkpoint_path(hf_id)
    assert result == hf_id


@patch("app.services.lora_trainer.get_settings")
def test_resolve_checkpoint_path_pure_filename_prepends_lora_checkpoint_dirs(
    mock_settings: MagicMock,
) -> None:
    """純檔名應與 LORA_CHECKPOINT_DIRS 首個路徑合併為絕對路徑"""
    mock_settings.return_value.lora_checkpoint_dirs = "D:/AI/ComfyUI/models/checkpoints"
    result = lora_trainer._resolve_checkpoint_path("model.safetensors")
    assert "model.safetensors" in result
    assert "D:" in result or "d:" in result
    assert "checkpoints" in result
    assert result.endswith("model.safetensors")


def test_set_and_get_pending_generate() -> None:
    """set_pending_generate 與 get_and_clear_pending_generate 正確存取與清除"""
    params = {"prompt": "2girls, beach", "count": 10, "batch_size": 8}
    lora_trainer.set_pending_generate("lovelive", params)
    got = lora_trainer.get_and_clear_pending_generate("lovelive")
    assert got == params
    assert lora_trainer.get_and_clear_pending_generate("lovelive") is None


def _mixed_precision_arg(cmd: list[str]) -> str:
    return cmd[cmd.index("--mixed_precision") + 1]


def _network_module_arg(cmd: list[str]) -> str:
    return cmd[cmd.index("--network_module") + 1]


def _arg_after(cmd: list[str], name: str) -> str:
    return cmd[cmd.index(name) + 1]


def _train_script_arg(cmd: list[str]) -> str:
    script_names = {"train_network.py", "sdxl_train_network.py", "anima_train_network.py"}
    for item in cmd:
        name = Path(item).name
        if name in script_names:
            return name
    raise AssertionError(f"train script not found in command: {cmd}")


@pytest.mark.parametrize(
    ("kwargs", "expected_script", "expected_network_module"),
    [
        ({"model_family": "sd15"}, "train_network.py", "networks.lora"),
        ({"model_family": "sdxl"}, "sdxl_train_network.py", "networks.lora"),
        ({"model_family": "anima"}, "anima_train_network.py", "networks.lora_anima"),
        ({"sdxl": True}, "sdxl_train_network.py", "networks.lora"),
    ],
)
def test_run_training_subprocess_routes_model_families_to_expected_train_script(
    tmp_path: Path, monkeypatch, kwargs: dict, expected_script: str, expected_network_module: str
) -> None:
    """SD1.x, SDXL, and Anima families use their dedicated Kohya entrypoints and LoRA modules."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    sd_scripts = tmp_path / "sd-scripts"
    sd_scripts.mkdir()
    if kwargs.get("model_family") == "anima":
        qwen3 = tmp_path / "qwen_3_06b_base.safetensors"
        qwen3.write_bytes(b"qwen3")
        kwargs = {**kwargs, "anima_qwen3": str(qwen3)}
    settings = SimpleNamespace(sd_scripts_python="", lora_save_every_n_epochs=None)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)

    with patch("app.services.lora_trainer.subprocess.Popen") as mock_popen:
        lora_trainer._run_training_subprocess(
            image_dir=image_dir,
            output_dir=output_dir,
            output_name="probe",
            checkpoint="model.safetensors",
            epochs=1,
            sd_scripts_path=sd_scripts,
            **kwargs,
        )

    cmd = mock_popen.call_args.args[0]
    assert _train_script_arg(cmd) == expected_script
    assert _network_module_arg(cmd) == expected_network_module


def test_run_training_subprocess_appends_anima_runtime_args(
    tmp_path: Path, monkeypatch
) -> None:
    """Anima command includes the required Qwen3/VAE flags and Kohya full-precision value."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    sd_scripts = tmp_path / "sd-scripts"
    sd_scripts.mkdir()
    qwen3 = tmp_path / "qwen_3_06b_base.safetensors"
    qwen3.write_bytes(b"qwen3")
    vae = tmp_path / "qwen_image_vae.safetensors"
    vae.write_bytes(b"vae")
    t5 = tmp_path / "t5_old"
    t5.mkdir()
    settings = SimpleNamespace(sd_scripts_python="", lora_save_every_n_epochs=None)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)

    with patch("app.services.lora_trainer.subprocess.Popen") as mock_popen:
        lora_trainer._run_training_subprocess(
            image_dir=image_dir,
            output_dir=output_dir,
            output_name="probe",
            checkpoint="anima_baseV10.safetensors",
            epochs=1,
            sd_scripts_path=sd_scripts,
            model_family="anima",
            mixed_precision="fp32",
            anima_qwen3=str(qwen3),
            anima_vae=str(vae),
            anima_t5_tokenizer_path=str(t5),
        )

    cmd = mock_popen.call_args.args[0]
    assert _train_script_arg(cmd) == "anima_train_network.py"
    assert _network_module_arg(cmd) == "networks.lora_anima"
    assert _arg_after(cmd, "--qwen3") == str(qwen3.resolve())
    assert _arg_after(cmd, "--vae") == str(vae.resolve())
    assert _arg_after(cmd, "--t5_tokenizer_path") == str(t5.resolve())
    assert _mixed_precision_arg(cmd) == "no"


def test_run_training_subprocess_respects_explicit_network_module_override(
    tmp_path: Path, monkeypatch
) -> None:
    """Callers can override the family default network module when needed."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    sd_scripts = tmp_path / "sd-scripts"
    sd_scripts.mkdir()
    qwen3 = tmp_path / "qwen_3_06b_base.safetensors"
    qwen3.write_bytes(b"qwen3")
    settings = SimpleNamespace(sd_scripts_python="", lora_save_every_n_epochs=None)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)

    with patch("app.services.lora_trainer.subprocess.Popen") as mock_popen:
        lora_trainer._run_training_subprocess(
            image_dir=image_dir,
            output_dir=output_dir,
            output_name="probe",
            checkpoint="anima_baseV10.safetensors",
            epochs=1,
            sd_scripts_path=sd_scripts,
            model_family="anima",
            network_module="networks.custom_anima_lora",
            anima_qwen3=str(qwen3),
        )

    cmd = mock_popen.call_args.args[0]
    assert _train_script_arg(cmd) == "anima_train_network.py"
    assert _network_module_arg(cmd) == "networks.custom_anima_lora"


def test_run_training_subprocess_maps_requested_fp32_to_kohya_no(
    tmp_path: Path, monkeypatch
) -> None:
    """Kohya full precision uses CLI value `no`, never the API-compatible `fp32`."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    sd_scripts = tmp_path / "sd-scripts"
    sd_scripts.mkdir()
    settings = SimpleNamespace(sd_scripts_python="", lora_save_every_n_epochs=None)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)

    with patch("app.services.lora_trainer.subprocess.Popen") as mock_popen:
        lora_trainer._run_training_subprocess(
            image_dir=image_dir,
            output_dir=output_dir,
            output_name="probe",
            checkpoint="model.safetensors",
            epochs=1,
            sd_scripts_path=sd_scripts,
            mixed_precision="fp32",
        )

    cmd = mock_popen.call_args.args[0]
    assert _mixed_precision_arg(cmd) == "no"
    assert "--mixed_precision" in cmd
    assert "fp32" not in cmd


def test_run_training_subprocess_accepts_kohya_no_for_full_precision(
    tmp_path: Path, monkeypatch
) -> None:
    """Callers may pass Kohya's native `no` full-precision value directly."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    sd_scripts = tmp_path / "sd-scripts"
    sd_scripts.mkdir()
    settings = SimpleNamespace(sd_scripts_python="", lora_save_every_n_epochs=None)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)

    with patch("app.services.lora_trainer.subprocess.Popen") as mock_popen:
        lora_trainer._run_training_subprocess(
            image_dir=image_dir,
            output_dir=output_dir,
            output_name="probe",
            checkpoint="model.safetensors",
            epochs=1,
            sd_scripts_path=sd_scripts,
            mixed_precision="no",
        )

    cmd = mock_popen.call_args.args[0]
    assert _mixed_precision_arg(cmd) == "no"


def test_get_pending_generate_nonexistent_returns_none() -> None:
    """不存在的 folder 呼叫 get_and_clear_pending_generate 回傳 None"""
    assert lora_trainer.get_and_clear_pending_generate("nonexistent") is None


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
    (tmp_path / "train_network.py").write_text("# kohya train script\n", encoding="utf-8")
    (tmp_path / "sdxl_train_network.py").write_text("# kohya sdxl train script\n", encoding="utf-8")
    (tmp_path / "anima_train_network.py").write_text("# kohya anima train script\n", encoding="utf-8")
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
def test_enqueue_missing_sd_scripts_path_raises_trainer_error_without_queueing(
    mock_settings: MagicMock, valid_train_dir: Path, tmp_path: Path
) -> None:
    """enqueue 在缺少 sd-scripts 目錄時應入列前失敗。"""
    mock_settings.return_value.lora_train_dir = str(valid_train_dir / "lora_train")
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"
    mock_settings.return_value.lora_train_threshold = 10
    mock_settings.return_value.sd_scripts_path = str(tmp_path / "missing-sd-scripts")
    mock_settings.return_value.lora_resolution = 512
    mock_settings.return_value.lora_batch_size = 4
    mock_settings.return_value.lora_learning_rate = "1e-4"
    mock_settings.return_value.lora_class_tokens = "sks"
    mock_settings.return_value.lora_keep_tokens = 1
    mock_settings.return_value.lora_num_repeats = 10
    mock_settings.return_value.lora_mixed_precision = "fp16"
    mock_settings.return_value.lora_network_dim = 16
    mock_settings.return_value.lora_network_alpha = 16

    with patch("app.services.lora_trainer._create_persistent_job") as mock_create:
        with pytest.raises(lora_trainer.TrainerServiceError) as exc:
            lora_trainer.enqueue("my_lora", checkpoint="model.ckpt", epochs=5)

    assert exc.value.code == "sd_scripts_path_missing"
    assert exc.value.details["sd_scripts_path"].endswith("missing-sd-scripts")
    mock_create.assert_not_called()
    st = lora_trainer.get_status()
    assert st["status"] == "idle"
    assert st["queue"] == []


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


def test_api_start_does_not_reference_removed_generate_after() -> None:
    """POST /start 不應讀取或轉送已移除的 generate_after 欄位"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    with patch("app.api.lora_train.lora_trainer.enqueue", return_value="job-123") as mock_enqueue:
        res = client.post(
            "/api/lora-train/start",
            json={"folder": "my_lora", "checkpoint": "model.ckpt", "epochs": 5},
        )

    assert res.status_code == 202
    assert res.json()["job_id"] == "job-123"
    assert "generate_after" not in mock_enqueue.call_args.kwargs


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
    mock_settings.return_value.sd_scripts_path = str(valid_train_dir)

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
def test_on_lora_complete_does_not_submit_to_queue(
    mock_settings: MagicMock, mock_queue_submit: MagicMock
) -> None:
    """LoRA 訓練完成 callback 不再自動提交生圖，改由 smoke-test endpoint 處理。"""
    mock_settings.return_value.lora_auto_prompt = "1girl"
    mock_settings.return_value.lora_default_checkpoint = "model.ckpt"

    from app.main import _on_lora_complete

    _on_lora_complete("/path/to/lora.safetensors", "my_lora")

    mock_queue_submit.assert_not_called()
