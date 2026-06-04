# Task Specs — Phase 2：後端 API 接通

## 全量測試指令

`pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

## 執行規則

- 同一 step 最多重試 2 次，第 3 次失敗停止並回報
- 每個 task 最後一個 step 永遠是全量測試
- 依賴關係：#9 依賴 #5；#10 依賴 #5, #9；#3 依賴 #1, #2；#4 獨立

---

### Task #9：api/generate.py 補傳 lora_strength / denoise

**Goal**: `trigger_generate()` 將 `body.lora_strength` 和 `body.denoise` 傳給 `submit()`。
**Dependencies**: #5
**Files**: `backend/app/api/generate.py`

#### Step 1：在 params dict 有條件加入兩個欄位

**What**: 在 `trigger_generate()` 的 params 建構區加入：
```python
if body.lora_strength is not None:
    params["lora_strength"] = body.lora_strength
if body.denoise is not None:
    params["denoise"] = body.denoise
```
**Goal**: api/generate.py 有條件加入 lora_strength 和 denoise
**Verify**:
- `grep -n "lora_strength" backend/app/api/generate.py` → 有輸出
- `grep -n "denoise" backend/app/api/generate.py` → 有輸出

#### Step 2：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #10：workflow.apply_params() 加 lora_strength 參數

**Goal**: `apply_params()` 接受 `lora_strength` 並替換 workflow 中 LoRA loader 節點的強度值。
**Dependencies**: #5, #9
**Files**: `backend/app/core/workflow.py`, `backend/tests/test_workflow.py`

**Background**: `denoise` 已存在於 apply_params 簽名，只需新增 lora_strength。

#### Step 1：在 apply_params 加 lora_strength 參數

**What**: 新增 `lora_strength: float | None = None` 到函式簽名，並在 workflow 替換邏輯中替換 LoRALoader 節點的 `strength_model` 和 `strength_clip`
**Goal**: apply_params 簽名含 lora_strength
**Verify**:
- `grep -n "lora_strength" backend/app/core/workflow.py` → 有輸出（函式簽名 + 替換邏輯）

#### Step 2：新增/更新 test_workflow.py 測試

**What**: 建立含 LoRALoader 節點的 mock workflow dict，呼叫 `apply_params(workflow, lora_strength=0.8)`，斷言節點的 `strength_model == 0.8`
**Verify**:
- `pytest backend/tests/test_workflow.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #3：新增 GET /api/generate/job/{job_id}

**Goal**: 新端點回傳指定 job 的狀態（status、prompt_id、submitted_at）；job 不存在時 404。
**Dependencies**: #1, #2
**Files**: `backend/app/core/queue.py`, `backend/app/api/generate.py`, `backend/tests/test_generate_api.py`

#### Step 1：在 queue.py 新增 get_job_status(job_id) 函式

**What**: 從 `_pending` list 和 `_running` 找到指定 job_id，回傳 dict；找不到則 return None
**Goal**: get_job_status 函式存在且可被 import
**Verify**:
- `grep -n "def get_job_status" backend/app/core/queue.py` → 有輸出

#### Step 2：在 api/generate.py 新增 GET 端點

**What**:
```python
@router.get("/job/{job_id}")
async def get_job_status_endpoint(job_id: str):
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(404, "Job not found")
    return status
```
**Verify**:
- `grep -n "job_id" backend/app/api/generate.py` → 輸出包含 router.get

#### Step 3：新增測試

**What**: mock queue 回傳 job，GET `/api/generate/job/test-id` → 200；不存在的 job_id → 404
**Verify**:
- `pytest backend/tests/test_generate_api.py -x -q` → exit 0

#### Step 4：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #4：新增 DELETE /api/generate/queue/{job_id}

**Goal**: DELETE 端點從 pending queue 移除指定 job 並回傳確認；job 不存在或已在執行中則 404。
**Dependencies**: 無
**Files**: `backend/app/core/queue.py`, `backend/app/api/generate.py`, `backend/tests/test_generate_api.py`

#### Step 1：在 queue.py 新增 cancel_job(job_id) 函式

**What**: 從 `_pending` 找到指定 job_id 並移除；找不到或 job 已在 `_running` 則 raise ValueError
**Goal**: cancel_job 函式存在
**Verify**:
- `grep -n "def cancel_job" backend/app/core/queue.py` → 有輸出

#### Step 2：在 api/generate.py 新增 DELETE 端點

**What**:
```python
@router.delete("/queue/{job_id}", status_code=200)
async def cancel_job_endpoint(job_id: str):
    try:
        cancel_job(job_id)
        return {"cancelled": job_id}
    except ValueError as e:
        raise HTTPException(404, str(e))
```
**Verify**:
- `grep -n "cancel_job\|DELETE\|router.delete" backend/app/api/generate.py` → 有輸出

#### Step 3：新增測試

**What**: pending job → DELETE → 200；不存在 job_id → 404；running job → 404
**Verify**:
- `pytest backend/tests/test_generate_api.py -x -q` → exit 0

#### Step 4：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0
