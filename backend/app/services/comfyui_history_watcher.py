"""
監聽 ComfyUI 執行歷史，自動記錄從 ComfyUI UI 直接生成的圖片至圖庫。

當使用者在 ComfyUI 網頁介面直接產圖時，本服務會定期輪詢 history，
取回輸出圖片與 workflow 參數，寫入 gallery_dir 與資料庫。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.core.comfyui import ComfyUIError, get_comfy_client, get_output_images
from app.core.recording import save as recording_save
from app.core.workflow import extract_params_from_workflow
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

_recorded_prompt_ids: set[str] = set()
_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _should_skip_prompt_id(prompt_id: str) -> bool:
    """是否應略過此 prompt_id（本系統提交的由 queue 記錄）"""
    from app.core.queue import get_our_prompt_ids, get_status

    if prompt_id in get_our_prompt_ids():
        return True
    st = get_status()
    running = st.get("queue_running", [])
    if running and running[0].get("prompt_id") == prompt_id:
        return True
    return False


def _process_external_prompt(comfy, prompt_id: str, prompt_data: dict) -> None:
    """處理單一外部 prompt：取圖、存檔、寫入 DB"""
    images_info = get_output_images({prompt_id: prompt_data}, prompt_id)
    if not images_info:
        return

    # 從 workflow 提取參數（ComfyUI prompt 為陣列，workflow 在 [2]）
    wf_prompt = prompt_data.get("prompt")
    params = extract_params_from_workflow(wf_prompt) if wf_prompt else {}

    # 印到 backend terminal，方便除錯
    print(
        f"[ComfyUI 外部] prompt_id={prompt_id[:8]}... "
        f"checkpoint={params.get('checkpoint')} lora={params.get('lora')} "
        f"seed={params.get('seed')} prompt={str(params.get('prompt', ''))[:50]}...",
        flush=True,
    )

    settings = get_settings()
    gallery_path = Path(settings.gallery_dir).resolve()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = gallery_path / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, img in enumerate(images_info):
        try:
            data = comfy.fetch_image(
                img["filename"],
                subfolder=img.get("subfolder", ""),
                ftype=img.get("type", "output"),
            )
        except ComfyUIError as e:
            logger.warning("ComfyUI history watcher: 無法取回圖片 %s: %s", img, e)
            continue

        base = img["filename"].rsplit(".", 1)[0] if "." in img["filename"] else img["filename"]
        ext = img["filename"].rsplit(".", 1)[-1] if "." in img["filename"] else "png"
        out_name = f"{base}_ext_{prompt_id[:8]}_{i}.{ext}"
        out_file = out_dir / out_name
        out_file.write_bytes(data)
        rel_path = str(Path(date_str) / out_name)

        db = SessionLocal()
        try:
            recording_save(
                rel_path,
                checkpoint=params.get("checkpoint"),
                lora=params.get("lora"),
                seed=params.get("seed"),
                steps=params.get("steps"),
                cfg=params.get("cfg"),
                prompt=params.get("prompt"),
                negative_prompt=params.get("negative_prompt"),
                db=db,
            )
        finally:
            db.close()

    logger.info("ComfyUI 外部生成已記錄: prompt_id=%s, %d 張", prompt_id, len(images_info))


def _poll_once(comfy) -> None:
    """執行一次輪詢"""
    try:
        full_history = comfy.get_full_history()
    except Exception as e:
        logger.debug("ComfyUI history 輪詢失敗: %s", e)
        return

    if not isinstance(full_history, dict):
        return

    for prompt_id, prompt_data in full_history.items():
        if not isinstance(prompt_data, dict):
            continue
        if _should_skip_prompt_id(prompt_id):
            continue
        with _lock:
            if prompt_id in _recorded_prompt_ids:
                continue
            _recorded_prompt_ids.add(prompt_id)

        try:
            _process_external_prompt(comfy, prompt_id, prompt_data)
        except Exception as e:
            logger.exception("處理 ComfyUI 外部 prompt %s 失敗: %s", prompt_id, e)
            with _lock:
                _recorded_prompt_ids.discard(prompt_id)


def _worker_loop() -> None:
    """背景 worker：定期輪詢 ComfyUI history"""
    try:
        comfy = get_comfy_client()
        settings = get_settings()
        interval = max(5.0, settings.comfyui_history_poll_interval)
    except Exception as e:
        logger.exception("History watcher 初始化失敗: %s", e)
        return

    # 啟動時將既有 history 標記為已見過，不記錄舊圖
    try:
        full_history = comfy.get_full_history()
        if isinstance(full_history, dict):
            with _lock:
                _recorded_prompt_ids.update(full_history.keys())
            logger.info("ComfyUI history watcher: 已略過 %d 筆既有記錄", len(full_history))
    except Exception as e:
        logger.debug("初始化時取得 history 失敗: %s", e)

    while not _stop_event.is_set():
        _poll_once(comfy)
        _stop_event.wait(interval)


def start_watcher() -> None:
    """啟動 ComfyUI history 監聽"""
    global _worker_thread
    settings = get_settings()
    if not settings.comfyui_record_external:
        return
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    logger.info("ComfyUI history watcher 已啟動（外部生成自動記錄）")


def stop_watcher() -> None:
    """停止監聽"""
    global _worker_thread
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5.0)
        _worker_thread = None
    logger.info("ComfyUI history watcher 已停止")
