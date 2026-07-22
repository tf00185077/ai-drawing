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
import json
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import get_settings
from app.core.queue import QueueFullError, submit as submit_generation
from app.db import database as db_database
from app.db.models import LoraTrainingJob
from app.schemas.lora_train import LoraSmokeTestRequest
from app.services import lora_dataset
from app.services.lora_dataset import DatasetServiceError
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

# 支援的圖片副檔名（與 watcher 一致，when-touching 可抽出共用）
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
# 訓練所需最少圖片數（含 .txt caption）
_MIN_IMAGES = 1
_KOHYA_MIXED_PRECISION_BY_REQUEST = {
    "fp16": "fp16",
    "bf16": "bf16",
    "no": "no",
    "fp32": "no",
}
_TRAIN_SCRIPT_BY_MODEL_FAMILY = {
    "sd15": "train_network.py",
    "sdxl": "sdxl_train_network.py",
    "anima": "anima_train_network.py",
}
_NETWORK_MODULE_BY_MODEL_FAMILY = {
    "sd15": "networks.lora",
    "sdxl": "networks.lora",
    "anima": "networks.lora_anima",
}
_MODEL_FAMILY_ALIASES = {
    "sd1": "sd15",
    "sd1.5": "sd15",
    "sd-1.5": "sd15",
    "sd_1_5": "sd15",
}

OnCompleteCallback = Callable[[str, str], None]
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class TrainerServiceError(ValueError):
    """Structured LoRA trainer workflow error."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class _TrainJob:
    """單一訓練任務"""

    job_id: str
    folder: str
    checkpoint: str
    model_family: str
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
    network_module: str
    network_dim: int
    network_alpha: int
    anima_qwen3: str | None = None
    anima_vae: str | None = None
    anima_t5_tokenizer_path: str | None = None
    dataset_hash: str | None = None
    normalized_trigger_token: str | None = None
    log_path: str | None = None


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


def _utcnow() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_lora_job_table() -> None:
    LoraTrainingJob.__table__.create(bind=db_database.engine, checkfirst=True)


def _with_db(operation: Callable[[Any], Any]) -> Any:
    db = db_database.SessionLocal()
    try:
        result = operation(db)
        db.commit()
        return result
    except OperationalError as exc:
        db.rollback()
        if "no such table" in str(exc).lower():
            _ensure_lora_job_table()
            result = operation(db)
            db.commit()
            return result
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _log_path(job_id: str) -> str:
    settings = get_settings()
    configured_logs_dir = getattr(settings, "lora_train_logs_dir", None)
    if isinstance(configured_logs_dir, str) and configured_logs_dir:
        logs_dir = Path(configured_logs_dir).resolve()
    else:
        logs_dir = (Path(settings.lora_train_dir).resolve() / "logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return str((logs_dir / f"{job_id}.log").resolve())


def _params_json(job: _TrainJob) -> str:
    params = {
        "checkpoint": job.checkpoint,
        "model_family": job.model_family,
        "trainer_script": _train_script_name(job.model_family),
        "sdxl": job.sdxl,
        "epochs": job.epochs,
        "resolution": job.resolution,
        "batch_size": job.batch_size,
        "learning_rate": job.learning_rate,
        "class_tokens": job.class_tokens,
        "keep_tokens": job.keep_tokens,
        "num_repeats": job.num_repeats,
        "mixed_precision": job.mixed_precision,
        "kohya_mixed_precision": _normalize_kohya_mixed_precision(job.mixed_precision),
        "network_module": job.network_module,
        "network_dim": job.network_dim,
        "network_alpha": job.network_alpha,
        "anima_qwen3": job.anima_qwen3,
        "anima_vae": job.anima_vae,
        "anima_t5_tokenizer_path": job.anima_t5_tokenizer_path,
    }
    return json.dumps(params, ensure_ascii=False, sort_keys=True)


def _deserialize_params(params_json: str | None) -> dict | None:
    if not params_json:
        return None
    try:
        return json.loads(params_json)
    except json.JSONDecodeError:
        return {"raw": params_json}


def _serialize_job(row: LoraTrainingJob, *, log_tail_lines: int | None = None, log_truncated: bool | None = None) -> dict:
    return {
        "ok": True,
        "job_id": row.job_id,
        "folder": row.folder,
        "status": row.status,
        "stage": row.stage,
        "progress": row.progress or 0.0,
        "current_epoch": row.current_epoch,
        "total_epochs": row.total_epochs,
        "dataset_hash": row.dataset_hash,
        "normalized_trigger_token": row.normalized_trigger_token,
        "log_path": row.log_path,
        "log_tail_lines": log_tail_lines,
        "log_truncated": log_truncated,
        "output_path": row.output_path,
        "registered_lora_name": row.registered_lora_name,
        "registration_error": row.registration_error,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "params": _deserialize_params(row.params_json),
        "smoke_test_status": row.smoke_test_status,
        "smoke_test_job_id": row.smoke_test_job_id,
        "smoke_test_artifact": row.smoke_test_artifact,
        "smoke_test_error": row.smoke_test_error,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "started_at": _iso(row.started_at),
        "completed_at": _iso(row.completed_at),
        "cancel_requested_at": _iso(row.cancel_requested_at),
    }


def _get_job_row(db: Any, job_id: str) -> LoraTrainingJob | None:
    return db.query(LoraTrainingJob).filter(LoraTrainingJob.job_id == job_id).first()


def _create_persistent_job(job: _TrainJob) -> None:
    def op(db: Any) -> None:
        db.add(
            LoraTrainingJob(
                job_id=job.job_id,
                folder=job.folder,
                status="queued",
                stage="queued",
                progress=0.0,
                total_epochs=job.epochs,
                log_path=job.log_path,
                dataset_hash=job.dataset_hash,
                normalized_trigger_token=job.normalized_trigger_token,
                params_json=_params_json(job),
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

    _with_db(op)


def _update_persistent_job(job_id: str, **fields: Any) -> None:
    def op(db: Any) -> None:
        row = _get_job_row(db, job_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = _utcnow()

    _with_db(op)


def _read_persistent_job(job_id: str) -> dict | None:
    def op(db: Any) -> dict | None:
        row = _get_job_row(db, job_id)
        if row is None:
            return None
        return _serialize_job(row)

    return _with_db(op)


def _is_cancel_requested(job_id: str) -> bool:
    def op(db: Any) -> bool:
        row = _get_job_row(db, job_id)
        return bool(row and row.cancel_requested_at)

    return bool(_with_db(op))


def _append_log(log_path: str | None, text: str) -> None:
    if not log_path:
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _reset_for_test() -> None:
    """僅供測試使用：清空佇列狀態"""
    global _queue, _running, _pending_generate, _last_result
    with _lock:
        _queue.clear()
        _running = None
        _pending_generate.clear()
        _last_result = None


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
        cancelled_jobs = [job.job_id for job in _queue]
        if _running and _running.proc:
            proc_to_terminate = _running.proc
            cancelled_jobs.append(_running.job.job_id)
            _running = None
        count = len(_queue) + (1 if proc_to_terminate else 0)
        _queue.clear()
    for job_id in cancelled_jobs:
        _update_persistent_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            cancel_requested_at=_utcnow(),
            completed_at=_utcnow(),
        )
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


def _dir_candidates(value: Any) -> list[str]:
    """Split a comma-separated directory setting into stripped entries.

    Non-string settings (e.g. an unset MagicMock in tests) yield an empty list so
    resolution degrades gracefully instead of raising.
    """
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _is_local_path(s: str) -> bool:
    """True if the string looks like a local filesystem path rather than a bare
    name or a remote/HuggingFace id."""
    return (
        "\\" in s
        or s.startswith("~")
        or (len(s) > 2 and s[1] == ":" and s[0].isalpha())
        or (s.startswith("/") and not s.startswith("//"))
    )


def _is_bare_filename(s: str) -> bool:
    """True if the string is a plain filename with no path separators."""
    return "/" not in s and "\\" not in s


def _resolve_model_file(name: str, search_dirs: list[str]) -> str:
    """Resolve one model-file input to a local path, accepting three input forms.

    - absolute / separator-bearing / ``~`` local path → resolved as given
    - bare filename → first ``search_dirs`` entry that contains it; otherwise a
      best-effort join with the first search dir; otherwise the bare name
    - remote / HuggingFace id (contains ``/`` but is not a local path) → unchanged

    This never raises and never enforces existence — existence is validated
    separately by the caller so remote references and unresolved names stay usable.
    """
    s = (name or "").strip()
    if not s:
        return s
    if _is_local_path(s):
        try:
            return str(Path(s).expanduser().resolve())
        except (OSError, RuntimeError):
            return s
    if _is_bare_filename(s):
        for d in search_dirs:
            candidate = Path(d) / s
            if candidate.exists():
                return str(candidate.resolve())
        if search_dirs:
            return str((Path(search_dirs[0]) / s).resolve())
        return s
    # Contains "/" but is not a local path → treat as a remote / HuggingFace id.
    return s


def _checkpoint_search_dirs(settings: Any, model_family: str) -> list[str]:
    """Family-aware checkpoint search order, reusing generation-side config.

    ``LORA_CHECKPOINT_DIRS`` stays first so existing SD/SDXL bare-name flows
    resolve identically; Anima additionally searches the diffusion-model dir.
    """
    dirs = _dir_candidates(getattr(settings, "lora_checkpoint_dirs", ""))
    if _normalize_model_family(model_family) == "anima":
        dirs += _dir_candidates(getattr(settings, "comfyui_diffusion_models_dir", ""))
    else:
        dirs += _dir_candidates(getattr(settings, "comfyui_checkpoints_dir", ""))
    return dirs


def _resolve_checkpoint_path(checkpoint: str, model_family: str = "sdxl") -> str:
    """Resolve a checkpoint input via the unified resolver with family-aware dirs."""
    settings = get_settings()
    return _resolve_model_file(checkpoint, _checkpoint_search_dirs(settings, model_family))


def _validate_checkpoint_exists(
    resolved: str,
    original_input: str,
    search_dirs: list[str],
    *,
    allow_unverified: bool,
) -> None:
    """Fail fast on a missing local checkpoint before a durable job is created.

    Remote/HuggingFace references are exempt, bare names with no configured search
    dirs are treated as unverifiable (warn, do not block), and ``allow_unverified``
    bypasses the check entirely.
    """
    if allow_unverified:
        return
    s = (original_input or "").strip()
    if not s:
        return
    if not _is_local_path(s) and not _is_bare_filename(s):
        # Remote / HuggingFace id — nothing to check on the local filesystem.
        return
    if _is_bare_filename(s) and not _is_local_path(s) and not search_dirs:
        logger.warning("checkpoint existence unverifiable (no search dirs configured): %s", s)
        return
    if Path(resolved).exists():
        return
    raise TrainerServiceError(
        "checkpoint_not_found",
        f"checkpoint not found: {resolved}",
        {"checkpoint": resolved, "searched_dirs": search_dirs},
    )


def _is_anima_family(model_family: str | None) -> bool:
    """Safe check for the Anima family that never raises on unknown/None values."""
    try:
        return _normalize_model_family(model_family) == "anima"
    except TrainerServiceError:
        return False


def _normalize_model_family(model_family: str | None) -> str:
    value = (model_family or "").strip().lower()
    value = _MODEL_FAMILY_ALIASES.get(value, value)
    if value in _TRAIN_SCRIPT_BY_MODEL_FAMILY:
        return value
    raise TrainerServiceError(
        "unsupported_model_family",
        "model_family must be one of: sd15, sdxl, anima",
        {
            "model_family": model_family,
            "accepted": sorted(_TRAIN_SCRIPT_BY_MODEL_FAMILY),
        },
    )


def _resolve_model_family(
    *,
    model_family: str | None,
    sdxl: bool | None,
    configured_model_family: str | None,
    configured_sdxl: bool | None,
) -> str:
    if model_family is not None and model_family.strip():
        return _normalize_model_family(model_family)
    if sdxl is not None:
        return "sdxl" if sdxl else "sd15"
    if configured_model_family is not None and configured_model_family.strip():
        return _normalize_model_family(configured_model_family)
    return "sdxl" if configured_sdxl is True else "sd15"


def _train_script_name(model_family: str) -> str:
    return _TRAIN_SCRIPT_BY_MODEL_FAMILY[_normalize_model_family(model_family)]


def _resolve_network_module(model_family: str, network_module: str | None) -> str:
    """Resolve the Kohya network module, defaulting Anima to its architecture-specific LoRA."""
    cleaned = _clean_optional_str(network_module)
    if cleaned:
        return cleaned
    return _NETWORK_MODULE_BY_MODEL_FAMILY[_normalize_model_family(model_family)]


def _normalize_kohya_mixed_precision(mixed_precision: str | None) -> str:
    """Map API/config precision values to current Kohya CLI choices."""
    value = (mixed_precision or "fp16").strip().lower()
    if value in _KOHYA_MIXED_PRECISION_BY_REQUEST:
        return _KOHYA_MIXED_PRECISION_BY_REQUEST[value]
    raise TrainerServiceError(
        "unsupported_mixed_precision",
        "mixed_precision must be one of: fp16, bf16, fp32, no",
        {
            "mixed_precision": mixed_precision,
            "accepted": sorted(_KOHYA_MIXED_PRECISION_BY_REQUEST),
            "kohya_cli_choices": ["no", "fp16", "bf16"],
        },
    )


def _clean_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _resolve_runtime_path(value: str) -> str:
    try:
        return str(Path(value).expanduser().resolve())
    except (OSError, RuntimeError):
        return value


def _validate_runtime_path(
    value: str | None,
    *,
    code: str,
    label: str,
    search_dirs: list[str] | None = None,
    required: bool = False,
) -> str | None:
    cleaned = _clean_optional_str(value)
    if not cleaned:
        if required:
            raise TrainerServiceError(
                code,
                f"model_family=anima requires {label}",
                {"model_family": "anima", label: value},
            )
        return None

    # Route through the unified resolver so a bare component filename resolves
    # against its ComfyUI directory instead of failing relative to the CWD.
    resolved = _resolve_model_file(cleaned, search_dirs or [])
    if not Path(resolved).exists():
        raise TrainerServiceError(
            code,
            f"{label} does not exist: {resolved}",
            {"model_family": "anima", label: resolved, "searched_dirs": search_dirs or []},
        )
    return resolved


def _resolve_anima_runtime_args(
    *,
    model_family: str,
    anima_qwen3: str | None,
    anima_vae: str | None,
    anima_t5_tokenizer_path: str | None,
    settings: Any,
) -> dict[str, str | None]:
    """Resolve and validate Anima-only runtime paths before queueing or launching."""
    if _normalize_model_family(model_family) != "anima":
        return {
            "anima_qwen3": None,
            "anima_vae": None,
            "anima_t5_tokenizer_path": None,
        }

    qwen3_value = _clean_optional_str(anima_qwen3) or _clean_optional_str(getattr(settings, "lora_anima_qwen3", ""))
    vae_value = _clean_optional_str(anima_vae) or _clean_optional_str(getattr(settings, "lora_anima_vae", ""))
    t5_value = _clean_optional_str(anima_t5_tokenizer_path) or _clean_optional_str(
        getattr(settings, "lora_anima_t5_tokenizer_path", "")
    )
    text_encoder_dirs = _dir_candidates(getattr(settings, "comfyui_text_encoders_dir", ""))
    vae_dirs = _dir_candidates(getattr(settings, "comfyui_vae_dir", ""))
    return {
        "anima_qwen3": _validate_runtime_path(
            qwen3_value,
            code="anima_qwen3_missing",
            label="anima_qwen3",
            search_dirs=text_encoder_dirs,
            required=True,
        ),
        "anima_vae": _validate_runtime_path(
            vae_value,
            code="anima_vae_missing",
            label="anima_vae",
            search_dirs=vae_dirs,
        ),
        "anima_t5_tokenizer_path": _validate_runtime_path(
            t5_value,
            code="anima_t5_tokenizer_path_missing",
            label="anima_t5_tokenizer_path",
            search_dirs=text_encoder_dirs,
        ),
    }


def _validate_trainer_runtime(sd_scripts_path: str | None, *, model_family: str) -> Path:
    """Validate Kohya sd-scripts runtime before creating a durable job."""
    family = _normalize_model_family(model_family)
    script_name = _train_script_name(family)
    raw_path = (sd_scripts_path or "").strip()
    details = {"sd_scripts_path": raw_path, "model_family": family, "expected_script": script_name}
    if not raw_path:
        raise TrainerServiceError(
            "sd_scripts_path_missing",
            "sd_scripts_path is not configured",
            details,
        )

    path = Path(raw_path).expanduser().resolve()
    details["sd_scripts_path"] = str(path)
    if not path.exists():
        raise TrainerServiceError(
            "sd_scripts_path_missing",
            f"sd_scripts_path does not exist: {path}",
            details,
        )
    if not path.is_dir():
        raise TrainerServiceError(
            "sd_scripts_path_not_directory",
            f"sd_scripts_path is not a directory: {path}",
            details,
        )

    script_path = path / script_name
    details["train_script"] = str(script_path)
    if not script_path.exists() or not script_path.is_file():
        raise TrainerServiceError(
            "train_script_missing",
            f"Kohya train script not found: {script_path}",
            details,
        )
    return path


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
    model_family: str | None = None,
    sdxl: bool = False,
    resolution: int = 512,
    batch_size: int = 4,
    learning_rate: str = "1e-4",
    class_tokens: str = "sks",
    keep_tokens: int = 1,
    num_repeats: int = 10,
    mixed_precision: str = "fp16",
    network_module: str | None = None,
    network_dim: int = 16,
    network_alpha: int = 16,
    anima_qwen3: str | None = None,
    anima_vae: str | None = None,
    anima_t5_tokenizer_path: str | None = None,
) -> subprocess.Popen[str]:
    """啟動 Kohya train_network.py subprocess"""
    family = _resolve_model_family(
        model_family=model_family,
        sdxl=sdxl,
        configured_model_family=None,
        configured_sdxl=False,
    )
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
    kohya_mixed_precision = _normalize_kohya_mixed_precision(mixed_precision)
    resolved_network_module = _resolve_network_module(family, network_module)
    anima_args = _resolve_anima_runtime_args(
        model_family=family,
        anima_qwen3=anima_qwen3,
        anima_vae=anima_vae,
        anima_t5_tokenizer_path=anima_t5_tokenizer_path,
        settings=settings,
    )
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
    train_script = _train_script_name(family)
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
        resolved_network_module,
        "--network_dim",
        str(network_dim),
        "--network_alpha",
        str(network_alpha),
        "--max_train_epochs",
        str(epochs),
        "--learning_rate",
        learning_rate,
    ]
    if family == "anima":
        cmd.extend(["--qwen3", str(anima_args["anima_qwen3"])])
        if anima_args["anima_vae"]:
            cmd.extend(["--vae", str(anima_args["anima_vae"])])
        if anima_args["anima_t5_tokenizer_path"]:
            cmd.extend(["--t5_tokenizer_path", str(anima_args["anima_t5_tokenizer_path"])])
    if settings.lora_save_every_n_epochs and settings.lora_save_every_n_epochs >= 1:
        cmd.extend(["--save_every_n_epochs", str(settings.lora_save_every_n_epochs)])
    cmd += [
        "--save_model_as",
        "safetensors",
        "--mixed_precision",
        kohya_mixed_precision,
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


def _register_output_lora(source_path: Path, job_id: str) -> tuple[str, str]:
    """Copy trained LoRA into ComfyUI LoRA directory with temp-file then rename."""
    settings = get_settings()
    target_dir_raw = (settings.comfyui_lora_dir or "").strip()
    if not target_dir_raw:
        raise TrainerServiceError("lora_registration_not_configured", "comfyui_lora_dir is not configured")

    source = source_path.resolve()
    target_dir = Path(target_dir_raw).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if source == target.resolve():
        return source.name, str(target)

    temp_target = target_dir / f".{source.name}.{job_id}.tmp"
    try:
        shutil.copy2(source, temp_target)
        os.replace(temp_target, target)
    finally:
        if temp_target.exists():
            temp_target.unlink(missing_ok=True)
    return source.name, str(target.resolve())


def _worker_loop() -> None:
    """背景 worker：依序執行佇列中的訓練"""
    global _running, _last_result
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
        log_path = job.log_path or _log_path(job.job_id)

        try:
            _append_log(log_path, f"Job {job.job_id} dequeued")
            _update_persistent_job(job.job_id, stage="preflight")
            image_dir = _resolve_image_dir(job.folder)
            output_dir = output_base
            output_dir.mkdir(parents=True, exist_ok=True)

            if not image_dir.exists():
                raise TrainerServiceError("dataset_not_found", f"image_dir not found: {image_dir}")

            output_lora = _get_output_lora_path(output_dir, job.folder.replace("/", "_"))
            if job.dataset_hash:
                current_hash = lora_dataset.compute_dataset_hash(job.folder)
                if current_hash != job.dataset_hash:
                    raise TrainerServiceError(
                        "dataset_hash_mismatch",
                        "dataset hash changed before training start",
                        {"expected_dataset_hash": job.dataset_hash, "current_dataset_hash": current_hash},
                    )

            with lora_dataset.dataset_lock(job.folder, owner=f"training:{job.job_id}"):
                _update_persistent_job(
                    job.job_id,
                    status="running",
                    stage="training",
                    progress=0.0,
                    total_epochs=job.epochs,
                    started_at=_utcnow(),
                    log_path=log_path,
                )
                proc = _run_training_subprocess(
                    image_dir=image_dir,
                    output_dir=output_dir,
                    output_name=job.folder.replace("/", "_"),
                    checkpoint=job.checkpoint,
                    epochs=job.epochs,
                    sd_scripts_path=sd_scripts,
                    model_family=job.model_family,
                    sdxl=job.sdxl,
                    resolution=job.resolution,
                    batch_size=job.batch_size,
                    learning_rate=job.learning_rate,
                    class_tokens=job.class_tokens,
                    keep_tokens=job.keep_tokens,
                    num_repeats=job.num_repeats,
                    mixed_precision=job.mixed_precision,
                    network_module=job.network_module,
                    network_dim=job.network_dim,
                    network_alpha=job.network_alpha,
                    anima_qwen3=job.anima_qwen3,
                    anima_vae=job.anima_vae,
                    anima_t5_tokenizer_path=job.anima_t5_tokenizer_path,
                )

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
                _append_log(log_path, f"Job {job.job_id} started")

                output_lines: list[str] = []
                cancelled = False
                if proc.stdout:
                    for line in proc.stdout:
                        if _stop_event.is_set() or _is_cancel_requested(job.job_id):
                            cancelled = True
                            proc.terminate()
                            _append_log(log_path, "Cancellation requested; terminating subprocess")
                            break
                        stripped = line.rstrip()
                        output_lines.append(stripped)
                        _append_log(log_path, stripped)
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
                            update_fields: dict[str, Any] = {"progress": prog, "stage": "training"}
                            if ep is not None:
                                update_fields["current_epoch"] = ep
                            if tot is not None:
                                update_fields["total_epochs"] = tot
                            _update_persistent_job(job.job_id, **update_fields)

                proc.wait()
                cancelled = cancelled or _is_cancel_requested(job.job_id)

            with _lock:
                if _running and _running.job.job_id == job.job_id:
                    _running = None

            if cancelled:
                get_and_clear_pending_generate(job.folder)
                _update_persistent_job(
                    job.job_id,
                    status="cancelled",
                    stage="cancelled",
                    completed_at=_utcnow(),
                )
                with _lock:
                    _last_result = {"folder": job.folder, "success": False, "path": None, "error": "cancelled"}
                logger.info("Job %s 已取消", job.job_id)
                continue

            if proc.returncode != 0:
                get_and_clear_pending_generate(job.folder)
                tail = "\n".join(output_lines[-50:]) if output_lines else "(無輸出)"
                err_preview = tail.split("\n")[-3:] if tail else []
                err_msg = "訓練失敗，請查看 job log" + (
                    f"\n最後幾行: {' '.join(err_preview)[:200]}" if err_preview else ""
                )
                _update_persistent_job(
                    job.job_id,
                    status="failed",
                    stage="failed",
                    error_code="kohya_failed",
                    error_message=err_msg,
                    completed_at=_utcnow(),
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

            found_path: Path | None = None
            prefix = job.folder.replace("/", "_")
            if output_lora.exists():
                found_path = output_lora
            else:
                for f in output_dir.glob(f"{prefix}*.safetensors"):
                    found_path = f
                    break

            if not found_path:
                get_and_clear_pending_generate(job.folder)
                err_msg = "訓練結束但找不到輸出檔案（請檢查 job log）"
                _update_persistent_job(
                    job.job_id,
                    status="failed",
                    stage="failed",
                    error_code="output_missing",
                    error_message=err_msg,
                    completed_at=_utcnow(),
                )
                with _lock:
                    _last_result = {"folder": job.folder, "success": False, "path": None, "error": err_msg}
                logger.warning("Job %s 完成但找不到輸出檔案: %s", job.job_id, output_dir)
                continue

            output_lora_str = str(found_path.resolve())
            registered_name: str | None = None
            registration_error: str | None = None
            registered_path = output_lora_str
            _update_persistent_job(
                job.job_id,
                stage="registering",
                progress=1.0,
                current_epoch=job.epochs,
                total_epochs=job.epochs,
                output_path=output_lora_str,
            )
            try:
                registered_name, registered_path = _register_output_lora(found_path, job.job_id)
                _append_log(log_path, f"Registered LoRA: {registered_name} -> {registered_path}")
            except Exception as exc:
                registration_error = str(exc)
                _append_log(log_path, f"Registration failed: {registration_error}")
                logger.warning("Job %s LoRA registration failed: %s", job.job_id, exc)

            _update_persistent_job(
                job.job_id,
                status="completed",
                stage="completed",
                progress=1.0,
                output_path=output_lora_str,
                registered_lora_name=registered_name,
                registration_error=registration_error,
                completed_at=_utcnow(),
            )
            with _lock:
                _last_result = {"folder": job.folder, "success": True, "path": output_lora_str, "error": None}
            for cb in _on_complete_callbacks:
                try:
                    cb(output_lora_str, job.folder)
                except Exception as e:
                    logger.exception("on_complete callback 錯誤: %s", e)
            logger.info("Job %s 完成: %s", job.job_id, output_lora_str)
        except DatasetServiceError as exc:
            err_msg = exc.message
            get_and_clear_pending_generate(job.folder)
            _append_log(log_path, f"Job failed: {exc.code}: {err_msg}")
            _update_persistent_job(
                job.job_id,
                status="failed",
                stage="failed",
                error_code=exc.code,
                error_message=err_msg,
                completed_at=_utcnow(),
            )
            with _lock:
                if _running and _running.job.job_id == job.job_id:
                    _running = None
                _last_result = {"folder": job.folder, "success": False, "path": None, "error": err_msg}
            logger.error("Job %s dataset error: %s", job.job_id, exc)
        except TrainerServiceError as exc:
            err_msg = exc.message
            get_and_clear_pending_generate(job.folder)
            _append_log(log_path, f"Job failed: {exc.code}: {err_msg}")
            _update_persistent_job(
                job.job_id,
                status="failed",
                stage="failed",
                error_code=exc.code,
                error_message=err_msg,
                completed_at=_utcnow(),
            )
            with _lock:
                if _running and _running.job.job_id == job.job_id:
                    _running = None
                _last_result = {"folder": job.folder, "success": False, "path": None, "error": err_msg}
            logger.error("Job %s trainer error: %s", job.job_id, exc)
        except Exception as exc:
            err_msg = str(exc)
            get_and_clear_pending_generate(job.folder)
            _append_log(log_path, f"Job failed: unexpected_error: {err_msg}")
            _update_persistent_job(
                job.job_id,
                status="failed",
                stage="failed",
                error_code="unexpected_error",
                error_message=err_msg,
                completed_at=_utcnow(),
            )
            with _lock:
                if _running and _running.job.job_id == job.job_id:
                    _running = None
                _last_result = {"folder": job.folder, "success": False, "path": None, "error": err_msg}
            logger.exception("Job %s 前置或訓練流程失敗: %s", job.job_id, exc)


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
    model_family: str | None = None,
    anima_qwen3: str | None = None,
    anima_vae: str | None = None,
    anima_t5_tokenizer_path: str | None = None,
    sdxl: bool | None = None,
    epochs: int = 10,
    resolution: int | None = None,
    batch_size: int | None = None,
    learning_rate: str | None = None,
    class_tokens: str | None = None,
    keep_tokens: int | None = None,
    num_repeats: int | None = None,
    mixed_precision: str | None = None,
    network_module: str | None = None,
    network_dim: int | None = None,
    network_alpha: int | None = None,
    trigger_token: str | None = None,
    expected_dataset_hash: str | None = None,
    allow_unverified_checkpoint: bool = False,
) -> str:
    """
    加入訓練佇列。
    folder: 相對 lora_train_dir 的路徑。
    訓練參數未指定時使用 config 預設值。
    allow_unverified_checkpoint: True 時跳過 checkpoint 存在性檢查（如遠端掛載邊界情境）。
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

    checkpoint_input = checkpoint or settings.lora_default_checkpoint
    if not checkpoint_input:
        raise ValueError("未指定 checkpoint 且 config 無 lora_default_checkpoint")

    configured_model_family = getattr(settings, "lora_model_family", "")
    if not isinstance(configured_model_family, str):
        configured_model_family = ""
    configured_sdxl = getattr(settings, "lora_sdxl", False)
    use_model_family = _resolve_model_family(
        model_family=model_family,
        sdxl=sdxl,
        configured_model_family=configured_model_family,
        configured_sdxl=configured_sdxl if isinstance(configured_sdxl, bool) else False,
    )
    use_sdxl = use_model_family == "sdxl"

    checkpoint_search_dirs = _checkpoint_search_dirs(settings, use_model_family)
    ckpt = _resolve_model_file(checkpoint_input, checkpoint_search_dirs)
    _validate_checkpoint_exists(
        ckpt,
        checkpoint_input,
        checkpoint_search_dirs,
        allow_unverified=allow_unverified_checkpoint,
    )
    resolved_network_module = _resolve_network_module(use_model_family, network_module)
    anima_args = _resolve_anima_runtime_args(
        model_family=use_model_family,
        anima_qwen3=anima_qwen3,
        anima_vae=anima_vae,
        anima_t5_tokenizer_path=anima_t5_tokenizer_path,
        settings=settings,
    )
    class_token_value = class_tokens or settings.lora_class_tokens
    normalized_token = lora_dataset.normalize_trigger_token(trigger_token or class_token_value)
    dataset_hash: str | None = None
    if trigger_token or expected_dataset_hash:
        try:
            validation = lora_dataset.validate_dataset(
                folder,
                trigger_token=normalized_token,
                expected_dataset_hash=expected_dataset_hash,
            )
        except DatasetServiceError as exc:
            raise TrainerServiceError(exc.code, exc.message, exc.details) from exc
        dataset_hash = validation.dataset_hash
        if not validation.ok:
            code = validation.errors[0].code if validation.errors else "dataset_validation_failed"
            raise TrainerServiceError(
                code,
                "dataset validation failed",
                {"errors": [issue.model_dump() for issue in validation.errors], "dataset_hash": validation.dataset_hash},
            )
    _validate_trainer_runtime(settings.sd_scripts_path, model_family=use_model_family)

    job_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_path = _log_path(job_id)
    job = _TrainJob(
        job_id=job_id,
        folder=folder,
        checkpoint=ckpt,
        model_family=use_model_family,
        sdxl=use_sdxl,
        epochs=epochs,
        submitted_at=submitted_at,
        resolution=resolution if resolution is not None else settings.lora_resolution,
        batch_size=batch_size if batch_size is not None else settings.lora_batch_size,
        learning_rate=learning_rate or settings.lora_learning_rate,
        class_tokens=class_token_value,
        keep_tokens=keep_tokens if keep_tokens is not None else settings.lora_keep_tokens,
        num_repeats=num_repeats if num_repeats is not None else settings.lora_num_repeats,
        mixed_precision=mixed_precision or settings.lora_mixed_precision,
        network_module=resolved_network_module,
        network_dim=network_dim if network_dim is not None else settings.lora_network_dim,
        network_alpha=network_alpha if network_alpha is not None else settings.lora_network_alpha,
        anima_qwen3=anima_args["anima_qwen3"],
        anima_vae=anima_args["anima_vae"],
        anima_t5_tokenizer_path=anima_args["anima_t5_tokenizer_path"],
        dataset_hash=dataset_hash,
        normalized_trigger_token=normalized_token,
        log_path=log_path,
    )

    _create_persistent_job(job)
    with _lock:
        # 同一 folder 已在 queue 或 running 則不重複加入
        if any(j.folder == folder for j in _queue):
            _update_persistent_job(
                job.job_id,
                status="cancelled",
                stage="cancelled",
                error_code="duplicate_folder",
                error_message=f"資料夾已在佇列中: {folder}",
                completed_at=_utcnow(),
            )
            raise ValueError(f"資料夾已在佇列中: {folder}")
        if _running and _running.job.folder == folder:
            _update_persistent_job(
                job.job_id,
                status="cancelled",
                stage="cancelled",
                error_code="duplicate_folder",
                error_message=f"資料夾訓練中: {folder}",
                completed_at=_utcnow(),
            )
            raise ValueError(f"資料夾訓練中: {folder}")
        _queue.append(job)

    _append_log(log_path, f"Job {job_id} queued for folder={folder}")
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


def get_job_status(job_id: str) -> dict:
    """Return durable status for one LoRA training job."""
    result = _read_persistent_job(job_id)
    if result is None:
        raise TrainerServiceError("job_not_found", f"LoRA training job not found: {job_id}")
    return result


def _tail_lines(path: Path, line_limit: int) -> tuple[list[str], bool]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= line_limit:
        return lines, False
    return lines[-line_limit:], True


def get_job_logs(job_id: str, *, line_limit: int = 100) -> dict:
    """Return bounded log lines for a durable LoRA training job."""
    job = get_job_status(job_id)
    log_path = job.get("log_path")
    if not log_path:
        return {
            "ok": False,
            "job_id": job_id,
            "lines": [],
            "truncated": False,
            "log_path": None,
            "error_code": "log_not_found",
            "error_message": "job has no log path",
        }
    path = Path(log_path)
    if not path.exists() or not path.is_file():
        return {
            "ok": False,
            "job_id": job_id,
            "lines": [],
            "truncated": False,
            "log_path": log_path,
            "error_code": "log_not_found",
            "error_message": "job log file not found",
        }
    try:
        lines, truncated = _tail_lines(path, max(1, min(line_limit, 1000)))
    except OSError as exc:
        return {
            "ok": False,
            "job_id": job_id,
            "lines": [],
            "truncated": False,
            "log_path": log_path,
            "error_code": "log_read_failed",
            "error_message": str(exc),
        }
    return {
        "ok": True,
        "job_id": job_id,
        "lines": lines,
        "truncated": truncated,
        "log_path": log_path,
    }


def cancel_job(job_id: str) -> dict:
    """Cancel a queued or running durable LoRA training job."""
    job = get_job_status(job_id)
    if job["status"] in TERMINAL_STATUSES:
        return {"ok": True, "job_id": job_id, "status": job["status"]}

    proc_to_terminate: subprocess.Popen[str] | None = None
    removed_from_queue = False
    with _lock:
        for idx, queued in enumerate(_queue):
            if queued.job_id == job_id:
                _queue.pop(idx)
                removed_from_queue = True
                break
        if _running and _running.job.job_id == job_id:
            proc_to_terminate = _running.proc

    if removed_from_queue:
        _update_persistent_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            cancel_requested_at=_utcnow(),
            completed_at=_utcnow(),
        )
        _append_log(job.get("log_path"), "Queued job cancelled")
        return {"ok": True, "job_id": job_id, "status": "cancelled"}

    if proc_to_terminate:
        _update_persistent_job(
            job_id,
            stage="cancelling",
            cancel_requested_at=_utcnow(),
        )
        _append_log(job.get("log_path"), "Cancellation requested")
        try:
            proc_to_terminate.terminate()
        except Exception as exc:
            raise TrainerServiceError(
                "job_cancel_failed",
                "failed to terminate training subprocess",
                {"error": str(exc)},
            ) from exc
        return {"ok": True, "job_id": job_id, "status": "running"}

    if job["status"] == "queued":
        _update_persistent_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            cancel_requested_at=_utcnow(),
            completed_at=_utcnow(),
        )
        _append_log(job.get("log_path"), "Queued job cancelled before worker picked it up")
        return {"ok": True, "job_id": job_id, "status": "cancelled"}

    raise TrainerServiceError("job_not_cancellable", f"job is not cancellable in status {job['status']}")


def smoke_test_job(job_id: str, body: LoraSmokeTestRequest) -> dict:
    """Submit a generation smoke test for a completed, registered LoRA job."""
    job = get_job_status(job_id)
    if job["status"] != "completed":
        raise TrainerServiceError(
            "smoke_test_precondition_failed",
            "LoRA job must be completed before smoke test",
            {"status": job["status"]},
        )
    registered_lora = job.get("registered_lora_name")
    if not registered_lora:
        raise TrainerServiceError(
            "smoke_test_precondition_failed",
            "LoRA job has no registered_lora_name",
            {"registration_error": job.get("registration_error")},
        )

    prompt_parts = [
        part for part in [job.get("normalized_trigger_token"), body.prompt or "high quality, 1girl, solo"] if part
    ]
    job_params = job.get("params") or {}
    params: dict[str, Any] = {
        "prompt": ", ".join(prompt_parts),
        "negative_prompt": body.negative_prompt or "low quality, blurry",
        "lora": registered_lora,
        "steps": 12,
        "cfg": 7.0,
    }
    # Build a generation request matching the trained model family. Anima is a
    # diffusion-model family (separate diffusion model / text encoder / VAE) and
    # cannot be exercised through a checkpoint-only request.
    if _is_anima_family(job_params.get("model_family")):
        params["template"] = "anima"
        params["diffusion_model"] = body.diffusion_model or job_params.get("checkpoint")
        params["text_encoder"] = body.text_encoder or job_params.get("anima_qwen3")
        vae_value = body.vae or job_params.get("anima_vae")
        if vae_value:
            params["vae"] = vae_value
    else:
        params["checkpoint"] = body.checkpoint or job_params.get("checkpoint")
    try:
        generation_job_id = submit_generation(params)
    except QueueFullError as exc:
        _update_persistent_job(
            job_id,
            smoke_test_status="failed",
            smoke_test_error=str(exc),
        )
        raise TrainerServiceError("generation_queue_full", str(exc)) from exc
    except Exception as exc:
        _update_persistent_job(
            job_id,
            smoke_test_status="failed",
            smoke_test_error=str(exc),
        )
        raise TrainerServiceError("smoke_test_submit_failed", str(exc)) from exc

    _update_persistent_job(
        job_id,
        smoke_test_status="submitted",
        smoke_test_job_id=generation_job_id,
        smoke_test_error=None,
    )
    return {
        "ok": True,
        "job_id": job_id,
        "registered_lora_name": registered_lora,
        "smoke_test_status": "submitted",
        "generation_job_id": generation_job_id,
        "artifact": None,
        "error": None,
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
        except (TrainerServiceError, ValueError):
            # checkpoint 未設定等，略過
            pass

    if enqueued:
        logger.info("trigger_check 已 enqueue: %s", enqueued)

    return {
        "should_trigger": len(candidates) > 0,
        "candidates": candidates,
    }
