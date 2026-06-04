# Task Specs — Phase 4：新功能 + 前端

## 全量測試指令

`pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

## 執行規則

- 同一 step 最多重試 2 次，第 3 次失敗停止並回報
- 每個 task 最後一個 step 永遠是全量測試
- #25, #26 可並行；#18, #19 前端任務 TypeScript 編譯通過為 pass 標準，功能正確性需人工確認
- #26 依賴 #25

---

### Task #25：新增 LLM caption 標注 API endpoint

**Goal**: `POST /api/lora-docs/caption-llm` 接受 `{"image_path": str}`，呼叫 LLM vision 並回傳 `{"caption": str}`。
**Dependencies**: 無
**Files**: `backend/app/api/lora_docs.py`, `backend/tests/test_lora_docs.py`

#### Step 1：新增 Request schema 與 endpoint

**What**:
```python
class CaptionLlmRequest(BaseModel):
    image_path: str

@router.post("/caption-llm")
async def caption_with_llm(body: CaptionLlmRequest):
    """呼叫 LLM 對圖片產生訓練用 caption"""
    ...  # 呼叫 Claude / OpenAI vision API
    return {"caption": result}
```
**Goal**: endpoint 存在，路由為 POST /api/lora-docs/caption-llm
**Verify**:
- `grep -n "caption.llm\|caption_llm" backend/app/api/lora_docs.py` → 有輸出，包含 `@router.post`

#### Step 2：新增測試（mock LLM 呼叫）

**What**: mock LLM 回傳假 caption，POST `/api/lora-docs/caption-llm` → 200，回應包含 `caption` 欄位
**Verify**:
- `pytest backend/tests/test_lora_docs.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #26：新增 caption_image MCP tool

**Goal**: `caption_image(image_path)` 呼叫 `POST /api/lora-docs/caption-llm` 並回傳 caption 字串。
**Dependencies**: #25
**Files**: `mcp-server/mcp_server/tools/`（擴充現有或新增檔案）, `mcp-server/tests/test_tools.py`

#### Step 1：實作 tool

**What**:
```python
@mcp.tool()
def caption_image(image_path: str) -> str:
    """對指定圖片呼叫 LLM 產生訓練用 caption。"""
    client = _get_client()
    data = client.post("/api/lora-docs/caption-llm", json={"image_path": image_path})
    return data.get("caption", "")
```
**Goal**: caption_image tool 存在
**Verify**:
- `grep -rn "caption_image" mcp-server/mcp_server/tools/` → 有輸出，包含 `@mcp.tool`

#### Step 2：新增測試

**What**: mock post 回傳 `{"caption": "1girl, solo, ..."}`, 斷言 tool 回傳 caption 字串
**Verify**:
- `pytest mcp-server/tests/test_tools.py -x -q -k "caption"` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #18：Generate.tsx 進階參數折疊區

**Goal**: 頁面有可展開的「進階參數」區塊，含 width/height/batch_size/sampler_name/scheduler/lora_strength/denoise 輸入欄位。
**Dependencies**: 無
**Files**: `frontend/src/pages/Generate.tsx`

> **自動驗證限制**：前端無 unit test。TypeScript 編譯通過為最低 pass 標準，UI 功能正確性需人工確認。

#### Step 1：新增折疊區塊與欄位

**What**: 在 Generate.tsx 加入可折疊的 `<details>` 或 accordion 元件，內含以上 7 個參數的輸入元件，submit 時將這些值帶入 POST body
**Verify**:
- `grep -n "lora_strength\|denoise\|sampler_name" frontend/src/pages/Generate.tsx` → 至少 3 行有輸出
- `cd frontend && npx tsc --noEmit 2>&1 | head -20` → 無 TypeScript error

---

### Task #19：LoraTrain.tsx 補 keep_tokens/mixed_precision/generate_after

**Goal**: 訓練頁面新增三個欄位的輸入（keep_tokens: number, mixed_precision: select, generate_after: 子表單）。
**Dependencies**: 無
**Files**: `frontend/src/pages/LoraTrain.tsx`

> **自動驗證限制**：同 #18，TypeScript 編譯通過為最低標準。

#### Step 1：新增三個輸入欄位

**What**: 新增 keep_tokens（數字輸入）、mixed_precision（select: fp16/bf16/fp32）、generate_after（含 prompt 文字欄和 count 數字輸入的子區塊）
**Verify**:
- `grep -n "keep_tokens\|mixed_precision\|generate_after" frontend/src/pages/LoraTrain.tsx` → 至少 3 行有輸出
- `cd frontend && npx tsc --noEmit 2>&1 | head -20` → 無 TypeScript error
