"""watcher 單元測試"""
import json
import os
import struct
import time
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import watcher
from app.services.watcher import on_new_image, start_watching, stop_watching


@pytest.fixture(autouse=True)
def clear_debounce_timers():
    """避免背景 debounce Timer 跨測試污染 patch 狀態。"""
    _cancel_pending_timers()
    yield
    _cancel_pending_timers()


def _cancel_pending_timers() -> None:
    with watcher._debounce_lock:
        timers = list(watcher._debounce_timers.values())
        watcher._debounce_timers.clear()
    for timer in timers:
        timer.cancel()
        timer.join(timeout=0.2)


def _wait_for_debounce(parent_dir: Path) -> None:
    deadline = time.monotonic() + 1.0
    parent_dir = parent_dir.resolve()
    while time.monotonic() < deadline:
        with watcher._debounce_lock:
            timer = watcher._debounce_timers.get(parent_dir)
        if timer is None:
            return
        timer.join(timeout=0.05)
    pytest.fail(f"debounce timer did not finish for {parent_dir}")


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def _tiny_png_bytes(pixel: bytes = b"\x00\x00\x00\xff") -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    idat = _png_chunk(b"IDAT", zlib.compress(b"\x00" + pixel))
    iend = _png_chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def _write_tiny_png(path: Path, pixel: bytes = b"\x00\x00\x00\xff") -> None:
    path.write_bytes(_tiny_png_bytes(pixel))


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
        _write_tiny_png(img)
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)

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
    _write_tiny_png(img)

    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        on_new_image(img.resolve())
        _wait_for_debounce(nested)

        mock_run.assert_called_once()
        call_dir = mock_run.call_args[0][0]
        assert call_dir == nested.resolve()
        assert "pose_1" in str(call_dir)


def test_on_new_image_skips_wd_tagger_when_dataset_locked(tmp_path: Path) -> None:
    """dataset lock 期間 watcher 不覆寫 caption。"""
    img = tmp_path / "test.png"
    _write_tiny_png(img)

    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.is_path_locked", return_value=True
    ), patch("app.services.watcher.DEBOUNCE_SECONDS", 0.01):
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)

        mock_run.assert_not_called()


def test_on_new_image_waits_until_image_file_is_stable(tmp_path: Path) -> None:
    """圖片 caption 前必須先通過 stable-file gate。"""
    img = tmp_path / "streaming.png"
    _write_tiny_png(img)
    events: list[str] = []

    def fake_wait(image_path: Path) -> bool:
        assert image_path == img.resolve()
        events.append("stable-check")
        return True

    def fake_tagger(_folder: Path) -> None:
        events.append("tagger")

    with patch("app.services.watcher.run_wd_tagger", side_effect=fake_tagger), patch(
        "app.services.watcher._wait_for_file_stable", side_effect=fake_wait
    ), patch("app.services.watcher.DEBOUNCE_SECONDS", 0.01):
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)

    assert events == ["stable-check", "tagger"]


def test_image_handler_reacts_to_created_modified_and_moved_images(tmp_path: Path) -> None:
    """watchdog handler 將 created/modified/moved 圖片事件導到 on_new_image。"""
    handler = watcher._ImageHandler()
    created = tmp_path / "created.png"
    modified = tmp_path / "modified.jpg"
    moved = tmp_path / "moved.webp"

    with patch("app.services.watcher.on_new_image") as mock_new:
        handler.on_created(SimpleNamespace(is_directory=False, src_path=str(created)))
        handler.on_modified(SimpleNamespace(is_directory=False, src_path=str(modified)))
        handler.on_moved(
            SimpleNamespace(is_directory=False, src_path=str(tmp_path / "old.tmp"), dest_path=str(moved))
        )

    assert [call.args[0] for call in mock_new.call_args_list] == [
        created.resolve(),
        modified.resolve(),
        moved.resolve(),
    ]


def test_on_new_image_skips_folder_when_all_captions_are_current(tmp_path: Path) -> None:
    """所有圖片都有 newer/current 同名 .txt 時不呼叫 WD Tagger。"""
    img = tmp_path / "current.png"
    txt = tmp_path / "current.txt"
    _write_tiny_png(img)
    txt.write_text("manual caption", encoding="utf-8")
    now = time.time()
    os.utime(img, (now - 10, now - 10))
    os.utime(txt, (now, now))

    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)

    mock_run.assert_not_called()


def test_on_new_image_runs_when_caption_is_stale(tmp_path: Path) -> None:
    """同名 .txt 比圖片舊時視為 stale，需要重新 caption。"""
    img = tmp_path / "stale.png"
    txt = tmp_path / "stale.txt"
    _write_tiny_png(img)
    txt.write_text("old caption", encoding="utf-8")
    now = time.time()
    os.utime(txt, (now - 10, now - 10))
    os.utime(img, (now, now))

    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)

    mock_run.assert_called_once_with(tmp_path.resolve())


def test_on_new_image_preserves_current_manual_captions(tmp_path: Path) -> None:
    """WD Tagger 執行期間若改寫 current/manual .txt，watcher 會還原內容。"""
    current_img = tmp_path / "manual.png"
    missing_img = tmp_path / "missing.png"
    current_txt = tmp_path / "manual.txt"
    _write_tiny_png(current_img)
    _write_tiny_png(missing_img)
    current_txt.write_text("manual caption", encoding="utf-8")
    now = time.time()
    os.utime(current_img, (now - 10, now - 10))
    os.utime(current_txt, (now, now))

    def fake_tagger(folder: Path) -> None:
        (folder / "manual.txt").write_text("tagger overwrite", encoding="utf-8")
        (folder / "missing.txt").write_text("new caption", encoding="utf-8")

    with patch("app.services.watcher.run_wd_tagger", side_effect=fake_tagger), patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        on_new_image(missing_img.resolve())
        _wait_for_debounce(tmp_path)

    assert current_txt.read_text(encoding="utf-8") == "manual caption"
    assert (tmp_path / "missing.txt").read_text(encoding="utf-8") == "new caption"


def test_on_new_image_records_corrupt_image_status_and_does_not_retry_same_file(tmp_path: Path) -> None:
    """無法 caption 的 corrupt image 會寫入 structured status，且同一檔未變更不重試。"""
    img = tmp_path / "bad.png"
    img.write_bytes(b"not a png")

    with patch("app.services.watcher.run_wd_tagger") as mock_run, patch(
        "app.services.watcher.DEBOUNCE_SECONDS", 0.01
    ):
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)
        on_new_image(img.resolve())
        _wait_for_debounce(tmp_path)

    mock_run.assert_not_called()
    status = json.loads((tmp_path / ".lora-watchdog" / "status.json").read_text(encoding="utf-8"))
    assert status["errors"][0]["image_path"] == "bad.png"
    assert status["errors"][0]["code"] == "invalid_image"


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
