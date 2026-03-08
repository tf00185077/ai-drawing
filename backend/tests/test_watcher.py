"""watcher 單元測試"""
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.watcher import on_new_image, start_watching, stop_watching


def test_on_new_image_ignores_non_image_extensions(tmp_path: Path) -> None:
    """非圖片副檔名不觸發 WD Tagger"""
    with patch("app.services.watcher.run_wd_tagger") as mock_run:
        on_new_image(tmp_path / "doc.txt")
        on_new_image(tmp_path / "data.json")
        mock_run.assert_not_called()


def test_on_new_image_triggers_wd_tagger_for_image(tmp_path: Path) -> None:
    """圖片副檔名觸發 WD Tagger（防抖後會呼叫 run_wd_tagger）"""
    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        img = tmp_path / "test.png"
        img.touch()
        on_new_image(img.resolve())
        time.sleep(0.05)  # 等待防抖 Timer 執行

        mock_run.assert_called_once()
        call_dir = mock_run.call_args[0][0]
        assert call_dir == tmp_path.resolve()


def test_on_new_image_in_nested_folder_triggers_wd_tagger_with_subdir(
    tmp_path: Path,
) -> None:
    """巢狀資料夾內的圖片觸發 WD Tagger 時，應傳入該子資料夾路徑"""
    nested = tmp_path / "lora_train" / "char_a" / "pose_1"
    nested.mkdir(parents=True)
    img = nested / "test.png"
    img.touch()

    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        on_new_image(img.resolve())
        time.sleep(0.05)

        mock_run.assert_called_once()
        call_dir = mock_run.call_args[0][0]
        assert call_dir == nested.resolve()
        assert "pose_1" in str(call_dir)


def test_start_watching_with_empty_dirs_does_not_crash() -> None:
    """watch_dirs 為空或路徑不存在時不崩潰"""
    with patch("app.services.watcher.get_settings") as mock_settings:
        mock_settings.return_value.watch_dirs = ""
        start_watching()
        stop_watching()
    # 若 watch_dirs 指向不存在的路徑，只會 log 略過
    with patch("app.services.watcher.get_settings") as mock_settings:
        mock_settings.return_value.watch_dirs = "/nonexistent_path_xyz_123"
        mock_settings.return_value.sd_scripts_path = "./sd-scripts"
        start_watching()
        stop_watching()
