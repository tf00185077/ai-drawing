"""
資料夾監聽與即時 .txt 產生
watchdog 監聽訓練資料夾，新圖觸發 WD Tagger 產生同名 .txt
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Timer

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.config import get_settings
from app.services.lora_dataset import is_path_locked
from app.services.wd_tagger import run_wd_tagger

logger = logging.getLogger(__name__)

# 支援的圖片副檔名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
# 防抖：同一目錄 N 秒內只觸發一次，避免大量上傳時重複執行
DEBOUNCE_SECONDS = 2.0
FILE_STABLE_SECONDS = 0.5
STABLE_POLL_INTERVAL = 0.1
FILE_STABLE_TIMEOUT = 10.0
WATCHDOG_STATUS_DIR = ".lora-watchdog"
WATCHDOG_STATUS_FILE = "status.json"
NON_RETRYABLE_ERROR_CODES = {"empty_image", "invalid_image", "unreadable_image"}

_observer: Observer | None = None
_debounce_timers: dict[Path, Timer] = {}
_debounce_lock = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _caption_for_image(image_path: Path) -> Path:
    return image_path.with_suffix(".txt")


def _is_caption_current(image_path: Path) -> bool:
    caption_path = _caption_for_image(image_path)
    if not caption_path.exists():
        return False
    try:
        image_stat = image_path.stat()
        caption_stat = caption_path.stat()
    except OSError:
        return False
    return caption_stat.st_mtime_ns >= image_stat.st_mtime_ns


def _status_path(folder: Path) -> Path:
    return folder / WATCHDOG_STATUS_DIR / WATCHDOG_STATUS_FILE


def _load_watchdog_status(folder: Path) -> dict:
    path = _status_path(folder)
    if not path.exists():
        return {"version": 1, "updated_at": None, "errors": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "updated_at": None, "errors": []}
    if not isinstance(data, dict):
        return {"version": 1, "updated_at": None, "errors": []}
    errors = data.get("errors")
    if not isinstance(errors, list):
        data["errors"] = []
    data.setdefault("version", 1)
    data.setdefault("updated_at", None)
    return data


def _write_watchdog_status(folder: Path, status: dict) -> None:
    status_dir = folder / WATCHDOG_STATUS_DIR
    status_dir.mkdir(parents=True, exist_ok=True)
    status["updated_at"] = _now_iso()
    tmp_path = status_dir / f"{WATCHDOG_STATUS_FILE}.tmp"
    tmp_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(_status_path(folder))


def _image_status_signature(image_path: Path) -> dict:
    try:
        stat = image_path.stat()
    except OSError:
        return {"size": None, "mtime_ns": None}
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _record_watchdog_error(image_path: Path, code: str, message: str) -> None:
    folder = image_path.parent
    status = _load_watchdog_status(folder)
    image_name = image_path.name
    status["errors"] = [
        error
        for error in status.get("errors", [])
        if not isinstance(error, dict) or error.get("image_path") != image_name
    ]
    status["errors"].append(
        {
            "image_path": image_name,
            "code": code,
            "message": message,
            "detected_at": _now_iso(),
            **_image_status_signature(image_path),
        }
    )
    _write_watchdog_status(folder, status)


def _clear_watchdog_error(image_path: Path) -> None:
    folder = image_path.parent
    status_path = _status_path(folder)
    if not status_path.exists():
        return
    status = _load_watchdog_status(folder)
    image_name = image_path.name
    errors = [
        error
        for error in status.get("errors", [])
        if not isinstance(error, dict) or error.get("image_path") != image_name
    ]
    if len(errors) == len(status.get("errors", [])):
        return
    status["errors"] = errors
    _write_watchdog_status(folder, status)


def _has_current_nonretryable_error(image_path: Path, status: dict | None = None) -> bool:
    status = status if status is not None else _load_watchdog_status(image_path.parent)
    signature = _image_status_signature(image_path)
    for error in status.get("errors", []):
        if not isinstance(error, dict):
            continue
        if error.get("image_path") != image_path.name:
            continue
        if error.get("code") not in NON_RETRYABLE_ERROR_CODES:
            continue
        if error.get("size") == signature["size"] and error.get("mtime_ns") == signature["mtime_ns"]:
            return True
    return False


def _iter_images(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return [
        path
        for path in sorted(folder.iterdir(), key=lambda p: p.name.lower())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def _images_needing_captioning(folder: Path) -> list[Path]:
    status = _load_watchdog_status(folder)
    return [
        image
        for image in _iter_images(folder)
        if not _is_caption_current(image) and not _has_current_nonretryable_error(image, status)
    ]


def _wait_for_file_stable(image_path: Path) -> bool:
    deadline = time.monotonic() + FILE_STABLE_TIMEOUT
    previous_signature: tuple[int, int] | None = None
    stable_since: float | None = None

    while time.monotonic() <= deadline:
        try:
            stat = image_path.stat()
        except OSError:
            return False
        signature = (stat.st_size, stat.st_mtime_ns)
        now = time.monotonic()
        if signature == previous_signature:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= FILE_STABLE_SECONDS:
                return True
        else:
            previous_signature = signature
            stable_since = now
        time.sleep(STABLE_POLL_INTERVAL)
    return False


def _has_supported_image_signature(image_path: Path, header: bytes) -> bool:
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".webp":
        return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if suffix == ".bmp":
        return header.startswith(b"BM")
    if suffix == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    return False


def _validate_image_for_captioning(image_path: Path) -> bool:
    try:
        stat = image_path.stat()
    except OSError as exc:
        _record_watchdog_error(image_path, "unreadable_image", f"image cannot be stat()ed: {exc}")
        return False
    if stat.st_size <= 0:
        _record_watchdog_error(image_path, "empty_image", "image file is empty")
        return False
    try:
        with image_path.open("rb") as handle:
            header = handle.read(16)
            if not header:
                _record_watchdog_error(image_path, "empty_image", "image file is empty")
                return False
    except OSError as exc:
        _record_watchdog_error(image_path, "unreadable_image", f"image cannot be read: {exc}")
        return False
    if not _has_supported_image_signature(image_path, header):
        _record_watchdog_error(
            image_path,
            "invalid_image",
            "image header does not match a supported image format",
        )
        return False
    _clear_watchdog_error(image_path)
    return True


def _snapshot_current_captions(folder: Path) -> dict[Path, tuple[str, int, int]]:
    snapshots: dict[Path, tuple[str, int, int]] = {}
    for image in _iter_images(folder):
        if not _is_caption_current(image):
            continue
        caption = _caption_for_image(image)
        try:
            stat = caption.stat()
            snapshots[caption] = (caption.read_text(encoding="utf-8"), stat.st_atime_ns, stat.st_mtime_ns)
        except OSError:
            continue
    return snapshots


def _restore_current_captions(snapshots: dict[Path, tuple[str, int, int]]) -> None:
    for caption_path, (content, atime_ns, mtime_ns) in snapshots.items():
        try:
            current = caption_path.read_text(encoding="utf-8") if caption_path.exists() else None
            if current != content:
                caption_path.write_text(content, encoding="utf-8")
            os.utime(caption_path, ns=(atime_ns, mtime_ns))
        except OSError as exc:
            logger.warning("還原 current caption 失敗 %s: %s", caption_path, exc)


def _process_caption_folder(parent_dir: Path) -> None:
    if is_path_locked(parent_dir):
        logger.info("略過 WD Tagger：dataset 鎖定中 %s", parent_dir)
        return

    needing_caption = _images_needing_captioning(parent_dir)
    if not needing_caption:
        logger.debug("略過 WD Tagger：caption 已是最新 %s", parent_dir)
        return

    ready_images: list[Path] = []
    for image in needing_caption:
        if not _wait_for_file_stable(image):
            _record_watchdog_error(image, "file_not_stable", "image file did not become stable before timeout")
            continue
        if _validate_image_for_captioning(image):
            ready_images.append(image)

    if not ready_images:
        logger.info("略過 WD Tagger：沒有可 caption 的穩定圖片 %s", parent_dir)
        return

    protected_captions = _snapshot_current_captions(parent_dir)
    try:
        run_wd_tagger(parent_dir)
    finally:
        _restore_current_captions(protected_captions)


def on_new_image(image_path: Path) -> None:
    """
    新圖寫入時被呼叫。
    實作：呼叫 WD Tagger 產生同名 .txt。
    image_path 為絕對路徑。
    """
    path = Path(image_path)
    if not path.is_absolute():
        path = path.resolve()

    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return

    parent_dir = path.parent

    def _do_tag() -> None:
        try:
            _process_caption_folder(parent_dir)
        except Exception:
            logger.exception("watchdog caption generation failed for %s", parent_dir)
        finally:
            with _debounce_lock:
                _debounce_timers.pop(parent_dir, None)

    with _debounce_lock:
        if old := _debounce_timers.get(parent_dir):
            old.cancel()
        t = Timer(DEBOUNCE_SECONDS, _do_tag)
        t.daemon = True
        _debounce_timers[parent_dir] = t
        t.start()


class _ImageHandler(FileSystemEventHandler):
    """監聽新檔建立，僅處理圖片副檔名"""

    def _handle_path(self, path: Path) -> None:
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            on_new_image(path.resolve())

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._handle_path(Path(event.src_path))

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._handle_path(Path(event.src_path))

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._handle_path(Path(event.dest_path))


def start_watching() -> None:
    """
    啟動 watchdog 監聽 config.watch_dirs。
    新圖寫入時觸發 on_new_image。
    """
    global _observer
    settings = get_settings()
    dirs_str = settings.watch_dirs
    watch_paths = [p.strip() for p in dirs_str.split(",") if p.strip()]

    if not watch_paths:
        logger.warning("watch_dirs 為空，不啟動監聽")
        return

    _observer = Observer()
    for p in watch_paths:
        path = Path(p)
        if not path.exists():
            logger.warning("監聽路徑不存在: %s，略過", path)
            continue
        path = path.resolve()
        _observer.schedule(_ImageHandler(), str(path), recursive=True)
        logger.info("開始監聽: %s", path)

    _observer.start()


def stop_watching() -> None:
    """停止監聽（用於測試或優雅關閉）"""
    global _observer
    if _observer:
        _observer.stop()
        _observer.join(timeout=5)
        _observer = None
