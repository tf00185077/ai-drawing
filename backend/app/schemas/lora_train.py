"""
LoRA 訓練 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 4
"""
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class TrainStartRequest(BaseModel):
    """POST /api/lora-train/start 的 Request Body"""

    folder: str = Field(..., min_length=1)
    checkpoint: str | None = None
    trigger_token: str | None = None
    expected_dataset_hash: str | None = None
    model_family: str | None = None  # sd15 | sdxl | anima；指定時優先於 sdxl
    anima_qwen3: str | None = Field(
        default=None,
        validation_alias=AliasChoices("anima_qwen3", "qwen3"),
        description="Anima/Qwen3 text encoder path；也接受 qwen3 alias",
    )
    anima_vae: str | None = Field(
        default=None,
        validation_alias=AliasChoices("anima_vae", "vae"),
        description="Anima/Qwen-Image VAE path；也接受 vae alias",
    )
    anima_t5_tokenizer_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("anima_t5_tokenizer_path", "t5_tokenizer_path"),
        description="Anima T5 tokenizer path；也接受 t5_tokenizer_path alias",
    )
    sdxl: bool | None = None  # True: SDXL 腳本；False: SD1.x；None: 用 config
    epochs: int = Field(default=10, ge=1, le=500)
    # 以下未帶入時使用 config 預設值
    resolution: int | None = Field(default=None, ge=256, le=2048)
    batch_size: int | None = Field(default=None, ge=1, le=32)
    learning_rate: str | None = None
    class_tokens: str | None = None
    keep_tokens: int | None = Field(default=None, ge=0, le=10)
    num_repeats: int | None = Field(default=None, ge=1, le=100)
    mixed_precision: str | None = None  # fp16 | bf16 | fp32 | no; fp32 maps to Kohya CLI no
    network_module: str | None = None
    network_dim: int | None = Field(default=None, ge=1, le=128)
    network_alpha: int | None = Field(default=None, ge=1, le=128)


class TrainStartResponse(BaseModel):
    """POST /api/lora-train/start 的 Response"""

    job_id: str
    status: str = "queued"
    stage: str | None = None
    dataset_hash: str | None = None
    normalized_trigger_token: str | None = None
    message: str | None = None


class TrainJobInfo(BaseModel):
    """訓練任務資訊"""

    job_id: str
    folder: str
    progress: float | None = None
    epoch: int | None = None
    total_epochs: int | None = None


class TrainLastResult(BaseModel):
    """最近一次訓練結果"""

    folder: str
    success: bool
    path: str | None = None
    error: str | None = None


class TrainStatusResponse(BaseModel):
    """GET /api/lora-train/status 的 Response"""

    status: str = "idle"  # idle | running | queued
    current_job: TrainJobInfo | None = None
    queue: list[TrainJobInfo] = Field(default_factory=list)
    last_result: TrainLastResult | None = None


class FolderItem(BaseModel):
    """可訓練的資料夾"""

    folder: str
    image_count: int


class TrainFoldersResponse(BaseModel):
    """GET /api/lora-train/folders 的 Response"""

    folders: list[FolderItem] = Field(default_factory=list)


class TriggerCandidate(BaseModel):
    """符合自動觸發條件的資料夾"""

    folder: str
    image_count: int


class TriggerCheckResponse(BaseModel):
    """POST /api/lora-train/trigger-check 的 Response"""

    should_trigger: bool
    candidates: list[TriggerCandidate] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    """Dataset validation issue."""

    code: str
    message: str
    path: str | None = None
    details: dict | None = None


class DatasetFileItem(BaseModel):
    """One image and its matching caption metadata."""

    image_path: str
    caption_path: str | None = None
    caption: str | None = None
    has_caption: bool
    caption_empty: bool = False


class DatasetItem(BaseModel):
    """LoRA dataset summary."""

    folder: str
    image_count: int
    caption_count: int
    missing_caption_count: int
    dataset_hash: str
    locked: bool = False
    trigger_token_candidates: list[str] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    """GET /api/lora-train/datasets response."""

    datasets: list[DatasetItem] = Field(default_factory=list)


class DatasetValidateRequest(BaseModel):
    """Dataset validation request."""

    folder: str = Field(..., min_length=1)
    trigger_token: str = Field(..., min_length=1)
    expected_dataset_hash: str | None = None
    require_lock: bool = False


class DatasetValidateResponse(BaseModel):
    """Dataset validation response."""

    ok: bool
    folder: str
    normalized_trigger_token: str
    dataset_hash: str
    image_count: int
    caption_count: int
    missing_caption_count: int
    warnings: list[ValidationIssue] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)
    locked: bool = False


class DatasetInspectResponse(BaseModel):
    """Detailed dataset inspection response."""

    folder: str
    image_count: int
    caption_count: int
    missing_caption_count: int
    dataset_hash: str
    locked: bool = False
    files: list[DatasetFileItem] = Field(default_factory=list)
    trigger_token_candidates: list[str] = Field(default_factory=list)
    validation: DatasetValidateResponse | None = None


class CaptionTagStat(BaseModel):
    """Caption tag frequency and coverage."""

    tag: str
    count: int
    coverage: float


class CaptionAssessmentMetrics(BaseModel):
    """Deterministic caption dispersion/coherence metrics."""

    total_tag_count: int = 0
    unique_tag_count: int = 0
    repeated_tag_count: int = 0
    rare_tag_count: int = 0
    singleton_tag_ratio: float = 0.0
    repeated_tag_ratio: float = 0.0
    average_tags_per_caption: float = 0.0
    mean_pairwise_jaccard: float = 0.0


class TriggerTokenCoverage(BaseModel):
    """Trigger-token coverage across non-empty caption files."""

    normalized_trigger_token: str | None = None
    covered_count: int = 0
    total_count: int = 0
    coverage: float = 0.0


class DatasetCaptionAssessmentRequest(BaseModel):
    """Dataset caption suitability assessment request."""

    folder: str = Field(..., min_length=1)
    trigger_token: str | None = None


class DatasetCaptionAssessmentResponse(BaseModel):
    """Agent-readable LoRA caption suitability assessment."""

    ok: bool = True
    folder: str
    verdict: Literal["suitable", "needs_review", "not_suitable"]
    reasons: list[str] = Field(default_factory=list)
    dataset_hash: str
    image_count: int
    txt_count: int
    missing_txt_count: int
    empty_txt_count: int
    trigger_token_coverage: TriggerTokenCoverage = Field(default_factory=TriggerTokenCoverage)
    top_tags: list[CaptionTagStat] = Field(default_factory=list)
    rare_tags: list[CaptionTagStat] = Field(default_factory=list)
    metrics: CaptionAssessmentMetrics = Field(default_factory=CaptionAssessmentMetrics)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class CaptionChange(BaseModel):
    """Caption preparation diff."""

    path: str
    before: str
    after: str
    changed: bool


class DatasetPrepareRequest(BaseModel):
    """Dataset caption preparation request."""

    folder: str = Field(..., min_length=1)
    trigger_token: str | None = None
    dry_run: bool = True
    use_ai_cleanup: bool = False
    expected_dataset_hash: str | None = None
    restore_backup_id: str | None = None


class DatasetPrepareResponse(BaseModel):
    """Dataset caption preparation or restore response."""

    ok: bool
    folder: str
    normalized_trigger_token: str | None = None
    changes: list[CaptionChange] = Field(default_factory=list)
    changed_count: int = 0
    unchanged_count: int = 0
    dataset_hash_before: str | None = None
    dataset_hash_after: str | None = None
    backup_id: str | None = None
    restored_files: list[str] = Field(default_factory=list)


class LoraTrainJobStatusResponse(BaseModel):
    """Durable LoRA training job status."""

    ok: bool = True
    job_id: str
    folder: str
    status: str
    stage: str
    progress: float = 0.0
    current_epoch: int | None = None
    total_epochs: int | None = None
    dataset_hash: str | None = None
    normalized_trigger_token: str | None = None
    log_path: str | None = None
    log_tail_lines: int | None = None
    log_truncated: bool | None = None
    output_path: str | None = None
    registered_lora_name: str | None = None
    registration_error: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    params: dict | None = None
    smoke_test_status: str | None = None
    smoke_test_job_id: str | None = None
    smoke_test_artifact: str | None = None
    smoke_test_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    cancel_requested_at: str | None = None


class LoraTrainLogsResponse(BaseModel):
    """Bounded LoRA training logs."""

    ok: bool
    job_id: str
    lines: list[str] = Field(default_factory=list)
    truncated: bool = False
    log_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class LoraTrainCancelResponse(BaseModel):
    """LoRA training cancellation response."""

    ok: bool
    job_id: str
    status: str


class LoraRegistrationResponse(BaseModel):
    """LoRA output registration response."""

    ok: bool
    job_id: str
    output_path: str | None = None
    registered_lora_name: str | None = None
    error: str | None = None


class LoraSmokeTestRequest(BaseModel):
    """LoRA smoke-test request."""

    prompt: str | None = None
    negative_prompt: str | None = None
    checkpoint: str | None = None


class LoraSmokeTestResponse(BaseModel):
    """LoRA smoke-test response."""

    ok: bool
    job_id: str
    registered_lora_name: str | None = None
    smoke_test_status: str
    generation_job_id: str | None = None
    artifact: str | None = None
    error: str | None = None
