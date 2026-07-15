# 專案目標

## 核心目標

**Agent-first 生圖系統**：使用者對 AI agent 口語描述圖片需求（角色、場景、動作、風格），agent 透過 MCP Tools 串接後端，自動觸發 ComfyUI 產圖。

整個系統以 **agent 為第一使用者**，人類介面（前端 UI）為次要。

## 系統架構

```
使用者口語描述 → AI Agent → MCP Tools → FastAPI Backend → ComfyUI → 產圖
                                              ↓
                                     SQLite / PostgreSQL（記錄參數）
```

## 現在聚焦的範圍

**目標狀態**：MCP Tools 功能完整，agent 可以：
1. 查詢可用的 checkpoints / LoRA / workflows
2. 用任意參數生圖（含進階參數：sampler、lora_strength、denoise）
3. **參考 Civitai 上別人的圖生圖**：給圖片連結＋想要的主題，自動沿用原圖參數、
   自動下載缺少的模型到外接硬碟、找不到就用最接近的本地模型代替（best-effort，不追求
   位元級精確重現；strict 稽核管線保留在 backend HTTP API）
4. 查詢 job 狀態、取消 job；對滿意的圖一鍵重抽（gallery_rerun）
5. 觸發 LoRA 訓練、查詢訓練狀態（訓練完後由 agent 自行呼叫生圖，backend 不自動串接）
6. 對圖片呼叫 LLM 自動標注 caption

**不在目前範圍**：
- Slack 整合（已移除）
- openclaw Skill 文件（等格式確認後再做）

## 設計原則

| 原則 | 說明 |
|------|------|
| Agent-first | API / MCP 先於 UI；以 agent 可完整呼叫為完成標準 |
| 驗證明確 | 每個 task 都有可執行的 verify 指令（見 [agent-framework.md](agent-framework.md)）|
| 單一來源 | 進度追蹤在 [PROGRESS.md](PROGRESS.md)；架構在 AGENTS.md；spec 在 task-specs/ |
| 安全第一 | 敏感資訊（Key、Token）絕不硬編碼，一律走環境變數 |
