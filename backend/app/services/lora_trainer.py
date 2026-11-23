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
import hashlib
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
from app.db.models import LoraTrainingJob, LoraOutputReservation
from app.services import lora_delivery as delivery, lora_parameters, lora_public, lora_smoke
from sqlalchemy import text
from app.schemas.lora_train import (
    ComponentIdentity,
    EffectiveTrainingRecipeV1,
    EvidenceValue,
    ExecutionEvidence,
    LoraSmokeTestRequest,
    RecipeCompilationResult,
    RequestedTrainingRecipeV1,
    TrainerCapabilitySnapshot,
    TrainingStepPlan,
)
from app.services import lora_dataset
from app.services.lora_dataset import DatasetServiceError
from app.services.lora_training_recipe import (
    RecipeError,
    compile_training_recipe,
    normalize_recipe_input,
)
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

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
        *,
        hint: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}
        self.hint = hint


class AdmissionUncertainError(TrainerServiceError):
    """A canonical durable ID exists; scheduling/acknowledgement is uncertain."""
    def __init__(self, job_id):
        super().__init__('admission_uncertain', 'reconcile the canonical job before another submission')
        self.job_id = job_id


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
    profile_hash: str | None = None
    normalized_trigger_token: str | None = None
    log_path: str | None = None
    recipe: RecipeCompilationResult | None = None
    output_name: str | None = None
    resolved_output_name: str | None = None
    output_serial: int | None = None
    run_locator: str | None = None
    output_config_hash: str | None = None


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
_children: list = []
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
    LoraOutputReservation.__table__.create(bind=db_database.engine, checkfirst=True)


def _with_db(operation: Callable[[Any], Any]) -> Any:
    db = db_database.SessionLocal()
    try:
        result = operation(db)
        db.commit()
        return result
    except OperationalError as exc:
        db.rollback()
        error_text = str(exc).lower()
        if "no such table" in error_text:
            _ensure_lora_job_table()
            result = operation(db)
            db.commit()
            return result
        if any(
            column in error_text
            for column in (
                "output_name", "run_locator", "validation_status", "output_sha256", "registration_status", "output_config_hash",
                "profile_hash",
                "error_details_json",
                "recipe_schema_version",
                "recipe_hash",
                "recipe_json",
                "execution_evidence_json",
            )
        ) and (
            "no such column" in error_text or "has no column named" in error_text
        ):
            db_database.init_db()
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
        "dataset_hash": job.dataset_hash,
        "profile_hash": job.profile_hash,
    }
    return json.dumps(params, ensure_ascii=False, sort_keys=True)


def _recipe_envelope_json(compiled: RecipeCompilationResult) -> str:
    envelope = {
        "requested": compiled.requested.model_dump(
            mode="json",
            exclude_none=True,
        ),
        "effective": compiled.effective.model_dump(mode="json"),
        "field_sources": dict(compiled.field_sources),
        "step_plan": compiled.step_plan.model_dump(mode="json"),
        "component_identities": {
            name: identity.model_dump(mode="json")
            for name, identity in compiled.component_identities.items()
        },
        "capability": compiled.capability.model_dump(mode="json"),
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _execution_evidence_json(
    compiled: RecipeCompilationResult,
) -> str | None:
    evidence = compiled.execution_evidence
    if evidence is None:
        return None
    return json.dumps(
        evidence.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _deserialize_recipe_envelope(recipe_json: str | None) -> dict[str, Any] | None:
    if not recipe_json:
        return None
    try:
        value = json.loads(recipe_json)
        if not isinstance(value, dict):
            return None
        requested = RequestedTrainingRecipeV1.model_validate(value["requested"])
        effective = EffectiveTrainingRecipeV1.model_validate(value["effective"])
        step_plan = TrainingStepPlan.model_validate(value["step_plan"])
        capability = TrainerCapabilitySnapshot.model_validate(value["capability"])
        raw_sources = value["field_sources"]
        if not isinstance(raw_sources, dict) or any(
            source not in {"caller", "preflight_policy", "server_policy", "derived"}
            for source in raw_sources.values()
        ):
            return None
        raw_components = value["component_identities"]
        if not isinstance(raw_components, dict):
            return None
        components = {
            str(name): ComponentIdentity.model_validate(identity)
            for name, identity in raw_components.items()
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return {
        "requested_recipe": requested.model_dump(
            mode="json",
            exclude_none=True,
        ),
        "effective_recipe": effective.model_dump(mode="json"),
        "requested_scope": (
            requested.scope.model_dump(mode="json", exclude_none=True)
            if requested.scope is not None
            else None
        ),
        "effective_scope": effective.scope.model_dump(mode="json"),
        "field_sources": dict(raw_sources),
        "step_plan": step_plan.model_dump(mode="json"),
        "component_identities": {
            name: identity.model_dump(mode="json")
            for name, identity in components.items()
        },
        "capability": capability.model_dump(mode="json"),
    }


def _deserialize_execution_evidence(
    execution_evidence_json: str | None,
) -> dict[str, Any] | None:
    if not execution_evidence_json:
        return None
    try:
        value = json.loads(execution_evidence_json)
        evidence = ExecutionEvidence.model_validate(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return evidence.model_dump(mode="json", exclude_none=True)


def _deserialize_params(params_json: str | None) -> dict | None:
    if not params_json:
        return None
    try:
        return json.loads(params_json)
    except json.JSONDecodeError:
        return {"raw": params_json}


def _deserialize_error_details(error_details_json: str | None) -> dict | None:
    if not error_details_json:
        return None
    try:
        value = json.loads(error_details_json)
    except json.JSONDecodeError:
        return {"raw": error_details_json}
    return value if isinstance(value, dict) else {"raw": value}


def _serialize_job(row: LoraTrainingJob, *, log_tail_lines: int | None = None, log_truncated: bool | None = None) -> dict:
    recipe_envelope = _deserialize_recipe_envelope(
        getattr(row, "recipe_json", None)
    ) or {
        "requested_recipe": None,
        "effective_recipe": None,
        "requested_scope": None,
        "effective_scope": None,
        "field_sources": None,
        "step_plan": None,
        "component_identities": None,
        "capability": None,
    }
    recipe_schema_version = getattr(row, "recipe_schema_version", None)
    if recipe_schema_version != "lora-training-recipe/v1":
        recipe_schema_version = None
    recipe_hash = getattr(row, "recipe_hash", None)
    if not isinstance(recipe_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}",
        recipe_hash,
    ):
        recipe_hash = None
    return {
        "ok": True,
        "job_id": row.job_id,
        **{key:getattr(row,key,None) for key in ("output_name","resolved_output_name","output_serial","run_locator","output_config_hash","validation_status","output_sha256","registration_status")},
        "folder": row.folder,
        "status": row.status,
        "stage": row.stage,
        "progress": row.progress or 0.0,
        "current_epoch": row.current_epoch,
        "total_epochs": row.total_epochs,
        "dataset_hash": row.dataset_hash,
        "profile_hash": row.profile_hash,
        "normalized_trigger_token": row.normalized_trigger_token,
        "log_path": row.log_path,
        "log_tail_lines": log_tail_lines,
        "log_truncated": log_truncated,
        "output_path": row.output_path,
        "registered_lora_name": row.registered_lora_name,
        "registration_error": row.registration_error,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "error_details": _deserialize_error_details(row.error_details_json),
        "recipe_schema_version": recipe_schema_version,
        "recipe_hash": recipe_hash,
        **recipe_envelope,
        "execution_evidence": _deserialize_execution_evidence(
            getattr(row, "execution_evidence_json", None)
        ),
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


def _occupied_output_names() -> set[str]:
    from app.core.resources import lora_catalog
    settings=get_settings()
    catalog=lora_catalog(settings)
    occupied=[*catalog["loras"],*(item["locator"] for item in catalog["lora_conflicts"])]
    names={delivery.name_key(Path(name).stem) for name in occupied}
    output=Path(settings.lora_train_dir).resolve()/"output"
    if output.is_dir():
        names.update(delivery.name_key(p.stem) for p in output.iterdir() if p.suffix.lower()==".safetensors")
    return names


def _create_persistent_job(job: _TrainJob) -> None:
    def op(db: Any) -> None:
        compiled = job.recipe
        if job.output_name is not None:
            # Allocation and job insert share one durable write transaction.
            assigned = delivery.reserve_name(db, job_id=job.job_id, requested=job.output_name,
                                             occupied=_occupied_output_names(), created_utc=job.submitted_at)
            active = db.query(LoraTrainingJob).filter(LoraTrainingJob.folder==job.folder, LoraTrainingJob.status.in_(["queued","running"])).first()
            if active and active.job_id != job.job_id:
                raise TrainerServiceError("duplicate_folder", "dataset already has an active durable job")
            for key in ('resolved_output_name','output_serial','run_locator'): setattr(job,key,assigned[key])
            settings=get_settings()
            publish_raw=getattr(settings,'comfyui_lora_dir','')
            delivery.check_run_paths(Path(settings.lora_train_dir).resolve(), job.run_locator, job.resolved_output_name, Path(publish_raw).expanduser().absolute() if publish_raw else None)
        db.add(
            LoraTrainingJob(
                job_id=job.job_id,
                folder=job.folder,
                output_name=job.output_name, resolved_output_name=job.resolved_output_name,
                output_serial=job.output_serial, run_locator=job.run_locator,
                output_config_hash=job.output_config_hash,
                status="queued",
                stage="queued",
                progress=0.0,
                total_epochs=job.epochs,
                log_path=job.log_path,
                dataset_hash=job.dataset_hash,
                profile_hash=job.profile_hash,
                normalized_trigger_token=job.normalized_trigger_token,
                params_json=_params_json(job),
                recipe_schema_version=(
                    compiled.effective.schema_version
                    if compiled is not None
                    else None
                ),
                recipe_hash=compiled.recipe_hash if compiled is not None else None,
                recipe_json=(
                    _recipe_envelope_json(compiled)
                    if compiled is not None
                    else None
                ),
                execution_evidence_json=(
                    _execution_evidence_json(compiled)
                    if compiled is not None
                    else None
                ),
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
            if key == "error_details":
                row.error_details_json = (
                    json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if value is not None
                    else None
                )
            else:
                setattr(row, key, value)
        row.updated_at = _utcnow()
        if row.run_locator and fields.get('status') in TERMINAL_STATUSES:
            try:
                lora_parameters.update_phase(delivery.run_path(Path(get_settings().lora_train_dir).resolve(),row.run_locator),job_id=row.job_id,status=fields.get('stage',fields['status']))
            except (OSError,ValueError):
                if fields['status']=='completed': raise
                logger.error('Terminal parameter phase update failed for %s',job_id)

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
    path = delivery.confined(Path(log_path),Path(log_path).parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(lora_public.public_log_line(text) + '\n')


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
            logger.warning("LoRA job_cancel_failed; check job state before retrying")
    if count > 0:
        logger.info("已清除訓練佇列，共 %d 個任務", count)
    return count


def _resolve_image_dir(folder: str) -> Path:
    """folder 相對 lora_train_dir，回傳絕對路徑的 image_dir"""
    try:
        return lora_dataset.resolve_dataset_dir(folder)
    except DatasetServiceError as exc:
        raise TrainerServiceError(exc.code, exc.message, exc.details) from exc


def _verify_profile_hash(inspected: Any, expected_profile_hash: str | None) -> str | None:
    current_profile_hash = getattr(inspected, "profile_hash", None)
    if expected_profile_hash is not None and current_profile_hash != expected_profile_hash:
        raise TrainerServiceError(
            "profile_hash_mismatch",
            "dataset profile changed after approval",
            {
                "expected_profile_hash": expected_profile_hash,
                "current_profile_hash": current_profile_hash,
            },
        )
    return current_profile_hash


def _verify_profile_family(
    inspected: Any,
    *,
    expected_profile_hash: str | None,
    model_family: str,
) -> None:
    # Historical/internal jobs without a profile approval remain readable. Every
    # public Start supplies a non-null expected_profile_hash and takes this path.
    if expected_profile_hash is None:
        return

    profile = inspected.profile
    if not getattr(profile, "valid", True):
        errors = list(getattr(profile, "errors", []) or [])
        first = errors[0] if errors else None
        raise TrainerServiceError(
            getattr(first, "code", "dataset_profile_invalid"),
            "dataset profile validation failed",
            {
                "errors": [
                    issue.model_dump() if hasattr(issue, "model_dump") else str(issue)
                    for issue in errors
                ]
            },
        )

    declared_family = str(getattr(profile, "model_family", "unknown") or "unknown").strip().lower()
    if declared_family != _normalize_model_family(model_family):
        raise TrainerServiceError(
            "model_family_mismatch",
            "dataset profile model family does not match the training job",
            {
                "requested_model_family": _normalize_model_family(model_family),
                "dataset_profile_model_family": declared_family,
            },
        )


def _require_validated_dataset(validation: Any) -> None:
    if validation.ok:
        return
    errors = list(validation.errors or [])
    first = errors[0] if errors else None
    details = {
        "errors": [
            issue.model_dump() if hasattr(issue, "model_dump") else str(issue)
            for issue in errors
        ],
        "dataset_hash": validation.dataset_hash,
    }
    first_details = getattr(first, "details", None)
    if isinstance(first_details, dict):
        details.update(first_details)
    raise TrainerServiceError(
        getattr(first, "code", "dataset_validation_failed"),
        getattr(first, "message", "dataset validation failed"),
        details,
    )


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
        logger.warning("LoRA checkpoint existence unverifiable; no search dirs configured")
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


def _train_script_name(model_family: str) -> str:
    return _TRAIN_SCRIPT_BY_MODEL_FAMILY[_normalize_model_family(model_family)]


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


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_dataset_toml(
    effective: EffectiveTrainingRecipeV1,
    *,
    image_dir: Path,
) -> str:
    """Build deterministic dataset TOML exclusively from an effective recipe."""
    dataset = effective.dataset
    server = effective.server
    return (
        "[general]\n"
        f"shuffle_caption = {_toml_bool(server.shuffle_caption)}\n"
        f"caption_extension = {_toml_string(server.caption_extension)}\n"
        f"keep_tokens = {dataset.keep_tokens}\n"
        "\n"
        "[[datasets]]\n"
        f"resolution = {dataset.resolution}\n"
        f"batch_size = {dataset.batch_size}\n"
        f"enable_bucket = {_toml_bool(dataset.enable_bucket)}\n"
        f"bucket_no_upscale = {_toml_bool(dataset.bucket_no_upscale)}\n"
        f"min_bucket_reso = {dataset.min_bucket_reso}\n"
        f"max_bucket_reso = {dataset.max_bucket_reso}\n"
        f"bucket_reso_steps = {dataset.bucket_reso_steps}\n"
        "\n"
        "  [[datasets.subsets]]\n"
        f"  image_dir = {_toml_string(image_dir.as_posix())}\n"
        f"  class_tokens = {_toml_string(dataset.class_tokens)}\n"
        f"  num_repeats = {dataset.num_repeats}\n"
    )


def build_training_argv(
    effective: EffectiveTrainingRecipeV1,
    *,
    launcher_argv: tuple[str, ...],
    sd_scripts_path: Path,
    dataset_config_path: Path,
    output_dir: Path,
    output_name: str,
) -> list[str]:
    """Build exact sd-scripts argv without consulting mutable server settings."""
    model = effective.model
    optimization = effective.optimization
    execution = effective.execution
    caching = effective.caching
    argv = [
        *launcher_argv,
        "--num_cpu_threads_per_process",
        str(effective.server.launcher_num_cpu_threads_per_process),
        str(sd_scripts_path / _TRAIN_SCRIPT_BY_MODEL_FAMILY[model.family]),
        "--pretrained_model_name_or_path",
        model.checkpoint,
        "--dataset_config",
        str(dataset_config_path),
        "--output_dir",
        str(output_dir),
        "--output_name",
        output_name,
        "--network_module",
        model.network_module,
        "--network_dim",
        str(model.network_dim),
        "--network_alpha",
        str(model.network_alpha),
        "--max_train_epochs",
        str(optimization.epochs),
        "--learning_rate",
        optimization.learning_rate,
        # sd-scripts retains the inherited native name for UNet and DiT.
        "--unet_lr",
        optimization.denoiser_learning_rate,
    ]
    if model.family == "anima":
        if model.anima is None:
            raise ValueError("effective Anima recipe is missing native components")
        argv.extend(["--qwen3", model.anima.qwen3])
        if model.anima.vae:
            argv.extend(["--vae", model.anima.vae])
        if model.anima.t5_tokenizer_path:
            argv.extend(
                ["--t5_tokenizer_path", model.anima.t5_tokenizer_path]
            )
    if effective.scope.native_scope_flag:
        argv.append(effective.scope.native_scope_flag)
    if effective.scope.train_text_encoder:
        rates = optimization.text_encoder_learning_rates
        if model.family == "sdxl":
            argv.extend(
                [
                    "--text_encoder_lr1",
                    rates[0],
                    "--text_encoder_lr2",
                    rates[1],
                ]
            )
        else:
            argv.extend(["--text_encoder_lr", rates[0]])
    if execution.save_every_n_epochs > 0:
        argv.extend(
            ["--save_every_n_epochs", str(execution.save_every_n_epochs)]
        )
    argv.extend(
        [
            "--gradient_accumulation_steps",
            str(optimization.gradient_accumulation_steps),
            "--max_data_loader_n_workers",
            str(execution.max_data_loader_n_workers),
        ]
    )
    if execution.persistent_data_loader_workers:
        argv.append("--persistent_data_loader_workers")
    argv.extend(["--optimizer_type", optimization.optimizer_type])
    if optimization.optimizer_args:
        argv.append("--optimizer_args")
        argv.extend(optimization.optimizer_args)
    argv.extend(["--lr_scheduler", optimization.lr_scheduler])
    if optimization.lr_scheduler_args:
        argv.append("--lr_scheduler_args")
        argv.extend(optimization.lr_scheduler_args)
    argv.extend(
        [
            "--lr_warmup_steps",
            str(optimization.warmup.resolved_steps),
            "--seed",
            str(optimization.seed.value),
            "--save_model_as",
            effective.server.save_model_as,
            "--mixed_precision",
            optimization.mixed_precision,
        ]
    )
    if caching.cache_latents:
        argv.append("--cache_latents")
    if caching.latent_cache_to_disk:
        argv.append("--cache_latents_to_disk")
    if caching.cache_text_encoder_outputs:
        argv.append("--cache_text_encoder_outputs")
    if caching.text_encoder_cache_to_disk:
        argv.append("--cache_text_encoder_outputs_to_disk")
    if effective.server.gradient_checkpointing:
        argv.append("--gradient_checkpointing")
    return argv


def select_accelerate_launcher(
    python_executable: str | None,
) -> tuple[tuple[str, ...], EvidenceValue]:
    """Select a deterministic launcher and report how strongly it was resolved."""
    configured = str(python_executable or "").strip()
    if configured:
        python_path = Path(configured).expanduser().resolve()
        accelerate_name = "accelerate.exe" if os.name == "nt" else "accelerate"
        accelerate_path = python_path.parent / accelerate_name
        if accelerate_path.is_file():
            resolved = str(accelerate_path.resolve())
            return (
                (resolved, "launch"),
                EvidenceValue(status="verified", value=resolved),
            )
        return (
            (str(python_path), "-m", "accelerate", "launch"),
            EvidenceValue(
                status="unverified",
                value=f"{python_path.name} -m accelerate",
                reason="accelerate module availability is not verified",
            ),
        )
    return (
        ("accelerate", "launch"),
        EvidenceValue(
            status="unverified",
            value="accelerate",
            reason="PATH launcher resolution is deferred until execution",
        ),
    )


def collect_component_identity(
    *,
    kind: str,
    requested_locator: str | None,
    resolved_path: Path | None,
    allow_unverified: bool,
    digest_resolver: Callable[[Path], str],
) -> ComponentIdentity:
    """Collect bounded file identity without leaking filesystem exceptions."""
    if resolved_path is None:
        return ComponentIdentity(
            kind=kind,
            requested_locator=requested_locator,
            resolved_locator=None,
            verification_status="unverified" if allow_unverified else "unavailable",
            reason="component could not be resolved",
            bypass_used=allow_unverified,
        )
    try:
        resolved = resolved_path.resolve()
        stat = resolved.stat()
    except OSError:
        return ComponentIdentity(
            kind=kind,
            requested_locator=requested_locator,
            resolved_locator=str(resolved_path),
            verification_status="unverified" if allow_unverified else "unavailable",
            reason="component identity is unavailable",
            bypass_used=allow_unverified,
        )
    try:
        digest = str(digest_resolver(resolved)).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError
    except (OSError, ValueError, TypeError):
        return ComponentIdentity(
            kind=kind,
            requested_locator=requested_locator,
            resolved_locator=str(resolved),
            size_bytes=stat.st_size,
            modified_time_ns=stat.st_mtime_ns,
            verification_status="unverified" if allow_unverified else "unavailable",
            reason="component digest is unavailable",
            bypass_used=allow_unverified,
        )
    return ComponentIdentity(
        kind=kind,
        requested_locator=requested_locator,
        resolved_locator=str(resolved),
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
        sha256=digest,
        verification_status="verified",
        bypass_used=False,
    )


_CAPABILITY_PROBE = (
    "import json,platform\n"
    "result={'platform':'unknown','python_version':platform.python_version(),"
    "'torch_version':None,'accelerate_version':None,"
    "'supported_mixed_precision':['no']}\n"
    "try:\n"
    " import torch\n"
    " result['torch_version']=str(torch.__version__)\n"
    " if torch.cuda.is_available():\n"
    "  result['platform']='cuda'; result['supported_mixed_precision'].append('fp16')\n"
    "  if getattr(torch.cuda,'is_bf16_supported',lambda:False)():"
    " result['supported_mixed_precision'].append('bf16')\n"
    " elif getattr(getattr(torch.backends,'mps',None),'is_available',lambda:False)():"
    " result['platform']='mps'\n"
    " else: result['platform']='cpu'\n"
    "except Exception: pass\n"
    "try:\n"
    " import accelerate\n"
    " result['accelerate_version']=str(accelerate.__version__)\n"
    "except Exception: pass\n"
    "print(json.dumps(result,separators=(',',':')))\n"
)


def _safe_version(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.+_-]{1,64}", value):
        return value
    return None


def inspect_trainer_capability(
    python_executable: str,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> TrainerCapabilitySnapshot:
    """Inspect the configured trainer Python with bounded, redacted output."""
    try:
        completed = runner(
            [python_executable, "-c", _CAPABILITY_PROBE],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0 or len(completed.stdout or "") > 16_384:
            raise ValueError
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            raise ValueError
        platform_name = payload.get("platform")
        if platform_name not in {"cuda", "mps", "cpu"}:
            raise ValueError
        supplied_modes = payload.get("supported_mixed_precision")
        if not isinstance(supplied_modes, list):
            supplied_modes = []
        modes = tuple(
            mode
            for mode in ("no", "fp16", "bf16")
            if mode in supplied_modes
        )
        if "no" not in modes:
            modes = ("no", *modes)
        return TrainerCapabilitySnapshot(
            platform=platform_name,
            status="verified",
            reason=None,
            torch_version=_safe_version(payload.get("torch_version")),
            accelerate_version=_safe_version(payload.get("accelerate_version")),
            python_version=_safe_version(payload.get("python_version")),
            supported_mixed_precision=modes,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return TrainerCapabilitySnapshot(
            platform="unknown",
            status="unavailable",
            reason="trainer runtime inspection failed",
            supported_mixed_precision=("no",),
        )
    except Exception:
        return TrainerCapabilitySnapshot(
            platform="unknown",
            status="unavailable",
            reason="trainer runtime inspection failed",
            supported_mixed_precision=("no",),
        )


def collect_sd_scripts_revision(
    sd_scripts_path: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> EvidenceValue:
    """Collect a bounded git revision or report explicit unavailability."""
    try:
        completed = runner(
            ["git", "-C", str(sd_scripts_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        revision = str(completed.stdout or "").strip().lower()
        if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise ValueError
        return EvidenceValue(status="verified", value=revision)
    except Exception:
        return EvidenceValue(
            status="unavailable",
            reason="sd-scripts revision is unavailable",
        )


def build_execution_evidence(
    *,
    argv: tuple[str, ...],
    dataset_config_content: str,
    launcher: EvidenceValue,
    capability: TrainerCapabilitySnapshot,
    sd_scripts_revision: EvidenceValue,
) -> ExecutionEvidence:
    """Build strict evidence from the exact artifacts that will be launched."""
    verified = (
        launcher.status == "verified"
        and capability.status == "verified"
        and sd_scripts_revision.status == "verified"
    )
    return ExecutionEvidence(
        status="verified" if verified else "unverified",
        reason=(
            None
            if verified
            else "one or more runtime evidence items are unavailable or unverified"
        ),
        argv=argv,
        dataset_config_content=dataset_config_content,
        dataset_config_sha256=hashlib.sha256(
            dataset_config_content.encode("utf-8")
        ).hexdigest(),
        launcher=launcher,
        capability=capability,
        sd_scripts_revision=sd_scripts_revision,
    )


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
    argv: tuple[str, ...],
    sd_scripts_path: Path,
    run_root: Path | None = None,
) -> subprocess.Popen[str]:
    """Launch exactly the persisted argv without resolving training defaults."""
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(sd_scripts_path)
        + os.pathsep
        + env.get("PYTHONPATH", "")
    )
    env["PYTHONUNBUFFERED"] = "1"
    if run_root is not None:
        for key in ('HF_HOME','XDG_CACHE_HOME','TORCH_HOME','TRITON_CACHE_DIR','MPLCONFIGDIR'):
            directory=run_root/'cache'/key.lower();directory.mkdir(exist_ok=True)
            env[key]=str(directory)
        temporary=run_root/'state'/'tmp';temporary.mkdir(exist_ok=True)
        for key in ('TMPDIR','TMP','TEMP'): env[key]=str(temporary)
        env['WANDB_DISABLED']='true'
        env['HF_HUB_OFFLINE']='1'
        env['TRANSFORMERS_OFFLINE']='1'
    process = subprocess.Popen(
        argv,
        cwd=str(sd_scripts_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    with _lock:
        _children.append(process)
    return process


def _get_output_lora_path(output_dir: Path, output_name: str) -> Path:
    """Kohya 輸出檔名為 {output_name}.safetensors"""
    return output_dir / f"{output_name}.safetensors"


def _register_output_lora(source_path: Path, job_id: str) -> tuple[str, str]:
    """Publish only the exact final declared and validated for this durable job."""
    job=get_job_status(job_id)
    settings=get_settings()
    raw=getattr(settings,'comfyui_lora_dir','')
    if not raw: raise TrainerServiceError('lora_registration_not_configured','LoRA publication root is not configured')
    try:
        if not job.get('run_locator') or not job.get('resolved_output_name'):
            raise delivery.DeliveryError('legacy_output_unknown','legacy job has no owned run; automatic registration is unavailable')
        root=delivery.run_path(Path(settings.lora_train_dir).resolve(),job['run_locator'])
        expected=root/'artifacts'/(job['resolved_output_name']+'.safetensors')
        if source_path.absolute() != expected.absolute():
            raise delivery.DeliveryError('output_ownership_mismatch','source is not this job’s exact final path')
        manifest=json.loads(delivery.confined(root/'manifest.json',root).read_text())
        if manifest.get('job_id') != job_id or manifest.get('run_locator') != job['run_locator']:
            raise delivery.DeliveryError('output_ownership_mismatch','run manifest does not belong to this job')
        content_hash=delivery.validate_final(expected,root/'artifacts')
        if job.get('output_sha256') and content_hash != job['output_sha256']:
            raise delivery.DeliveryError('output_hash_changed','previously validated source changed')
        identity={key:job.get(key) for key in ('job_id','folder','dataset_hash','profile_hash','recipe_hash','output_config_hash','output_name','resolved_output_name','output_serial','run_locator')}
        identity.update(sha256=content_hash,source='artifacts/'+expected.name)
        manifest.update(final=identity,validation_status='verified')
        delivery.write_json(root/'manifest.json',manifest)
        _update_persistent_job(job_id,output_sha256=content_hash,validation_status='verified',registration_status='pending')
        result=delivery.publish_final(expected,artifacts=root/'artifacts',publish_root=Path(raw).expanduser().absolute(),locator=job['run_locator'],identity=identity)
        manifest.update(registered_lora_name=result[0],registration_status='registered')
        delivery.write_json(root/'manifest.json',manifest)
        _update_persistent_job(job_id,registered_lora_name=result[0],registration_status='registered',registration_error=None)
        return result
    except (OSError,ValueError) as exc:
        raise TrainerServiceError(getattr(exc,'code','lora_registration_failed'),getattr(exc,'message','LoRA publication failed')) from exc


def _revalidate_launch_components(job: _TrainJob, settings: Any) -> TrainerCapabilitySnapshot:
    """Keep frozen effective options; reject changed inputs instead of re-defaulting."""
    for identity in job.recipe.component_identities.values():
        if identity.sha256 and identity.resolved_locator:
            try:
                if delivery.digest(Path(identity.resolved_locator)) != identity.sha256:
                    raise ValueError('component changed')
            except (OSError,ValueError) as exc:
                raise TrainerServiceError('training_component_changed','a verified model component changed after job creation; no trainer started') from exc
    observed=inspect_trainer_capability(getattr(settings,'sd_scripts_python',''))
    previous=job.recipe.capability
    if previous.status=='verified' and observed != previous:
        raise TrainerServiceError('trainer_capability_changed','trainer capability/version changed after job creation; no trainer started')
    if job.recipe.effective.optimization.mixed_precision != 'no' and job.recipe.effective.optimization.mixed_precision not in observed.supported_mixed_precision:
        raise TrainerServiceError('trainer_capability_changed','selected precision is no longer verified for this trainer')
    return observed


def _record_failure(job, log_path, *, code=None, phase='unknown', details=None, stage='failed', fallback='unexpected_error', path=None):
    """One safe failure representation for persistence, aggregate status and both logs."""
    global _last_result, _running
    safe = lora_public.failure(code, phase=phase, details=details, fallback=fallback)
    get_and_clear_pending_generate(job.folder)
    # A log write failure must not turn a failed/not-started job into an unhandled error.
    try:
        _append_log(log_path, lora_public.event_line('failed', code=safe['code'], phase=phase))
    except (OSError, ValueError):
        logger.error('LoRA log_write_failed; failure still recorded on the job')
    _update_persistent_job(job.job_id, status='failed', stage=stage, error_code=safe['code'], error_message=safe['message'], error_details=safe['details'], completed_at=_utcnow())
    with _lock:
        if _running and _running.job.job_id == job.job_id:
            _running = None
        _last_result = {
            'folder': job.folder, 'output_name': job.output_name, 'resolved_output_name': job.resolved_output_name,
            'output_serial': job.output_serial, 'run_locator': job.run_locator, 'output_config_hash': job.output_config_hash,
            'success': False, 'path': path, 'error': safe['message'], 'error_code': safe['code'], 'error_details': safe['details'], 'stage': phase,
        }
    logger.error('LoRA %s phase=%s classification=%s', safe['code'], safe['details']['phase'], safe['details']['classification'])
    return safe


def _worker_loop() -> None:
    """背景 worker：依序執行佇列中的訓練"""
    global _running, _last_result
    try:
        settings = get_settings()
        sd_scripts = Path(settings.sd_scripts_path).resolve()
        lora_base = Path(settings.lora_train_dir).resolve()
        output_base = lora_base / "output"
    except Exception:
        logger.error("LoRA worker_initialization_failed; check trainer configuration")
        return

    _wait_count = 0
    while not _stop_event.is_set():
        with _lock:
            if _running or not _queue or _stop_event.is_set():
                job = None
            else:
                job = _queue.pop(0)

        if job is None:
            _wait_count += 1
            _stop_event.wait(1.0)
            continue
        _wait_count = 0
        log_path = None
        dataset_lock_context: Any | None = None
        dataset_lock_entered = False
        proc = None
        failure_phase = 'preflight'

        try:
            _update_persistent_job(job.job_id, stage="preflight")
            if not job.run_locator or not job.resolved_output_name:
                raise TrainerServiceError('legacy_output_unknown','job lacks an allocated run; cannot launch')
            run_root=delivery.run_path(lora_base,job.run_locator)
            manifest=json.loads(delivery.confined(run_root/'manifest.json',run_root).read_text())
            if manifest.get('job_id') != job.job_id:
                raise TrainerServiceError('output_ownership_mismatch','run belongs to another job')
            output_dir = delivery.confined(run_root/'artifacts',run_root)
            log_path = str(delivery.confined(run_root/'logs'/'training.log',run_root))
            _append_log(log_path, lora_public.event_line('dequeued'))

            dataset_lock_context = lora_dataset.dataset_lock(
                job.folder,
                owner=f"training:{job.job_id}",
            )
            dataset_lock_context.__enter__()
            dataset_lock_entered = True
            if dataset_lock_entered:
                # Resolve and revalidate after taking the same lock held through
                # the subprocess, closing the approval-to-launch mutation race.
                image_dir = _resolve_image_dir(job.folder)
                if not image_dir.exists() or not image_dir.is_dir():
                    raise TrainerServiceError("dataset_not_found", f"image_dir not found: {image_dir}")

                inspected = lora_dataset.inspect_dataset(job.folder)
                _verify_profile_hash(inspected, job.profile_hash)
                validation = lora_dataset.validate_dataset(
                    job.folder,
                    trigger_token=job.normalized_trigger_token or job.class_tokens,
                    expected_dataset_hash=job.dataset_hash,
                    ignore_lock=True,
                )
                _require_validated_dataset(validation)
                _verify_profile_family(
                    inspected,
                    expected_profile_hash=job.profile_hash,
                    model_family=job.model_family,
                )

                if job.recipe is None:
                    raise TrainerServiceError(
                        "recipe_missing",
                        "queued training job has no immutable v1 recipe",
                        {"job_id": job.job_id},
                    )
                compiled = job.recipe
                launch_capability=_revalidate_launch_components(job,settings)
                effective = compiled.effective
                lora_parameters.validate_reportable(effective)
                output_name = job.resolved_output_name
                output_lora = _get_output_lora_path(output_dir, output_name)
                dataset_config_content = build_dataset_toml(
                    effective,
                    image_dir=image_dir,
                )
                dataset_config_path = delivery.confined(run_root/"configs"/"dataset.toml",run_root)
                launcher_argv, launcher_evidence = select_accelerate_launcher(
                    getattr(settings, "sd_scripts_python", "")
                )
                launch_argv = tuple(
                    build_training_argv(
                        effective,
                        launcher_argv=launcher_argv,
                        sd_scripts_path=sd_scripts,
                        dataset_config_path=dataset_config_path,
                        output_dir=output_dir,
                        output_name=output_name,
                    )
                )
                execution_evidence = build_execution_evidence(
                    argv=launch_argv,
                    dataset_config_content=dataset_config_content,
                    launcher=launcher_evidence,
                    capability=launch_capability,
                    sd_scripts_revision=collect_sd_scripts_revision(sd_scripts),
                )
                job.recipe = compiled.model_copy(
                    update={"execution_evidence": execution_evidence}
                )
                _update_persistent_job(
                    job.job_id,
                    execution_evidence_json=_execution_evidence_json(job.recipe),
                )
                try:
                    delivery.atomic_write(dataset_config_path,dataset_config_content.encode('utf-8'))
                    if dataset_config_path.read_text(encoding='utf-8') != dataset_config_content:
                        raise ValueError('dataset configuration changed')
                    lora_parameters.prepare_parameters(run_root,job=job,argv=launch_argv,dataset_toml=dataset_config_content,evidence=execution_evidence)
                except (OSError,ValueError) as exc:
                    raise TrainerServiceError('training_parameters_write_failed','could not prepare verified config and parameter files; no trainer started') from exc
                if _is_cancel_requested(job.job_id):
                    _update_persistent_job(job.job_id,status='cancelled',stage='cancelled',completed_at=_utcnow())
                    lora_parameters.update_phase(run_root,job_id=job.job_id,status='cancelled')
                    continue
                _update_persistent_job(
                    job.job_id,
                    status="running",
                    stage="prepared",
                    progress=0.0,
                    total_epochs=effective.optimization.epochs,
                    log_path=log_path,
                )
                failure_phase = 'prepared'
                proc = _run_training_subprocess(
                    argv=launch_argv,
                    sd_scripts_path=sd_scripts,
                    run_root=run_root,
                )
                started=_utcnow()
                _update_persistent_job(job.job_id,stage='training',started_at=started)
                failure_phase = 'training'
                lora_parameters.update_phase(run_root,job_id=job.job_id,status='started',started_utc=_iso(started))

                running_job = _RunningJob(
                    job=job,
                    proc=proc,
                    progress=0.0,
                    epoch=None,
                    total_epochs=effective.optimization.epochs,
                )
                with _lock:
                    _running = running_job

                logger.info("Job %s 開始訓練: folder=%s（載入模型需數分鐘，請稍候）", job.job_id, job.folder)
                _append_log(log_path, lora_public.event_line('started'))

                cancelled = False
                if proc.stdout:
                    for line in proc.stdout:
                        if _is_cancel_requested(job.job_id):
                            cancelled = True
                            proc.terminate()
                            _append_log(log_path, lora_public.event_line('cancellation_requested'))
                            break
                        parsed = _parse_progress(line)
                        if parsed:
                            prog, ep, tot = parsed
                            _append_log(log_path, lora_public.event_line('progress', progress=prog, epoch=ep, total_epochs=tot))
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
                    _last_result = {"folder": job.folder, "resolved_output_name":job.resolved_output_name, "output_name":job.output_name, "output_serial":job.output_serial, "run_locator":job.run_locator, "output_config_hash":job.output_config_hash, "success": False, "path": None, "error": "cancelled", "error_code":"cancelled", "stage":"cancelled"}
                logger.info("Job %s 已取消", job.job_id)
                continue

            if proc.returncode != 0:
                get_and_clear_pending_generate(job.folder)
                _record_failure(job, log_path, code='kohya_failed', phase=failure_phase)
                continue

            try:
                output_hash=delivery.validate_final(output_lora,output_dir)
            except delivery.DeliveryError as exc:
                _update_persistent_job(job.job_id,validation_status='failed',registration_status='not_registered')
                raise TrainerServiceError(exc.code,exc.message) from exc
            found_path=output_lora
            _update_persistent_job(job.job_id,validation_status='verified',output_sha256=output_hash)

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
            failure_phase = 'registering'
            try:
                registered_name, registered_path = _register_output_lora(found_path, job.job_id)
                _append_log(log_path, lora_public.event_line('registered'))
            except Exception as exc:
                safe = _record_failure(job, log_path, code=getattr(exc, 'code', None), phase=failure_phase, details=getattr(exc, 'details', None), stage='registration_failed', fallback='lora_registration_failed', path=output_lora_str)
                _update_persistent_job(job.job_id, registration_status='failed', registration_error=safe['message'])
                lora_parameters.update_phase(run_root,job_id=job.job_id,status='registration_failed',training_status='completed',validation_status='verified',registration_status='failed')
                continue

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
                _last_result = {"folder": job.folder, "resolved_output_name":job.resolved_output_name, "output_name":job.output_name, "output_serial":job.output_serial, "run_locator":job.run_locator, "output_config_hash":job.output_config_hash, "success": True, "path": output_lora_str, "error": None}
            lora_parameters.update_phase(run_root,job_id=job.job_id,status="completed",training_status="completed",validation_status="verified",registration_status="registered")
            for cb in _on_complete_callbacks:
                try:
                    cb(output_lora_str, job.folder)
                except Exception:
                    _append_log(log_path, lora_public.event_line('callback_failed', code='completion_callback_failed', phase='completed'))
                    logger.warning("LoRA completion_callback_failed; registered artifact remains completed")
            _append_log(log_path, lora_public.event_line('completed'))
            logger.info("Job %s completed", job.job_id)
        except (DatasetServiceError, TrainerServiceError, delivery.DeliveryError) as exc:
            _record_failure(job, log_path, code=exc.code, phase=failure_phase, details=exc.details)
        except Exception:
            _record_failure(job, log_path, phase=failure_phase)


        finally:
            # Do not leave a trainer running if post-spawn persistence/reporting fails.
            try:
                if proc is not None and hasattr(proc,'poll') and proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(timeout=10)
            except Exception:
                logger.error('LoRA trainer_cleanup_failed; reconcile the trainer process before retrying')
            try:
                if job.run_locator:
                    current=_read_persistent_job(job.job_id)
                    if current and current['status'] in TERMINAL_STATUSES:
                        lora_parameters.update_phase(delivery.run_path(lora_base,job.run_locator),job_id=job.job_id,status=current['stage'])
            except (OSError,ValueError):
                logger.error('Unable to update terminal parameter phase for %s',job.job_id)
            if dataset_lock_entered and dataset_lock_context is not None:
                try:
                    dataset_lock_context.__exit__(None, None, None)
                except Exception:
                    logger.error('LoRA dataset_unlock_failed; reconcile the dataset lock before retrying')


def _ensure_worker() -> None:
    """確保 worker 線程已啟動"""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    logger.info("LoRA 訓練 worker 已啟動")


def request_stop() -> None:
    """Fence new background work before any worker joins."""
    _stop_event.set()


def stop_worker(timeout: float = 5.0) -> bool:
    """No new queue work; never terminate a running trainer during drain."""
    global _worker_thread
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=max(0, timeout))
        if _worker_thread.is_alive():
            return False
        _worker_thread = None
    with _lock:
        _children[:] = [p for p in _children if p.poll() is None]
        if _running is not None and _running.proc is not None and _running.proc.poll() is None:
            return False
        return not _children


def ensure_worker() -> None:
    """公開 API：確保 worker 在 app 啟動時即就緒"""
    _ensure_worker()


def _trainer_recipe_error(exc: RecipeError) -> TrainerServiceError:
    return TrainerServiceError(
        exc.code,
        exc.message,
        exc.details,
        hint=exc.hint,
    )


def enqueue(
    folder: str,
    *,
    output_name: str,
    expected_output_config_hash: str | None = None,
    expected_dataset_hash: str,
    expected_profile_hash: str,
    recipe: object,
) -> str:
    """Validate and compile one immutable recipe before creating a queued job."""
    try: output_name=delivery.validate_output_name(output_name)
    except delivery.DeliveryError as exc: raise TrainerServiceError(exc.code,exc.message) from exc
    settings = get_settings()
    image_dir = _resolve_image_dir(folder)
    train_root = Path(settings.lora_train_dir).resolve()
    canonical_folder = image_dir.relative_to(train_root).as_posix()
    if not image_dir.is_dir():
        raise TrainerServiceError(
            "dataset_not_found",
            "training dataset folder was not found",
            {"folder": canonical_folder},
        )

    try:
        normalized = normalize_recipe_input(
            recipe,
            policy_source="server_policy",
            accept_materialized_policy_seed=True,
        )
        requested_optimization = normalized.requested.optimization
        requested_seed = (
            requested_optimization.seed
            if requested_optimization is not None
            else None
        )
        if (
            "optimization.seed" in normalized.provided_fields
            and requested_seed is not None
            and requested_seed.source != "caller"
            and normalized.requested.expected_recipe_hash is None
        ):
            raise RecipeError(
                "recipe_validation_failed",
                "training recipe is invalid",
                "rerun decision preflight or mark a direct Start seed as caller-owned",
                {
                    "issues": [
                        {
                            "location": "optimization.seed.source",
                            "type": "untrusted_policy_source",
                        }
                    ]
                },
            )

        try:
            inspected = lora_dataset.inspect_dataset(canonical_folder)
        except DatasetServiceError as exc:
            raise TrainerServiceError(
                exc.code,
                exc.message,
                exc.details,
            ) from exc
        profile_hash = _verify_profile_hash(
            inspected,
            expected_profile_hash,
        )
        requested_dataset = normalized.requested.dataset
        approved_token = (
            requested_dataset.trigger_token
            if requested_dataset is not None
            and requested_dataset.trigger_token
            else inspected.profile.trigger_token
        )
        if not approved_token and inspected.trigger_token_candidates:
            approved_token = inspected.trigger_token_candidates[0]
        if not approved_token:
            raise RecipeError(
                "recipe_context_unavailable",
                "approved dataset metadata is incomplete",
                "choose a trigger token and rerun decision preflight",
                {
                    "issues": [
                        {
                            "location": "dataset.trigger_token",
                            "type": "required_value",
                        }
                    ]
                },
            )
        normalized_token = lora_dataset.normalize_trigger_token(approved_token)
        try:
            validation = lora_dataset.validate_dataset(
                canonical_folder,
                trigger_token=normalized_token,
                expected_dataset_hash=expected_dataset_hash,
            )
        except DatasetServiceError as exc:
            raise TrainerServiceError(
                exc.code,
                exc.message,
                exc.details,
            ) from exc
        _require_validated_dataset(validation)

        # Local import avoids the decision module's dependency on this service.
        from app.services.lora_training_decision import (
            build_recipe_compilation_context,
        )

        context = build_recipe_compilation_context(
            inspected,
            normalized,
            approved_trigger_token=validation.normalized_trigger_token,
            settings=settings,
        )
        compiled = compile_training_recipe(
            normalized,
            context=context,
            policy_source="server_policy",
        )
    except RecipeError as exc:
        raise _trainer_recipe_error(exc) from exc

    effective = compiled.effective
    try: lora_parameters.validate_reportable(effective)
    except delivery.DeliveryError as exc: raise TrainerServiceError(exc.code,exc.message) from exc
    output_identity=delivery.output_config_hash(output_name,compiled.recipe_hash)
    if (expected_output_config_hash is not None or compiled.requested.expected_recipe_hash is not None) and expected_output_config_hash != output_identity:
        raise TrainerServiceError("output_config_hash_mismatch","output name changed since preflight; rerun preflight")
    _verify_profile_family(
        inspected,
        expected_profile_hash=expected_profile_hash,
        model_family=effective.model.family,
    )
    checkpoint_dirs = _checkpoint_search_dirs(
        settings,
        effective.model.family,
    )
    resolved_checkpoint = _resolve_model_file(
        effective.model.checkpoint,
        checkpoint_dirs,
    )
    _validate_checkpoint_exists(
        resolved_checkpoint,
        effective.model.checkpoint,
        checkpoint_dirs,
        allow_unverified=effective.model.allow_unverified_checkpoint,
    )
    effective_anima = effective.model.anima
    anima_args = _resolve_anima_runtime_args(
        model_family=effective.model.family,
        anima_qwen3=effective_anima.qwen3 if effective_anima else None,
        anima_vae=effective_anima.vae if effective_anima else None,
        anima_t5_tokenizer_path=(
            effective_anima.t5_tokenizer_path if effective_anima else None
        ),
        settings=settings,
    )
    _validate_trainer_runtime(
        settings.sd_scripts_path,
        model_family=effective.model.family,
    )

    job_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_path = None
    job = _TrainJob(
        job_id=job_id,
        output_name=output_name, output_config_hash=output_identity,
        folder=canonical_folder,
        checkpoint=resolved_checkpoint,
        model_family=effective.model.family,
        sdxl=effective.model.family == "sdxl",
        epochs=effective.optimization.epochs,
        submitted_at=submitted_at,
        resolution=effective.dataset.resolution,
        batch_size=effective.dataset.batch_size,
        learning_rate=effective.optimization.learning_rate,
        class_tokens=effective.dataset.class_tokens,
        keep_tokens=effective.dataset.keep_tokens,
        num_repeats=effective.dataset.num_repeats,
        mixed_precision=effective.optimization.mixed_precision,
        network_module=effective.model.network_module,
        network_dim=effective.model.network_dim,
        network_alpha=effective.model.network_alpha,
        anima_qwen3=anima_args["anima_qwen3"],
        anima_vae=anima_args["anima_vae"],
        anima_t5_tokenizer_path=anima_args["anima_t5_tokenizer_path"],
        dataset_hash=validation.dataset_hash,
        profile_hash=profile_hash,
        normalized_trigger_token=validation.normalized_trigger_token,
        log_path=log_path,
        recipe=compiled,
    )

    with _lock:
        if any(queued.folder == canonical_folder for queued in _queue):
            raise TrainerServiceError(
                "duplicate_folder",
                "training is already queued for this dataset folder",
                {"folder": canonical_folder},
                hint="monitor the existing job instead of starting a duplicate",
            )
        if _running and _running.job.folder == canonical_folder:
            raise TrainerServiceError(
                "duplicate_folder",
                "training is already running for this dataset folder",
                {"folder": canonical_folder},
                hint="monitor the existing job instead of starting a duplicate",
            )
        _ensure_lora_job_table()
        try:
            _create_persistent_job(job)
        except Exception:
            from app.services.lora_observation import contains
            if contains(job_id) is not False:
                raise AdmissionUncertainError(job_id) from None
            raise
        try:
            root=delivery.run_path(train_root,job.run_locator)
            delivery.create_run(root,job_id=job.job_id)
            lora_parameters.queued_parameters(root,job)
            job.log_path=str(root/'logs'/'training.log')
            _update_persistent_job(job.job_id,log_path=job.log_path)
            _queue.append(job)
        except Exception:
            raise AdmissionUncertainError(job_id) from None

    # Diagnostic writes must not prevent scheduling or erase an acknowledgement.
    try:
        _append_log(job.log_path, lora_public.event_line('queued'))
    except Exception:
        pass
    try:
        _ensure_worker()
    except Exception:
        raise AdmissionUncertainError(job_id) from None
    try:
        logger.info("Job %s queued", job_id)
    except Exception:
        pass
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
                "resolved_output_name":rj.job.resolved_output_name, "output_name":rj.job.output_name, "output_serial":rj.job.output_serial, "run_locator":rj.job.run_locator,
                "output_config_hash":rj.job.output_config_hash,
                "progress": rj.progress,
                "epoch": rj.epoch,
                "total_epochs": rj.total_epochs,
            }
            queue_list = [
                {"job_id": j.job_id, "folder": j.folder, "output_name":j.output_name,"resolved_output_name":j.resolved_output_name,"output_serial":j.output_serial,"run_locator":j.run_locator,"output_config_hash":j.output_config_hash}
                for j in _queue
            ]
        elif _queue:
            status = "queued"
            current_job = None
            queue_list = [
                {"job_id": j.job_id, "folder": j.folder, "output_name":j.output_name,"resolved_output_name":j.resolved_output_name,"output_serial":j.output_serial,"run_locator":j.run_locator,"output_config_hash":j.output_config_hash}
                for j in _queue
            ]
        else:
            status = "idle"
            current_job = None
            queue_list = []

    from app.services.lora_observation import observe
    memory_ids = [j["job_id"] for j in queue_list]
    if current_job:
        memory_ids.append(current_job["job_id"])
    durable = observe(memory_ids)
    last = lora_parameters.public_last_result(_last_result)
    return {
        "status": status,
        "current_job": current_job,
        "queue": queue_list,
        "last_result": last,
        "durable": durable,
    }


def get_job_status(job_id: str) -> dict:
    """Read training status and reconcile its bound smoke without submitting."""
    result = _read_persistent_job(job_id)
    if result is None:
        raise TrainerServiceError("job_not_found", f"LoRA training job not found: {job_id}")
    gallery_dir = getattr(get_settings(), 'gallery_dir', None)
    if result.get('smoke_test_job_id'):
        fields = lora_smoke.observe(result, gallery_dir)
        if any(result.get(key) != value for key, value in fields.items()):
            def reconcile(db):
                # A late queue read may not clobber a newer binding or outcome.
                query = db.query(LoraTrainingJob).filter_by(job_id=job_id)
                for key in ('smoke_test_job_id','smoke_test_status','smoke_test_artifact','smoke_test_error'):
                    query = query.filter(getattr(LoraTrainingJob, key) == result[key])
                query.update({**fields, 'updated_at':_utcnow()}, synchronize_session=False)
            _with_db(reconcile)
            result = _read_persistent_job(job_id)
    return lora_smoke.decorate(result, gallery_dir)


def _tail_lines(path: Path, line_limit: int) -> tuple[list[str], bool]:
    delivery.confined(path,path.parent)
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
            "error_message": lora_public.failure('log_read_failed')['message'],
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
        _append_log(job.get("log_path"), lora_public.event_line('cancelled'))
        return {"ok": True, "job_id": job_id, "status": "cancelled"}

    if proc_to_terminate:
        _update_persistent_job(
            job_id,
            stage="cancelling",
            cancel_requested_at=_utcnow(),
        )
        _append_log(job.get("log_path"), lora_public.event_line('cancellation_requested'))
        try:
            proc_to_terminate.terminate()
        except Exception as exc:
            raise TrainerServiceError(
                "job_cancel_failed",
                "failed to terminate training subprocess",
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
        _append_log(job.get("log_path"), lora_public.event_line('cancelled'))
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

    def response(current):
        public = lora_parameters.public_job(current)
        return {
            'ok':True, 'job_id':job_id, 'registered_lora_name':public.get('registered_lora_name'),
            'smoke_test_status':public.get('smoke_test_status'),
            'generation_job_id':public.get('smoke_test_job_id'),
            'artifact':public.get('smoke_test_artifact'),
            'artifact_id':public.get('smoke_test_artifact_id'), 'image_id':public.get('smoke_test_image_id'),
            'artifact_url':public.get('smoke_test_artifact_url'),
            'error':public.get('smoke_test_error'), 'error_code':public.get('smoke_test_error_code'),
            'hint':public.get('smoke_test_hint'),
        }

    if job.get('smoke_test_job_id') or job.get('smoke_test_status') not in {None, 'failed'}:
        return response(job)

    def claim(db):
        from sqlalchemy import or_, and_
        return db.query(LoraTrainingJob).filter(
            LoraTrainingJob.job_id == job_id, LoraTrainingJob.smoke_test_job_id.is_(None),
            or_(LoraTrainingJob.smoke_test_status.is_(None),
                and_(LoraTrainingJob.smoke_test_status == 'failed',
                     LoraTrainingJob.smoke_test_error == 'generation_queue_full')),
        ).update({'smoke_test_status':'submitting','smoke_test_error':None,
                  'smoke_test_artifact':None,'updated_at':_utcnow()}, synchronize_session=False)
    if not _with_db(claim):
        return response(get_job_status(job_id))

    def finish_claim(**fields):
        def finish(db):
            return db.query(LoraTrainingJob).filter_by(
                job_id=job_id, smoke_test_status='submitting', smoke_test_job_id=None,
            ).update({**fields,'updated_at':_utcnow()}, synchronize_session=False)
        return _with_db(finish)

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
        "execution_target": body.execution_target,
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
        if not isinstance(generation_job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', generation_job_id):
            raise ValueError('invalid generation receipt')
    except QueueFullError as exc:
        saved = finish_claim(
            smoke_test_status="failed",
            smoke_test_error='generation_queue_full',
        )
        if not saved:
            return response(get_job_status(job_id))
        raise TrainerServiceError("generation_queue_full", lora_public.failure('generation_queue_full')['message']) from None
    except Exception as exc:
        finish_claim(
            smoke_test_status="submission_unknown",
            smoke_test_error='smoke_submission_unknown',
        )
        return response(get_job_status(job_id))

    finish_claim(
        smoke_test_status="submitted",
        smoke_test_job_id=generation_job_id,
        smoke_test_error=None,
    )
    # Preserve submission semantics; the next explicit status read reconciles.
    return response(lora_smoke.decorate(_read_persistent_job(job_id), getattr(get_settings(), 'gallery_dir', None)))


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
        if not folder or folder == "." or rel.parts[0] in {"output","logs",".lora_prep_backups"}:
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
    探索符合訓練門檻的資料夾，不建立或排入訓練工作。
    Returns: {"should_trigger": bool, "candidates": [{"folder": str, "image_count": int}]}
    """
    settings = get_settings()
    base = Path(settings.lora_train_dir).resolve()
    threshold = settings.lora_train_threshold

    if not base.exists() or not base.is_dir():
        return {"should_trigger": False, "candidates": []}

    candidates: list[dict] = []

    for image_dir, folder in _iter_training_folders(base):
        count = _count_trainable_images(image_dir)
        if count < threshold:
            continue
        candidates.append({"folder": folder, "image_count": count})

    return {
        "should_trigger": len(candidates) > 0,
        "candidates": candidates,
    }
