"""WD Tagger 單元測試"""
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import wd_tagger


def test_resolve_folder_type_character() -> None:
    """路徑含 character 回傳 character"""
    assert wd_tagger.resolve_folder_type(Path("/lora_train/character/10_arashi")) == "character"
    assert wd_tagger.resolve_folder_type(Path("C:/data/lora_train/character")) == "character"


def test_resolve_folder_type_style_costume_or_background() -> None:
    """路徑含 style、costume 或 background 回傳對應類型，未符合則 default"""
    assert wd_tagger.resolve_folder_type(Path("/lora_train/style/10_artist")) == "style"
    assert wd_tagger.resolve_folder_type(Path("/lora_train/costume/10_uniform")) == "costume"
    assert wd_tagger.resolve_folder_type(Path("/lora_train/background/10_scenery")) == "background"
    assert wd_tagger.resolve_folder_type(Path("/lora_train/10_lovelive")) == "default"


@patch("app.services.wd_tagger.subprocess.run")
@patch("app.services.wd_tagger.get_settings")
def test_run_wd_tagger_uses_thresh_and_undesired_tags(
    mock_settings, mock_run, tmp_path: Path
) -> None:
    """WD Tagger 傳入 blacklist + rating 至 undesired_tags，預設路徑用 character blacklist"""
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
    assert cmd[thresh_idx + 1] == "0.7"
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


@patch("app.services.wd_tagger.subprocess.run")
@patch("app.services.wd_tagger.get_settings")
def test_run_wd_tagger_background_folder_uses_background_blacklist(
    mock_settings, mock_run, tmp_path: Path
) -> None:
    """路徑含 background 時使用 background blacklist（含 1girl 等人物 tag）"""
    mock_settings.return_value.sd_scripts_path = str(tmp_path)
    mock_settings.return_value.sd_scripts_python = ""
    mock_run.return_value.returncode = 0

    (tmp_path / "finetune").mkdir(parents=True)
    (tmp_path / "finetune" / "tag_images_by_wd14_tagger.py").touch()

    img_dir = tmp_path / "background" / "10_scenery"
    img_dir.mkdir(parents=True)

    wd_tagger.run_wd_tagger(img_dir)

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    undesired_idx = cmd.index("--undesired_tags")
    undesired_val = cmd[undesired_idx + 1]
    assert "1girl" in undesired_val
    assert "breasts" in undesired_val


@patch("app.services.wd_tagger.subprocess.run")
@patch("app.services.wd_tagger.get_settings")
def test_run_wd_tagger_costume_folder_uses_costume_blacklist(
    mock_settings, mock_run, tmp_path: Path
) -> None:
    """路徑含 costume 時使用 costume blacklist（濾除 black_hair，保留 dress 等服裝 tag）"""
    mock_settings.return_value.sd_scripts_path = str(tmp_path)
    mock_settings.return_value.sd_scripts_python = ""
    mock_run.return_value.returncode = 0

    (tmp_path / "finetune").mkdir(parents=True)
    (tmp_path / "finetune" / "tag_images_by_wd14_tagger.py").touch()

    img_dir = tmp_path / "costume" / "10_uniform"
    img_dir.mkdir(parents=True)

    wd_tagger.run_wd_tagger(img_dir)

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    undesired_idx = cmd.index("--undesired_tags")
    undesired_val = cmd[undesired_idx + 1]
    assert "black_hair" in undesired_val
    assert "solo" in undesired_val
    assert "dress" not in undesired_val
