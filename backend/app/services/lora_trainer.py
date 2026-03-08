"""
LoRA 訓練執行器
整合 Kohya sd-scripts，subprocess 執行 train_network.py
佇列管理、dataset_config TOML 動態生成、訓練完成回呼

對應 docs/internal-interfaces.md lora_trainer 介面
"""
from __future__ import annotations

import logging
import os
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
    sdxl: bool
    epochs: int
    submitted_at: str
    resolution: int
    batch_size: int
    learning_rate: str
    class_tokens: str
    keep_tokens: int
    num_repeats: int
    mixed_precision: str
    network_dim: int
    network_alpha: int


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
_last_result: dict | None = None  # {"folder": str, "success": bool, "path": str | None, "error": str | None}
_on_complete_callbacks: list[OnCompleteCallback] = []
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
# 訓練完成後待執行的生圖參數，key 為 folder
_pending_generate: dict[str, dict] = {}  # {"prompt": str, "count": int, "batch_size": int?, ...}


def _reset_for_test() -> None:
    """僅供測試使用：清空佇列狀態"""
    global _queue, _running, _pending_generate
    with _lock:
        _queue.clear()
        _running = None
        _pending_generate.clear()


def set_pending_generate(folder: str, params: dict) -> None:
    """設定訓練完成後待執行的生圖參數（僅在該 folder 訓練成功時執行）"""
    with _lock:
        _pending_generate[folder] = dict(params)


def get_and_clear_pending_generate(folder: str) -> dict | None:
    """取得並清除該 folder 的待生圖參數，訓練失敗時也應呼叫以清除"""
    with _lock:
        return _pending_generate.pop(folder, None)


def clear_queue() -> int:
    """
    清除佇列並停止正在執行的訓練。
    Returns: 被清除的 job 數量（佇列 + 1 若在執行中）
    """
    global _queue, _running
    with _lock:
        proc_to_terminate = None
        if _running and _running.proc:
            proc_to_terminate = _running.proc
            _running = None
        count = len(_queue) + (1 if proc_to_terminate else 0)
        _queue.clear()
    if proc_to_terminate:
        try:
            proc_to_terminate.terminate()
            proc_to_terminate.wait(timeout=5)
        except Exception as e:
            logger.warning("終止訓練 subprocess 時發生錯誤: %s", e)
    if count > 0:
        logger.info("已清除訓練佇列，共 %d 個任務", count)
    return count


def _resolve_image_dir(folder: str) -> Path:
    """folder 相對 lora_train_dir，回傳絕對路徑的 image_dir"""
    settings = get_settings()
    base = Path(settings.lora_train_dir).resolve()
    return (base / folder).resolve()


def _resolve_checkpoint_path(checkpoint: str) -> str:
    """
    解析 checkpoint 為本機絕對路徑。
    - 含 \\、Windows 磁碟代號、或以 / 開頭：當作路徑解析
    - 純檔名：使用 LORA_CHECKPOINT_DIRS 第一個路徑作為前綴，回傳絕對路徑
    - 否則原樣回傳（如 HuggingFace ID）
    """
    s = checkpoint.strip()
    if not s:
        return s
    # 本機路徑：含 \、Windows 磁碟代號 (D:)、或以 / 開頭（排除 //）
    is_local = (
        "\\" in s
        or (len(s) > 2 and s[1] == ":" and s[0].isalpha())
        or (s.startswith("/") and not s.startswith("//"))
    )
    if is_local:
        try:
            return str(Path(s).resolve())
        except (OSError, RuntimeError):
            return s
    # 純檔名：用 LORA_CHECKPOINT_DIRS 第一個路徑前綴成絕對路徑
    if "/" not in s and "\\" not in s:
        settings = get_settings()
        dirs_str = getattr(settings, "lora_checkpoint_dirs", None) or ""
        for d in dirs_str.split(","):
            d = d.strip()
            if not d:
                continue
            return str((Path(d) / s).resolve())
    return s


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
    resolution: int = 512,
    batch_size: int = 4,
    class_tokens: str = "sks",
    keep_tokens: int = 1,
    num_repeats: int = 10,
) -> Path:
    """產生 dataset_config TOML，image_dir 需為絕對路徑"""
    toml_dir = image_dir.parent
    toml_path = toml_dir / f"{output_name}_dataset.toml"
    content = f"""[general]
shuffle_caption = true
caption_extension = ".txt"
keep_tokens = {keep_tokens}

[[datasets]]
resolution = {resolution}
batch_size = {batch_size}

  [[datasets.subsets]]
  image_dir = "{image_dir.as_posix()}"
  class_tokens = "{class_tokens}"
  num_repeats = {num_repeats}
"""
    toml_path.write_text(content, encoding="utf-8")
    return toml_path


def _parse_progress(line: str) -> tuple[float, int | None, int | None] | None:
    """從 stdout 解析進度，回傳 (progress, epoch, total_epochs)"""
    # epoch 1/10
    m = re.search(r"epoch\s+(\d+)/(\d+)", line, re.I)
    if m:
        e, t = int(m.group(1)), int(m.group(2))
        return (e / t if t else 0.0, e, t)
    # tqdm: " 50/100 [00:30<..." or "steps: 50/100"
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*\[", line)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (a / b if b else 0.0, None, None)
    # tqdm 或 step 格式 " 50/100 " 且後接時間 (避免誤匹配 tensor shape)
    m = re.search(r"(\d+)\s*/\s*(\d+)\s+[\d:]+<\d", line)
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
    sdxl: bool = False,
    resolution: int = 512,
    batch_size: int = 4,
    learning_rate: str = "1e-4",
    class_tokens: str = "sks",
    keep_tokens: int = 1,
    num_repeats: int = 10,
    mixed_precision: str = "fp16",
    network_dim: int = 16,
    network_alpha: int = 16,
) -> subprocess.Popen[str]:
    """啟動 Kohya train_network.py subprocess"""
    toml_path = _write_dataset_config(
        image_dir,
        output_name,
        resolution=resolution,
        batch_size=batch_size,
        class_tokens=class_tokens,
        keep_tokens=keep_tokens,
        num_repeats=num_repeats,
    )
    settings = get_settings()
    python_exe = (settings.sd_scripts_python or "").strip()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(sd_scripts_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    venv_dir = Path(python_exe).resolve().parent if python_exe else None
    acc_path = venv_dir / ("accelerate.exe" if os.name == "nt" else "accelerate") if venv_dir else None
    if acc_path and acc_path.exists():
        cmd_head = [str(acc_path), "launch"]
    elif python_exe:
        cmd_head = [python_exe, "-m", "accelerate", "launch"]
    else:
        cmd_head = ["accelerate", "launch"]
    train_script = "sdxl_train_network.py" if sdxl else "train_network.py"
    cmd = [
        *cmd_head,
        "--num_cpu_threads_per_process",
        "1",
        str(sd_scripts_path / train_script),
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
        "--network_dim",
        str(network_dim),
        "--network_alpha",
        str(network_alpha),
        "--max_train_epochs",
        str(epochs),
        "--learning_rate",
        learning_rate,
    ]
    if settings.lora_save_every_n_epochs and settings.lora_save_every_n_epochs >= 1:
        cmd.extend(["--save_every_n_epochs", str(settings.lora_save_every_n_epochs)])
    cmd += [
        "--save_model_as",
        "safetensors",
        "--mixed_precision",
        mixed_precision,
        "--cache_latents",
        "--gradient_checkpointing",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(sd_scripts_path),
        env=env,
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
    try:
        settings = get_settings()
        sd_scripts = Path(settings.sd_scripts_path).resolve()
        lora_base = Path(settings.lora_train_dir).resolve()
        output_base = lora_base / "output"
    except Exception as e:
        logger.exception("Worker 初始化失敗: %s", e)
        return

    _wait_count = 0
    while not _stop_event.is_set():
        with _lock:
            if _running or not _queue:
                job = None
            else:
                job = _queue.pop(0)

        if job is None:
            _wait_count += 1
            _stop_event.wait(1.0)
            continue
        _wait_count = 0

        try:
            image_dir = _resolve_image_dir(job.folder)
            output_dir = output_base
            output_dir.mkdir(parents=True, exist_ok=True)

            if not image_dir.exists():
                logger.error("Job %s: image_dir 不存在 %s", job.job_id, image_dir)
                continue

            output_lora = _get_output_lora_path(output_dir, job.folder.replace("/", "_"))

        except OSError as e:
            logger.error("Job %s: 路徑或目錄錯誤: %s", job.job_id, e)
            continue
        except Exception as e:
            logger.exception("Job %s: 前置處理失敗: %s", job.job_id, e)
            continue

        try:
            proc = _run_training_subprocess(
                image_dir=image_dir,
                output_dir=output_dir,
                output_name=job.folder.replace("/", "_"),
                checkpoint=job.checkpoint,
                epochs=job.epochs,
                sd_scripts_path=sd_scripts,
                sdxl=job.sdxl,
                resolution=job.resolution,
                batch_size=job.batch_size,
                learning_rate=job.learning_rate,
                class_tokens=job.class_tokens,
                keep_tokens=job.keep_tokens,
                num_repeats=job.num_repeats,
                mixed_precision=job.mixed_precision,
                network_dim=job.network_dim,
                network_alpha=job.network_alpha,
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

        logger.info("Job %s 開始訓練: folder=%s（載入模型需數分鐘，請稍候）", job.job_id, job.folder)

        # 讀取 stdout 更新進度，並累積輸出供失敗時紀錄
        output_lines: list[str] = []
        if proc.stdout:
            for line in proc.stdout:
                if _stop_event.is_set():
                    proc.terminate()
                    break
                stripped = line.rstrip()
                output_lines.append(stripped)
                if stripped:
                    print(f"[LoRA] {stripped}", flush=True)
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
            get_and_clear_pending_generate(job.folder)  # 訓練失敗則清除待生圖
            tail = "\n".join(output_lines[-50:]) if output_lines else "(無輸出)"
            err_preview = tail.split("\n")[-3:] if tail else []
            err_msg = "訓練失敗，請查看 backend 終端機的錯誤輸出" + (
                f"\n最後幾行: {' '.join(err_preview)[:200]}" if err_preview else ""
            )
            with _lock:
                _last_result = {"folder": job.folder, "success": False, "path": None, "error": err_msg}
            logger.error(
                "Job %s 訓練失敗, returncode=%s\n--- 最後輸出 ---\n%s",
                job.job_id,
                proc.returncode,
                tail,
            )
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
            with _lock:
                _last_result = {"folder": job.folder, "success": True, "path": output_lora_str, "error": None}
            for cb in _on_complete_callbacks:
                try:
                    cb(output_lora_str, job.folder)
                except Exception as e:
                    logger.exception("on_complete callback 錯誤: %s", e)
            logger.info("Job %s 完成: %s", job.job_id, output_lora_str)
        else:
            get_and_clear_pending_generate(job.folder)  # 失敗則清除待生圖
            err_msg = f"訓練結束但找不到輸出檔案（請檢查 backend 日誌）"
            with _lock:
                _last_result = {"folder": job.folder, "success": False, "path": None, "error": err_msg}
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


def ensure_worker() -> None:
    """公開 API：確保 worker 在 app 啟動時即就緒"""
    _ensure_worker()


def enqueue(
    folder: str,
    *,
    checkpoint: str | None = None,
    sdxl: bool | None = None,
    epochs: int = 10,
    resolution: int | None = None,
    batch_size: int | None = None,
    learning_rate: str | None = None,
    class_tokens: str | None = None,
    keep_tokens: int | None = None,
    num_repeats: int | None = None,
    mixed_precision: str | None = None,
    network_dim: int | None = None,
    network_alpha: int | None = None,
    generate_after: dict | None = None,
) -> str:
    """
    加入訓練佇列。
    folder: 相對 lora_train_dir 的路徑。
    訓練參數未指定時使用 config 預設值。
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
    ckpt = _resolve_checkpoint_path(ckpt)

    use_sdxl = sdxl if sdxl is not None else settings.lora_sdxl
    job_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    job = _TrainJob(
        job_id=job_id,
        folder=folder,
        checkpoint=ckpt,
        sdxl=use_sdxl,
        epochs=epochs,
        submitted_at=submitted_at,
        resolution=resolution if resolution is not None else settings.lora_resolution,
        batch_size=batch_size if batch_size is not None else settings.lora_batch_size,
        learning_rate=learning_rate or settings.lora_learning_rate,
        class_tokens=class_tokens or settings.lora_class_tokens,
        keep_tokens=keep_tokens if keep_tokens is not None else settings.lora_keep_tokens,
        num_repeats=num_repeats if num_repeats is not None else settings.lora_num_repeats,
        mixed_precision=mixed_precision or settings.lora_mixed_precision,
        network_dim=network_dim if network_dim is not None else settings.lora_network_dim,
        network_alpha=network_alpha if network_alpha is not None else settings.lora_network_alpha,
    )

    with _lock:
        # 同一 folder 已在 queue 或 running 則不重複加入
        if any(j.folder == folder for j in _queue):
            raise ValueError(f"資料夾已在佇列中: {folder}")
        if _running and _running.job.folder == folder:
            raise ValueError(f"資料夾訓練中: {folder}")
        _queue.append(job)

    if generate_after:
        set_pending_generate(folder, generate_after)

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

    last = _last_result
    return {
        "status": status,
        "current_job": current_job,
        "queue": queue_list,
        "last_result": last,
    }


def register_on_complete(callback: OnCompleteCallback) -> None:
    """
    註冊訓練完成回呼。
    完成時會呼叫 callback(output_lora_path, folder)。
    實作 4c 時：在此回呼中呼叫 comfyui 產圖 + recording.save()
    """
    with _lock:
        _on_complete_callbacks.append(callback)


def _iter_training_folders(base: Path) -> list[tuple[Path, str]]:
    """遍歷 base 下所有子資料夾，回傳 (絕對路徑, 相對 folder)，不含 base 本身"""
    result: list[tuple[Path, str]] = []
    base_resolved = base.resolve()
    for p in base_resolved.rglob("*"):
        if not p.is_dir():
            continue
        try:
            rel = p.relative_to(base_resolved)
            folder = rel.as_posix()
        except ValueError:
            continue
        if not folder or folder == ".":
            continue
        result.append((p, folder))
    return result


def list_folders() -> list[dict]:
    """
    列出 lora_train_dir 下所有含可訓練圖片的子資料夾。
    Returns: [{"folder": str, "image_count": int}, ...]
    """
    settings = get_settings()
    base = Path(settings.lora_train_dir).resolve()

    if not base.exists() or not base.is_dir():
        return []

    result: list[dict] = []
    for image_dir, folder in _iter_training_folders(base):
        count = _count_trainable_images(image_dir)
        if count >= _MIN_IMAGES:
            result.append({"folder": folder, "image_count": count})
    return result


def trigger_check() -> dict:
    """
    檢查是否符合自動觸發條件（圖片數 ≥ 門檻）。
    遍歷 lora_train_dir 下各子資料夾，達門檻且未在佇列／執行中者自動 enqueue。
    Returns: {"should_trigger": bool, "candidates": [{"folder": str, "image_count": int}]}
    """
    settings = get_settings()
    base = Path(settings.lora_train_dir).resolve()
    threshold = settings.lora_train_threshold

    if not base.exists() or not base.is_dir():
        return {"should_trigger": False, "candidates": []}

    candidates: list[dict] = []
    enqueued: list[str] = []

    for image_dir, folder in _iter_training_folders(base):
        count = _count_trainable_images(image_dir)
        if count < threshold:
            continue
        candidates.append({"folder": folder, "image_count": count})

        with _lock:
            if any(j.folder == folder for j in _queue):
                continue
            if _running and _running.job.folder == folder:
                continue

        try:
            enqueue(folder)
            enqueued.append(folder)
        except ValueError:
            # checkpoint 未設定等，略過
            pass

    if enqueued:
        logger.info("trigger_check 已 enqueue: %s", enqueued)

    return {
        "should_trigger": len(candidates) > 0,
        "candidates": candidates,
    }
