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

export interface TrainStartRequest {
  folder: string;
  checkpoint?: string;
  model_family?: string;
  anima_qwen3?: string;
  anima_vae?: string;
  anima_t5_tokenizer_path?: string;
  sdxl?: boolean;
  epochs?: number;
  resolution?: number;
  batch_size?: number;
  learning_rate?: string;
  class_tokens?: string;
  keep_tokens?: number;
  num_repeats?: number;
  mixed_precision?: string;
  network_module?: string;
  network_dim?: number;
  network_alpha?: number;
}

export interface TrainStartResponse {
  job_id: string;
  status: string;
  message?: string;
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
