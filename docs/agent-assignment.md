# 代理人分工文件

> 依軌道 A–F 分配給代理人 A–F，並行開發時必讀。**實作前必須參考介面文件。**

---

## 一、介面文件位置（必讀）

| 文件 | 路徑 | 適用代理人 | 用途 |
|------|------|------------|------|
| **API 契約** | `docs/api-contract.md` | A, B, C, D, E, F | REST API Request/Response 規格 |
| **內部介面** | `docs/internal-interfaces.md` | A, B, C, D | 後端模組函式簽名、回呼契約 |
| **對接索引** | `docs/handoff-index.md` | 全員 | 文件索引、程式碼對應 |
| **ComfyUI 設計** | `docs/comfyui-di-design.md` | A, D | ComfyUI DI / Protocol |
| **Schemas（程式）** | `backend/app/schemas/*.py` | A, B, C, D | Pydantic 模型，與 API 契約對齊 |
| **前端型別** | `frontend/src/types/api.ts` | A, B, C, D, E | TypeScript 介面 |

**實作規則**：  
開始任一任務前，須先閱讀該任務對應的介面文件；完成後在 `README.md` 的「Agent 進度追蹤」區塊標註「完成者」與「完成檔案位置」。

**共用檔案 `frontend/src/types/api.ts` 編輯規則**：

- 代理人僅修改**自身模組對應區塊**（依檔內 `// ---- 模組名 ----` 註解劃分）
- 生圖 → A；圖庫 → B；LoRA 文件 → C；LoRA 訓練 → D；進階/分析 → E
- 若需新增跨模組型別，優先協調或由後整合者統一修改

---

## 二、軌道與代理人對應

```
         ┌─────────────────────────────────────────────────────────────┐
         │ 可並行（前置：1a✅ 2a✅ config✅）                             │
         └─────────────────────────────────────────────────────────────┘
                                    │
     ┌──────────────────────────────┼──────────────────────────────┐
     ▼                              ▼                              ▼
┌─────────┐                   ┌─────────┐                   ┌─────────┐
│ 代理人 A │                   │ 代理人 B │                   │ 代理人 C │
│ 軌道 A   │                   │ 軌道 B   │                   │ 軌道 C   │
│ 生圖模組 │                   │ 圖庫模組 │                   │ LoRA文件 │
└────┬────┘                   └────┬────┘                   └────┬────┘
     │                              │                              │
     │         ┌────────────────────┴────────────────────┐         │
     │         ▼                                         ▼         │
     │   ┌─────────┐                              ┌─────────┐      │
     │   │ 代理人 E │                              │ 代理人 D │      │
     │   │ 軌道 E   │                              │ 軌道 D   │      │
     │   │ 進階功能 │                              │ LoRA訓練 │◄─────┘
     │   └─────────┘                              └────┬────┘
     │                                                 │
     └─────────────────────────────────────────────────┼─────────────┐
                                                       ▼             │
                                                ┌─────────┐          │
                                                │ 代理人 F │          │
                                                │ 軌道 F   │◄─────────┘
                                                │ MCP介面  │
                                                └─────────┘
```

---

## 三、各代理人任務與可並行步驟

### 代理人 A · 軌道 A · 生圖模組

| 步驟 | 任務 ID | 說明 | 實作檔案 | 依賴 | 狀態 |
|------|---------|------|----------|------|------|
| A1 | 1b | Workflow JSON 管理 | `core/workflow.py`, `workflows/*.json` | 1a ✅ | [v] |
| A2 | 1c | 批次生圖排程器 | `core/queue.py` | 1b | [v] |
| A3 | 1d | 基礎 UI（參數面板） | `pages/Generate.tsx` | API 契約 | [v] |

**必讀**：`docs/api-contract.md` 模組 1、`docs/internal-interfaces.md` workflow/queue、`docs/comfyui-di-design.md`、`app/schemas/generate.py`

**可與 B、C 並行**：A1 完成後，A2 與 B、C 可並行；A3 可依 stub API 先行開發。

**擴展性審核**：已審核，見 `docs/reviews/extensibility-review-agent-a.md`。Verdict：有風險。Phase 4 前建議處理 queue/recording 抽象；`MAX_PENDING`/`WORKFLOW_TEMPLATE` 建議移至 config（when-touching）。

---

### 代理人 B · 軌道 B · 圖庫模組

| 步驟 | 任務 ID | 說明 | 實作檔案 | 依賴 | 狀態 |
|------|---------|------|----------|------|------|
| B1 | 2b | 自動記錄 Pipeline | `core/recording.py` | 2a ✅ | [v] |
| B2 | 2c | Gallery 瀏覽器 | `pages/Gallery.tsx`, `api/gallery.py` | 2b | [v] |
| B3 | 2d | 一鍵重現 / 匯出 | `api/gallery.py` | 2b | [v] |

**必讀**：`docs/api-contract.md` 模組 2、`docs/internal-interfaces.md` recording、`app/schemas/gallery.py`

**可與 A、C 並行**：B1–B3 可同時進行（B2、B3 依 B1）。

**擴展性審核**：已審核，見 `docs/reviews/agent-b-extensibility-review.md`。Verdict：有風險。須注意項目與階段：

| 項目 | 須注意階段 | 說明 |
|------|------------|------|
| GalleryRepository 抽象 | **before-phase-5** | E2 生成統計分析需更多查詢 |
| `_to_image_url` 參數化 | when-touching | 下次改 gallery 時順便 |
| Export formatter 抽出 | when-touching | 加新 export 格式時再重構 |
| 日期錯誤回傳 400 | when-touching | 避免靜默忽略無效日期 |

---

### 代理人 C · 軌道 C · LoRA 文件工具

| 步驟 | 任務 ID | 說明 | 實作檔案 | 依賴 | 狀態 |
|------|---------|------|----------|------|------|
| C1 | 3a | 資料夾監聽 .txt | `services/watcher.py` | config | [v] |
| C2 | 3b | 圖片上傳介面 | `pages/LoraDocs.tsx`, `api/lora_docs.py` | API 契約 | [v] |
| C3 | 3c | Caption 編輯器 | `pages/LoraDocs.tsx`, `api/lora_docs.py` | C2 | [v] |
| C4 | 3d | 打包下載 | `api/lora_docs.py` | config | [v] |

**必讀**：`docs/api-contract.md` 模組 3、`docs/internal-interfaces.md` watcher、`app/schemas/lora_docs.py`、`.cursor/skills/wd-tagger/SKILL.md`

**可與 A、B 並行**：C1–C4 彼此可並行（C3 依 C2）。

**擴展性審核**：已審核，見 `docs/reviews/agent-c-extensibility-review.md`。Phase 4 前建議抽出 CaptionProvider Protocol；WD Tagger 參數可配置、IMAGE_EXTENSIONS 共用、watcher 狀態封裝、api-contract 補 GET /files 為 when-touching 項目。

---

### 代理人 D · 軌道 D · LoRA 訓練與產圖串接

| 步驟 | 任務 ID | 說明 | 實作檔案 | 依賴 | 狀態 |
|------|---------|------|----------|------|------|
| D1 | 4a | LoRA 訓練執行器 | `services/lora_trainer.py` | A, C | [v] |
| D2 | 4b | 訓練觸發邏輯 | `lora_trainer.py` | 4a, 3a | [v] |
| D3 | 4c | 訓練完成 → 產圖 Pipeline | `lora_trainer` → comfyui + recording | 4a, A, B | [ ] |
| D4 | 4d | 訓練狀態與佇列 | `api/lora_train.py`, `pages/LoraTrain.tsx` | 4a | [ ] |

**必讀**：`docs/api-contract.md` 模組 4、`docs/internal-interfaces.md` lora_trainer、`app/schemas/lora_train.py`、`.cursor/skills/lora-train-docs/SKILL.md`、`.cursor/skills/kohya-sd-scripts/SKILL.md`

**前置**：軌道 A、B、C 完成後始可進行。

**擴展性審核**：已審核，見 [`docs/reviews/agent-d-extensibility-review.md`](docs/reviews/agent-d-extensibility-review.md)。Kohya 參數可配置、IMAGE_EXTENSIONS 共用為 when-touching 項目。

---

### 代理人 E · 軌道 E · 進階功能

| 步驟 | 任務 ID | 說明 | 實作檔案 | 依賴 | 狀態 |
|------|---------|------|----------|------|------|
| E1 | 5b | Prompt 模板庫 | `core/prompt_templates.py` | 2a ✅ | [v] |
| E2 | 5c | 生成統計分析 | `api/analytics.py` | 2a ✅, 2c | [v] |

**必讀**：`docs/api-contract.md`、`app/schemas/gallery.py`

**擴展性審核**：已審核，見 [`docs/reviews/agent-e-extensibility-review.md`](docs/reviews/agent-e-extensibility-review.md)。Phase 5 擴展性注意已處理。

**可與 A、B、C 並行**：E1 可獨立；E2 需 2c（Gallery）完成後有資料。

---

### 代理人 F · 軌道 F · MCP 自然語言介面

| 步驟 | 任務 ID | 說明 | 實作檔案 | 依賴 | 狀態 |
|------|---------|------|----------|------|------|
| F1 | 6a | MCP Server 建置 | `mcp-server/` | Phase 1–4 | [ ] |
| F2 | 6b | 生圖與訓練 Tools | `mcp-server/tools/` | 6a | [ ] |
| F3 | 6c | 角色與風格語意對應 | `mcp-server/character_style.py` | 6b | [ ] |
| F4 | 6d | MCP 整合文件與 Cursor 配置 | `docs/mcp-setup.md` | 6b | [ ] |

**必讀**：`docs/api-contract.md` 全模組、`docs/handoff-index.md`

**前置**：Phase 1–4（軌道 A、B、C、D）完成後始可進行。

---

## 四、擴展性須注意項目（依階段）

> 來源：Agent A、B、C 擴展性審核報告。實作或重構時優先處理 Phase 4/5 前項目。

| 需注意階段 | 項目 | 責任代理人 |
|------------|------|------------|
| **Phase 4 前** | queue/recording 抽象／注入（lora_trainer 需共用） | A, B |
| **Phase 4 前** | CaptionProvider Protocol（支援 BLIP2 前先抽象） | C |
| **Phase 5 前** | GalleryRepository 抽象（E2 分析需更多查詢） | B |
| when-touching | MAX_PENDING、WORKFLOW_TEMPLATE 移至 config | A |
| when-touching | 每圖一 Session 改為單一 transaction | B |
| when-touching | queue 類別化、消除模組級全域狀態 | A |
| when-touching | workflow 結構可配置化 | A |
| when-touching | _to_image_url 參數化、Export formatter 抽出、日期錯誤回傳 400 | B |
| when-touching | 模板來源可配置（prompt_templates）、analytics 改為 GalleryRepository | E |
| when-touching | WD Tagger 參數可配置（repo_id、batch_size、thresh、timeout） | C |
| when-touching | IMAGE_EXTENSIONS 共用、watcher 狀態封裝、api-contract 補 GET /files | C |

---

## 五、並行時序摘要

| 階段 | 可同時執行的代理人 | 說明 |
|------|---------------------|------|
| 階段 1 | **A, B, C**（可加 E1） | 生圖、圖庫、LoRA 文件並行 |
| 階段 2 | **D** | 等 A、B、C 完成 |
| 階段 3 | **E2**（可與 D 重疊） | 等 2c Gallery 完成 |
| 階段 4 | **F** | 等 A、B、C、D 完成 |

---

## 六、完成後註記規範

完成任一任務後，須在 **README.md** 的「Agent 進度追蹤」區塊更新：

1. 將該任務的 `[ ]` 改為 `[v]`
2. 填寫 **完成者**（代理人代號或名稱）
3. 填寫 **完成檔案位置**（實際修改的檔案路徑）

範例：

```markdown
| 1a | ComfyUI API 串接 | [v] | `core/comfyui.py` | Agent A | `backend/app/core/comfyui.py` |
```

---

## 七、快速參考：介面文件路徑

```
docs/
├── api-contract.md        # REST API 契約 ← 全員必讀
├── internal-interfaces.md # 後端模組介面 ← A,B,C,D
├── handoff-index.md       # 對接索引
├── agent-assignment.md    # 本文件
├── comfyui-di-design.md   # ComfyUI 設計 ← A,D
├── extensibility-review-agent-a.md  # Agent A 生圖模組擴展性審核
└── reviews/
    ├── agent-b-extensibility-review.md  # Agent B 圖庫模組擴展性審核
    ├── agent-c-extensibility-review.md  # Agent C LoRA 文件擴展性審核
    └── agent-e-extensibility-review.md  # Agent E 進階功能擴展性審核

backend/app/schemas/       # Pydantic 模型 ← A,B,C,D
frontend/src/types/api.ts  # 前端型別 ← A,B,C,D,E
```
