"""LoRA 文件 API 單元測試"""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def lora_train_tmp(tmp_path: Path):
    """暫存 lora_train_dir"""
    (tmp_path / "lora_train").mkdir()
    return tmp_path / "lora_train"


@patch("app.api.lora_docs.run_wd_tagger")
@patch("app.api.lora_docs.get_settings")
def test_upload_saves_files_and_returns_items(
    mock_settings, mock_wd_tagger, lora_train_tmp: Path
) -> None:
    """上傳圖片會寫入目標目錄並回傳 items"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)

    files = [
        ("files", ("a.png", BytesIO(b"fake-png"), "image/png")),
        ("files", ("b.jpg", BytesIO(b"fake-jpg"), "image/jpeg")),
    ]
    res = client.post("/api/lora-docs/upload", files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["uploaded"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["filename"] == "a.png"
    assert data["items"][0]["caption_path"] == "a.txt"
    assert (lora_train_tmp / "a.png").exists()
    assert (lora_train_tmp / "b.jpg").exists()
    mock_wd_tagger.assert_called_once()


@patch("app.api.lora_docs.run_wd_tagger")
@patch("app.api.lora_docs.get_settings")
def test_upload_with_folder_uses_subdir(
    mock_settings, mock_wd_tagger, lora_train_tmp: Path
) -> None:
    """上傳時指定 folder 會存入子目錄"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)

    files = [("files", ("x.png", BytesIO(b"x"), "image/png"))]
    res = client.post(
        "/api/lora-docs/upload",
        files=files,
        data={"folder": "my_lora"},
    )

    assert res.status_code == 200
    assert (lora_train_tmp / "my_lora" / "x.png").exists()
    assert res.json()["items"][0]["path"] == "my_lora/x.png"
    assert res.json()["items"][0]["caption_path"] == "my_lora/x.txt"


def test_upload_rejects_path_traversal() -> None:
    """folder 含 .. 時回傳 400"""
    files = [("files", ("x.png", BytesIO(b"x"), "image/png"))]
    res = client.post(
        "/api/lora-docs/upload",
        files=files,
        data={"folder": "../etc"},
    )
    assert res.status_code == 400
