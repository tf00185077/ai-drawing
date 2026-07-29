/**
 * API 型別定義
 * 與 docs/api-contract.md 對齊，供 API 呼叫與型別檢查使用
 */

// ---- 生圖 ----

export interface GenerateRequest {
  checkpoint?: string;
  lora?: string;
  prompt: string;
  negative_prompt?: string;
  seed?: number;
  steps?: number;
  cfg?: number;
}

export interface GenerateResponse {
  job_id: string;
  status: string;
  message?: string;
}

export interface QueueItem {
  job_id: string;
  status: string;
  submitted_at?: string;
  prompt_id?: string;
}

export interface QueueStatusResponse {
  queue_running: QueueItem[];
  queue_pending: QueueItem[];
}

// ---- 圖庫 ----

export interface GalleryItem {
  id: number;
  image_path: string;
  image_url?: string | null;
  checkpoint: string | null;
  lora: string | null;
  seed: number | null;
  steps: number | null;
  cfg: number | null;
  prompt: string | null;
  negative_prompt: string | null;
  created_at: string;
}

export interface GalleryListResponse {
  items: GalleryItem[];
  total: number;
}

export interface RerunResponse {
  job_id: string;
  status: string;
  message?: string;
}

// ---- LoRA 文件 ----

export interface UploadResponse {
  uploaded: number;
  items?: { filename: string; path: string; caption_path: string }[];
}

export interface BatchPrefixRequest {
  images: string[];
  prefix: string;
}

export interface BatchPrefixResponse {
  updated: number;
  failed: string[];
}

// ---- LoRA 訓練 ----

export interface FolderItem {
  folder: string;
  image_count: number;
}

export interface TrainFoldersResponse {
  folders: FolderItem[];
}

export type RecipeSchemaVersion = "lora-training-recipe/v1";
export type RecipeFieldSource =
  | "caller"
  | "preflight_policy"
  | "server_policy"
  | "derived";
export type ModelFamily = "sd15" | "sdxl" | "anima";
export type MixedPrecision = "no" | "fp16" | "bf16";
export type EvidenceStatus = "verified" | "unverified" | "unavailable";
export type RuntimePlatform = "cuda" | "mps" | "cpu" | "unknown";

export interface RecipeSeed {
  mode: "fixed" | "random";
  value: number;
  source: "caller" | "preflight_policy" | "server_policy";
}

export interface RequestedAnimaRecipe {
  qwen3?: string | null;
  vae?: string | null;
  t5_tokenizer_path?: string | null;
}

export interface RequestedModelRecipe {
  family?: ModelFamily | null;
  checkpoint?: string | null;
  allow_unverified_checkpoint?: boolean | null;
  network_module?: string | null;
  network_dim?: number | null;
  network_alpha?: number | null;
  anima?: RequestedAnimaRecipe | null;
}

export interface RequestedScopeRecipe {
  train_text_encoder?: boolean | null;
}

export interface RequestedDatasetRecipe {
  trigger_token?: string | null;
  resolution?: number | null;
  batch_size?: number | null;
  keep_tokens?: number | null;
  num_repeats?: number | null;
  enable_bucket?: boolean | null;
  bucket_no_upscale?: boolean | null;
  min_bucket_reso?: number | null;
  max_bucket_reso?: number | null;
  bucket_reso_steps?: number | null;
}

export interface RequestedWarmup {
  mode: "steps" | "ratio";
  value: number;
}

export interface RequestedOptimizationRecipe {
  epochs?: number | null;
  learning_rate?: string | null;
  denoiser_learning_rate?: string | null;
  text_encoder_learning_rates?: string[] | null;
  gradient_accumulation_steps?: number | null;
  optimizer_type?: string | null;
  optimizer_args?: string[] | null;
  lr_scheduler?: string | null;
  lr_scheduler_args?: string[] | null;
  warmup?: RequestedWarmup | null;
  seed?: RecipeSeed | null;
  mixed_precision?: MixedPrecision | null;
}

export interface RequestedCachingRecipe {
  cache_latents?: boolean | null;
  cache_text_encoder_outputs?: boolean | null;
  cache_to_disk?: boolean | null;
}

export interface RequestedExecutionRecipe {
  max_data_loader_n_workers?: number | null;
  persistent_data_loader_workers?: boolean | null;
  save_every_n_epochs?: number | null;
}

export interface TrainingRecipeHints {
  schema_version?: RecipeSchemaVersion;
  expected_recipe_hash?: string | null;
  model?: RequestedModelRecipe | null;
  scope?: RequestedScopeRecipe | null;
  dataset?: RequestedDatasetRecipe | null;
  optimization?: RequestedOptimizationRecipe | null;
  caching?: RequestedCachingRecipe | null;
  execution?: RequestedExecutionRecipe | null;
}

export type TrainingRecipeTransport =
  | TrainingRecipeHints
  | Record<string, unknown>
  | string;

export interface RequestedTrainingRecipeV1 extends TrainingRecipeHints {
  schema_version: RecipeSchemaVersion;
}

export interface TrainingStartRecipeV1 extends RequestedTrainingRecipeV1 {
  expected_recipe_hash: string;
  optimization: RequestedOptimizationRecipe & {
    seed: RecipeSeed;
  };
}

export interface EffectiveAnimaRecipe {
  qwen3: string;
  vae: string | null;
  t5_tokenizer_path: string | null;
}

export interface EffectiveModelRecipe {
  family: ModelFamily;
  checkpoint: string;
  allow_unverified_checkpoint: boolean;
  network_module: string;
  network_dim: number;
  network_alpha: number;
  anima: EffectiveAnimaRecipe | null;
}

export interface EffectiveScopeRecipe {
  denoiser_kind: "unet" | "dit";
  train_denoiser: true;
  train_text_encoder: boolean;
  native_scope_flag: "--network_train_unet_only" | null;
  verification_status:
    | "source_contract"
    | "runtime_verified"
    | "unverified";
}

export interface EffectiveDatasetRecipe {
  trigger_token: string;
  class_tokens: string;
  resolution: number;
  batch_size: number;
  keep_tokens: number;
  num_repeats: number;
  enable_bucket: boolean;
  bucket_no_upscale: boolean;
  min_bucket_reso: number;
  max_bucket_reso: number;
  bucket_reso_steps: number;
}

export interface EffectiveWarmup {
  mode: "steps" | "ratio";
  value: number;
  resolved_steps: number;
}

export interface EffectiveOptimizationRecipe {
  epochs: number;
  learning_rate: string;
  denoiser_learning_rate: string;
  text_encoder_learning_rates: string[];
  gradient_accumulation_steps: number;
  optimizer_type: string;
  optimizer_args: string[];
  lr_scheduler: string;
  lr_scheduler_args: string[];
  warmup: EffectiveWarmup;
  seed: RecipeSeed;
  mixed_precision: MixedPrecision;
}

export interface EffectiveCachingRecipe {
  cache_latents: boolean;
  cache_text_encoder_outputs: boolean;
  cache_to_disk: boolean;
  latent_cache_to_disk: boolean;
  text_encoder_cache_to_disk: boolean;
}

export interface EffectiveExecutionRecipe {
  max_data_loader_n_workers: number;
  persistent_data_loader_workers: boolean;
  save_every_n_epochs: number;
  final_only: boolean;
}

export interface EffectiveServerRecipe {
  gradient_checkpointing: boolean;
  caption_extension: string;
  shuffle_caption: boolean;
  save_model_as: "safetensors";
  launcher_num_cpu_threads_per_process: number;
}

export interface EffectiveTrainingRecipeV1 {
  schema_version: RecipeSchemaVersion;
  model: EffectiveModelRecipe;
  scope: EffectiveScopeRecipe;
  dataset: EffectiveDatasetRecipe;
  optimization: EffectiveOptimizationRecipe;
  caching: EffectiveCachingRecipe;
  execution: EffectiveExecutionRecipe;
  server: EffectiveServerRecipe;
}

export interface ComponentIdentity {
  kind: "checkpoint" | "text_encoder" | "vae" | "tokenizer";
  requested_locator: string | null;
  resolved_locator: string | null;
  size_bytes: number | null;
  modified_time_ns: number | null;
  sha256: string | null;
  verification_status: EvidenceStatus;
  reason: string | null;
  bypass_used: boolean;
}

export interface TrainerCapabilitySnapshot {
  platform: RuntimePlatform;
  status: EvidenceStatus;
  reason: string | null;
  torch_version: string | null;
  accelerate_version: string | null;
  python_version: string | null;
  supported_mixed_precision: MixedPrecision[];
}

export interface TrainingStepPlan {
  image_count: number;
  num_repeats: number;
  train_examples: number;
  batch_size: number;
  batches_per_epoch: number;
  gradient_accumulation_steps: number;
  optimizer_steps_per_epoch: number;
  epochs: number;
  total_optimizer_steps: number;
  warmup_steps: number;
  process_count: 1;
}

export interface EvidenceValue {
  status: EvidenceStatus;
  value: string | null;
  reason: string | null;
}

export interface ExecutionEvidence {
  status: EvidenceStatus;
  reason: string | null;
  argv: string[] | null;
  dataset_config_content: string | null;
  dataset_config_sha256: string | null;
  launcher: EvidenceValue | null;
  capability: TrainerCapabilitySnapshot;
  sd_scripts_revision: EvidenceValue | null;
}

export interface TrainStartRequest {
  folder: string;
  expected_dataset_hash: string;
  expected_profile_hash: string;
  recipe: TrainingRecipeTransport;
}

export interface TrainingStartPayload {
  folder: string;
  expected_dataset_hash: string;
  expected_profile_hash: string;
  recipe: TrainingStartRecipeV1;
}

export interface TrainStartResponse {
  job_id: string;
  status: string;
  stage?: string;
  dataset_hash?: string | null;
  profile_hash?: string | null;
  normalized_trigger_token?: string | null;
  recipe_schema_version?: RecipeSchemaVersion | null;
  recipe_hash?: string | null;
  requested_recipe?: RequestedTrainingRecipeV1 | null;
  effective_recipe?: EffectiveTrainingRecipeV1 | null;
  requested_scope?: RequestedScopeRecipe | null;
  effective_scope?: EffectiveScopeRecipe | null;
  field_sources?: Record<string, RecipeFieldSource> | null;
  step_plan?: TrainingStepPlan | null;
  component_identities?: Record<string, ComponentIdentity> | null;
  capability?: TrainerCapabilitySnapshot | null;
  execution_evidence?: ExecutionEvidence | null;
  message?: string;
}

export interface TrainingDecisionIssue {
  code: string;
  message: string;
  path?: string | null;
  details?: Record<string, unknown> | null;
}

export interface TrainingDecisionPreflightRequest {
  folder: string;
  trigger_token?: string;
  expected_dataset_hash?: string;
  expected_profile_hash?: string;
  recipe?: TrainingRecipeTransport;
}

export interface TrainingParameterSuggestion {
  params: Record<string, unknown>;
  rationale: string[];
}

export interface TrainingDecisionPreflightResponse {
  ok: boolean;
  folder: string;
  decision: "train" | "needs_review" | "do_not_train";
  reasons: string[];
  blocking_issues: TrainingDecisionIssue[];
  warnings: TrainingDecisionIssue[];
  next_actions: string[];
  dataset_hash: string | null;
  profile_hash: string | null;
  normalized_trigger_token: string | null;
  requested_recipe: RequestedTrainingRecipeV1 | null;
  effective_recipe: EffectiveTrainingRecipeV1 | null;
  requested_scope: RequestedScopeRecipe | null;
  effective_scope: EffectiveScopeRecipe | null;
  field_sources: Record<string, RecipeFieldSource> | null;
  step_plan: TrainingStepPlan | null;
  component_identities: Record<string, ComponentIdentity> | null;
  capability: TrainerCapabilitySnapshot | null;
  execution_evidence: ExecutionEvidence | null;
  recipe_hash: string | null;
  policy_rationale: string[];
  start_payload: TrainingStartPayload | null;
  suggested_params: TrainingParameterSuggestion | null;
}

export interface TrainJobInfo {
  job_id: string;
  folder: string;
  progress?: number;
  epoch?: number;
  total_epochs?: number;
}

export interface TrainLastResult {
  folder: string;
  success: boolean;
  path?: string | null;
  error?: string | null;
}

export interface TrainStatusResponse {
  status: "idle" | "running" | "queued";
  current_job?: TrainJobInfo;
  queue: TrainJobInfo[];
  last_result?: TrainLastResult | null;
}

export interface TriggerCheckResponse {
  should_trigger: boolean;
  candidates: { folder: string; image_count: number }[];
}

// ---- 進階 / 分析（Prompt 模板、Analytics） ----

export interface PromptTemplateItem {
  id: string;
  name: string;
  template: string;
  variables: string[];
}

export interface PromptTemplateListResponse {
  items: PromptTemplateItem[];
}

export interface PromptTemplateApplyRequest {
  template_id: string;
  variables?: Record<string, string>;
}

export interface PromptTemplateApplyResponse {
  prompt: string;
}

// ---- Prompt Library ----

export type PromptPolarity = "positive" | "negative";
export type PromptResourceType = "category" | "entry" | "combination";
export type PromptRestoreResourceType = "category" | "entry";

export interface PromptLibraryManifest {
  schema_version: 1 | 2;
  library_id: string;
  name: string;
  description_zh: string;
  comma_atomic_version?: 0 | 1;
  comma_atomic_migration_required?: boolean;
}

export interface CommaAtomicMigrationStatus {
  state: "required" | "applying" | "incomplete" | "validating" | "rolled_back_required" | "finalized";
  marker_present: boolean;
  comma_atomic_ready: boolean;
  atomic_enforcement_active: boolean;
  run_id: string | null;
  data_validated: boolean;
}

export interface PromptEntryRef {
  polarity: PromptPolarity;
  category_id: string;
  entry_id: string;
}

export interface PromptFragment {
  kind: "entry" | "literal";
  ref: PromptEntryRef | null;
  snapshot: string;
  source_revision: number | null;
  weight: number;
  order: number;
}

export interface PromptFragmentInput
  extends Omit<PromptFragment, "ref" | "source_revision"> {
  ref?: PromptEntryRef | null;
  source_revision?: number | null;
}

export interface PromptEntry {
  id: string;
  name_zh: string;
  description_zh: string;
  prompt: string;
  aliases: string[];
  keywords: string[];
  order: number;
  revision: number;
  archived: boolean;
}

export interface PromptCategory {
  schema_version: 1;
  id: string;
  polarity: PromptPolarity;
  name_zh: string;
  description_zh: string;
  aliases: string[];
  keywords: string[];
  order: number;
  revision: number;
  archived: boolean;
  entries: PromptEntry[];
  parent_id?: string | null;
}

export interface PromptCategorySummary {
  id: string;
  polarity: PromptPolarity;
  name_zh: string;
  description_zh: string;
  aliases: string[];
  keywords: string[];
  order: number;
  revision: number;
  archived: boolean;
  entry_count: number;
  etag: string;
  parent_id?: string | null;
}

/** @deprecated PromptCategorySummary is the exact catalog wire DTO. */
export type PromptCatalogCategorySummary = PromptCategorySummary;

export interface PromptCombinationSummary {
  id: string;
  name_zh: string;
  description_zh: string;
  aliases: string[];
  keywords: string[];
  order: number;
  revision: number;
  archived: boolean;
  legacy_template: boolean;
  positive_prompt_snapshot: string;
  negative_prompt_snapshot: string;
  etag: string;
}

export interface PromptCombination {
  schema_version: 1;
  id: string;
  name_zh: string;
  description_zh: string;
  aliases: string[];
  keywords: string[];
  order: number;
  revision: number;
  archived: boolean;
  legacy_template: boolean;
  positive: PromptFragment[];
  negative: PromptFragment[];
  positive_prompt_snapshot: string;
  negative_prompt_snapshot: string;
}

export interface PromptVersionedCategory {
  category: PromptCategory;
  etag: string;
}

export interface PromptWarning {
  code: string;
  message: string;
  hint: string;
  ref: PromptEntryRef | null;
  details: Record<string, unknown>;
}

export interface PromptLibraryDiagnostic {
  code: string;
  message: string;
  hint: string;
  path: string;
  details: Record<string, unknown>;
}

export interface PromptVersionedCombination {
  combination: PromptCombination;
  etag: string;
  repaired: boolean;
  warnings: PromptWarning[];
  blocking_diagnostics: PromptBlockingDocumentDiagnostic[];
  document_context_token: string | null;
}

export interface PromptBlockingDocumentDiagnostic {
  id: string;
  code: "legacy_reference_unresolved";
  original_ref: PromptEntryRef;
  combination_id: string;
  revision: number;
  etag: string;
  polarity: PromptPolarity;
  fallback_start_position: number;
  fallback_count: number;
  fallback_atom_hashes: string[];
  blocking: true;
}

export interface PromptProvenanceResolution {
  document_context_token: string;
  diagnostic_id: string;
  action: "reviewed_mapping" | "replacement_entries" | "acknowledge_convert_to_literals";
  replacement_refs: PromptEntryRef[];
}

export interface PromptLibraryCatalogResponse {
  manifest: PromptLibraryManifest;
  categories: PromptCatalogCategorySummary[];
  combinations: PromptCombinationSummary[];
  diagnostics: PromptLibraryDiagnostic[];
}

export interface PromptConcurrencyToken {
  expected_revision: number;
  expected_etag?: string;
}

export interface PromptCategoryWriteRequest extends PromptConcurrencyToken {
  name_zh: string;
  description_zh: string;
  aliases: string[];
  keywords: string[];
  order: number;
  parent_id?: string | null;
}

export interface PromptEntryWriteRequest extends PromptCategoryWriteRequest {
  prompt: string;
}

export interface PromptMoveEntryRequest extends PromptEntryWriteRequest {
  to_category_id: string;
}

export interface PromptCombinationWriteRequest extends PromptCategoryWriteRequest {
  legacy_template: boolean;
  positive: PromptFragmentInput[];
  negative: PromptFragmentInput[];
  source_combination_id?: string;
  document_context_token?: string;
  literal_conversion_token?: string;
  provenance_resolutions?: PromptProvenanceResolution[];
}

export interface PromptCombinationSaveIntent extends PromptCombinationWriteRequest {
  id: string;
}

export interface PromptArchiveRequest extends PromptConcurrencyToken {
  resource_type: PromptResourceType;
  resource_id: string;
  polarity?: PromptPolarity;
  category_id?: string;
}

export interface PromptRestoreRequest extends PromptConcurrencyToken {
  resource_type: PromptRestoreResourceType;
  resource_id: string;
  polarity: PromptPolarity;
  category_id?: string;
}

export interface PromptComposeRequest {
  combination_id?: string;
  positive: PromptFragmentInput[];
  negative: PromptFragmentInput[];
  save_as?: PromptCombinationSaveIntent;
}

export interface PromptComposeResponse {
  positive_prompt: string;
  negative_prompt: string;
  positive: PromptFragment[];
  negative: PromptFragment[];
  warnings: PromptWarning[];
  snapshot_repaired: boolean;
  saved_combination: PromptVersionedCombination | null;
}

export interface PromptLibraryWriteResponse {
  category: PromptVersionedCategory | null;
  combination: PromptVersionedCombination | null;
  entry: PromptEntry | null;
  entry_revision: number | null;
  affected_combinations: string[];
}

export interface PromptLiteralConversionAcknowledgeResponse {
  literal_conversion_token: string;
  diagnostic_ids: string[];
}

export interface PromptLibraryErrorDetail {
  code: string;
  message: string;
  hint: string;
  details: Record<string, unknown>;
}

export interface FastApiValidationError {
  loc: Array<string | number>;
  msg: string;
  type?: string;
}

export interface UsageItem {
  name: string;
  count: number;
}

export interface NumericStats {
  min: number | null;
  max: number | null;
  avg: number | null;
  count: number;
}

export interface SeedUsageItem {
  seed: number;
  count: number;
}

export interface AnalyticsSummaryResponse {
  total_count: number;
  checkpoint_usage: UsageItem[];
  lora_usage: UsageItem[];
  steps_stats: NumericStats;
  cfg_stats: NumericStats;
  top_seeds: SeedUsageItem[];
}
