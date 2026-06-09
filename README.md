# AI 自動化出圖系統

> 資料夾監聽自動 .txt · LoRA 訓練觸發 · 參數記錄

整合 ComfyUI、LoRA 訓練與參數記錄的自動化工作流。

## Agent / 新成員入口

> 不同 agent 系統讀取不同入口，但都指向同一份 context：

| 你是誰 | 讀哪裡 |
|--------|--------|
| Claude Code | [CLAUDE.md](CLAUDE.md) → [AGENTS.md](AGENTS.md) |
| OpenAI Codex / GPT agents | [AGENTS.md](AGENTS.md)（直接） |
| Cursor | [.cursor/rules/](.cursor/rules/) |
| 人類 / 新成員 | 本頁 → [AGENTS.md](AGENTS.md) |

**必讀順序**（適用所有 agent）：

1. [AGENTS.md](AGENTS.md) — 架構、Tech Stack、安全規則、編碼慣例
2. [docs/GOAL.md](docs/GOAL.md) — 系統目標與設計原則
3. [docs/PROGRESS.md](docs/PROGRESS.md) — 當前進度，確認下一步

> **文件同步規則**：完成的任務要同步修改 [docs/PROGRESS.md](docs/PROGRESS.md)。

---

## Tech Stack

| 類別 | 技術 |
|------|------|
| 後端 | Python + FastAPI |
| 前端 | React + Tailwind |
| 資料庫 | SQLite / PostgreSQL |
| AI 標註 | WD Tagger / BLIP2 |
| 圖片引擎 | ComfyUI API |
| LoRA 訓練 | Kohya sd-scripts |
| 資料夾監聽 | watchdog |
| 部署 | Docker |

---

## 模組架構

- **生圖**：ComfyUI API 串接、Workflow 模板、批次排程
- **圖庫**：參數記錄、Gallery 瀏覽、一鍵重現
- **LoRA 文件工具**：資料夾監聽 .txt、Caption 編輯、打包下載
- **LoRA 訓練流程**：訓練執行、自動觸發、訓練結果管理
- **MCP 自然語言介面**：MCP Server、角色/風格語意對應、Cursor 整合（設定見 [docs/mcp-setup.md](docs/mcp-setup.md)）

---

## 模組

| 模組 | 說明 |
|------|------|
| 生圖 | ComfyUI API 串接、Workflow 模板、批次排程 |
| 圖庫 | 參數記錄、Gallery 瀏覽、一鍵重現 |
| LoRA 文件工具 | 資料夾監聽 .txt、Caption 編輯、打包下載 |
| LoRA 訓練 | 訓練執行器、自動觸發、訓練流程管理 |
| MCP Tools | 生圖、訓練、圖庫操作，供 agent 呼叫 |

進度追蹤：[docs/PROGRESS.md](docs/PROGRESS.md)

---

## 自動化流水線

```
[訓練資料夾] → watchdog 監聽 → WD Tagger/BLIP2 → 自動 .txt
     ↓
[圖片數 ≥ 門檻] → Kohya sd-scripts → LoRA 訓練
     ↓
[LoRA 與參數資料可供後續生圖流程使用] → 參數記錄 / Gallery 串接
```

### WD Tagger 資料夾類型（依路徑選用 blacklist）

將訓練素材放入對應資料夾，WD Tagger 會自動套用不同的 tag 過濾：

| 資料夾 | 用途 | 過濾重點 |
|--------|------|----------|
| `lora_train/character/` | 人物訓練 | 構圖、背景、髮瞳色等噪音 |
| `lora_train/style/` | 畫風訓練 | 角色名、系列名、品質元資料 |
| `lora_train/costume/` | 服裝訓練 | 背景、髮瞳色、臉部；保留服裝 tag |
| `lora_train/background/` | 背景訓練 | 人物、身體、服裝等 |

範例：`lora_train/costume/10_school_uniform/` 內的圖片會使用服裝 blacklist。

---

## 專案結構

```
ai-drawing/
├── README.md                   # 本文件（技術入口）
├── AGENTS.md                   # Agent 必讀：架構、Tech Stack、編碼慣例
├── backend/                    # Python + FastAPI
│   └── app/
│       ├── api/               # generate, gallery, lora_docs, lora_train, analytics
│       ├── core/              # comfyui, workflow, queue, recording
│       ├── db/                # models, database
│       ├── services/          # watcher, lora_trainer
│       └── schemas/           # generate, lora_train
├── frontend/src/pages/         # Generate, Gallery, LoraDocs, LoraTrain, Dashboard
├── mcp-server/mcp_server/tools/ # generate, lora_train, gallery（MCP Tools）
├── backend/workflows/          # Workflow JSON 模板
└── docs/
    ├── GOAL.md                 # 系統目標與設計原則
    ├── PROGRESS.md             # 唯一進度追蹤來源
    ├── task-specs/             # 可執行的 task spec（含 verify 指令）
    │   ├── phase1-schema-db.md
    │   ├── phase2-backend.md
    │   ├── phase3-mcp.md
    │   └── phase4-features.md
    ├── agent-framework.md      # Task spec 撰寫方法論
    ├── api-contract.md         # REST API 契約
    ├── internal-interfaces.md  # 後端模組介面
    ├── mcp-setup.md            # MCP Server 設定指南
    ├── setup-guide.md          # 完整啟動與環境設定
    └── archive/                # 已停用文件（Slack、舊分工等）
```

### 啟動

> 完整參數說明與 ComfyUI/Kohya/WD 設定見 [`docs/setup-guide.md`](docs/setup-guide.md)

**建議順序**（前端會 proxy `/api` 至後端，故後端需先啟動）：

| 步驟 | 指令 | 說明 |
|------|------|------|
| 0 | `cp .env.example .env` | 首次使用時複製環境變數範例，並編輯 `.env` |
| 1 | `cd backend && pip install -r requirements.txt` | 安裝後端依賴 |
| 2 | `python backend/scripts/init_db.py` | 初始化資料庫（首次或 DB 不存在時） |
| 3 | `cd backend && uvicorn app.main:app --reload` | **先啟動後端**（預設 port 8000） |
| 4 | `cd frontend && npm install && npm run dev` | **再啟動前端**（新開一個終端機，預設 port 5173） |

啟動完成後：

- 前端：<http://localhost:5173>
- 後端 API：<http://localhost:8000>
- API 文件：<http://localhost:8000/docs>

**Docker 一鍵啟動**：

```bash
cp .env.example .env && docker-compose up -d
```

### 測試

```bash
# 後端 (pytest)
cd backend && pytest

# 前端 (Vitest)
cd frontend && npm run test

# MCP Server (pytest)
cd mcp-server && uv run pytest
```


