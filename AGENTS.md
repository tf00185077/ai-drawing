# Agent Context: AI 自動化出圖系統

> 本文件為 AI Agent 專用上下文，提供架構、檔案對應、資料結構與實作指引。修改前請先閱讀。

---

## 1. 專案摘要

| 項目 | 說明 |
|------|------|
| 專案名稱 | AI 自動化出圖系統 |
| 核心流程 | 資料夾監聽 → .txt 產生 → LoRA 訓練 → ComfyUI 產圖 → 參數記錄 |
| 架構 | Monorepo：`backend/` (FastAPI) + `frontend/` (React) |
| 規格來源 | `roadmap.tsx`（唯一規格來源） |

---

## 2. 安全性原則（最高優先）

**本專案安全性為最高原則。**

凡涉及 **KEY、API Key、Secret、Token、密碼** 等敏感資訊：

| 禁止 | 必須 |
|------|------|
| 上傳至 Git（含 commit、PR） | 使用環境變數（`.env`）或 secrets 管理 |
| 硬編碼於程式碼中 | 透過 `config` 載入，僅在 runtime 讀取 |
| 寫入 `.env.example` 的範例使用真實值 | `.env.example` 僅放占位符（如 `YOUR_API_KEY=`） |

- `.env` 必須在 `.gitignore` 中，不得提交。
- 新增需 KEY 的整合（如第三方 API）時，一律透過環境變數注入。

---

## 3. Tech Stack（固定，勿替換）

| 類別 | 技術 | 說明 |
|------|------|------|
| 後端 | Python 3.11 + FastAPI | REST API |
| 前端 | React 18 + Vite + Tailwind | SPA |
| 資料庫 | SQLite / PostgreSQL | SQLAlchemy ORM |
| 圖片引擎 | ComfyUI API | WebSocket + REST |
| AI 標註 | WD Tagger / BLIP2 | 產生 .txt caption |
| LoRA 訓練 | Kohya sd-scripts | subprocess 呼叫 |
| 資料夾監聽 | watchdog | 監聽訓練資料夾 |
| 部署 | Docker | docker-compose |

**禁止**：不使用 n8n、Zapier 等外部工作流引擎；所有邏輯由 Python 實作。

---

## 4. 四大模組與檔案對應

### 模組 1：生圖

| 職責 | 檔案路徑 | 狀態 |
|------|----------|------|
| API 端點 | `backend/app/api/generate.py` | stub |
| ComfyUI 串接 | `backend/app/core/comfyui.py` | stub |
| Workflow 模板 | `backend/app/core/workflow.py` | stub |
| 批次排程 | `backend/app/core/queue.py` | stub |
| 前端參數面板 | `frontend/src/pages/Generate.tsx` | stub |
| 模板存放 | `backend/workflows/` | 空 |

**API 約定**：`POST /api/generate/` 觸發生圖，`GET /api/generate/queue` 取得佇列狀態。

### 模組 2：圖庫

| 職責 | 檔案路徑 | 狀態 |
|------|----------|------|
| API 端點 | `backend/app/api/gallery.py` | stub |
| 自動記錄 | `backend/app/core/recording.py` | stub |
| DB 模型 | `backend/app/db/models.py` | 已定義 |
| 前端 Gallery | `frontend/src/pages/Gallery.tsx` | stub |

**API 約定**：`GET /api/gallery/`（篩選）、`GET /api/gallery/{id}`（詳情）、`POST /api/gallery/{id}/rerun`、`GET /api/gallery/{id}/export?format=json|csv`。

### 模組 3：LoRA 文件工具

| 職責 | 檔案路徑 | 狀態 |
|------|----------|------|
| API 端點 | `backend/app/api/lora_docs.py` | stub |
| 資料夾監聽 | `backend/app/services/watcher.py` | stub |
| 前端介面 | `frontend/src/pages/LoraDocs.tsx` | stub |

**API 約定**：`POST /api/lora-docs/upload`、`PUT /api/lora-docs/caption/{id}`、`POST /api/lora-docs/batch-prefix`、`GET /api/lora-docs/download-zip?folder=xxx`。

### 模組 4：LoRA 訓練與產圖串接

| 職責 | 檔案路徑 | 狀態 |
|------|----------|------|
| API 端點 | `backend/app/api/lora_train.py` | stub |
| 訓練執行器 | `backend/app/services/lora_trainer.py` | stub |
| 前端介面 | `frontend/src/pages/LoraTrain.tsx` | stub |

**API 約定**：`POST /api/lora-train/start`、`GET /api/lora-train/status`、`POST /api/lora-train/trigger-check`。

### 模組 5：MCP 自然語言介面（Phase 6）

| 職責 | 檔案路徑 | 狀態 |
|------|----------|------|
| MCP Server 主程式 | `mcp-server/` 或 `backend/mcp_server.py` | 待實作 |
| Tools 定義 | `mcp-server/tools.py` | 待實作 |
| Cursor 配置說明 | `docs/mcp-setup.md` | 待實作 |

**MCP Tools 對應**：
- `lora_train_start` → `POST /api/lora-train/start`
- `lora_train_status` → `GET /api/lora-train/status`
- `generate_image` → `POST /api/generate/`
- `generate_queue_status` → `GET /api/generate/queue`
- `gallery_list` → `GET /api/gallery/`
- `gallery_rerun` → `POST /api/gallery/{id}/rerun`
- `gallery_detail` → `GET /api/gallery/{id}`

**目標**：使用者可對 Cursor / Claude 說「產生 XX 角色、YY 風格的 5 張照片」，AI 透過 MCP Tools 串接訓練與生圖。

---

## 5. 資料結構

### GeneratedImage (資料庫)

```python
# backend/app/db/models.py
id, image_path, checkpoint, lora, seed, steps, cfg,
prompt, negative_prompt, created_at
```

### 配置 (Config)

```python
# backend/app/config.py
database_url, comfyui_base_url, comfyui_ws_url,
output_dir, gallery_dir, lora_train_dir, lora_train_threshold,
sd_scripts_path, watch_dirs
```

環境變數以 `.env.example` 為準，透過 pydantic-settings 載入。

### Workflow 可替換參數

生圖 workflow 需支援動態替換：`checkpoint`, `lora`, `prompt`, `seed`, `steps`, `cfg`。

---

## 6. 資料流與約束

### 必須遵守

1. **生圖後**：自動呼叫 `recording` 寫入 `GeneratedImage`，圖片存至 `gallery_dir`。
2. **LoRA 訓練完成後**：自動選用新 LoRA → 呼叫 ComfyUI 生圖 → 寫入記錄。
3. **避免重複觸發**：訓練佇列、產圖佇列需狀態追蹤。
4. **圖片儲存**：使用結構化資料夾（依日期/模型等）。

### 自動化流水線

```
watch_dirs → watchdog → 新圖 → WD Tagger/BLIP2 → 同名 .txt
     ↓
圖片數 ≥ lora_train_threshold → lora_trainer → Kohya sd-scripts
     ↓
訓練完成 → comfyui.trigger(新 LoRA) → recording.save()
```

---

## 7. Roadmap 對應（任務 → 實作位置）

**Agent 開發規則**：
1. **按表順序完成功能**：依下表 1a → 1b → … → 6d 的順序實作，遵循 Section 10 相依關係。
2. **完成後打勾標記**：實作完成後，在本表與 `README.md` 的進度追蹤區塊將該任務改為 `[v]`，未完成保持 `[]`。

| Phase | 任務 | 實作檔案 |
|-------|------|----------|
| 1a | ComfyUI API 串接 | `core/comfyui.py` [v] |
| 1b | Workflow JSON 管理 | `core/workflow.py`, `workflows/*.json` |
| 1c | 批次生圖排程器 | `core/queue.py` |
| 1d | 基礎 UI 參數面板 | `pages/Generate.tsx` |
| 2a | 資料庫設計 | `db/models.py` [v] |
| 2b | 自動記錄 Pipeline | `core/recording.py` |
| 2c | Gallery 瀏覽器 | `pages/Gallery.tsx`, `api/gallery.py` |
| 2d | 一鍵重現 / 匯出 | `api/gallery.py` |
| 3a | 資料夾監聽 .txt | `services/watcher.py` |
| 3b | 圖片上傳介面 | `pages/LoraDocs.tsx`, `api/lora_docs.py` |
| 3c | Caption 編輯器 | `pages/LoraDocs.tsx`, `api/lora_docs.py` |
| 3d | 打包下載 | `api/lora_docs.py` |
| 4a | LoRA 訓練執行器 | `services/lora_trainer.py` |
| 4b | 訓練觸發邏輯 | `services/lora_trainer.py`, watcher |
| 4c | 訓練完成 → 產圖 Pipeline | `services/lora_trainer.py` → `core/comfyui` + `recording` |
| 4d | 訓練狀態與佇列 | `api/lora_train.py`, `pages/LoraTrain.tsx` |
| 5a | 統一儀表板 | `pages/Dashboard.tsx` [v] |
| 5b | Prompt 模板庫 | 新建 `core/prompt_templates.py` 等 |
| 5c | 生成統計分析 | 新建 `api/analytics.py` 等 |
| 5d | 部署 & 文件 | `Dockerfile`, `docker-compose.yml` [v] |
| 6a | MCP Server 建置 | `mcp-server/`, Python MCP SDK |
| 6b | 生圖與訓練 Tools | `mcp-server/tools/` |
| 6c | 角色與風格語意對應 | `mcp-server/character_style.py` |
| 6d | MCP 整合文件與 Cursor 配置 | `docs/mcp-setup.md` |

---

## 8. 編碼慣例

| 層級 | 慣例 |
|------|------|
| 後端 | FastAPI 路由、Pydantic 型別註解、`Depends(get_db)` 注入 |
| 前端 | React 函數元件、Tailwind CSS、`/api` proxy 至 backend:8000 |
| 資料庫 | SQLAlchemy 2.x、`Session` 透過 `get_db` |
| 新增 API | 在對應 `backend/app/api/*.py` 新增路由，於 `main.py` 已 include |

---

## 9. 啟動指令

```bash
# 後端
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# 前端
cd frontend && npm install && npm run dev

# 初始化 DB
python backend/scripts/init_db.py

# Docker
cp .env.example .env && docker-compose up -d
```

### 測試指令

```bash
# 後端 (pytest)
cd backend && pytest

# 前端 (Vitest)
cd frontend && npm run test
# 監聽模式：npm run test:watch
```

---

## 10. 相依關係（實作順序建議）

1. `config` → `db` → `core/comfyui` + `core/workflow` → `core/queue`
2. `core/recording` 依賴 `db`，生圖完成後呼叫
3. `services/watcher` 依賴 `config.watch_dirs`，觸發 WD Tagger/BLIP2
4. `services/lora_trainer` 依賴 `config.sd_scripts_path`，完成後呼叫 `comfyui` + `recording`
5. 前端頁面可並行，依 API 約定呼叫後端
6. `mcp-server` 依賴 Phase 1–4 完成後的 backend APIs（comfyui、lora_trainer、recording 等均已實作）

---

## 11. 關鍵參考

- 規格定義：`roadmap.tsx`
- 專案規則：`.cursor/rules/auto-draw-project.mdc`
- 環境範例：`.env.example`
- **代理人分工**：`docs/agent-assignment.md`（A–F 軌道、並行步驟、介面文件位置）
- **Slack 指令實作追蹤**：`docs/slack-command-agent-tracker.md`（任務依賴、驗證、進度標記，Agent 專用）
- **API 契約**：`docs/api-contract.md`
- **內部介面**：`docs/internal-interfaces.md`
