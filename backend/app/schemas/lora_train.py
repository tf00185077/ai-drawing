"""
LoRA 訓練 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 4
"""
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


RecipeSchemaVersion = Literal["lora-training-recipe/v1"]
RecipeFieldSource = Literal["caller", "preflight_policy", "server_policy", "derived"]
ModelFamily = Literal["sd15", "sdxl", "anima"]
MixedPrecision = Literal["no", "fp16", "bf16"]
EvidenceStatus = Literal["verified", "unverified", "unavailable"]
RuntimePlatform = Literal["cuda", "mps", "cpu", "unknown"]


class FrozenRecipeModel(BaseModel):
    """Base for immutable canonical recipe values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _FrozenDict(dict):
    """Small JSON-serializable mapping that rejects mutation after validation."""

    @staticmethod
    def _immutable(*_args: object, **_kwargs: object) -> None:
        raise TypeError("canonical recipe mappings are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable

    def __copy__(self) -> "_FrozenDict":
        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> "_FrozenDict":
        return self


def _freeze_dict(value: dict) -> _FrozenDict:
    return _FrozenDict(value)


class RecipeSeed(FrozenRecipeModel):
    mode: Literal["fixed", "random"]
    value: int = Field(ge=0, le=2**32 - 1)
    source: Literal["caller", "preflight_policy", "server_policy"]


class RequestedAnimaRecipe(FrozenRecipeModel):
    qwen3: str | None = None
    vae: str | None = None
    t5_tokenizer_path: str | None = None


class RequestedModelRecipe(FrozenRecipeModel):
    family: ModelFamily | None = None
    checkpoint: str | None = None
    allow_unverified_checkpoint: bool | None = None
    network_module: str | None = None
    network_dim: int | None = Field(default=None, ge=1, le=512)
    network_alpha: int | None = Field(default=None, ge=1, le=512)
    anima: RequestedAnimaRecipe | None = None


class RequestedScopeRecipe(FrozenRecipeModel):
    train_text_encoder: bool | None = None


class RequestedDatasetRecipe(FrozenRecipeModel):
    trigger_token: str | None = None
    resolution: int | None = Field(default=None, ge=256, le=4096)
    batch_size: int | None = Field(default=None, ge=1, le=32)
    keep_tokens: int | None = Field(default=None, ge=0, le=64)
    num_repeats: int | None = Field(default=None, ge=1, le=1000)
    enable_bucket: bool | None = None
    bucket_no_upscale: bool | None = None
    min_bucket_reso: int | None = Field(default=None, ge=64, le=4096)
    max_bucket_reso: int | None = Field(default=None, ge=64, le=8192)
    bucket_reso_steps: int | None = Field(default=None, ge=1, le=1024)


class RequestedWarmup(FrozenRecipeModel):
    mode: Literal["steps", "ratio"]
    value: int | float = Field(ge=0)


class RequestedOptimizationRecipe(FrozenRecipeModel):
    epochs: int | None = Field(default=None, ge=1, le=500)
    learning_rate: str | None = None
    denoiser_learning_rate: str | None = None
    text_encoder_learning_rates: tuple[str, ...] | None = None
    gradient_accumulation_steps: int | None = Field(default=None, ge=1, le=1024)
    optimizer_type: str | None = None
    optimizer_args: tuple[str, ...] | None = None
    lr_scheduler: str | None = None
    lr_scheduler_args: tuple[str, ...] | None = None
    warmup: RequestedWarmup | None = None
    seed: RecipeSeed | None = None
    mixed_precision: MixedPrecision | None = None


class RequestedCachingRecipe(FrozenRecipeModel):
    cache_latents: bool | None = None
    cache_text_encoder_outputs: bool | None = None
    cache_to_disk: bool | None = None


class RequestedExecutionRecipe(FrozenRecipeModel):
    max_data_loader_n_workers: int | None = Field(default=None, ge=0, le=128)
    persistent_data_loader_workers: bool | None = None
    save_every_n_epochs: int | None = Field(default=None, ge=0, le=500)


class RequestedTrainingRecipeV1(FrozenRecipeModel):
    schema_version: RecipeSchemaVersion = "lora-training-recipe/v1"
    expected_recipe_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model: RequestedModelRecipe | None = None
    scope: RequestedScopeRecipe | None = None
    dataset: RequestedDatasetRecipe | None = None
    optimization: RequestedOptimizationRecipe | None = None
    caching: RequestedCachingRecipe | None = None
    execution: RequestedExecutionRecipe | None = None


class EffectiveAnimaRecipe(FrozenRecipeModel):
    qwen3: str
    vae: str | None
    t5_tokenizer_path: str | None


class EffectiveModelRecipe(FrozenRecipeModel):
    family: ModelFamily
    checkpoint: str
    allow_unverified_checkpoint: bool
    network_module: str
    network_dim: int = Field(ge=1, le=512)
    network_alpha: int = Field(ge=1, le=512)
    anima: EffectiveAnimaRecipe | None


class EffectiveScopeRecipe(FrozenRecipeModel):
    denoiser_kind: Literal["unet", "dit"]
    train_denoiser: Literal[True] = True
    train_text_encoder: bool
    native_scope_flag: Literal["--network_train_unet_only"] | None
    verification_status: Literal["source_contract", "runtime_verified", "unverified"]


class EffectiveDatasetRecipe(FrozenRecipeModel):
    trigger_token: str
    class_tokens: str
    resolution: int = Field(ge=256, le=4096)
    batch_size: int = Field(ge=1, le=32)
    keep_tokens: int = Field(ge=0, le=64)
    num_repeats: int = Field(ge=1, le=1000)
    enable_bucket: bool
    bucket_no_upscale: bool
    min_bucket_reso: int = Field(ge=64, le=4096)
    max_bucket_reso: int = Field(ge=64, le=8192)
    bucket_reso_steps: int = Field(ge=1, le=1024)


class EffectiveWarmup(FrozenRecipeModel):
    mode: Literal["steps", "ratio"]
    value: int | float = Field(ge=0)
    resolved_steps: int = Field(ge=0)


class EffectiveOptimizationRecipe(FrozenRecipeModel):
    epochs: int = Field(ge=1, le=500)
    learning_rate: str
    denoiser_learning_rate: str
    text_encoder_learning_rates: tuple[str, ...]
    gradient_accumulation_steps: int = Field(ge=1, le=1024)
    optimizer_type: str
    optimizer_args: tuple[str, ...]
    lr_scheduler: str
    lr_scheduler_args: tuple[str, ...]
    warmup: EffectiveWarmup
    seed: RecipeSeed
    mixed_precision: MixedPrecision


class EffectiveCachingRecipe(FrozenRecipeModel):
    cache_latents: bool
    cache_text_encoder_outputs: bool
    cache_to_disk: bool
    latent_cache_to_disk: bool
    text_encoder_cache_to_disk: bool


class EffectiveExecutionRecipe(FrozenRecipeModel):
    max_data_loader_n_workers: int = Field(ge=0, le=128)
    persistent_data_loader_workers: bool
    save_every_n_epochs: int = Field(ge=0, le=500)
    final_only: bool


class EffectiveServerRecipe(FrozenRecipeModel):
    gradient_checkpointing: bool
    caption_extension: str
    shuffle_caption: bool
    save_model_as: Literal["safetensors"]
    launcher_num_cpu_threads_per_process: int = Field(ge=1, le=128)


class EffectiveTrainingRecipeV1(FrozenRecipeModel):
    schema_version: RecipeSchemaVersion = "lora-training-recipe/v1"
    model: EffectiveModelRecipe
    scope: EffectiveScopeRecipe
    dataset: EffectiveDatasetRecipe
    optimization: EffectiveOptimizationRecipe
    caching: EffectiveCachingRecipe
    execution: EffectiveExecutionRecipe
    server: EffectiveServerRecipe


class ComponentIdentity(FrozenRecipeModel):
    kind: Literal["checkpoint", "text_encoder", "vae", "tokenizer"]
    requested_locator: str | None = None
    resolved_locator: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    modified_time_ns: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    verification_status: EvidenceStatus
    reason: str | None = None
    bypass_used: bool = False


class TrainerCapabilitySnapshot(FrozenRecipeModel):
    platform: RuntimePlatform
    status: EvidenceStatus
    reason: str | None = None
    torch_version: str | None = None
    accelerate_version: str | None = None
    python_version: str | None = None
    supported_mixed_precision: tuple[MixedPrecision, ...] = ()


class RecipePolicySnapshot(FrozenRecipeModel):
    default_checkpoint: str
    default_anima_qwen3: str | None = None
    default_anima_vae: str | None = None
    default_anima_t5_tokenizer_path: str | None = None
    resolution: int = Field(default=1024, ge=256, le=4096)
    batch_size: int = Field(default=4, ge=1, le=32)
    learning_rate: str = "1e-4"
    keep_tokens: int = Field(default=1, ge=0, le=64)
    num_repeats: int = Field(default=10, ge=1, le=1000)
    mixed_precision: MixedPrecision = "no"
    network_dim: int = Field(default=32, ge=1, le=512)
    network_alpha: int = Field(default=16, ge=1, le=512)


class RecipeCompilationContext(FrozenRecipeModel):
    dataset_hash: str = Field(min_length=1)
    profile_hash: str = Field(min_length=1)
    profile_model_family: ModelFamily
    approved_trigger_token: str = Field(min_length=1)
    image_count: int = Field(ge=1)
    policy: RecipePolicySnapshot
    capability: TrainerCapabilitySnapshot
    component_identities: Annotated[
        dict[str, ComponentIdentity],
        AfterValidator(_freeze_dict),
    ]


class TrainingStepPlan(FrozenRecipeModel):
    image_count: int = Field(ge=1)
    num_repeats: int = Field(ge=1)
    train_examples: int = Field(ge=1)
    batch_size: int = Field(ge=1)
    batches_per_epoch: int = Field(ge=1)
    gradient_accumulation_steps: int = Field(ge=1)
    optimizer_steps_per_epoch: int = Field(ge=1)
    epochs: int = Field(ge=1)
    total_optimizer_steps: int = Field(ge=1)
    warmup_steps: int = Field(ge=0)
    process_count: Literal[1] = 1


class EvidenceValue(FrozenRecipeModel):
    status: EvidenceStatus
    value: str | None = None
    reason: str | None = None


class ExecutionEvidence(FrozenRecipeModel):
    status: EvidenceStatus
    reason: str | None = None
    argv: tuple[str, ...] | None = None
    dataset_config_content: str | None = None
    dataset_config_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    launcher: EvidenceValue | None = None
    capability: TrainerCapabilitySnapshot
    sd_scripts_revision: EvidenceValue | None = None


class RecipeCompilationResult(FrozenRecipeModel):
    requested: RequestedTrainingRecipeV1
    effective: EffectiveTrainingRecipeV1
    field_sources: Annotated[
        dict[str, RecipeFieldSource],
        AfterValidator(_freeze_dict),
    ]
    component_identities: Annotated[
        dict[str, ComponentIdentity],
        AfterValidator(_freeze_dict),
    ]
    capability: TrainerCapabilitySnapshot
    step_plan: TrainingStepPlan
    recipe_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_evidence: ExecutionEvidence | None = None


class TrainStartRequest(BaseModel):
    """Canonical public Start transport."""

    model_config = ConfigDict(extra="forbid")

    folder: str = Field(..., min_length=1)
    expected_dataset_hash: str = Field(..., min_length=1)
    expected_profile_hash: str = Field(..., min_length=1)
    recipe: dict[str, Any] | str


class TrainStartResponse(BaseModel):
    """POST /api/lora-train/start 的 Response"""

    job_id: str
    status: str = "queued"
    stage: str | None = None
    dataset_hash: str | None = None
    profile_hash: str | None = None
    normalized_trigger_token: str | None = None
    recipe_schema_version: RecipeSchemaVersion | None = None
    recipe_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    requested_recipe: RequestedTrainingRecipeV1 | None = None
    effective_recipe: EffectiveTrainingRecipeV1 | None = None
    requested_scope: RequestedScopeRecipe | None = None
    effective_scope: EffectiveScopeRecipe | None = None
    field_sources: dict[str, RecipeFieldSource] | None = None
    step_plan: TrainingStepPlan | None = None
    component_identities: dict[str, ComponentIdentity] | None = None
    capability: TrainerCapabilitySnapshot | None = None
    execution_evidence: ExecutionEvidence | None = None
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


class DatasetProfileSummary(BaseModel):
    """Normalized dataset-local .lora-dataset.json metadata profile."""

    present: bool = False
    valid: bool = True
    dataset_type: str = "unknown"
    trigger_token: str | None = None
    caption_profile: str = "unknown"
    model_family: str = "unknown"
    protected_tags: list[str] = Field(default_factory=list)
    removable_tags: list[str] = Field(default_factory=list)
    auto_train: bool = False
    profile_hash: str | None = None
    warnings: list[ValidationIssue] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)


class DatasetItem(BaseModel):
    """LoRA dataset summary."""

    folder: str
    image_count: int
    caption_count: int
    missing_caption_count: int
    dataset_hash: str
    profile_hash: str | None = None
    profile: DatasetProfileSummary = Field(default_factory=DatasetProfileSummary)
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
    profile_hash: str | None = None
    profile: DatasetProfileSummary = Field(default_factory=DatasetProfileSummary)
    locked: bool = False
    files: list[DatasetFileItem] = Field(default_factory=list)
    trigger_token_candidates: list[str] = Field(default_factory=list)
    validation: DatasetValidateResponse | None = None


class DatasetMetadataRequest(BaseModel):
    """Proposed dataset metadata profile payload."""

    profile: Any = Field(default_factory=dict)


class DatasetMetadataUpdateRequest(DatasetMetadataRequest):
    """Dataset metadata update request with optimistic conflict protection."""

    expected_profile_hash: str | None = None


class DatasetMetadataResponse(BaseModel):
    """Dataset metadata get/validate/update response."""

    ok: bool = True
    folder: str
    valid: bool
    profile_hash: str | None = None
    profile: DatasetProfileSummary = Field(default_factory=DatasetProfileSummary)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)


class DatasetMetadataUpdateResponse(DatasetMetadataResponse):
    """Dataset metadata update response."""

    updated: bool = False


class DatasetAgentSummary(BaseModel):
    """Dataset-level summary for agent inspection."""

    folder: str
    image_count: int
    caption_count: int
    missing_caption_count: int
    locked: bool = False
    trigger_token_candidates: list[str] = Field(default_factory=list)


class DatasetProfileValidationSummary(BaseModel):
    """Profile validation fields for agent inspection."""

    valid: bool
    warnings: list[ValidationIssue] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)


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


class DatasetAgentInspectionResponse(BaseModel):
    """Agent-ready LoRA dataset inspection summary."""

    ok: bool = True
    folder: str
    dataset_hash: str
    profile_hash: str | None = None
    dataset: DatasetAgentSummary
    profile: DatasetProfileSummary = Field(default_factory=DatasetProfileSummary)
    profile_validation: DatasetProfileValidationSummary
    caption_suitability: DatasetCaptionAssessmentResponse
    validation: DatasetValidateResponse | None = None


class DatasetCurationFileChange(BaseModel):
    """One deterministic curation decision for a dataset caption file."""

    path: str
    image_path: str
    before: str
    after: str
    changed: bool
    status: Literal["changed", "unchanged", "skipped", "review_required", "restored"]
    reasons: list[str] = Field(default_factory=list)
    blocked: bool = False
    review_required: bool = False
    manual: bool = False
    manual_reason: str | None = None
    manual_overwrite_approved: bool = False
    outlier_flags: list[str] = Field(default_factory=list)
    removed_tags: list[str] = Field(default_factory=list)
    duplicate_tags: list[str] = Field(default_factory=list)
    protected_tags: list[str] = Field(default_factory=list)


class DatasetCurationSummary(BaseModel):
    """Summary counts for a dataset curation plan or operation."""

    total_files: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    blocked_count: int = 0
    review_required_count: int = 0
    manual_count: int = 0
    outlier_count: int = 0


class DatasetCurationRequest(BaseModel):
    """Dataset curation dry-run, apply, or rollback request."""

    folder: str = Field(..., min_length=1)
    mode: Literal["dry_run", "apply", "rollback"] = "dry_run"
    trigger_token: str | None = None
    protected_tags: list[str] | None = None
    removable_tags: list[str] | None = None
    expected_dataset_hash: str | None = None
    expected_profile_hash: str | None = None
    backup_id: str | None = None
    approved_manual_overwrite_paths: list[str] = Field(default_factory=list)


class DatasetCurationResponse(BaseModel):
    """Dataset curation plan/apply/rollback response."""

    ok: bool = True
    mode: Literal["dry_run", "apply", "rollback"]
    folder: str
    normalized_trigger_token: str | None = None
    dataset_hash: str | None = None
    profile_hash: str | None = None
    dataset_hash_before: str | None = None
    dataset_hash_after: str | None = None
    backup_id: str | None = None
    changes: list[DatasetCurationFileChange] = Field(default_factory=list)
    summary: DatasetCurationSummary = Field(default_factory=DatasetCurationSummary)
    changed_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    manually_overwritten_files: list[str] = Field(default_factory=list)
    restored_files: list[str] = Field(default_factory=list)


class TrainingParameterSuggestion(BaseModel):
    """Advisory LoRA training parameters with deterministic rationale."""

    params: dict[str, Any] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)


class TrainingDecisionPreflightRequest(BaseModel):
    """Side-effect-free training decision preflight request."""

    folder: str = Field(..., min_length=1)
    trigger_token: str | None = None
    expected_dataset_hash: str | None = None
    expected_profile_hash: str | None = None
    recipe: dict[str, Any] | str | None = None


class TrainingStartPayload(FrozenRecipeModel):
    folder: str = Field(min_length=1)
    expected_dataset_hash: str = Field(min_length=1)
    expected_profile_hash: str = Field(min_length=1)
    recipe: RequestedTrainingRecipeV1


class TrainingDecisionPreflightResponse(BaseModel):
    """Agent-readable deterministic LoRA training decision."""

    ok: bool = True
    folder: str
    decision: Literal["train", "needs_review", "do_not_train"]
    reasons: list[str] = Field(default_factory=list)
    blocking_issues: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    dataset_hash: str | None = None
    profile_hash: str | None = None
    normalized_trigger_token: str | None = None
    requested_recipe: RequestedTrainingRecipeV1 | None = None
    effective_recipe: EffectiveTrainingRecipeV1 | None = None
    requested_scope: RequestedScopeRecipe | None = None
    effective_scope: EffectiveScopeRecipe | None = None
    field_sources: dict[str, RecipeFieldSource] | None = None
    step_plan: TrainingStepPlan | None = None
    component_identities: dict[str, ComponentIdentity] | None = None
    capability: TrainerCapabilitySnapshot | None = None
    execution_evidence: ExecutionEvidence | None = None
    recipe_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    policy_rationale: list[str] = Field(default_factory=list)
    start_payload: TrainingStartPayload | None = None
    suggested_params: TrainingParameterSuggestion | None = None


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
    profile_hash: str | None = None
    normalized_trigger_token: str | None = None
    log_path: str | None = None
    log_tail_lines: int | None = None
    log_truncated: bool | None = None
    output_path: str | None = None
    registered_lora_name: str | None = None
    registration_error: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None
    recipe_schema_version: RecipeSchemaVersion | None = None
    recipe_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    requested_recipe: RequestedTrainingRecipeV1 | None = None
    effective_recipe: EffectiveTrainingRecipeV1 | None = None
    requested_scope: RequestedScopeRecipe | None = None
    effective_scope: EffectiveScopeRecipe | None = None
    field_sources: dict[str, RecipeFieldSource] | None = None
    step_plan: TrainingStepPlan | None = None
    component_identities: dict[str, ComponentIdentity] | None = None
    capability: TrainerCapabilitySnapshot | None = None
    execution_evidence: ExecutionEvidence | None = None
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
    """LoRA smoke-test request.

    For diffusion-model families (e.g. Anima) the component overrides take
    precedence over values derived from the training job params; unset values
    fall back to those job params.
    """

    prompt: str | None = None
    negative_prompt: str | None = None
    checkpoint: str | None = None
    diffusion_model: str | None = None
    text_encoder: str | None = None
    vae: str | None = None


class LoraSmokeTestResponse(BaseModel):
    """LoRA smoke-test response."""

    ok: bool
    job_id: str
    registered_lora_name: str | None = None
    smoke_test_status: str
    generation_job_id: str | None = None
    artifact: str | None = None
    error: str | None = None
