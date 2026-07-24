"""
批次生圖排程器
佇列式批次生成，串接 workflow、comfyui、recording

對應 docs/internal-interfaces.md queue 介面
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import random
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import httpx

from app.config import get_settings
from app.core.artifacts import gallery_output_filename, get_output_artifacts
from app.core.comfyui import (
    ComfyUIClient,
    ComfyUIError,
    get_comfy_client,
    structure_execution_error,
    structure_node_errors,
)
from app.core.generation_batches import (
    cancel_queued_batch,
    create_batch,
    mark_member_running,
    mark_member_terminal,
    reconcile_interrupted_batches,
    sanitize_failure_message,
)
from app.core.recording import save as recording_save, save_artifact as recording_save_artifact
from app.core.resources import default_checkpoint
from app.core.workflow import (
    apply_params,
    extract_model_files_from_workflow,
    get_seed_from_workflow,
    get_sampling_params_from_workflow,
    load_template,
)
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

MAX_PENDING = 50
WORKFLOW_TEMPLATE = "default"
WORKFLOW_TEMPLATE_LORA = "default_lora"


def _canonical_workflow_sha256(workflow: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(workflow, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class QueueFullError(Exception):
    """佇列已滿"""


class AuditedWorkflowHashMismatchError(RuntimeError):
    """Immutable recipe workflow no longer matches its audited digest."""


class GenerateParams(TypedDict, total=False):
    workflow: dict[str, Any]  # 自訂 workflow，若有則跳過 template 載入
    template: str  # 指定 workflow 模板名稱（如 "anima"），優先於依 lora 推斷的預設
    checkpoint: str
    diffusion_model: str  # UNETLoader.unet_name（diffusion-model 家族，如 Anima）
    text_encoder: str  # CLIPLoader.clip_name
    vae: str  # VAELoader.vae_name
    lora: str
    loras: list[dict]  # 多 lora：[{name, strength_model, strength_clip?}]，有則優先於單一 lora
    prompt: str
    image: str  # 主體圖路徑（img2img），相對於 gallery_dir
    first_frame: str  # 影片 workflow 第一幀參考圖，gallery 相對路徑
    last_frame: str  # 影片 workflow 最後一幀參考圖，gallery 相對路徑
    video_ref: str  # 影片參考檔，gallery 相對路徑
    image_pose: str  # 姿態圖路徑，相對於 gallery_dir，會上傳至 ComfyUI
    mask: str  # 遮罩圖路徑（inpaint），相對於 gallery_dir，會上傳至 ComfyUI
    negative_prompt: str
    seed: int
    steps: int
    cfg: float
    width: int
    height: int
    batch_size: int
    batch_seed_mode: str
    sampler_name: str
    scheduler: str
    lora_strength: float
    denoise: float
    recipe_provenance: dict[str, Any]  # CIV-F verified CIV-E bundle, persisted on completion
    server_owned_verbatim: bool  # internal saved-style-workflow submission marker


class _Job:
    __slots__ = (
        "execution_id",
        "public_job_id",
        "batch_index",
        "params",
        "submitted_at",
        "prompt_id",
        "completion_polls",
    )

    def __init__(
        self,
        job_id: str | None = None,
        params: dict[str, Any] | None = None,
        submitted_at: str = "",
        *,
        execution_id: str | None = None,
        public_job_id: str | None = None,
        batch_index: int | None = None,
    ):
        legacy_id = job_id or execution_id or public_job_id
        if legacy_id is None:
            raise ValueError("job identity is required")
        self.execution_id = execution_id or legacy_id
        self.public_job_id = public_job_id or legacy_id
        self.batch_index = batch_index
        self.params = params or {}
        self.submitted_at = submitted_at
        self.prompt_id: str | None = None
        self.completion_polls = 0  # ComfyUI 狀態不確定時的等待計數

    @property
    def job_id(self) -> str:
        """Backward-compatible public identity used by existing callers/tests."""
        return self.public_job_id


@dataclass
class _BatchProgress:
    public_job_id: str
    total: int
    completed: int
    failed: int
    started: bool
    seeds: tuple[int, ...]
    submitted_at: str
    current_batch_index: int | None = None
    failed_members: list[dict[str, Any]] = field(default_factory=list)


MAX_FAILED = 100  # 失敗任務保留上限（含結構化錯誤，供 agent 查詢後自我修正）
# ComfyUI queue/history 暫時無法判定狀態時的最大重試 tick 數（每 tick ~2s）；
# 超過才標 failed，避免瞬時 malformed response 提早放行 sibling，也避免永久卡槽。
MAX_COMPLETION_POLLS = 15

_lock = threading.Lock()
_pending: list[_Job] = []
_running: _Job | None = None
_batches: dict[str, _BatchProgress] = {}
_failed: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_our_prompt_ids: set[str] = set()  # 本系統提交的 prompt_id，history watcher 略過


def _batch_status_item(
    progress: _BatchProgress,
    *,
    status: str,
    prompt_id: str | None = None,
) -> dict[str, Any]:
    return {
        "job_id": progress.public_job_id,
        "status": status,
        "submitted_at": progress.submitted_at,
        "prompt_id": prompt_id,
        "batch_total": progress.total,
        "batch_completed": progress.completed,
        "batch_failed": progress.failed,
        "current_batch_index": progress.current_batch_index,
        "failed_members": [dict(item) for item in progress.failed_members],
    }


def _reset_for_test() -> None:
    """僅供測試使用：清空佇列狀態"""
    global _pending, _running
    with _lock:
        _pending.clear()
        _running = None
        _batches.clear()
        _failed.clear()


def _record_failure(
    job: "_Job",
    error: Exception,
    node_errors: list[dict[str, str]] | None = None,
    recording_error: dict[str, Any] | None = None,
    failure_code: str | None = None,
) -> None:
    """記錄失敗任務（不重試）。validation 類錯誤帶 node_errors 供 agent 修正。"""
    safe_error = sanitize_failure_message(error)
    if recording_error is not None:
        recording_error = {
            **recording_error,
            "message": sanitize_failure_message(recording_error.get("message")),
        }
    if job.batch_index is not None:
        db = SessionLocal()
        try:
            batch_status = mark_member_terminal(
                db,
                public_job_id=job.public_job_id,
                batch_index=job.batch_index,
                succeeded=False,
                failure_code=(
                    failure_code
                    or (
                        str(recording_error.get("code"))
                        if recording_error
                        else None
                    )
                    or ("comfyui_error" if node_errors else "submission_failed")
                ),
                failure_message=safe_error,
            )
        finally:
            db.close()
        with _lock:
            progress = _batches.get(job.public_job_id)
            if progress is not None:
                progress.completed = batch_status["batch_completed"]
                progress.failed = batch_status["batch_failed"]
                progress.current_batch_index = batch_status.get(
                    "current_batch_index"
                )
                progress.failed_members = list(
                    batch_status.get("failed_members") or []
                )
                if (
                    progress.completed + progress.failed
                    == progress.total
                ):
                    _batches.pop(job.public_job_id, None)
            if batch_status["status"] == "failed":
                _failed[job.public_job_id] = {
                    **batch_status,
                    "error": "all independent batch members failed",
                    "node_errors": [],
                    "recording_error": None,
                    "is_custom": False,
                }
                while len(_failed) > MAX_FAILED:
                    _failed.popitem(last=False)
        return

    with _lock:
        _failed[job.job_id] = {
            "job_id": job.job_id,
            "status": "failed",
            "submitted_at": job.submitted_at,
            "error": safe_error,
            "node_errors": node_errors or [],
            "recording_error": recording_error,
            "is_custom": bool(job.params.get("workflow")),
        }
        while len(_failed) > MAX_FAILED:
            _failed.popitem(last=False)


def _record_success(job: "_Job") -> None:
    if job.batch_index is None:
        return
    db = SessionLocal()
    try:
        batch_status = mark_member_terminal(
            db,
            public_job_id=job.public_job_id,
            batch_index=job.batch_index,
            succeeded=True,
        )
    finally:
        db.close()
    with _lock:
        progress = _batches.get(job.public_job_id)
        if progress is None:
            return
        progress.completed = batch_status["batch_completed"]
        progress.failed = batch_status["batch_failed"]
        progress.current_batch_index = batch_status.get("current_batch_index")
        progress.failed_members = list(batch_status.get("failed_members") or [])
        if progress.completed + progress.failed == progress.total:
            _batches.pop(job.public_job_id, None)


def _allocate_unique_seeds(count: int, *, max_attempts: int | None = None) -> tuple[int, ...]:
    """Allocate unique seeds from the template-generation range with a bounded retry."""
    if count < 1:
        raise ValueError("independent batch_size must be at least 1")
    attempt_limit = max_attempts or max(count * 10, count + 8)
    seeds: list[int] = []
    seen: set[int] = set()
    attempts = 0
    while len(seeds) < count and attempts < attempt_limit:
        attempts += 1
        seed = random.randint(0, 2**32 - 1)
        if seed in seen:
            continue
        seen.add(seed)
        seeds.append(seed)
    if len(seeds) != count:
        raise RuntimeError("unable to allocate unique independent batch seeds")
    return tuple(seeds)


def submit(params: GenerateParams) -> str:
    """
    提交生圖任務至佇列。

    Returns:
        job_id

    Raises:
        QueueFullError: 佇列已滿
    """
    with _lock:
        batch_seed_mode = str(params.get("batch_seed_mode") or "shared")
        batch_size = int(params.get("batch_size") or 1)
        if batch_seed_mode not in {"shared", "independent"}:
            raise ValueError("batch_seed_mode must be shared or independent")
        if batch_seed_mode == "independent" and (
            params.get("seed") is not None
            or params.get("seed_mode") in {"fixed", "workflow_default"}
        ):
            raise ValueError(
                "independent batch seed mode requires server-allocated random seeds"
            )
        required_slots = batch_size if batch_seed_mode == "independent" else 1
        if len(_pending) + required_slots > MAX_PENDING:
            raise QueueFullError("生圖佇列已滿，請稍後再試")

        public_job_id = str(uuid.uuid4())
        submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if batch_seed_mode == "independent":
            if params.get("workflow") or params.get("recipe_provenance") or params.get("server_owned_verbatim"):
                raise ValueError("independent batch seed mode only supports template generation")
            seeds = _allocate_unique_seeds(batch_size)
            jobs: list[_Job] = []
            for batch_index, seed in enumerate(seeds):
                child_params = dict(params)
                child_params["batch_size"] = 1
                child_params["seed"] = seed
                jobs.append(
                    _Job(
                        execution_id=str(uuid.uuid4()),
                        public_job_id=public_job_id,
                        batch_index=batch_index,
                        params=child_params,
                        submitted_at=submitted_at,
                    )
                )
            db = SessionLocal()
            try:
                create_batch(
                    db,
                    public_job_id=public_job_id,
                    execution_ids=tuple(job.execution_id for job in jobs),
                    seeds=seeds,
                    submitted_at=submitted_at,
                )
            finally:
                db.close()
            _batches[public_job_id] = _BatchProgress(
                public_job_id=public_job_id,
                total=batch_size,
                completed=0,
                failed=0,
                started=False,
                seeds=seeds,
                submitted_at=submitted_at,
            )
            _pending.extend(jobs)
        else:
            _pending.append(
                _Job(
                    execution_id=public_job_id,
                    public_job_id=public_job_id,
                    params=dict(params),
                    submitted_at=submitted_at,
                )
            )
    logger.info("Job %s queued", public_job_id)
    return public_job_id


def submit_custom(params: GenerateParams) -> str:
    """
    提交自訂 workflow 生圖任務至佇列。
    params 必須包含 "workflow" key，為 ComfyUI API 格式的 workflow dict。
    """
    if "workflow" not in params:
        raise ValueError("submit_custom 需要 params.workflow")
    return submit(params)


def submit_saved_workflow(workflow: dict[str, Any]) -> str:
    """Queue a server-owned saved graph without applying runtime parameters."""
    if not isinstance(workflow, dict) or not workflow:
        raise ValueError("saved workflow submission requires a nonempty graph object")
    return submit(
        {
            "workflow": copy.deepcopy(workflow),
            "server_owned_verbatim": True,
        }
    )


def submit_audited_recipe(params: GenerateParams, *, job_id: str) -> str:
    """Queue one already-validated immutable recipe under its pre-bound opaque job id.

    This is deliberately internal-only: callers cannot select a job id through HTTP/MCP.
    """
    if params.get("batch_seed_mode") == "independent":
        raise ValueError(
            "independent batch seed mode does not support audited workflows"
        )
    if "workflow" not in params or "recipe_provenance" not in params or not isinstance(job_id, str) or not job_id:
        raise ValueError("audited recipe submission requires immutable workflow, provenance, and job id")
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _lock:
        if len(_pending) >= MAX_PENDING:
            raise QueueFullError("生圖佇列已滿，請稍後再試")
        _pending.append(_Job(job_id=job_id, params=dict(params), submitted_at=submitted_at))
    logger.info("Audited recipe job %s queued", job_id)
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
        if _running and _running.batch_index is None:
            running_list.append({
                "job_id": _running.public_job_id,
                "prompt_id": _running.prompt_id,
                "status": "running",
                "submitted_at": _running.submitted_at,
            })
        for progress in _batches.values():
            if not progress.started:
                continue
            prompt_id = (
                _running.prompt_id
                if _running and _running.public_job_id == progress.public_job_id
                else None
            )
            running_list.append(
                _batch_status_item(progress, status="running", prompt_id=prompt_id)
            )

        pending_list: list[dict[str, Any]] = []
        seen_parents: set[str] = set()
        for job in _pending:
            if job.batch_index is None:
                pending_list.append(
                    {
                        "job_id": job.public_job_id,
                        "status": "queued",
                        "submitted_at": job.submitted_at,
                    }
                )
                continue
            progress = _batches.get(job.public_job_id)
            if (
                progress is None
                or progress.started
                or progress.public_job_id in seen_parents
            ):
                continue
            seen_parents.add(progress.public_job_id)
            pending_list.append(_batch_status_item(progress, status="queued"))
    return {
        "queue_running": running_list,
        "queue_pending": pending_list,
    }


def get_our_prompt_ids() -> set[str]:
    """取得本系統已提交的 prompt_id 集合，供 history watcher 略過用"""
    with _lock:
        return set(_our_prompt_ids)


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """取得單一任務狀態，None 表示不存在"""
    with _lock:
        progress = _batches.get(job_id)
        if progress is not None:
            status = "running" if progress.started else "queued"
            prompt_id = (
                _running.prompt_id
                if _running and _running.public_job_id == job_id
                else None
            )
            return _batch_status_item(progress, status=status, prompt_id=prompt_id)
        if _running and _running.public_job_id == job_id:
            return {
                "job_id": _running.public_job_id,
                "prompt_id": _running.prompt_id,
                "status": "running",
                "submitted_at": _running.submitted_at,
            }
        for j in _pending:
            if j.public_job_id == job_id:
                return {
                    "job_id": j.job_id,
                    "status": "queued",
                    "submitted_at": j.submitted_at,
                }
        if job_id in _failed:
            return dict(_failed[job_id])
    return None


def cancel(job_id: str) -> bool:
    """
    取消 pending 中的 job。
    
    Returns:
        True: 取消成功
        False: 找不到（不在 pending 中）
    
    Raises:
        ValueError: job 正在執行中（running），無法取消
    """
    with _lock:
        if _running and _running.public_job_id == job_id:
            raise ValueError(f"Job {job_id} 正在執行中，無法取消")
        progress = _batches.get(job_id)
        if progress is not None:
            if progress.started:
                raise ValueError(f"Job {job_id} 正在執行中，無法取消")
            db = SessionLocal()
            try:
                cancel_queued_batch(db, job_id)
            finally:
                db.close()
            _pending[:] = [
                job for job in _pending if job.public_job_id != job_id
            ]
            _batches.pop(job_id, None)
            return True
        for i, j in enumerate(_pending):
            if j.public_job_id == job_id:
                _pending.pop(i)
                return True
    return False


def _fail_saved_workflow_submit(job: "_Job", error: Exception) -> None:
    """Make every server-owned saved-graph submit exception terminal."""
    _release_running(job)
    structured: list[dict[str, str]] = []
    if isinstance(error, ComfyUIError):
        try:
            structured = structure_node_errors(
                error.node_errors, job.params.get("workflow")
            )
        except Exception as structure_error:
            logger.warning(
                "Ignored malformed ComfyUI node_errors for saved workflow job %s: %s",
                job.job_id,
                structure_error,
            )
    _record_failure(job, error, structured)
    logger.error(
        "Saved style workflow job %s submit failed: %s (node_errors=%s)",
        job.job_id,
        error,
        structured,
    )


def _process_pending(comfy: ComfyUIClient) -> None:
    """從 pending 取一筆提交至 ComfyUI，移入 running"""
    global _running
    with _lock:
        if _running or not _pending:
            return
        job = _pending.pop(0)
        _running = job
        if job.batch_index is not None:
            progress = _batches.get(job.public_job_id)
            if progress is not None:
                progress.started = True
                progress.current_batch_index = job.batch_index

    try:
        if job.batch_index is not None:
            db = SessionLocal()
            try:
                mark_member_running(
                    db,
                    public_job_id=job.public_job_id,
                    batch_index=job.batch_index,
                )
            finally:
                db.close()
        if job.params.get("server_owned_verbatim"):
            saved_workflow = job.params.get("workflow")
            if not isinstance(saved_workflow, dict) or not saved_workflow:
                raise ValueError(
                    "server-owned saved workflow is missing its graph"
                )
            prompt = copy.deepcopy(saved_workflow)
            job.params["workflow_json"] = copy.deepcopy(prompt)
            try:
                prompt_id = comfy.submit_prompt(prompt)
            except Exception as error:
                _fail_saved_workflow_submit(job, error)
                return
            if not isinstance(prompt_id, str) or not prompt_id.strip():
                _fail_saved_workflow_submit(
                    job,
                    ValueError(
                        "ComfyUI response is missing a non-empty string prompt_id"
                    ),
                )
                return
            with _lock:
                if _running and _running.execution_id == job.execution_id:
                    _running.prompt_id = prompt_id
                _our_prompt_ids.add(prompt_id)
            logger.info(
                "Saved style workflow job %s submitted verbatim to ComfyUI, prompt_id=%s",
                job.job_id,
                prompt_id,
            )
            return

        audited_bundle = job.params.get("recipe_provenance")
        if audited_bundle is not None:
            audited_workflow = audited_bundle.get("workflow") if isinstance(audited_bundle, dict) else None
            submitted_workflow = job.params.get("workflow")
            declared_digest = audited_bundle.get("workflow_sha256") if isinstance(audited_bundle, dict) else None
            if (
                not isinstance(audited_workflow, dict)
                or not isinstance(submitted_workflow, dict)
                or not isinstance(declared_digest, str)
                or submitted_workflow != audited_workflow
                or _canonical_workflow_sha256(audited_workflow) != declared_digest
                or _canonical_workflow_sha256(submitted_workflow) != declared_digest
            ):
                raise AuditedWorkflowHashMismatchError("audited_workflow_hash_mismatch")

            # Provenance-bearing submissions are immutable: bypass defaults, uploads,
            # randomization, and apply_params, then submit the audited snapshot verbatim.
            prompt = copy.deepcopy(audited_workflow)
            job.params["workflow_json"] = prompt
            prompt_id = comfy.submit_prompt(prompt)
            if not isinstance(prompt_id, str) or not prompt_id.strip():
                raise ValueError(
                    "ComfyUI response is missing a non-empty string prompt_id"
                )
            with _lock:
                if _running and _running.execution_id == job.execution_id:
                    _running.prompt_id = prompt_id
                _our_prompt_ids.add(prompt_id)
            logger.info("Audited recipe job %s submitted to ComfyUI, prompt_id=%s", job.job_id, prompt_id)
            return

        settings = get_settings()
        # 先決定並載入 workflow；checkpoint 預設邏輯需依其節點型別判斷。
        # template 優先序：自訂 workflow > 明確指定的 template > 依 lora 推斷的預設模板。
        custom_wf = job.params.get("workflow")
        if custom_wf:
            wf = copy.deepcopy(custom_wf)
        else:
            template = (
                job.params.get("template")
                or (WORKFLOW_TEMPLATE_LORA if job.params.get("lora") else WORKFLOW_TEMPLATE)
            )
            wf = load_template(template)

        # 僅傳統 checkpoint workflow（含 CheckpointLoaderSimple）才套用預設 checkpoint；
        # diffusion-model workflow（如 Anima 的 UNETLoader）模板已內嵌模型檔名，
        # 不應把傳統 checkpoint 名稱注入進去。
        has_checkpoint_loader = any(
            isinstance(n, dict) and n.get("class_type") == "CheckpointLoaderSimple"
            for n in wf.values()
        )
        use_workflow_defaults = bool(job.params.get("use_workflow_defaults"))
        if has_checkpoint_loader and not custom_wf and not use_workflow_defaults:
            effective_checkpoint = (
                job.params.get("checkpoint")
                or default_checkpoint(settings)
            )
            if effective_checkpoint is None:
                raise FileNotFoundError(
                    "No checkpoint available from /api/generate/available-resources"
                )
            if not job.params.get("checkpoint"):
                job.params["checkpoint"] = effective_checkpoint
        else:
            # Custom workflows and diffusion-model templates already bind their model files.
            # Only an explicit caller override may replace those audited bindings.
            effective_checkpoint = job.params.get("checkpoint")

        width = job.params.get("width")
        height = job.params.get("height")
        if not use_workflow_defaults and width is None and height is None and effective_checkpoint and settings.lora_sdxl:
            width, height = 1024, 1024
        # 若提供 image / image_pose，從 gallery 讀取並上傳至 ComfyUI，取得檔名後替換
        image_for_wf: str | None = None
        image_pose_for_wf: str | None = None
        gallery_path = Path(settings.gallery_dir).resolve()

        def _resolve_gallery_file(rel_path: str, *, strict: bool = False) -> Path | None:
            path = (gallery_path / rel_path).resolve()
            try:
                path.relative_to(gallery_path)
            except ValueError:
                logger.warning("Path traversal blocked: %s", rel_path)
                if strict:
                    raise FileNotFoundError(f"Unsafe gallery path: {rel_path}")
                return None
            if not path.exists() or not path.is_file():
                logger.warning("Gallery file not found: %s", path)
                if strict:
                    raise FileNotFoundError(f"Gallery file not found: {rel_path}")
                return None
            return path

        def _upload_gallery_image(rel_path: str) -> str | None:
            path = _resolve_gallery_file(rel_path)
            if path is None:
                return None
            if path.exists():
                uploaded = comfy.upload_image(path)
                result = uploaded["name"]
                if uploaded.get("subfolder"):
                    result = f"{uploaded['subfolder']}/{uploaded['name']}"
                return result

        mask_for_wf: str | None = None
        first_frame_for_wf: str | None = None
        last_frame_for_wf: str | None = None
        video_ref_for_wf: str | None = None
        if job.params.get("image"):
            image_for_wf = _upload_gallery_image(job.params["image"])
        if job.params.get("first_frame"):
            first_frame_for_wf = _upload_gallery_image(job.params["first_frame"])
        if job.params.get("last_frame"):
            last_frame_for_wf = _upload_gallery_image(job.params["last_frame"])
        if job.params.get("video_ref"):
            video_ref_for_wf = str(_resolve_gallery_file(job.params["video_ref"], strict=True))
        if job.params.get("mask"):
            mask_for_wf = _upload_gallery_image(job.params["mask"])
        if job.params.get("image_pose"):
            image_pose_for_wf = _upload_gallery_image(job.params["image_pose"])
        elif settings.controlnet_default_pose_image:
            # 未指定 image_pose 時，若 workflow 有 ControlNet (DWPreprocessor) 則使用預設姿態圖
            pose_has_dw = any(
                n.get("class_type") == "DWPreprocessor"
                for n in wf.values()
                if isinstance(n, dict)
            )
            if pose_has_dw:
                proj_root = Path(__file__).resolve().parent.parent.parent
                default_pose_path = (proj_root / settings.controlnet_default_pose_image).resolve()
                if default_pose_path.exists():
                    uploaded = comfy.upload_image(default_pose_path)
                    image_pose_for_wf = uploaded["name"]
                    if uploaded.get("subfolder"):
                        image_pose_for_wf = f"{uploaded['subfolder']}/{uploaded['name']}"
                else:
                    logger.warning("ControlNet default pose image not found: %s", default_pose_path)

        # template 路徑維持既有行為：省略 steps/cfg 補上預設值，省略 seed 則產生隨機值並記錄；
        # custom 路徑尊重提交的 workflow JSON，省略時原樣傳遞 None（不覆寫）。
        if custom_wf or use_workflow_defaults:
            effective_steps = job.params.get("steps")
            effective_cfg = job.params.get("cfg")
            effective_seed = job.params.get("seed")
            if (
                job.params.get("seed_mode") == "random"
                and job.params.get("batch_seed_mode") != "independent"
            ):
                effective_seed = random.randint(0, 2**32 - 1)
        else:
            effective_steps = job.params.get("steps", 20)
            effective_cfg = job.params.get("cfg", 7.0)
            effective_seed = job.params.get("seed")
            if effective_seed is None:
                effective_seed = random.randint(0, 2**32 - 1)

        prompt = apply_params(
            wf,
            checkpoint=effective_checkpoint,
            image=image_for_wf,
            first_frame=first_frame_for_wf,
            last_frame=last_frame_for_wf,
            video_ref=video_ref_for_wf,
            image_pose=image_pose_for_wf,
            mask=mask_for_wf,
            lora=job.params.get("lora"),
            loras=job.params.get("loras"),
            prompt=job.params.get("prompt", ""),
            negative_prompt=job.params.get("negative_prompt"),
            seed=effective_seed,
            steps=effective_steps,
            cfg=effective_cfg,
            width=width,
            height=height,
            batch_size=job.params.get("batch_size"),
            sampler_name=job.params.get("sampler_name"),
            scheduler=job.params.get("scheduler"),
            lora_strength=job.params.get("lora_strength"),
            denoise=job.params.get("denoise"),
            diffusion_model=job.params.get("diffusion_model"),
            text_encoder=job.params.get("text_encoder"),
            vae=job.params.get("vae"),
        )
        # 使用者未提供 seed 時，apply_params 會產生隨機值；擷取實際使用的 seed 供 recording
        if job.params.get("seed") is None:
            effective_seed = get_seed_from_workflow(prompt)
            if effective_seed is not None:
                job.params["seed"] = effective_seed
        for key, value in get_sampling_params_from_workflow(prompt).items():
            if job.params.get(key) is None:
                job.params[key] = value
        # 反解實際送出 workflow 的模型檔名（含 anima.json 內嵌值），供 recording 記錄、之後重生
        for key, value in extract_model_files_from_workflow(prompt).items():
            if value is not None and not job.params.get(key):
                job.params[key] = value
        # 擷取「實際送出的完整 workflow」與來源圖/遮罩（gallery 相對路徑，非 ComfyUI 暫存檔名），
        # 供 gallery_rerun 忠實重生（見 persist-full-workflow-for-rerun）。
        job.params["workflow_json"] = prompt
        if job.params.get("image"):
            job.params["source_image"] = job.params["image"]
        if job.params.get("mask"):
            job.params["source_mask"] = job.params["mask"]
        prompt_id = comfy.submit_prompt(prompt)
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise ValueError(
                "ComfyUI response is missing a non-empty string prompt_id"
            )
        with _lock:
            if _running and _running.execution_id == job.execution_id:
                _running.prompt_id = prompt_id
            _our_prompt_ids.add(prompt_id)
        logger.info("Job %s submitted to ComfyUI, prompt_id=%s", job.job_id, prompt_id)
    except AuditedWorkflowHashMismatchError as e:
        logger.error("Audited recipe job %s rejected before ComfyUI submit: %s", job.job_id, e)
        with _lock:
            if _running and _running.execution_id == job.execution_id:
                _running = None
        _record_failure(job, e)
    except ComfyUIError as e:
        # ComfyUI /prompt 驗證/執行被拒：永久性失敗，不重試（過去插回隊首會無限重試而堵塞隊列）。
        # 把 node_errors 結構化記錄，供 agent 查 job 狀態後自我修正並重送。
        try:
            structured = structure_node_errors(
                e.node_errors, job.params.get("workflow")
            )
        except Exception:
            structured = []
            logger.warning(
                "Could not structure ComfyUI node errors for job %s",
                job.job_id,
            )
        logger.error(
            "ComfyUI rejected job %s: %s (node_errors=%s)",
            job.job_id, e, structured,
        )
        with _lock:
            if _running and _running.execution_id == job.execution_id:
                _running = None
        _record_failure(job, e, structured)
    except FileNotFoundError as e:
        # 參考圖/遮罩等輸入檔不存在：永久性失敗，不重試。
        logger.error("Job %s input file missing: %s", job.job_id, e)
        with _lock:
            if _running and _running.execution_id == job.execution_id:
                _running = None
        _record_failure(job, e)
    except (httpx.ConnectError, httpx.RequestError) as e:
        # ComfyUI 連線失敗：任務失敗，不重試（記錄以利 agent 查詢，而非靜默消失）。
        logger.exception("ComfyUI connection failed for job %s: %s", job.job_id, e)
        with _lock:
            if _running and _running.execution_id == job.execution_id:
                _running = None
        _record_failure(job, e)
    except Exception as e:
        logger.exception("Job %s submission failed: %s", job.job_id, e)
        _release_running(job)
        _record_failure(job, e, failure_code="submission_failed")


def _release_running(job: "_Job") -> None:
    """釋放 running 槽（限本 job），讓後續任務可被處理。"""
    global _running
    with _lock:
        if _running and _running.execution_id == job.execution_id:
            _running = None


def _prompt_in_comfy_queue(queue_data: object, prompt_id: str) -> bool:
    """prompt 是否仍在 ComfyUI 佇列（running 或 pending）。
    ComfyUI item 格式：[job_number, prompt_id, workflow, output_node_ids, metadata]。"""
    if not isinstance(queue_data, Mapping):
        raise ValueError("ComfyUI queue response must be a mapping")
    for key in ("queue_running", "queue_pending"):
        entries = queue_data.get(key, [])
        if entries is None:
            entries = []
        if not isinstance(entries, (list, tuple)):
            raise ValueError(f"ComfyUI queue field {key} must be a sequence")
        for item in entries:
            pid = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else None
            if pid == prompt_id:
                return True
    return False


def _save_job_outputs(
    comfy: ComfyUIClient, job: "_Job", artifacts_info: list[dict[str, Any]]
) -> int:
    """Fetch outputs, copy to gallery, and persist image/artifact records."""
    settings = get_settings()
    gallery_path = Path(settings.gallery_dir).resolve()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = gallery_path / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_infos: list[tuple[str, dict[str, Any], int]] = []
    for i, artifact in enumerate(artifacts_info):
        data = comfy.fetch_image(
            artifact["filename"],
            subfolder=artifact.get("subfolder", ""),
            ftype=artifact.get("type", "output"),
        )
        out_name = gallery_output_filename(
            artifact["filename"],
            job.public_job_id,
            i,
            batch_index=job.batch_index,
        )
        (out_dir / out_name).write_bytes(data)
        saved_infos.append((str(Path(date_str) / out_name), artifact, len(data)))

    count = 0
    for rel_path, artifact, file_size in saved_infos:
        db = SessionLocal()
        try:
            artifact_type = artifact.get("artifact_type")
            if artifact_type == "image":
                recording_save(
                    rel_path,
                    job_id=job.job_id,
                    checkpoint=job.params.get("checkpoint"),
                    lora=job.params.get("lora"),
                    template=job.params.get("template"),
                    diffusion_model=job.params.get("diffusion_model"),
                    text_encoder=job.params.get("text_encoder"),
                    vae=job.params.get("vae"),
                    seed=job.params.get("seed"),
                    steps=job.params.get("steps"),
                    cfg=job.params.get("cfg"),
                    prompt=job.params.get("prompt"),
                    negative_prompt=job.params.get("negative_prompt"),
                    workflow_json=job.params.get("workflow_json"),
                    source_image=job.params.get("source_image"),
                    source_mask=job.params.get("source_mask"),
                    artifact_mime_type=artifact.get("mime_type"),
                    artifact_source_node_id=artifact.get("source_node_id"),
                    artifact_source_node_type=artifact.get("source_node_type"),
                    artifact_file_size=file_size,
                    artifact_metadata=(
                        {
                            "batch_index": job.batch_index,
                            "seed": job.params.get("seed"),
                        }
                        if job.batch_index is not None
                        else None
                    ),
                    recipe_provenance=job.params.get("recipe_provenance"),
                    db=db,
                )
            else:
                recording_save_artifact(
                    gallery_path=rel_path,
                    artifact_type=str(artifact_type or "file"),
                    mime_type=artifact.get("mime_type"),
                    job_id=job.job_id,
                    source_node_id=artifact.get("source_node_id"),
                    source_node_type=artifact.get("source_node_type"),
                    file_size=file_size,
                    workflow_json=job.params.get("workflow_json"),
                    prompt=job.params.get("prompt"),
                    negative_prompt=job.params.get("negative_prompt"),
                    metadata={
                        "output_key": artifact.get("output_key"),
                        **(
                            {
                                "batch_index": job.batch_index,
                                "seed": job.params.get("seed"),
                            }
                            if job.batch_index is not None
                            else {}
                        ),
                    },
                    db=db,
                )
            count += 1
        finally:
            db.close()
    return count


def _defer_uncertain_completion(
    job: "_Job",
    *,
    failure_code: str,
    message: str,
) -> None:
    """Retain the running slot until repeated queue/history uncertainty is bounded."""
    job.completion_polls += 1
    if job.completion_polls < MAX_COMPLETION_POLLS:
        logger.warning(
            "Job %s status remains uncertain (%d/%d)",
            job.job_id,
            job.completion_polls,
            MAX_COMPLETION_POLLS,
        )
        return
    _release_running(job)
    _record_failure(
        job,
        RuntimeError(message),
        failure_code=failure_code,
    )
    logger.error(
        "Job %s status remained uncertain for %d polls",
        job.job_id,
        MAX_COMPLETION_POLLS,
    )


def _check_running_complete(comfy: ComfyUIClient) -> None:
    """檢查 running job 的終局狀態。

    保證每個終局 job 都落在 completed（DB）或 failed（_failed，帶原因）其一，不再靜默消失：
    - 仍在 ComfyUI queue_running/queue_pending → 還在處理。
    - 離開佇列但 history 未出現 → 有上限地等待（history 延遲競態）。
    - history status_str == "error" → failed（結構化 execution_error）。
    - success 有圖 → 存檔記錄 completed；save 失敗 → failed（不靜默丟）。
    - success 無圖 → failed。
    """
    with _lock:
        job = _running
        if not job or not job.prompt_id:
            return

    queue_failure_code = "comfyui_status_unknown"
    queue_failure_message = (
        "ComfyUI returned no result (history missing after completion)"
    )
    try:
        queue_data = comfy.get_queue()
        try:
            if _prompt_in_comfy_queue(queue_data, job.prompt_id):
                job.completion_polls = 0
                return  # 仍在 ComfyUI 佇列（執行中或排隊中）
        except Exception:
            queue_failure_code = "malformed_queue_response"
            queue_failure_message = (
                "ComfyUI queue response remained malformed and history "
                "did not provide a terminal result"
            )
    except Exception as e:
        logger.warning(
            "Failed to get ComfyUI queue: %s",
            e,
        )

    try:
        history = comfy.get_history(job.prompt_id)
    except Exception as e:
        logger.warning(
            "Failed to get ComfyUI history for job %s: %s",
            job.job_id,
            e,
        )
        _defer_uncertain_completion(
            job,
            failure_code=queue_failure_code,
            message=queue_failure_message,
        )
        return

    if not isinstance(history, Mapping):
        _defer_uncertain_completion(
            job,
            failure_code=queue_failure_code,
            message=queue_failure_message,
        )
        return
    entry = history.get(job.prompt_id)
    if entry is None:
        _defer_uncertain_completion(
            job,
            failure_code=queue_failure_code,
            message=queue_failure_message,
        )
        return
    if not isinstance(entry, Mapping):
        _defer_uncertain_completion(
            job,
            failure_code=queue_failure_code,
            message=queue_failure_message,
        )
        return

    try:
        status = entry.get("status")
        if not isinstance(status, Mapping):
            raise ValueError("history status must be a mapping")
        status_str = status.get("status_str")
        if status_str not in {"success", "error"}:
            raise ValueError("history status is not terminal")
        artifacts_info = get_output_artifacts(
            history,
            job.prompt_id,
            workflow=job.params.get("workflow_json"),
        )
    except Exception:
        _defer_uncertain_completion(
            job,
            failure_code=queue_failure_code,
            message=queue_failure_message,
        )
        return

    job.completion_polls = 0
    _release_running(job)  # 已是終局，先釋放槽

    if status_str == "error":
        try:
            node_errors = structure_execution_error(status)
        except Exception:
            node_errors = []
            logger.warning(
                "Could not structure ComfyUI execution error for job %s",
                job.job_id,
            )
        reason = node_errors[0]["reason"] if node_errors else "ComfyUI execution error"
        _record_failure(job, RuntimeError(reason), node_errors)
        logger.error("Job %s failed during ComfyUI execution: %s", job.job_id, reason)
        return

    if job.batch_index is not None:
        artifacts_info = [
            artifact
            for artifact in artifacts_info
            if artifact.get("artifact_type") == "image"
            and artifact.get("source_node_type") == "SaveImage"
        ]
        if not artifacts_info:
            message = "generation finished without a SaveImage artifact"
            _record_failure(
                job,
                RuntimeError(message),
                recording_error={
                    "code": "no_saveimage_artifact",
                    "message": message,
                },
            )
            logger.warning(
                "Independent member %s finished without SaveImage output",
                job.job_id,
            )
            return

    if not artifacts_info:
        message = "generation finished with no supported output artifact"
        _record_failure(
            job,
            RuntimeError(message),
            recording_error={
                "code": "no_supported_output_artifact",
                "message": message,
            },
        )
        logger.warning("Job %s finished with no supported output artifact", job.job_id)
        return

    try:
        n = _save_job_outputs(comfy, job, artifacts_info)
        _record_success(job)
        logger.info("Job %s completed, saved %d artifact(s)", job.job_id, n)
    except Exception as e:
        logger.exception("Failed to save job %s output: %s", job.job_id, e)
        _record_failure(
            job,
            e,
            recording_error={
                "code": "recording_failed",
                "message": str(e),
            },
        )


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
    reconcile_interrupted_batches(SessionLocal)
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
