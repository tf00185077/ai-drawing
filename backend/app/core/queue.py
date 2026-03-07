"""
批次生圖排程器
佇列式批次生成，串接 workflow、comfyui、recording

對應 docs/internal-interfaces.md queue 介面
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from app.config import get_settings
from app.core.comfyui import ComfyUIClient, ComfyUIError, get_comfy_client, get_output_images
from app.core.recording import save as recording_save
from app.core.workflow import apply_params, load_template
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

MAX_PENDING = 50
WORKFLOW_TEMPLATE = "default"


class QueueFullError(Exception):
    """佇列已滿"""


class GenerateParams(TypedDict, total=False):
    checkpoint: str
    lora: str
    prompt: str
    negative_prompt: str
    seed: int
    steps: int
    cfg: float


class _Job:
    __slots__ = ("job_id", "params", "submitted_at", "prompt_id")

    def __init__(self, job_id: str, params: dict[str, Any], submitted_at: str):
        self.job_id = job_id
        self.params = params
        self.submitted_at = submitted_at
        self.prompt_id: str | None = None


_lock = threading.Lock()
_pending: list[_Job] = []
_running: _Job | None = None
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _reset_for_test() -> None:
    """僅供測試使用：清空佇列狀態"""
    global _pending, _running
    with _lock:
        _pending.clear()
        _running = None


def submit(params: GenerateParams) -> str:
    """
    提交生圖任務至佇列。

    Returns:
        job_id

    Raises:
        QueueFullError: 佇列已滿
    """
    if len(_pending) >= MAX_PENDING:
        raise QueueFullError("生圖佇列已滿，請稍後再試")
    job_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    job = _Job(job_id=job_id, params=dict(params), submitted_at=submitted_at)
    with _lock:
        _pending.append(job)
    logger.info("Job %s queued", job_id)
    return job_id


def get_status() -> dict[str, Any]:
    """
    取得佇列狀態。

    Returns:
        {
            "queue_running": [{"job_id", "prompt_id", "status", "submitted_at"}],
            "queue_pending": [{"job_id", "status", "submitted_at"}]
        }
    """
    with _lock:
        running_list: list[dict[str, Any]] = []
        if _running:
            running_list.append({
                "job_id": _running.job_id,
                "prompt_id": _running.prompt_id,
                "status": "running",
                "submitted_at": _running.submitted_at,
            })
        pending_list = [
            {"job_id": j.job_id, "status": "queued", "submitted_at": j.submitted_at}
            for j in _pending
        ]
    return {
        "queue_running": running_list,
        "queue_pending": pending_list,
    }


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """取得單一任務狀態，None 表示不存在"""
    with _lock:
        if _running and _running.job_id == job_id:
            return {
                "job_id": _running.job_id,
                "prompt_id": _running.prompt_id,
                "status": "running",
                "submitted_at": _running.submitted_at,
            }
        for j in _pending:
            if j.job_id == job_id:
                return {
                    "job_id": j.job_id,
                    "status": "queued",
                    "submitted_at": j.submitted_at,
                }
    return None


def _process_pending(comfy: ComfyUIClient) -> None:
    """從 pending 取一筆提交至 ComfyUI，移入 running"""
    global _running
    with _lock:
        if _running or not _pending:
            return
        job = _pending.pop(0)
        _running = job

    try:
        wf = load_template(WORKFLOW_TEMPLATE)
        prompt = apply_params(
            wf,
            checkpoint=job.params.get("checkpoint"),
            lora=job.params.get("lora"),
            prompt=job.params.get("prompt", ""),
            negative_prompt=job.params.get("negative_prompt", ""),
            seed=job.params.get("seed"),
            steps=job.params.get("steps", 20),
            cfg=job.params.get("cfg", 7.0),
        )
        prompt_id = comfy.submit_prompt(prompt)
        with _lock:
            if _running and _running.job_id == job.job_id:
                _running.prompt_id = prompt_id
        logger.info("Job %s submitted to ComfyUI, prompt_id=%s", job.job_id, prompt_id)
    except (ComfyUIError, FileNotFoundError) as e:
        logger.exception("ComfyUI submit failed for job %s: %s", job.job_id, e)
        with _lock:
            if _running and _running.job_id == job.job_id:
                _running = None
            _pending.insert(0, job)


def _check_running_complete(comfy: ComfyUIClient) -> None:
    """檢查 running 是否完成，完成則取圖、存檔、記錄"""
    global _running
    with _lock:
        job = _running
        if not job or not job.prompt_id:
            return

    try:
        queue_data = comfy.get_queue()
        running_items = queue_data.get("queue_running", [])
        still_running = any(
            item.get("prompt_id") == job.prompt_id for item in running_items
        )
        if still_running:
            return
    except Exception as e:
        logger.warning("Failed to get ComfyUI queue: %s", e)
        return

    with _lock:
        if _running and _running.job_id == job.job_id:
            _running = None

    try:
        history = comfy.get_history(job.prompt_id)
        images_info = get_output_images(history, job.prompt_id)
        if not images_info:
            logger.warning("Job %s completed but no output images", job.job_id)
            return

        settings = get_settings()
        gallery_path = Path(settings.gallery_dir)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir = gallery_path / date_str
        out_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[str] = []
        for i, img in enumerate(images_info):
            data = comfy.fetch_image(
                img["filename"],
                subfolder=img.get("subfolder", ""),
                ftype=img.get("type", "output"),
            )
            base = img["filename"].rsplit(".", 1)[0] if "." in img["filename"] else img["filename"]
            ext = img["filename"].rsplit(".", 1)[-1] if "." in img["filename"] else "png"
            out_name = f"{base}_{job.job_id[:8]}_{i}.{ext}"
            out_file = out_dir / out_name
            out_file.write_bytes(data)
            rel_path = str(Path(date_str) / out_name)
            saved_paths.append(rel_path)

        for image_path in saved_paths:
            db = SessionLocal()
            try:
                recording_save(
                    image_path,
                    checkpoint=job.params.get("checkpoint"),
                    lora=job.params.get("lora"),
                    seed=job.params.get("seed"),
                    steps=job.params.get("steps"),
                    cfg=job.params.get("cfg"),
                    prompt=job.params.get("prompt"),
                    negative_prompt=job.params.get("negative_prompt"),
                    db=db,
                )
            finally:
                db.close()

        logger.info("Job %s completed, saved %d image(s)", job.job_id, len(saved_paths))
    except Exception as e:
        logger.exception("Failed to save job %s output: %s", job.job_id, e)


def _worker_loop() -> None:
    """背景 worker 迴圈"""
    comfy = get_comfy_client()
    while not _stop_event.is_set():
        try:
            _process_pending(comfy)
            _check_running_complete(comfy)
        except Exception as e:
            logger.exception("Queue worker error: %s", e)
        _stop_event.wait(2.0)


def start_worker() -> None:
    """啟動佇列背景 worker（應用啟動時呼叫）"""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    logger.info("Queue worker started")


def stop_worker() -> None:
    """停止佇列背景 worker（應用關閉時呼叫）"""
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5.0)
    logger.info("Queue worker stopped")
