# 專案討論紀錄

---

## GOAL

**功能完整化**：現有功能標記完成但實作陽春，要補齊；不單是修現有功能，還包含考慮需要擴充哪些新功能。

**MCP → Skill**：讓 MCP 包裝成可供 agent 使用的 skill。openclaw 使用本地 LLM，skill 要寫通用格式（需查詢 openclaw 接受的 skill formatter）。

**使用情境（核心）**：使用者對 agent 口語描述希望的圖片（角色、場景、動作、人數等），agent 理解後生圖。整個系統以 **agent-first** 為設計原則。

---

## 大方向討論

| 方向 | 狀態 | 文件 |
|------|------|------|
| A. 生圖 function 完整化 | ✅ 討論完成 | [docs/discussion/a-generate.md](docs/discussion/a-generate.md) |
| B. Schema / API 驗證強化 | ✅ 討論完成 | [docs/discussion/b-schema-api.md](docs/discussion/b-schema-api.md) |
| C. LoRA 訓練參數補齊 | ✅ 討論完成 | [docs/discussion/c-lora-train.md](docs/discussion/c-lora-train.md) |
| D. MCP Tools 參數補齊 | 與 A 合併 | — |
| E. MCP Skill 文件 | ⏸ 功能補齊後再設計 | [docs/discussion/e-skill-docs.md](docs/discussion/e-skill-docs.md) |

---

## 實作追蹤

- 完整清單（#1–29）：[docs/discussion/checklist.md](docs/discussion/checklist.md)
- 執行順序（Phase 0–5）：[docs/discussion/phases.md](docs/discussion/phases.md)

### Phase 總覽

| Phase | 內容 | 關鍵產出 |
|-------|------|---------|
| 0 | Slack 清理 | 乾淨的 codebase |
| 1 | Schema + DB | 所有新欄位到位 |
| 2 | 後端 API | lora_strength/denoise 可用；job 查詢/取消可用 |
| 3 | MCP Tools | agent 可完整呼叫所有功能 |
| 4 | 新功能 + 前端 | LLM caption；UI 補齊 |
| 5 | Skill 文件 | agent 可透過 skill 使用整個系統 |
