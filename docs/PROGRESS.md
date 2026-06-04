# 進度追蹤

> **唯一來源**。完成任務後只更新這個文件，不改 README.md 或 AGENTS.md。
> 完整 task spec 見 `docs/task-specs/`。

---

## 目前聚焦

待開始。F-A 到 F-F 均可獨立進行，建議先做 F-D（最小範圍，純 MCP tool）確認開發流程，再依優先度選擇。

---

## 已完成

### 系統基礎建置
- [x] ComfyUI API 串接（`backend/app/core/comfyui.py`）
- [x] Workflow JSON 模板管理（`backend/app/core/workflow.py`）
- [x] 批次生圖排程器（`backend/app/core/queue.py`）
- [x] 資料庫設計（`backend/app/db/models.py`）
- [x] 自動記錄 Pipeline（`backend/app/core/recording.py`）
- [x] Gallery 瀏覽器 + 一鍵重現（`backend/app/api/gallery.py`）
- [x] LoRA 文件工具（watcher、caption editor、zip download）
- [x] LoRA 訓練執行器（`backend/app/services/lora_trainer.py`）
- [x] MCP Server 基礎建置（`mcp-server/`）
- [x] MCP Tools 初版（generate、lora_train、gallery）
- [x] Docker 部署

### Phase 0：Slack 清理（PR #1，2026-06-04）
- [x] 刪除 Slack service 檔案
- [x] 移除 main.py Slack 啟動邏輯
- [x] 移除 config Slack token 欄位
- [x] 移除 schema slack_channel_id / slack_thread_ts
- [x] 更新 README / AGENTS 移除 Slack 相關章節

---

## 進行中

（目前無）

---

## 待做

每個功能任務獨立，可並行。完整 spec 見 `docs/task-specs/F-*.md`。

| 任務 | 說明 | 狀態 | Spec |
|------|------|------|------|
| F-A | 生圖完整參數（lora_strength、denoise、width/height 等暴露至 MCP） | 待做 | [F-A](task-specs/F-A-generate-params.md) |
| F-B | Job 狀態查詢（DB job_id + API endpoint + MCP tool） | 待做 | [F-B](task-specs/F-B-job-status.md) |
| F-C | Job 取消（queue cancel + API endpoint + MCP tool） | 待做 | [F-C](task-specs/F-C-job-cancel.md) |
| F-D | 查詢可用資源（純 MCP tool，API 已有） | 待做 | [F-D](task-specs/F-D-available-resources.md) |
| F-E | LoRA 訓練完整參數（移除 generate_after + MCP 補齊參數） | 待做 | [F-E](task-specs/F-E-lora-train-params.md) |
| F-F | LLM 自動 caption（API + MCP tool） | 待做 | [F-F](task-specs/F-F-llm-caption.md) |

---

## 卡住 / 待決策

| 項目 | 原因 | 需要 |
|------|------|------|
| Skill 文件 | openclaw skill 格式未確認 | 確認工具名稱 / 框架後才能開始 |
