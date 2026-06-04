# Agent Task Spec — Phase 1–4

## 執行規則

- **失敗策略**：同一個 step 最多重試 2 次。第 3 次失敗則停止，輸出失敗的 verify 指令與實際輸出，等待人工介入。
- **Regression**：每個 task 的最後一個 step 永遠是全量測試。
- **MCP 測試**：只用 mock（test_tools.py），不需要啟動 backend。
- **Phase 5**：跳過，openclaw 格式未確認，格式確認後再補。
- **前端任務**（#18, #19）：TypeScript 編譯通過為 pass 標準，功能正確性需人工確認。

---

## Phase 1：基礎層（Schema + DB）

依賴關係：#5 → #9 → #10；#1 → #2；其餘可並行。

---

### Task #1：GeneratedImage 加 job_id 欄位

**Goal**: `GeneratedImage` 模型有 `job_id` 欄位，test_recording.py 驗證其被存入。  
**Dependencies**: 無  
**Files**: `backend/app/db/models.py`, `backend/tests/test_recording.py`

#### Step 1：在 models.py 加 job_id 欄位

**What**: 在 `GeneratedImage` class 加入 `job_id = Column(String(128), nullable=True)`，並在頂部 import 確認 String 已引入。  
**Goal**: `GeneratedImage` 有 job_id 欄位，型別為 `String(128)`, nullable  
**Verify**:
- `grep -n "job_id" backend/app/db/models.py` → 有輸出，包含 `Column` 與 `String`

#### Step 2：更新 test_recording.py 驗證 job_id 被儲存

**What**: 新增或更新測試呼叫 `save(..., job_id="test-job-123")`，斷言回傳物件的 `record.job_id == "test-job-123"`  
**Goal**: 測試明確覆蓋 job_id 欄位的存取  
**Verify**:
- `grep -n "job_id" backend/tests/test_recording.py` → 有輸出
- `pytest backend/tests/test_recording.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #2：recording.save() 補傳 job_id

**Goal**: `save()` 函式接受 `job_id` 參數並寫入 DB；`queue.py` 呼叫時帶入 job_id。  
**Dependencies**: #1  
**Files**: `backend/app/core/recording.py`, `backend/app/core/queue.py`

#### Step 1：在 recording.save() 加 job_id 參數

**What**: 在 `save()` 的 keyword-only 參數加入 `job_id: str | None = None`，並在 `GeneratedImage(...)` 建構時帶入。  
**Goal**: save() 簽名含 job_id，GeneratedImage 建構時使用此值  
**Verify**:
- `grep -n "job_id" backend/app/core/recording.py` → 至少 2 行輸出（函式簽名 + 建構式）

#### Step 2：更新 queue.py 呼叫 recording_save 時傳入 job_id

**What**: 找到 `recording_save(...)` 的呼叫點，加入 `job_id=job.job_id`  
**Goal**: queue.py 呼叫 recording_save 時帶 job_id  
**Verify**:
- `grep -n "recording_save" backend/app/core/queue.py` → 輸出行包含 `job_id`

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #5：GenerateRequest 加 lora_strength / denoise 欄位

**Goal**: `POST /api/generate` 接受 lora_strength 與 denoise，Pydantic 拒絕範圍外的值。  
**Dependencies**: 無  
**Files**: `backend/app/schemas/generate.py`, `backend/tests/test_generate_api.py`

#### Step 1：在 GenerateRequest 加兩個欄位

**What**:
```python
lora_strength: float | None = Field(default=None, ge=0.0, le=2.0)
denoise: float | None = Field(default=None, ge=0.0, le=1.0)
```
**Goal**: 兩個欄位存在於 GenerateRequest，有 ge/le 驗證  
**Verify**:
- `grep -n "lora_strength" backend/app/schemas/generate.py` → 有輸出，包含 `Field`
- `grep -n "denoise" backend/app/schemas/generate.py` → 有輸出，包含 `Field`（注意：denoise 已存在於 apply_params，只需確認 schema 層新增）

#### Step 2：新增/更新測試

**What**: 在 `test_generate_api.py` 新增測試：
- `lora_strength=1.0` → POST 回傳 201
- `lora_strength=3.0`（超出上限）→ 422
- `denoise=0.5` → 201

**Verify**:
- `pytest backend/tests/test_generate_api.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #6：GenerateRequest sampler_name / scheduler 加 Literal 枚舉

**Goal**: 兩個欄位改為 Literal 型別，無效 sampler 名稱被 Pydantic 拒絕（422）。  
**Dependencies**: 無  
**Files**: `backend/app/schemas/generate.py`, `backend/tests/test_generate_api.py`

**Background**: 目前 `sampler_name: str | None`、`scheduler: str | None`，無枚舉限制。

#### Step 1：改為 Literal 枚舉

**What**: 在 schemas/generate.py 頂部加 `from typing import Literal`，將欄位改為：
```python
sampler_name: Literal[
    "euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral",
    "lms", "dpmpp_2s_ancestral", "dpmpp_sde", "dpmpp_2m",
    "dpmpp_2m_sde", "dpmpp_3m_sde", "ddim", "uni_pc"
] | None = None

scheduler: Literal[
    "normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"
] | None = None
```
**Goal**: 兩個欄位使用 Literal 型別  
**Verify**:
- `grep -n "Literal" backend/app/schemas/generate.py` → 有輸出
- `grep -n "sampler_name" backend/app/schemas/generate.py` → 包含 `Literal`

#### Step 2：新增/更新測試

**What**: 合法值 `sampler_name="euler"` → 201；非法值 `sampler_name="invalid_sampler"` → 422  
**Verify**:
- `pytest backend/tests/test_generate_api.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #7：GenerateRequest width/height 上限改 4096

**Goal**: width 和 height 的 `le` 改為 4096，4097 被 Pydantic 拒絕。  
**Dependencies**: 無  
**Files**: `backend/app/schemas/generate.py`, `backend/tests/test_generate_api.py`

#### Step 1：修改 Field 上限

**What**: 將 `width` 和 `height` 兩個 Field 的 `le=2048` 改為 `le=4096`  
**Verify**:
- `grep -n "le=4096" backend/app/schemas/generate.py` → 出現 2 次（width 和 height 各一）
- `grep -n "le=2048" backend/app/schemas/generate.py` → 無輸出（確認舊值已移除）

#### Step 2：新增/更新測試

**What**: `width=4096` → 201；`width=4097` → 422  
**Verify**:
- `pytest backend/tests/test_generate_api.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #8：GenerateCustomRequest 改繼承 GenerateRequest

**Goal**: `GenerateCustomRequest(GenerateRequest)` 繼承，不重複定義共用欄位，只保留 `workflow`, `image`, `image_pose`。  
**Dependencies**: #5, #6, #7（建議先完成，避免重複改同一個欄位）  
**Files**: `backend/app/schemas/generate.py`

#### Step 1：重構 GenerateCustomRequest

**What**: 將 `class GenerateCustomRequest(BaseModel)` 改為 `class GenerateCustomRequest(GenerateRequest)`，移除已繼承的重複欄位（prompt, checkpoint, lora, negative_prompt, seed, steps, cfg, width, height, batch_size, sampler_name, scheduler），只保留：
```python
workflow: dict[str, Any] = Field(...)
image: str | None = Field(default=None, description="...")
image_pose: str | None = Field(default=None, description="...")
```
**Goal**: GenerateCustomRequest 繼承 GenerateRequest，class 定義不含重複欄位  
**Verify**:
- `grep -n "class GenerateCustomRequest" backend/app/schemas/generate.py` → 輸出包含 `(GenerateRequest)`
- `grep -c "prompt\|checkpoint\|lora\|negative_prompt\|seed\|steps\|cfg\|batch_size" backend/app/schemas/generate.py` → 計數比重構前少（重複定義已移除）

#### Step 2：確認 API 測試仍通過

**Verify**:
- `pytest backend/tests/test_generate_api.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #11：TrainStartRequest.generate_after 改必填

**Goal**: `generate_after` 從 `Optional` 改為必填欄位，呼叫方必須提供。  
**Dependencies**: 無  
**Files**: `backend/app/schemas/lora_train.py`, `backend/tests/test_lora_trainer.py`

**Background**: 目前 `generate_after: GenerateAfterParams | None = None`。

#### Step 1：改為必填

**What**: 將 `generate_after` 改為 `generate_after: GenerateAfterParams`（移除 `| None = None`）  
**Goal**: generate_after 不再是 Optional  
**Verify**:
- `grep -n "generate_after" backend/app/schemas/lora_train.py` → 輸出不含 `| None` 或 `= None`

#### Step 2：更新受影響的測試

**What**: 所有建立 `TrainStartRequest` 的地方都必須提供 `generate_after` 參數（加入 prompt 最少值）  
**Verify**:
- `pytest backend/tests/test_lora_trainer.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #12：TrainStartRequest.mixed_precision 加 Literal 枚舉

**Goal**: `mixed_precision` 改為 `Literal["fp16", "bf16", "fp32"] | None`，無效值被拒絕。  
**Dependencies**: 無  
**Files**: `backend/app/schemas/lora_train.py`, `backend/tests/test_lora_trainer.py`

#### Step 1：改為 Literal 枚舉

**What**:
```python
mixed_precision: Literal["fp16", "bf16", "fp32"] | None = None
```
確認 `from typing import Literal` 已引入。  
**Verify**:
- `grep -n "mixed_precision" backend/app/schemas/lora_train.py` → 輸出包含 `Literal`

#### Step 2：新增/更新測試

**What**: `mixed_precision="fp16"` → 合法；`mixed_precision="float16"` → 422  
**Verify**:
- `pytest backend/tests/test_lora_trainer.py -x -q` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

## Phase 2：後端 API 接通

依賴關係：#9 依賴 #5；#10 依賴 #5, #9；#3 依賴 #1, #2；#4 獨立。

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

**Background**: `denoise` 已存在於 apply_params 簽名（第 56 行），只需新增 lora_strength。

#### Step 1：在 apply_params 加 lora_strength 參數

**What**: 新增 `lora_strength: float | None = None` 到函式簽名，並在 workflow 替換邏輯中處理（替換 LoRALoader 節點的 `strength_model` 和 `strength_clip`）  
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

---

## Phase 3：MCP Tools 補齊

> 測試策略：全用 mock，不需要啟動 backend。

---

### Task #13：新增 get_available_resources MCP tool

**Goal**: `get_available_resources()` 呼叫 `GET /api/generate/available-resources`，回傳 checkpoints/loras/workflows 清單。  
**Dependencies**: 無（API 已存在）  
**Files**: `mcp-server/mcp_server/tools/generate.py`, `mcp-server/tests/test_tools.py`

#### Step 1：實作 tool

**What**: 在 generate.py 新增：
```python
@mcp.tool()
def get_available_resources() -> str:
    """列出可用的 checkpoints、LoRA 模型與 workflow 模板。"""
    client = _get_client()
    data = client.get("/api/generate/available-resources")
    return json.dumps(data, ensure_ascii=False, indent=2)
```
**Verify**:
- `grep -n "get_available_resources" mcp-server/mcp_server/tools/generate.py` → 有輸出，包含 `@mcp.tool`

#### Step 2：新增測試

**What**: mock `client.get` 回傳 `{"checkpoints": ["a.safetensors"], "loras": [], "workflows": ["default"]}`，呼叫 `get_available_resources()`，斷言回傳字串包含 `checkpoints`  
**Verify**:
- `pytest mcp-server/tests/test_tools.py -x -q -k "get_available_resources"` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #14：新增 get_job_result(job_id) MCP tool

**Goal**: `get_job_result(job_id)` 呼叫 `GET /api/generate/job/{job_id}` 並回傳 job 狀態字串。  
**Dependencies**: #3  
**Files**: `mcp-server/mcp_server/tools/generate.py`, `mcp-server/tests/test_tools.py`

#### Step 1：實作 tool

**What**: 新增 `get_job_result(job_id: str)` tool，呼叫 `client.get(f"/api/generate/job/{job_id}")`  
**Verify**:
- `grep -n "get_job_result" mcp-server/mcp_server/tools/generate.py` → 有輸出

#### Step 2：新增測試

**What**: mock get 回傳 job dict，斷言回傳值包含 job_id  
**Verify**:
- `pytest mcp-server/tests/test_tools.py -x -q -k "get_job_result"` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #15：新增 cancel_job(job_id) MCP tool

**Goal**: `cancel_job(job_id)` 呼叫 `DELETE /api/generate/queue/{job_id}` 並回傳確認訊息。  
**Dependencies**: #4  
**Files**: `mcp-server/mcp_server/tools/generate.py`, `mcp-server/tests/test_tools.py`

#### Step 1：實作 tool

**What**: 新增 `cancel_job(job_id: str)` tool，呼叫 `client.delete(f"/api/generate/queue/{job_id}")`（若 client 無 delete 方法則使用 `client.post` 或擴充 client）  
**Verify**:
- `grep -n "cancel_job" mcp-server/mcp_server/tools/generate.py` → 有輸出

#### Step 2：新增測試

**Verify**:
- `pytest mcp-server/tests/test_tools.py -x -q -k "cancel_job"` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #16：generate_image 補 width/height/sampler_name/scheduler/lora_strength/denoise

**Goal**: `generate_image()` tool 接受 6 個新參數並傳給 backend API body。  
**Dependencies**: #5, #6, #7, #9  
**Files**: `mcp-server/mcp_server/tools/generate.py`, `mcp-server/tests/test_tools.py`

#### Step 1：擴充 generate_image 函式簽名

**What**: 在 `generate_image()` 加入以下參數（與 backend schema 對齊）：
```python
width: int | None = None,
height: int | None = None,
sampler_name: str | None = None,
scheduler: str | None = None,
lora_strength: float | None = None,
denoise: float | None = None,
```
並在 body dict 有條件加入（`if xxx is not None: body["xxx"] = xxx`）  
**Goal**: 6 個新參數存在於 generate_image 簽名  
**Verify**:
- `grep -n "lora_strength\|denoise\|sampler_name" mcp-server/mcp_server/tools/generate.py` → 至少 3 行有輸出

#### Step 2：更新測試

**What**: 新增測試傳入 `lora_strength=0.8, width=1024`，斷言 body dict 包含這兩個欄位  
**Verify**:
- `pytest mcp-server/tests/test_tools.py -x -q -k "generate_image"` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

### Task #17：lora_train_start 補齊所有 schema 參數

**Goal**: `lora_train_start()` tool 包含 TrainStartRequest 所有欄位：resolution, keep_tokens, mixed_precision, network_dim, network_alpha，以及 generate_after 的子參數（prompt, count, batch_size, negative_prompt）。  
**Dependencies**: #11, #12  
**Files**: `mcp-server/mcp_server/tools/lora_train.py`, `mcp-server/tests/test_tools.py`

#### Step 1：擴充 lora_train_start 函式簽名

**What**: 新增以下參數（皆 optional）：
```python
resolution: int | None = None,
keep_tokens: int | None = None,
mixed_precision: str | None = None,   # "fp16" | "bf16" | "fp32"
network_dim: int | None = None,
network_alpha: int | None = None,
generate_after_prompt: str | None = None,
generate_after_count: int = 1,
generate_after_batch_size: int = 1,
generate_after_negative_prompt: str | None = None,
generate_after_checkpoint: str | None = None,
```
並將這些欄位有條件組裝進 body，`generate_after` 子欄位若有 `generate_after_prompt` 則組成 `GenerateAfterParams` 格式。  
**Goal**: mixed_precision, keep_tokens, network_dim 等欄位存在於 lora_train_start 簽名  
**Verify**:
- `grep -n "mixed_precision\|keep_tokens\|network_dim" mcp-server/mcp_server/tools/lora_train.py` → 有輸出

#### Step 2：更新測試

**What**: 新增測試傳入 `mixed_precision="fp16", keep_tokens=2`，斷言 body dict 包含這些欄位  
**Verify**:
- `pytest mcp-server/tests/test_tools.py -x -q -k "lora_train_start"` → exit 0

#### Step 3：全量回歸測試

**Verify**:
- `pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

---

## Phase 4：新功能

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

**What**: 在 Generate.tsx 加入可折疊的 `<details>` 或 accordion 元件，內含以上 7 個參數的輸入元件，state 和 form submit 時將這些值帶入 POST body  
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

---

## Phase 5：Skill 文件

**跳過**。openclaw skill 格式尚未確認，等格式確認後再補齊 #27–#29。
