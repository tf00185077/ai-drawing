# Agent Context: AI 自動化出圖系統

> 修改前請先閱讀。本文件是所有 agent 的單一資訊來源（Single Source of Truth）。

---

## Agent 系統導航說明

不同 agent 系統各有自己的自動讀取規則，本文件作為統一的實質 context：

| Agent 系統 | 自動讀取入口 | 說明 |
|-----------|------------|------|
| Claude Code | [CLAUDE.md](CLAUDE.md) → 本文件 | CLAUDE.md 導航至此 |
| OpenAI Codex / GPT agents | 本文件（直接） | `AGENTS.md` 為標準慣例 |
| Cursor | [.cursor/rules/](.cursor/rules/) | 各 `.mdc` 規則檔 |
| 人類 / 新成員 | [README.md](README.md) → 本文件 | README 導航至此 |

**所有 agent 的架構、約束、編碼慣例皆以本文件為準。**

---

## 快速導航

| 問題 | 去哪找 |
|------|--------|
| 我們在造什麼？ | [docs/GOAL.md](docs/GOAL.md) |
| 現在做到哪裡？下一步是什麼？ | [docs/PROGRESS.md](docs/PROGRESS.md) |
| 這個 task 要怎麼做？如何驗證？ | [docs/task-specs/](docs/task-specs/)（F-A 到 F-F，每個 task = 一個完整功能） |
| REST API 格式？ | [docs/api-contract.md](docs/api-contract.md) |
| 模組介面？ | [docs/internal-interfaces.md](docs/internal-interfaces.md) |
| 如何啟動系統？ | [docs/setup-guide.md](docs/setup-guide.md) |

**執行規則**：完成的任務要同步修改 [docs/PROGRESS.md](docs/PROGRESS.md)。

---

## 1. 安全性原則（最高優先）

凡涉及 **KEY、API Key、Secret、Token、密碼** 等敏感資訊：

| 禁止 | 必須 |
|------|------|
| 上傳至 Git（含 commit、PR） | 使用環境變數（`.env`）或 secrets 管理 |
| 硬編碼於程式碼中 | 透過 `config` 載入，僅在 runtime 讀取 |
| 寫入 `.env.example` 的範例使用真實值 | `.env.example` 僅放占位符（如 `YOUR_API_KEY=`） |

- `.env` 必須在 `.gitignore` 中，不得提交。

---

## 2. Tech Stack（固定，勿替換）

| 類別 | 技術 |
|------|------|
| 後端 | Python 3.11 + FastAPI |
| 前端 | React 18 + Vite + Tailwind |
| 資料庫 | SQLite / PostgreSQL（SQLAlchemy ORM） |
| 圖片引擎 | ComfyUI API（WebSocket + REST） |
| AI 標註 | WD Tagger / BLIP2 |
| LoRA 訓練 | Kohya sd-scripts（subprocess 呼叫） |
| 資料夾監聽 | watchdog |
| 部署 | Docker + docker-compose |
| MCP | Python MCP SDK（`mcp-server/`） |

**禁止**：不使用 n8n、Zapier 等外部工作流引擎；所有邏輯由 Python 實作。

---

## 3. 專案結構

```
ai-drawing/
├── backend/app/
│   ├── api/          # generate, gallery, lora_docs, lora_train, analytics
│   ├── core/         # comfyui, workflow, queue, recording
│   ├── db/           # models, database
│   ├── services/     # watcher, lora_trainer
│   └── schemas/      # generate, lora_train
├── frontend/src/pages/  # Generate, Gallery, LoraDocs, LoraTrain, Dashboard
├── mcp-server/mcp_server/tools/  # generate, lora_train, gallery
├── backend/workflows/   # workflow JSON 模板
└── docs/
    ├── GOAL.md          # 目標與範圍
    ├── PROGRESS.md      # 唯一進度來源
    ├── task-specs/      # 各 phase 的可執行 task spec
    ├── api-contract.md
    └── internal-interfaces.md
```

---

## 4. 核心資料流

```
watch_dirs → watchdog → 新圖 → WD Tagger/BLIP2 → 同名 .txt
     ↓
圖片數 ≥ threshold → lora_trainer → Kohya sd-scripts
     ↓
訓練完成 → comfyui.trigger(新 LoRA) → recording.save()
```

**必須遵守**：
1. 生圖後自動呼叫 `recording` 寫入 `GeneratedImage`
2. LoRA 訓練完成後自動選用新 LoRA → 呼叫 ComfyUI → 寫入記錄
3. 避免重複觸發：訓練佇列、產圖佇列需狀態追蹤

---

## 5. 主要資料結構

```python
# backend/app/db/models.py
GeneratedImage:
    id, job_id, image_path, checkpoint, lora, seed, steps, cfg,
    prompt, negative_prompt, created_at

# backend/app/config.py（透過 pydantic-settings 載入）
database_url, comfyui_base_url, comfyui_ws_url,
output_dir, gallery_dir, lora_train_dir, lora_train_threshold,
sd_scripts_path, watch_dirs
```

---

## 6. 編碼慣例

| 層級 | 慣例 |
|------|------|
| 後端 | FastAPI 路由、Pydantic 型別註解、`Depends(get_db)` 注入 |
| 前端 | React 函數元件、**檔名使用 .tsx**、Tailwind CSS |
| 資料庫 | SQLAlchemy 2.x、`Session` 透過 `get_db` |
| 新增 API | 在對應 `backend/app/api/*.py` 新增路由，已在 `main.py` include |
| MCP Tool | 在 `mcp-server/mcp_server/tools/*.py` 加 `@mcp.tool()` 裝飾器 |

---

## 7. Skill 優先參考

若程式碼涉及以下領域，**實作前先查閱對應 `.cursor/skills/` 下的 SKILL.md**：

| 領域 | Skill |
|------|-------|
| ComfyUI（生圖、workflow、佇列） | `comfyui-api-client` |
| Workflow JSON 組裝 | `comfyui-workflow` |
| LoRA 模組 | `lora-train-docs` |
| Kohya sd-scripts | `kohya-sd-scripts` |
| WD Tagger | `wd-tagger` |
| Python 後端擴展性審核 | `python-extensibility-review` |
| MCP Tools 呼叫 | `mcp-tools-usage` |

---

## 8. 實作相依關係

```
config → db → core/comfyui + core/workflow → core/queue
core/recording 依賴 db，生圖完成後呼叫
services/watcher 依賴 config.watch_dirs
services/lora_trainer 依賴 config.sd_scripts_path，完成後呼叫 comfyui + recording
mcp-server 依賴 backend APIs 全部可用
```

---

## 9. 啟動指令

```bash
# 後端
cd backend && uvicorn app.main:app --reload

# 前端
cd frontend && npm run dev

# 測試
pytest backend/tests/ mcp-server/tests/ -x -q
```

詳細設定見 [docs/setup-guide.md](docs/setup-guide.md)。
