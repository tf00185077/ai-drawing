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

export interface TrainStartRequest {
  folder: string;
  checkpoint?: string;
  epochs?: number;
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

export interface TrainStatusResponse {
  status: "idle" | "running" | "queued";
  current_job?: TrainJobInfo;
  queue: TrainJobInfo[];
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
