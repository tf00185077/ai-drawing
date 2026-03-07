---
name: python-extensibility-review
description: Review Python backend code with focus on extensibility, low coupling, clear boundaries, and future-proof architecture. Use when reviewing APIs, services, repositories, async jobs, domain logic, integrations, or backend refactors.
---

# Python Backend 擴展性審核 Skill

> **核心目標**：擴展性（extensibility）、低耦合（low coupling）。審核時問：「若產品新增 3 個類似功能、2 個外部整合、1 個新儲存後端，這份程式碼能否演進而無須大改？」

---

## 審核前準備

開始審核前，須先釐清專案的預期架構與契約，避免用錯標準：

1. **讀專案介面文件**：如 `internal-interfaces.md`、`api-contract.md`、`AGENTS.md`
2. **確認契約**：被審核模組應符合的文件、簽名、呼叫時機
3. **找出參考範例**：識別專案中設計較佳的模組（如已用 DI + Protocol 者），作為對照基準

**目的**：有「預期架構」才能判斷現況是否偏離，也利於與既有好範例做一致性檢視。

---

## 審核時機

- 新增或修改 API 端點
- 新增服務層、repository、第三方整合
- 異步任務、佇列、排程
- 重構或架構檢視

---

## 審核優先順序

1. 架構與邊界
2. 依賴方向
3. 擴展性
4. 可測性
5. 可讀性與維護性
6. 正確性風險
7. 效能
8. 風格（最後處理）

---

## 快速檢查清單

### 1. 職責分離（Separation of Concerns）

| 層級 | 職責 | 不應混入 |
|------|------|----------|
| API 層 | 路由、請求解析、回應格式 | 業務邏輯、SQL |
| 服務層 | 編排、業務規則 | DB 細節、HTTP 物件 |
| 領域層 | 核心規則、領域模型 | 框架、儲存 |
| 持久層 | 查詢、寫入、交易 | 業務決策 |
| 整合層 | 呼叫外部 API、adapter | 業務規則 |

**Flag**：route handler 含業務邏輯、controller 含 SQL、一個 class 同時處理驗證 + 編排 + DB + HTTP。

### 2. 依賴設計（Dependency Direction）

**偏好**：
- 依賴注入（DI）
- Repository / Gateway 抽象
- Adapter 模式包第三方 API
- 透過設定控制行為

**Flag**：
- Service 到處 import 具體實作
- 業務邏輯直接依賴 SDK client
- 換實作需改很多檔案
- 隱藏的全域狀態影響行為

### 3. 擴展性

問自己：
- 新增一個類似功能，需改幾個檔案？能否只在 1–2 處新增？
- 新增第二種實作（如另一個儲存後端）是否容易？
- 新 endpoint 能否重用既有 service 邏輯？

**Flag**：
- 邏輯在模組間重複
- 每個新功能都在同一 service 加 if/elif
- 行為依賴硬編碼 type check
- 新功能靠 copy-paste
- **結構假設耦合**：對外部結構（JSON、API 回應、檔案格式）有隱含假設，結構一變需改多處

### 4. 介面品質

**偏好**：小、清楚、穩定、表達意圖。

- 明確的輸入/輸出
- 型別化 DTO / schema
- 狹窄的 service 合約

**Flag**：
- 方法簽名過胖
- 到處用 `dict` / `**kwargs`
- 回傳型別不一致
- 單一介面承擔太多責任

### 5. 資料存取

**偏好**：
- 獨立的 repository / query 層
- DB 細節與業務邏輯分離
- 交易邊界明確

**Flag**：
- ORM model 到處洩漏
- 查詢邏輯重複
- 業務邏輯依賴 DB 特有行為

### 6. 設定與環境

**偏好**：環境變數、集中設定、必要時 feature flag。

**Flag**：URL、secret、timeout、路徑、上限硬編碼在程式碼。

### 7. CLI / subprocess 整合

呼叫外部 CLI（如 WD Tagger、Kohya scripts）時，檢查：

| 項目 | 偏好 | Flag |
|------|------|------|
| 可執行檔路徑 | 從 config 讀取 | 寫死在程式碼 |
| 參數（repo_id、batch_size、thresh 等） | 可配置或由設定檔控制 | 硬編碼 |
| timeout、cwd、env | 可調整 | 魔法常數 |
| 抽象 | Adapter / Protocol 包起來 | 直接 subprocess 嵌在業務邏輯 |

**目的**：未來換工具或加第二種實作時，不需改動呼叫端。

---

## 必要輸出格式

審核完成後依序產出：

1. **Overall Verdict**：整體 verdict（通過 / 有風險 / 需重構）
2. **Architecture Summary**：架構摘要
3. **Positive Findings**（做得好的設計）：點出設計較佳處，避免過度重構，並供其他模組參考
4. **Extensibility Risks**：擴展性風險
5. **Coupling & Boundary Issues**：耦合與邊界問題
6. **Testability Issues**：可測性問題
7. **Concrete Refactor Suggestions**：具體重構建議
8. **Priority Order of Fixes**：修復優先順序（含 Fix Urgency，見下）
9. **使用者測試方法與預期結果**：使用者如何驗證、各項測試的預期結果

盡量說明：
- 目前設計偏向什麼
- 未來哪些變更會吃力
- 建議的抽象邊界

---

## 嚴重程度分級

| 等級 | 含義 |
|------|------|
| **Critical** | 會明顯阻礙擴展、替換或安全擴充 |
| **Major** | 能運作，但未來功能會導致重複或脆弱變更 |
| **Minor** | 建議改進，尚不阻礙成長 |

---

## Fix Urgency（修復時機）

針對每個 finding，標註**何時修**，避免「全部都要立刻改」的過度反應：

| 等級 | 含義 | 範例 |
|------|------|------|
| **now** | 阻礙當前開發，需立即處理 | 編譯不過、測試全掛、阻塞其他 Agent |
| **before-phase-X** | 在該階段前處理，否則後續會吃力 | 要加 BLIP2 前，先抽出 CaptionProvider |
| **when-touching** | 下次改該模組時順便修，不必特地開工 | 路過 recording 時一併加 Repository |

**若有 roadmap**：依階段判斷「何時會踩到這個問題」，再決定 Fix Urgency。

---

## Python 具體建議

### 依賴注入（FastAPI）

```python
# 偏好：透過 Depends 注入
def get_comfy_client() -> ComfyUIClient:
    return ComfyUIClient(base_url=get_settings().comfyui_base_url)

@router.post("/")
async def trigger_generate(comfy: ComfyUIClient = Depends(get_comfy_client)):
    ...
```

### Adapter 抽象外部 API

```python
# 定義介面，業務邏輯依賴介面
class ImageGenerationClient(Protocol):
    def submit(self, workflow: dict) -> str: ...
    def get_result(self, prompt_id: str) -> dict: ...

# 具體實作可替換
class ComfyUIAdapter(ImageGenerationClient):
    ...
```

### Repository 隔離資料存取

```python
# 業務邏輯依賴抽象
class ImageRecordRepository(Protocol):
    def save(self, record: GeneratedImage) -> None: ...
    def get_by_id(self, id: int) -> GeneratedImage | None: ...

# 具體實作可替換（SQLite、PostgreSQL、Mock）
class SQLAlchemyImageRepository(ImageRecordRepository):
    ...
```

---

## 反模式（強烈 Flag）

- Fat controller（route 含大量邏輯）
- God service（單一 class 管太多領域）
- Copy-paste feature branching
- 業務邏輯散落各處的 DB 查詢
- 第三方整合邏輯硬編碼在 domain
- 隱藏的共享可變狀態（模組級變數被 mutate，如 `_observer`、`_debounce_timers`）
- 持續堆疊無關職責的 utility 模組
- Request/Response 物件滲入 service 深層
- 「再加一個 if/elif」的擴展模式
- **結構假設耦合**：對 JSON、API 回應、檔案格式有隱含假設，結構變更需改多處

---

## 最終啟發式問題

- 此模組職責若翻倍，會怎樣？
- 需要第二種實作時，會怎樣？
- 要單獨測試時，會怎樣？
- API 變了但業務邏輯應保持穩定時，會怎樣？
- 背景 job 和 HTTP endpoint 需要共用邏輯時，會怎樣？

**若答案是「很多檔案必須一起改」，擴展性就弱。**

---

## 使用者測試方法與預期結果

審核報告或重構完成後，須附上使用者可執行的測試方法及對應的預期結果，供驗證功能正確性。

### 1. 單元測試（無需啟動服務、無需外部依賴）

| 項目 | 說明 |
|------|------|
| **指令** | `cd backend && pytest tests/<相關測試檔> -v` |
| **適用** | 工具函數、服務邏輯、DI 工廠、Protocol 實作 |
| **預期結果** | 所有測試 PASSED，無 FAILED / ERROR |
| **範例** | `pytest tests/test_comfyui.py -v` → 6 passed |

### 2. API 端點測試（需啟動後端）

| 項目 | 說明 |
|------|------|
| **前置** | `uvicorn app.main:app --reload` |
| **指令** | `Invoke-RestMethod`、curl、或 Swagger UI `http://localhost:8000/docs` |
| **適用** | 驗證 DI 注入、路由正確、依賴解析無 500 |
| **預期結果** | 依 endpoint 設計；若為 stub 則 501 + `{"detail":"TODO: ..."}` 表示 DI 成功 |
| **注意** | PowerShell `Invoke-RestMethod` 對非 2xx 會拋錯，但回應體已收到，可視為連線成功 |

**範例（生圖 API stub）：**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/generate/" -Method Post -ContentType "application/json" -Body "{}"
# 預期：PowerShell 拋出，但伺服器日誌顯示 "501 Not Implemented"、回應為 {"detail":"TODO: ComfyUI API 串接"}
# 若 DI 失敗：會是 500 Internal Server Error
```

### 3. 設定／環境變數測試

| 項目 | 說明 |
|------|------|
| **方式** | 在 `.env` 設定 `COMFYUI_BASE_URL`、`COMFYUI_TIMEOUT_*` 等 |
| **驗證** | 執行單元測試（mock get_settings）或暫時 `print(settings.xxx)` 確認讀取 |
| **預期結果** | 程式讀取到 `.env` 中的值，非硬編碼預設 |

### 4. 整合測試（需外部服務）

| 項目 | 說明 |
|------|------|
| **前置** | 啟動 ComfyUI、DB 等外部依賴 |
| **適用** | 真實打 ComfyUI API、寫入 DB、完整流程 |
| **預期結果** | 依業務需求；例如 ComfyUI 回傳 queue、生圖完成寫入記錄 |

### 5. 報告輸出範本

審核／重構完成時，應附上類似表格：

| 測試類型 | 指令／步驟 | 預期結果 |
|----------|------------|----------|
| 單元測試 | `pytest tests/test_comfyui.py -v` | 6 passed |
| API（DI 驗證） | 起後端 → `POST /api/generate/` | 501 + `{"detail":"TODO: ..."}`，非 500 |
| 設定 | 設 `.env` 後執行對應 pytest | mock 驗證或 print 確認讀取正確 |

---

## 進一步參考

- 完整維度說明、反模式清單、重構 patterns → [reference.md](reference.md)
