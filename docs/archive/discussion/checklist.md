# 實作清單

優先順序依照 skill 可用性影響排列。完整執行順序見 [phases.md](phases.md)。

## 後端

| # | 項目 | 檔案 | 來源 |
|---|------|------|------|
| 1 | `GeneratedImage` 加 `job_id` 欄位 + migration | `db/models.py`, `scripts/init_db.py` | [A](a-generate.md)-缺口3 |
| 2 | `recording.save()` 補傳 job_id | `core/recording.py` | [A](a-generate.md)-缺口3 |
| 3 | 新增 `GET /api/generate/job/{job_id}` endpoint | `api/generate.py` | [A](a-generate.md)-缺口3 |
| 4 | 新增 `DELETE /api/generate/queue/{job_id}` cancel endpoint | `api/generate.py` | [A](a-generate.md)-缺口4 |
| 5 | `GenerateRequest` 加 lora_strength / denoise 欄位 | `schemas/generate.py` | [B](b-schema-api.md) |
| 6 | `GenerateRequest` sampler_name / scheduler 加 Literal 枚舉 | `schemas/generate.py` | [B](b-schema-api.md) |
| 7 | `GenerateRequest` width/height 上限改 4096 | `schemas/generate.py` | [B](b-schema-api.md) |
| 8 | `GenerateCustomRequest` 改繼承 `GenerateRequest` | `schemas/generate.py` | [B](b-schema-api.md) |
| 9 | `api/generate.py` 補傳 lora_strength / denoise 給 apply_params | `api/generate.py` | [B](b-schema-api.md) |
| 10 | `workflow.apply_params()` 加 lora_strength 參數 | `core/workflow.py` | [B](b-schema-api.md) |
| 11 | `TrainStartRequest.generate_after` 改必填 | `schemas/lora_train.py` | [C](c-lora-train.md) |
| 12 | `TrainStartRequest.mixed_precision` 加 Literal 枚舉 | `schemas/lora_train.py` | [C](c-lora-train.md) |

## MCP Server

| # | 項目 | 檔案 | 來源 |
|---|------|------|------|
| 13 | 新增 `get_available_resources` tool | `tools/generate.py` | [A](a-generate.md)-缺口1 |
| 14 | 新增 `get_job_result(job_id)` tool | `tools/generate.py` | [A](a-generate.md)-缺口3 |
| 15 | 新增 `cancel_job(job_id)` tool | `tools/generate.py` | [A](a-generate.md)-缺口4 |
| 16 | `generate_image` 補 width / height / sampler_name / scheduler / lora_strength / denoise | `tools/generate.py` | [B](b-schema-api.md) |
| 17 | `lora_train_start` 補齊所有 schema 參數（常用+細節分層） | `tools/lora_train.py` | [C](c-lora-train.md) |

## 前端（次要，agent-first 為主）

| # | 項目 | 檔案 | 來源 |
|---|------|------|------|
| 18 | Generate.tsx 加進階參數折疊區（width/height/batch_size/sampler/scheduler/lora_strength/denoise） | `pages/Generate.tsx` | [B](b-schema-api.md) |
| 19 | LoraTrain.tsx 補 keep_tokens / mixed_precision / generate_after | `pages/LoraTrain.tsx` | [C](c-lora-train.md) |

## Slack 移除

| # | 項目 | 檔案 |
|---|------|------|
| 20 | 刪除 Slack 相關 service 檔案 | `services/slack_handler.py`, `slack_notifier.py`, `slack_commands.py` |
| 21 | 移除 main.py 的 Slack Socket Mode 啟動邏輯 | `app/main.py` |
| 22 | 移除 config 的 slack token 欄位 | `app/config.py` |
| 23 | 移除 schema 的 slack_channel_id / slack_thread_ts | `schemas/generate.py` |
| 24 | 更新 README.md / AGENTS.md 移除 Slack 相關章節 | `README.md`, `AGENTS.md` |

## 新增功能

| # | 項目 | 說明 |
|---|------|------|
| 25 | 新增 LLM caption 標注 API endpoint | `api/lora_docs.py` — 新增 POST /api/lora-docs/caption-llm |
| 26 | 新增 LLM caption 標注 MCP tool | `tools/lora_train.py` 或新增 `tools/caption.py` |

## Skill 文件（功能補齊後）

| # | 項目 | 說明 |
|---|------|------|
| 27 | 確認 openclaw skill 格式 | 需知道工具名稱/框架 |
| 28 | 撰寫 `ai-drawing-generate` skill | 依賴 #13, #14, #16 完成 |
| 29 | 撰寫 `ai-drawing-train` skill | 依賴 #17, #25, #26 完成 |
