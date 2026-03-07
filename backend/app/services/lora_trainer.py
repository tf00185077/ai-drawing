"""
LoRA 訓練執行器
整合 Kohya sd-scripts，subprocess 執行 train_network.py
佇列管理、dataset_config TOML 動態生成、訓練完成回呼

對應 docs/internal-interfaces.md lora_trainer 介面
"""
from __future__ import annotations

import logging
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.config import get_settings

logger = logging.getLogger(__name__)

# 支援的圖片副檔名（與 watcher 一致，when-touching 可抽出共用）
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
# 訓練所需最少圖片數（含 .txt caption）
_MIN_IMAGES = 1

OnCompleteCallback = Callable[[str, str], None]


@dataclass
class _TrainJob:
    """單一訓練任務"""

    job_id: str
    folder: str
    checkpoint: str
    epochs: int
    submitted_at: str


@dataclass
class _RunningJob:
    """執行中的任務"""

    job: _TrainJob
    proc: subprocess.Popen[str] | None
    progress: float
    epoch: int | None
    total_epochs: int | None


_lock = threading.Lock()
_queue: list[_TrainJob] = []
_running: _RunningJob | None = None
_on_complete_callbacks: list[OnCompleteCallback] = []
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _reset_for_test() -> None:
    """僅供測試使用：清空佇列狀態"""
    global _queue, _running
    with _lock:
        _queue.clear()
        _running = None


def _resolve_image_dir(folder: str) -> Path:
    """folder 相對 lora_train_dir，回傳絕對路徑的 image_dir"""
    settings = get_settings()
    base = Path(settings.lora_train_dir).resolve()
    return (base / folder).resolve()


def _count_trainable_images(image_dir: Path) -> int:
    """計算有對應 .txt 的圖片數量"""
    count = 0
    for p in image_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        txt_path = p.with_suffix(".txt")
        if txt_path.exists():
            count += 1
    return count


def _write_dataset_config(
    image_dir: Path,
    output_name: str,
    *,
    class_tokens: str = "sks",
) -> Path:
    """產生 dataset_config TOML，image_dir 需為絕對路徑"""
    toml_dir = image_dir.parent
    toml_path = toml_dir / f"{output_name}_dataset.toml"
    content = f"""[general]
shuffle_caption = true
caption_extension = ".txt"
keep_tokens = 1

[[datasets]]
resolution = 512
batch_size = 4

  [[datasets.subsets]]
  image_dir = "{image_dir.as_posix()}"
  class_tokens = "{class_tokens}"
  num_repeats = 10
"""
    toml_path.write_text(content, encoding="utf-8")
    return toml_path


def _parse_progress(line: str) -> tuple[float, int | None, int | None] | None:
    """從 stdout 解析 epoch 進度，回傳 (progress, epoch, total_epochs)"""
    m = re.search(r"epoch\s+(\d+)/(\d+)", line, re.I)
    if m:
        e, t = int(m.group(1)), int(m.group(2))
        return (e / t if t else 0.0, e, t)
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*\[", line)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (a / b if b else 0.0, None, None)
    return None


def _run_training_subprocess(
    *,
    image_dir: Path,
    output_dir: Path,
    output_name: str,
    checkpoint: str,
    epochs: int,
    sd_scripts_path: Path,
) -> subprocess.Popen[str]:
    """啟動 Kohya train_network.py subprocess"""
    toml_path = _write_dataset_config(image_dir, output_name)
    cmd = [
        "accelerate",
        "launch",
        "--num_cpu_threads_per_process",
        "1",
        str(sd_scripts_path / "train_network.py"),
        "--pretrained_model_name_or_path",
        checkpoint,
        "--dataset_config",
        str(toml_path),
        "--output_dir",
        str(output_dir),
        "--output_name",
        output_name,
        "--network_module",
        "networks.lora",
        "--max_train_epochs",
        str(epochs),
        "--learning_rate",
        "1e-4",
        "--save_model_as",
        "safetensors",
        "--mixed_precision",
        "fp16",
        "--cache_latents",
        "--gradient_checkpointing",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(sd_scripts_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _get_output_lora_path(output_dir: Path, output_name: str) -> Path:
    """Kohya 輸出檔名為 {output_name}.safetensors"""
    return output_dir / f"{output_name}.safetensors"


def _worker_loop() -> None:
    """背景 worker：依序執行佇列中的訓練"""
    global _running
    settings = get_settings()
    sd_scripts = Path(settings.sd_scripts_path).resolve()
    lora_base = Path(settings.lora_train_dir).resolve()
    output_base = lora_base / "output"

    while not _stop_event.is_set():
        with _lock:
            if _running or not _queue:
                _stop_event.wait(1.0)
                continue
            job = _queue.pop(0)
            image_dir = _resolve_image_dir(job.folder)
            output_dir = output_base
            output_dir.mkdir(parents=True, exist_ok=True)

        if not image_dir.exists():
            logger.error("Job %s: image_dir 不存在 %s", job.job_id, image_dir)
            continue

        output_lora = _get_output_lora_path(output_dir, job.folder.replace("/", "_"))

        try:
            proc = _run_training_subprocess(
                image_dir=image_dir,
                output_dir=output_dir,
                output_name=job.folder.replace("/", "_"),
                checkpoint=job.checkpoint,
                epochs=job.epochs,
                sd_scripts_path=sd_scripts,
            )
        except Exception as e:
            logger.exception("Job %s 啟動失敗: %s", job.job_id, e)
            continue

        running_job = _RunningJob(
            job=job,
            proc=proc,
            progress=0.0,
            epoch=None,
            total_epochs=job.epochs,
        )
        with _lock:
            _running = running_job

        logger.info("Job %s 開始訓練: folder=%s", job.job_id, job.folder)

        # 讀取 stdout 更新進度
        if proc.stdout:
            for line in proc.stdout:
                if _stop_event.is_set():
                    proc.terminate()
                    break
                parsed = _parse_progress(line)
                if parsed:
                    prog, ep, tot = parsed
                    with _lock:
                        if _running and _running.job.job_id == job.job_id:
                            _running.progress = prog
                            if ep is not None:
                                _running.epoch = ep
                            if tot is not None:
                                _running.total_epochs = tot

        proc.wait()

        with _lock:
            if _running and _running.job.job_id == job.job_id:
                _running = None

        if proc.returncode != 0:
            logger.error("Job %s 訓練失敗, returncode=%s", job.job_id, proc.returncode)
            continue

        # 實際輸出路徑可能帶 epoch，先檢查主檔名
        found_path: Path | None = None
        prefix = job.folder.replace("/", "_")
        if output_lora.exists():
            found_path = output_lora
        else:
            for f in output_dir.glob(f"{prefix}*.safetensors"):
                found_path = f
                break

        if found_path:
            output_lora_str = str(found_path.resolve())
            for cb in _on_complete_callbacks:
                try:
                    cb(output_lora_str, job.folder)
                except Exception as e:
                    logger.exception("on_complete callback 錯誤: %s", e)
            logger.info("Job %s 完成: %s", job.job_id, output_lora_str)
        else:
            logger.warning("Job %s 完成但找不到輸出檔案: %s", job.job_id, output_dir)


def _ensure_worker() -> None:
    """確保 worker 線程已啟動"""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    logger.info("LoRA 訓練 worker 已啟動")


def enqueue(
    folder: str,
    *,
    checkpoint: str | None = None,
    epochs: int = 10,
) -> str:
    """
    加入訓練佇列。
    folder: 相對 lora_train_dir 的路徑。
    Returns: job_id
    Raises: ValueError 若資料夾不存在或圖片數不足
    """
    settings = get_settings()
    image_dir = _resolve_image_dir(folder)

    if not image_dir.exists() or not image_dir.is_dir():
        raise ValueError(f"資料夾不存在: {folder}")

    count = _count_trainable_images(image_dir)
    if count < _MIN_IMAGES:
        raise ValueError(f"圖片數不足（需至少 {_MIN_IMAGES} 張含 .txt）: {folder} 僅 {count} 張")

    ckpt = checkpoint or settings.lora_default_checkpoint
    if not ckpt:
        raise ValueError("未指定 checkpoint 且 config 無 lora_default_checkpoint")

    job_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    job = _TrainJob(
        job_id=job_id,
        folder=folder,
        checkpoint=ckpt,
        epochs=epochs,
        submitted_at=submitted_at,
    )

    with _lock:
        # 同一 folder 已在 queue 或 running 則不重複加入
        if any(j.folder == folder for j in _queue):
            raise ValueError(f"資料夾已在佇列中: {folder}")
        if _running and _running.job.folder == folder:
            raise ValueError(f"資料夾訓練中: {folder}")
        _queue.append(job)

    _ensure_worker()
    logger.info("Job %s 已加入佇列: folder=%s", job_id, folder)
    return job_id


def get_status() -> dict:
    """
    取得訓練狀態。
    Returns: {
        "status": "idle" | "running" | "queued",
        "current_job": {...} | None,
        "queue": [...]
    }
    """
    with _lock:
        if _running:
            rj = _running
            status = "running"
            current_job = {
                "job_id": rj.job.job_id,
                "folder": rj.job.folder,
                "progress": rj.progress,
                "epoch": rj.epoch,
                "total_epochs": rj.total_epochs,
            }
            queue_list = [
                {"job_id": j.job_id, "folder": j.folder}
                for j in _queue
            ]
        elif _queue:
            status = "queued"
            current_job = None
            queue_list = [
                {"job_id": j.job_id, "folder": j.folder}
                for j in _queue
            ]
        else:
            status = "idle"
            current_job = None
            queue_list = []

    return {
        "status": status,
        "current_job": current_job,
        "queue": queue_list,
    }


def register_on_complete(callback: OnCompleteCallback) -> None:
    """
    註冊訓練完成回呼。
    完成時會呼叫 callback(output_lora_path, folder)。
    實作 4c 時：在此回呼中呼叫 comfyui 產圖 + recording.save()
    """
    with _lock:
        _on_complete_callbacks.append(callback)
