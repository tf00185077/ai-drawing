"""WD Tagger 單元測試"""
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import wd_tagger


@patch("app.services.wd_tagger.subprocess.run")
@patch("app.services.wd_tagger.get_settings")
def test_run_wd_tagger_uses_thresh_035_and_undesired_tags(
    mock_settings, mock_run, tmp_path: Path
) -> None:
    """WD Tagger 使用 thresh 0.35 且傳入 blacklist + rating 至 undesired_tags"""
    mock_settings.return_value.sd_scripts_path = str(tmp_path)
    mock_settings.return_value.sd_scripts_python = ""
    mock_run.return_value.returncode = 0

    (tmp_path / "finetune").mkdir(parents=True)
    (tmp_path / "finetune" / "tag_images_by_wd14_tagger.py").touch()

    img_dir = tmp_path / "images"
    img_dir.mkdir()

    wd_tagger.run_wd_tagger(img_dir)

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--thresh" in cmd
    thresh_idx = cmd.index("--thresh")
    assert cmd[thresh_idx + 1] == "0.35"
    assert "--undesired_tags" in cmd
    undesired_idx = cmd.index("--undesired_tags")
    undesired_val = cmd[undesired_idx + 1]
    assert "solo" in undesired_val
    assert "rating:general" in undesired_val


@patch("app.services.wd_tagger._apply_caption_filter")
@patch("app.services.wd_tagger.subprocess.run")
@patch("app.services.wd_tagger.get_settings")
def test_run_wd_tagger_applies_filter_on_success(
    mock_settings, mock_run, mock_filter, tmp_path: Path
) -> None:
    """WD Tagger 成功後會對目錄內 .txt 套用 caption filter"""
    mock_settings.return_value.sd_scripts_path = str(tmp_path)
    mock_settings.return_value.sd_scripts_python = ""
    mock_settings.return_value.wd_tag_limit = 15
    mock_settings.return_value.wd_trigger_word = ""
    mock_run.return_value.returncode = 0

    (tmp_path / "finetune").mkdir(parents=True)
    (tmp_path / "finetune" / "tag_images_by_wd14_tagger.py").touch()

    img_dir = tmp_path / "images"
    img_dir.mkdir()

    wd_tagger.run_wd_tagger(img_dir)

    mock_filter.assert_called_once_with(img_dir)
