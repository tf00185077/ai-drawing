"""
資料夾監聽與即時 .txt 產生
watchdog 監聽訓練資料夾，新圖觸發 WD Tagger 產生同名 .txt
"""
import logging
import subprocess
from pathlib import Path
from threading import Lock, Timer

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.config import get_settings

logger = logging.getLogger(__name__)

# 支援的圖片副檔名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
# 防抖：同一目錄 N 秒內只觸發一次，避免大量上傳時重複執行
DEBOUNCE_SECONDS = 2.0

_observer: Observer | None = None
_debounce_timers: dict[Path, Timer] = {}
_debounce_lock = Lock()


def _run_wd_tagger(image_dir: Path) -> None:
    """對指定目錄執行 WD Tagger，產生 .txt caption"""
    settings = get_settings()
    sd_scripts = Path(settings.sd_scripts_path)
    script = sd_scripts / "finetune" / "tag_images_by_wd14_tagger.py"

    if not script.exists():
        logger.warning("WD Tagger 腳本不存在: %s，略過標註", script)
        return

    cmd = [
        "python",
        str(script),
        "--onnx",
        "--repo_id",
        "SmilingWolf/wd-swinv2-tagger-v3",
        "--batch_size",
        "4",
        "--thresh",
        "0.35",
        "--recursive",
        str(image_dir.resolve()),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(sd_scripts),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            logger.error("WD Tagger 執行失敗: %s", proc.stderr or proc.stdout)
        else:
            logger.info("WD Tagger 完成: %s", image_dir)
    except subprocess.TimeoutExpired:
        logger.error("WD Tagger 逾時: %s", image_dir)
    except Exception as e:
        logger.error("WD Tagger 錯誤: %s", e)


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
        _run_wd_tagger(parent_dir)
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

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        src = Path(event.src_path)
        if src.suffix.lower() in IMAGE_EXTENSIONS:
            on_new_image(src.resolve())


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
