# Task Specs — Phase 3：MCP Tools 補齊

## 全量測試指令

`pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

## 執行規則

- 同一 step 最多重試 2 次，第 3 次失敗停止並回報
- 每個 task 最後一個 step 永遠是全量測試
- **MCP 測試策略**：全用 mock，不需要啟動 backend
- 依賴關係：#13 無依賴（API 已存在）；#14 依賴 #1, #3；#15 依賴 #4；#16 依賴 #5–#10；#17 依賴 #11–#12

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

**What**: mock `client.get` 回傳 `{"checkpoints": ["a.safetensors"], "loras": [], "workflows": ["default"]}`，斷言回傳字串包含 `checkpoints`
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

**What**: 新增 `cancel_job(job_id: str)` tool，呼叫 `client.delete(f"/api/generate/queue/{job_id}")`（若 client 無 delete 方法則擴充 client）
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

**Goal**: `lora_train_start()` tool 包含 TrainStartRequest 所有欄位：resolution, keep_tokens, mixed_precision, network_dim, network_alpha，以及 generate_after 的子參數。
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
並將這些欄位有條件組裝進 body，`generate_after_prompt` 有值時組成 `GenerateAfterParams` 格式。
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
