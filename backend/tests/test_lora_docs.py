"""LoRA 文件 API 單元測試"""
import zipfile
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


@patch("app.api.lora_docs.get_settings")
def test_download_zip_returns_zip_when_folder_exists(
    mock_settings, lora_train_tmp: Path
) -> None:
    """資料夾存在時回傳 ZIP 且內容正確"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    subdir = lora_train_tmp / "my_lora"
    subdir.mkdir()
    (subdir / "img1.png").write_bytes(b"png-data")
    (subdir / "img1.txt").write_text("1girl, solo")

    res = client.get("/api/lora-docs/download-zip?folder=my_lora")

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "my_lora.zip" in res.headers.get("content-disposition", "")
    with zipfile.ZipFile(BytesIO(res.content), "r") as zf:
        names = zf.namelist()
        assert "img1.png" in names
        assert "img1.txt" in names
        assert zf.read("img1.txt").decode() == "1girl, solo"


@patch("app.api.lora_docs.get_settings")
def test_download_zip_returns_404_when_folder_not_exists(
    mock_settings, lora_train_tmp: Path
) -> None:
    """資料夾不存在時回傳 404"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    res = client.get("/api/lora-docs/download-zip?folder=nonexistent")
    assert res.status_code == 404


def test_download_zip_rejects_path_traversal() -> None:
    """folder 含 .. 時回傳 400"""
    res = client.get("/api/lora-docs/download-zip?folder=../etc")
    assert res.status_code == 400


@patch("app.api.lora_docs.get_settings")
def test_get_caption_returns_content(mock_settings, lora_train_tmp: Path) -> None:
    """GET caption 回傳 .txt 內容"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    (lora_train_tmp / "img1.png").write_bytes(b"x")
    (lora_train_tmp / "img1.txt").write_text("1girl, solo", encoding="utf-8")
    res = client.get("/api/lora-docs/caption/img1.png")
    assert res.status_code == 200
    assert res.json()["content"] == "1girl, solo"


@patch("app.api.lora_docs.get_settings")
def test_put_caption_updates_txt(mock_settings, lora_train_tmp: Path) -> None:
    """PUT caption 更新 .txt 內容"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    (lora_train_tmp / "img1.png").write_bytes(b"x")
    (lora_train_tmp / "img1.txt").write_text("old", encoding="utf-8")
    res = client.put(
        "/api/lora-docs/caption/img1.png",
        json={"content": "1girl, new caption"},
    )
    assert res.status_code == 200
    assert res.json()["path"] == "img1.txt"
    assert (lora_train_tmp / "img1.txt").read_text(encoding="utf-8") == "1girl, new caption"


@patch("app.api.lora_docs.get_settings")
def test_put_caption_returns_404_when_image_missing(mock_settings, lora_train_tmp: Path) -> None:
    """PUT caption 在圖片不存在時回傳 404"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    res = client.put(
        "/api/lora-docs/caption/nonexistent.png",
        json={"content": "x"},
    )
    assert res.status_code == 404


@patch("app.api.lora_docs.get_settings")
def test_batch_prefix_adds_prefix(mock_settings, lora_train_tmp: Path) -> None:
    """POST batch-prefix 在 .txt 前加入前綴"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    subdir = lora_train_tmp / "my_lora"
    subdir.mkdir()
    (subdir / "a.png").write_bytes(b"x")
    (subdir / "a.txt").write_text("solo", encoding="utf-8")
    (subdir / "b.png").write_bytes(b"x")
    (subdir / "b.txt").write_text("1girl", encoding="utf-8")
    res = client.post(
        "/api/lora-docs/batch-prefix",
        json={"images": ["my_lora/a.png", "my_lora/b.png"], "prefix": "sks "},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["updated"] == 2
    assert data["failed"] == []
    assert (subdir / "a.txt").read_text(encoding="utf-8") == "sks solo"
    assert (subdir / "b.txt").read_text(encoding="utf-8") == "sks 1girl"


@patch("app.api.lora_docs.get_settings")
def test_files_list_returns_items(mock_settings, lora_train_tmp: Path) -> None:
    """GET files 回傳資料夾內圖片列表"""
    mock_settings.return_value.lora_train_dir = str(lora_train_tmp)
    subdir = lora_train_tmp / "my_lora"
    subdir.mkdir()
    (subdir / "x.png").write_bytes(b"x")
    (subdir / "x.txt").write_text("caption", encoding="utf-8")
    res = client.get("/api/lora-docs/files?folder=my_lora")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["path"] == "my_lora/x.png"
    assert items[0]["caption_path"] == "my_lora/x.txt"
