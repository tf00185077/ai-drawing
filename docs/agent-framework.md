# Agent 自主執行框架

跨 project 通用。描述如何將任務拆解成 agent 可自主執行並自我驗證的 spec。

---

## 核心概念

### Goal vs. Verify 分離

**Goal** = 完成後世界應該長什麼樣子（人類語言，描述狀態）  
**Verify** = 如何用指令確認 Goal 已達成（可執行指令 + pass 標準）

這兩者必須分開寫。Goal 說「是什麼」，Verify 說「怎麼證明」。

---

## 結構

```
Task
├── goal        任務完成的整體預期狀態（一句話）
├── dependencies 必須先完成的 task 編號
├── files       主要修改的檔案
└── steps
    ├── Step 1
    │   ├── what    做什麼（動作）
    │   ├── goal    這個 step 的完成判定（observable、specific）
    │   └── verify  指令清單 + pass 標準
    ├── Step 2 ...
    └── Step N  永遠是全量測試（regression）
```

---

## 好的 Goal 的五個屬性

| 屬性 | 說明 | 反例 → 正例 |
|------|------|------------|
| **Observable** | 可用指令檢查，不靠人眼 | "看起來正確" → `grep` 有輸出 |
| **Specific** | 有具體名稱/數值 | "加一個欄位" → "加 `lora_strength: float \| None = None`" |
| **Falsifiable** | 明確 pass/fail，沒有「差不多」 | "差不多對了" → exit 0 或 exit 非 0 |
| **Atomic** | 一個 goal 只描述一件事 | 兩件事塞一個 goal → 拆成兩個 step |
| **Terminal** | 說明什麼時候「夠了」 | "盡量改善" → "所有測試通過" |

---

## 五類 Verify 方法

不是每個 step 都能用 unit test，但每個 step 都可以驗證。

| 類型 | 何時使用 | 範例 |
|------|---------|------|
| **Structural** | 欄位/函式/import 是否存在 | `grep -n "field_name" path/to/file.py` → 有輸出 |
| **Negative** | 某東西應該已被移除 | `grep -r "old_import" src/` → 無輸出 |
| **Type check** | 型別改動後確認不破壞 | `mypy path/to/file.py` → exit 0 |
| **Unit test** | 函式行為、API 回應、DB 操作 | `pytest tests/test_xxx.py -x -q` → exit 0 |
| **Smoke test** | 整體不崩潰 | `pytest tests/test_main.py::test_root -x` → exit 0 |
| **Format check** | 文件包含必要章節 | `grep -n "## Usage" docs/skill.md` → 有輸出 |
| **Compile check** | 前端/靜態語言編譯通過 | `npx tsc --noEmit` → exit 0 |

### 選擇 Verify 類型的決策規則

```
step 性質                    → 使用
─────────────────────────────────────────────────────
新增欄位/函式               → Structural + Unit test
移除欄位/檔案/import        → Negative + Smoke test
型別/Schema 改動            → Type check + Unit test
新增 API endpoint           → Unit test（TestClient）
文件撰寫                    → Format check（grep 必要章節）
前端 UI 改動                → Compile check（tsc/build）
整體 regression             → 全量 Unit test
```

---

## 執行規則（可依 project 調整）

| 規則 | 預設值 | 說明 |
|------|--------|------|
| **失敗重試** | 2 次 | 同一 step 最多重試 2 次，第 3 次停止並回報 |
| **Regression** | 每個 task | 每個 task 最後一個 step 永遠是全量測試 |
| **停止條件** | verify 失敗 3 次 | 輸出失敗的指令與實際輸出，等待人工介入 |
| **跳過規則** | 明確標注 | 無法自動驗證的 step 要標注「需人工確認」 |

---

## Task Spec 模板

```markdown
### Task #{編號}：{標題}

**Goal**: {完成後的整體狀態，一句話，符合五屬性}
**Dependencies**: {依賴的 task 編號，或「無」}
**Files**: {主要修改的檔案路徑}

#### Step 1：{動作標題}

**What**: {做什麼，足夠具體讓 agent 不需猜測}
**Goal**: {這個 step 的完成判定}
**Verify**:
- `{指令}` → expect: {pass 標準}
- `{指令}` → expect: {pass 標準}
**If failed**: {停止並回報 / 嘗試 X 替代方案}

#### Step N：全量回歸測試

**Verify**:
- `{full test command}` → exit 0
```

---

## 寫 Spec 之前的必要準備

Spec 裡的每個 verify 指令都是具體路徑和關鍵字，**沒有以下兩件事就無法寫出有效的 spec**。

### 前提一：充分探索現有 codebase

寫 spec 之前必須知道：

| 需要知道的 | 用途 |
|-----------|------|
| 主要檔案的路徑與結構 | verify 指令的 grep 目標 |
| 現有程式碼的欄位名、函式簽名 | 才能寫「加什麼」而不是「加一些東西」 |
| 測試在哪裡、用什麼框架跑 | 全量測試指令、每個模組對應哪個 test file |
| 哪些東西已存在、哪些需要新建 | 避免 spec 要求 agent 重複造輪子 |

探索方式：讀主要模組的程式碼、讀現有測試的 fixture 和 mock 模式、跑一次全量測試確認基準線是綠燈。

### 前提二：設計決策已定案

Goal 的 Specific 屬性要求所有名稱和型別都必須確定，寫 spec 前需要決定：

| 決策類型 | 範例 |
|---------|------|
| 新欄位的名稱與型別 | `lora_strength: float \| None`，不是「一個強度欄位」 |
| 新 API endpoint 的 path 和 method | `GET /api/generate/job/{job_id}`，不是「一個查詢端點」 |
| 新函式的簽名 | `cancel_job(job_id: str) -> None`，不是「一個取消函式」 |
| 枚舉的合法值 | `Literal["fp16", "bf16", "fp32"]`，不是「幾個精度選項」 |

設計還沒定就寫 spec，Goal 會淪為模糊描述，agent 被迫自行決策，結果不可控。

> **判斷標準**：如果你在寫 Goal 時需要用「適當的」、「一些」、「合理的」這類詞，代表設計還沒定，先停下來決定設計再寫。

---

## 如何為新 Project 寫 Spec

### Step 1：盤點任務性質

將所有 task 依性質分類：

| 性質 | 天然的 Verify 方法 |
|------|-------------------|
| Schema / 型別改動 | Type check + Unit test |
| DB 欄位新增 | Unit test（in-memory DB） |
| 新增 API endpoint | TestClient unit test |
| 刪除程式碼/檔案 | Negative check + Smoke test |
| 新增 SDK/library tool | Unit test（mock 外部依賴） |
| 文件撰寫 | Format check（grep 章節標題） |
| 前端 UI | Compile check，功能正確性標注為人工確認 |
| 設定檔改動 | Structural check（grep） + Smoke test |

### Step 2：找出 Task 間的 dependency

畫出 dependency graph，找出哪些可並行、哪些必須串行。  
依賴關係寫在每個 task 的 `Dependencies` 欄位。

### Step 3：確認全量測試指令

每個 project 的全量測試指令不同，但 spec 裡的最後 step 都應該是同一個指令。  
在 spec 頂部定義一次：

```markdown
## 全量測試指令

`{your test command}` → exit 0
```

### Step 4：標注無法自動驗證的任務

下列情況無法用指令完整驗證，需在 step 裡明確標注：
- 前端 UI 行為（只能 compile check，功能需人工確認）
- LLM 輸出品質（只能驗證 endpoint 存在並回傳 200）
- 文件內容正確性（只能驗證結構，內容需人工確認）
- 需要外部服務運行的 end-to-end 流程

格式：在 step 前加一行 `> **自動驗證限制**：{說明限制，功能正確性需人工確認}`

---

## 常見錯誤

| 錯誤 | 修正方式 |
|------|---------|
| Goal 寫「更新 schema」 | 改為「`field_name: type` 存在於 ClassName，mypy 通過」 |
| 把兩件事塞進一個 step | 拆成兩個 step，各自有獨立 verify |
| 最後 step 不是全量測試 | 補上全量測試 step |
| Verify 沒有 pass 標準 | 每條 verify 都要有 `→ expect: {標準}` |
| 前端 step 沒有標注限制 | 補上「自動驗證限制」說明 |
| 移除程式碼的 step 只有 smoke test | 加 Negative check 確認舊東西真的消失 |
