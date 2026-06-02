# 實作順序

完整清單見 [checklist.md](checklist.md)。

## Phase 0：清理 Slack（無依賴，先做）

移除 Slack 整合，讓後續 schema 改動更乾淨。

`#20 → #21 → #22 → #23 → #24`

## Phase 1：基礎層（Schema + DB）

兩條線可並行：

| 線 A（DB） | 線 B（Schema） |
|-----------|---------------|
| #1 DB 加 job_id + migration | #5–8 GenerateRequest 加欄位、枚舉、改繼承 |
| #2 recording.py 補傳 job_id | #11–12 TrainStartRequest 必填/枚舉 |

## Phase 2：後端 API 接通

依賴 Phase 1。

- `#9` api/generate.py 補傳 lora_strength / denoise
- `#10` workflow.apply_params 加 lora_strength
- `#3` GET /api/generate/job/{job_id}
- `#4` DELETE /api/generate/queue/{job_id}

## Phase 3：MCP Tools 補齊

依賴 Phase 1 + 2。

- `#13` get_available_resources（API 已存在，最快）
- `#14` get_job_result（依賴 #1, #3）
- `#15` cancel_job（依賴 #4）
- `#16` generate_image 補參數（依賴 #5–10）
- `#17` lora_train_start 補齊（依賴 #11–12）

## Phase 4：新功能 + 前端（可並行）

| 新功能 | 前端（次要） |
|--------|-------------|
| #25 LLM caption API | #18 Generate.tsx 進階參數折疊區 |
| #26 LLM caption MCP tool | #19 LoraTrain.tsx 補齊欄位 |

## Phase 5：Skill 文件（最後）

依賴 Phase 0–4 全部完成。

- `#27` 確認 openclaw skill 格式
- `#28` 撰寫 ai-drawing-generate skill
- `#29` 撰寫 ai-drawing-train skill

## 總覽

| Phase | 內容 | 關鍵產出 |
|-------|------|---------|
| 0 | Slack 清理 | 乾淨的 codebase |
| 1 | Schema + DB | 所有新欄位到位 |
| 2 | 後端 API | lora_strength/denoise 可用；job 查詢/取消可用 |
| 3 | MCP Tools | agent 可完整呼叫所有功能 |
| 4 | 新功能 + 前端 | LLM caption；UI 補齊 |
| 5 | Skill 文件 | agent 可透過 skill 使用整個系統 |
