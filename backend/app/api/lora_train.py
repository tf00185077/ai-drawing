"""
模組 4：LoRA 訓練與產圖串接 API
訓練執行器、觸發邏輯、Pipeline 自動產圖、佇列管理
契約：docs/api-contract.md
"""
from fastapi import APIRouter, HTTPException, Query

from app.schemas.lora_train import (
    DatasetAgentInspectionResponse,
    DatasetAgentSummary,
    DatasetCaptionAssessmentRequest,
    DatasetCaptionAssessmentResponse,
    DatasetCurationRequest,
    DatasetCurationResponse,
    DatasetInspectResponse,
    DatasetListResponse,
    DatasetMetadataRequest,
    DatasetMetadataResponse,
    DatasetMetadataUpdateRequest,
    DatasetMetadataUpdateResponse,
    DatasetProfileValidationSummary,
    DatasetPrepareRequest,
    DatasetPrepareResponse,
    DatasetValidateRequest,
    DatasetValidateResponse,
    FolderItem,
    LoraSmokeTestRequest,
    LoraSmokeTestResponse,
    LoraTrainCancelResponse,
    LoraTrainJobStatusResponse,
    LoraTrainLogsResponse,
    TrainFoldersResponse,
    TrainJobInfo,
    TrainLastResult,
    TrainStartRequest,
    TrainStartResponse,
    TrainStatusResponse,
    TrainingDecisionPreflightRequest,
    TrainingDecisionPreflightResponse,
    TriggerCandidate,
    TriggerCheckResponse,
)
from app.config import get_settings
from app.services import (
    lora_dataset,
    lora_dataset_assessment,
    lora_dataset_curation,
    lora_trainer,
    lora_training_decision,
)
from app.services.lora_dataset import DatasetServiceError

router = APIRouter(prefix="/api/lora-train", tags=["LoRA 訓練"])


def _dataset_error(exc: DatasetServiceError) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message, "details": exc.details}
    if exc.code in {"dataset_locked", "dataset_hash_mismatch", "profile_hash_mismatch"}:
        return HTTPException(409, detail=detail)
    if exc.code in {"dataset_not_found", "backup_not_found"}:
        return HTTPException(404, detail=detail)
    return HTTPException(400, detail=detail)


def _trainer_error(exc: lora_trainer.TrainerServiceError) -> HTTPException:
    detail = {"code": exc.code, "message": exc.message, "details": exc.details}
    if exc.code in {"dataset_locked", "dataset_hash_mismatch", "job_not_cancellable"}:
        return HTTPException(409, detail=detail)
    if exc.code in {"job_not_found", "log_not_found"}:
        return HTTPException(404, detail=detail)
    return HTTPException(400, detail=detail)


@router.get("/config")
async def get_train_config():
    """取得訓練預設設定（供前端 checkbox 預設值）"""
    settings = get_settings()
    model_family = (getattr(settings, "lora_model_family", "") or "").strip().lower()
    if not model_family:
        model_family = "sdxl" if settings.lora_sdxl else "sd15"
    return {
        "sdxl": settings.lora_sdxl,
        "model_family": model_family,
        "anima_qwen3": getattr(settings, "lora_anima_qwen3", "") or None,
        "anima_vae": getattr(settings, "lora_anima_vae", "") or None,
        "anima_t5_tokenizer_path": getattr(settings, "lora_anima_t5_tokenizer_path", "") or None,
    }


@router.get("/folders", response_model=TrainFoldersResponse)
async def list_training_folders():
    """列出可訓練的資料夾（含圖片數）"""
    items = lora_trainer.list_folders()
    return TrainFoldersResponse(
        folders=[FolderItem(folder=f["folder"], image_count=f["image_count"]) for f in items]
    )


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets():
    """列出 LoRA dataset，含圖片/caption/hash/lock 摘要。"""
    try:
        return DatasetListResponse(datasets=lora_dataset.list_datasets())
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/datasets/prepare", response_model=DatasetPrepareResponse)
async def prepare_dataset(body: DatasetPrepareRequest):
    """Dry-run/apply caption preparation；也可用 restore_backup_id 還原。"""
    try:
        return lora_dataset.prepare_dataset(
            body.folder,
            trigger_token=body.trigger_token,
            dry_run=body.dry_run,
            use_ai_cleanup=body.use_ai_cleanup,
            expected_dataset_hash=body.expected_dataset_hash,
            restore_backup_id=body.restore_backup_id,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/datasets/restore", response_model=DatasetPrepareResponse)
async def restore_dataset(body: DatasetPrepareRequest):
    """還原指定 dataset preparation backup。"""
    if not body.restore_backup_id:
        raise HTTPException(
            400,
            detail={
                "code": "backup_id_required",
                "message": "restore_backup_id is required",
                "details": {},
            },
        )
    try:
        return lora_dataset.restore_dataset(body.folder, body.restore_backup_id)
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/datasets/validate", response_model=DatasetValidateResponse)
async def validate_dataset(body: DatasetValidateRequest):
    """訓練前 dataset validation。"""
    try:
        return lora_dataset.validate_dataset(
            body.folder,
            trigger_token=body.trigger_token,
            expected_dataset_hash=body.expected_dataset_hash,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/datasets/caption-assessment", response_model=DatasetCaptionAssessmentResponse)
async def assess_dataset_captions(body: DatasetCaptionAssessmentRequest):
    """以 deterministic 統計評估 dataset captions 是否適合訓練。"""
    try:
        return lora_dataset_assessment.assess_caption_suitability(
            body.folder,
            trigger_token=body.trigger_token,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/datasets/curate", response_model=DatasetCurationResponse)
async def curate_dataset(body: DatasetCurationRequest):
    """Dry-run/apply/rollback deterministic dataset caption curation."""
    try:
        if body.mode == "dry_run":
            return lora_dataset_curation.plan_curation(
                body.folder,
                trigger_token=body.trigger_token,
                protected_tags=body.protected_tags,
                removable_tags=body.removable_tags,
                approved_manual_overwrite_paths=body.approved_manual_overwrite_paths,
            )
        if body.mode == "apply":
            return lora_dataset_curation.apply_curation(
                body.folder,
                expected_dataset_hash=body.expected_dataset_hash,
                expected_profile_hash=body.expected_profile_hash,
                trigger_token=body.trigger_token,
                protected_tags=body.protected_tags,
                removable_tags=body.removable_tags,
                approved_manual_overwrite_paths=body.approved_manual_overwrite_paths,
            )
        if not body.backup_id:
            raise HTTPException(
                400,
                detail={
                    "code": "backup_id_required",
                    "message": "backup_id is required for curation rollback",
                    "details": {},
                },
            )
        return lora_dataset_curation.rollback_curation(
            body.folder,
            body.backup_id,
            approved_manual_overwrite_paths=body.approved_manual_overwrite_paths,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post(
    "/datasets/training-decision-preflight",
    response_model=TrainingDecisionPreflightResponse,
)
async def training_decision_preflight(body: TrainingDecisionPreflightRequest):
    """Deterministic agent decision preflight; never starts or enqueues training."""
    try:
        return lora_training_decision.decide_training_preflight(
            body.folder,
            trigger_token=body.trigger_token,
            expected_dataset_hash=body.expected_dataset_hash,
            expected_profile_hash=body.expected_profile_hash,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.get("/datasets/{folder:path}/metadata", response_model=DatasetMetadataResponse)
async def get_dataset_metadata(folder: str):
    """讀取 dataset-local .lora-dataset.json metadata profile。"""
    try:
        return lora_dataset.get_metadata_profile(folder)
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/datasets/{folder:path}/metadata/validate", response_model=DatasetMetadataResponse)
async def validate_dataset_metadata(folder: str, body: DatasetMetadataRequest):
    """驗證 proposed metadata profile；不寫入 .lora-dataset.json。"""
    try:
        return lora_dataset.validate_metadata_profile(folder, body.profile)
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.put("/datasets/{folder:path}/metadata", response_model=DatasetMetadataUpdateResponse)
async def update_dataset_metadata(folder: str, body: DatasetMetadataUpdateRequest):
    """以 profile_hash conflict protection 更新 dataset metadata profile。"""
    try:
        return lora_dataset.update_metadata_profile(
            folder,
            body.profile,
            expected_profile_hash=body.expected_profile_hash,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.get("/datasets/{folder:path}/agent-inspect", response_model=DatasetAgentInspectionResponse)
async def agent_inspect_dataset(folder: str, trigger_token: str | None = Query(default=None)):
    """組合 dataset/profile/caption suitability signals 給 agent 做 pre-training review。"""
    try:
        inspected = lora_dataset.inspect_dataset(folder)
        token = trigger_token or inspected.profile.trigger_token
        if not token and inspected.trigger_token_candidates:
            token = inspected.trigger_token_candidates[0]
        validation = (
            lora_dataset.validate_dataset(inspected.folder, trigger_token=token)
            if token
            else None
        )
        caption_suitability = lora_dataset_assessment.assess_caption_suitability(
            inspected.folder,
            trigger_token=token,
        )
        return DatasetAgentInspectionResponse(
            folder=inspected.folder,
            dataset_hash=inspected.dataset_hash,
            profile_hash=inspected.profile_hash,
            dataset=DatasetAgentSummary(
                folder=inspected.folder,
                image_count=inspected.image_count,
                caption_count=inspected.caption_count,
                missing_caption_count=inspected.missing_caption_count,
                locked=inspected.locked,
                trigger_token_candidates=inspected.trigger_token_candidates,
            ),
            profile=inspected.profile,
            profile_validation=DatasetProfileValidationSummary(
                valid=inspected.profile.valid,
                warnings=inspected.profile.warnings,
                errors=inspected.profile.errors,
            ),
            caption_suitability=caption_suitability,
            validation=validation,
        )
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.get("/datasets/{folder:path}", response_model=DatasetInspectResponse)
async def inspect_dataset(folder: str, trigger_token: str | None = Query(default=None)):
    """檢查單一 dataset 檔案、hash、trigger token 與可選 validation。"""
    try:
        inspected = lora_dataset.inspect_dataset(folder)
        token = trigger_token or (inspected.trigger_token_candidates[0] if inspected.trigger_token_candidates else None)
        if token:
            inspected.validation = lora_dataset.validate_dataset(
                inspected.folder,
                trigger_token=token,
            )
        return inspected
    except DatasetServiceError as exc:
        raise _dataset_error(exc)


@router.post("/start", response_model=TrainStartResponse, status_code=202)
async def start_training(body: TrainStartRequest):
    """手動觸發 LoRA 訓練。訓練完成後如需生圖，請另行呼叫生圖 API。"""
    try:
        job_id = lora_trainer.enqueue(
            body.folder,
            checkpoint=body.checkpoint,
            model_family=body.model_family,
            anima_qwen3=body.anima_qwen3,
            anima_vae=body.anima_vae,
            anima_t5_tokenizer_path=body.anima_t5_tokenizer_path,
            sdxl=body.sdxl,
            epochs=body.epochs,
            resolution=body.resolution,
            batch_size=body.batch_size,
            learning_rate=body.learning_rate,
            class_tokens=body.class_tokens,
            keep_tokens=body.keep_tokens,
            num_repeats=body.num_repeats,
            mixed_precision=body.mixed_precision,
            network_module=body.network_module,
            network_dim=body.network_dim,
            network_alpha=body.network_alpha,
            trigger_token=body.trigger_token,
            expected_dataset_hash=body.expected_dataset_hash,
        )
        try:
            job_status = lora_trainer.get_job_status(job_id)
        except lora_trainer.TrainerServiceError:
            job_status = {"status": "queued", "stage": "queued", "dataset_hash": None, "normalized_trigger_token": None}
    except lora_trainer.TrainerServiceError as e:
        raise _trainer_error(e)
    except ValueError as e:
        msg = str(e)
        if "已在佇列" in msg or "訓練中" in msg:
            raise HTTPException(409, msg)
        raise HTTPException(400, msg)
    return TrainStartResponse(
        job_id=job_id,
        status=job_status["status"] if job_status else "queued",
        stage=job_status.get("stage") if job_status else "queued",
        dataset_hash=job_status.get("dataset_hash") if job_status else None,
        normalized_trigger_token=job_status.get("normalized_trigger_token") if job_status else None,
        message="已加入訓練佇列",
    )


@router.post("/clear")
async def clear_training_queue():
    """清除訓練佇列，停止正在執行的任務"""
    count = lora_trainer.clear_queue()
    return {"cleared": count, "message": f"已清除 {count} 個任務"}


@router.get("/status", response_model=TrainStatusResponse)
async def get_training_status():
    """訓練進度與佇列狀態"""
    st = lora_trainer.get_status()
    current = st.get("current_job")
    current_job = None
    if current:
        current_job = TrainJobInfo(
            job_id=current["job_id"],
            folder=current["folder"],
            progress=current.get("progress"),
            epoch=current.get("epoch"),
            total_epochs=current.get("total_epochs"),
        )
    queue_list = [
        TrainJobInfo(job_id=q["job_id"], folder=q["folder"])
        for q in st.get("queue", [])
    ]
    last = st.get("last_result")
    last_result = TrainLastResult(**last) if last else None
    return TrainStatusResponse(
        status=st["status"],
        current_job=current_job,
        queue=queue_list,
        last_result=last_result,
    )


@router.get("/jobs/{job_id}", response_model=LoraTrainJobStatusResponse)
async def get_training_job(job_id: str):
    """以 job_id 查詢 durable LoRA training job。"""
    try:
        result = lora_trainer.get_job_status(job_id)
    except lora_trainer.TrainerServiceError as exc:
        raise _trainer_error(exc)
    return LoraTrainJobStatusResponse(**result)


@router.get("/jobs/{job_id}/logs", response_model=LoraTrainLogsResponse)
async def get_training_job_logs(
    job_id: str,
    lines: int = Query(default=100, ge=1, le=1000),
):
    """取得 bounded per-job log tail。"""
    try:
        return LoraTrainLogsResponse(**lora_trainer.get_job_logs(job_id, line_limit=lines))
    except lora_trainer.TrainerServiceError as exc:
        raise _trainer_error(exc)


@router.post("/jobs/{job_id}/cancel", response_model=LoraTrainCancelResponse)
async def cancel_training_job(job_id: str):
    """取消 queued/running LoRA training job。"""
    try:
        return LoraTrainCancelResponse(**lora_trainer.cancel_job(job_id))
    except lora_trainer.TrainerServiceError as exc:
        raise _trainer_error(exc)


@router.post("/jobs/{job_id}/smoke-test", response_model=LoraSmokeTestResponse)
async def smoke_test_training_job(job_id: str, body: LoraSmokeTestRequest | None = None):
    """使用已註冊 LoRA 提交一筆 smoke-test generation。"""
    try:
        return LoraSmokeTestResponse(**lora_trainer.smoke_test_job(job_id, body or LoraSmokeTestRequest()))
    except lora_trainer.TrainerServiceError as exc:
        raise _trainer_error(exc)


@router.post("/trigger-check", response_model=TriggerCheckResponse)
async def check_auto_trigger():
    """檢查是否符合自動觸發條件（圖片數 ≥ 門檻），符合者自動加入訓練佇列"""
    result = lora_trainer.trigger_check()
    candidates = [
        TriggerCandidate(folder=c["folder"], image_count=c["image_count"])
        for c in result["candidates"]
    ]
    return TriggerCheckResponse(
        should_trigger=result["should_trigger"],
        candidates=candidates,
    )
