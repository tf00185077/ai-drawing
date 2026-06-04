# Task Specs — Phase 1：Schema + DB

## 全量測試指令

`pytest backend/tests/ mcp-server/tests/ -x -q` → exit 0

## 執行規則

- 同一 step 最多重試 2 次，第 3 次失敗停止並回報
- 每個 task 最後一個 step 永遠是全量測試
- 依賴關係：#5 → #9 → #10；#1 → #2；其餘可並行

---

### Task #1：GeneratedImage 加 job_id 欄位

**Goal**: `GeneratedImage` 模型有 `job_id` 欄位，test_recording.py 驗證其被存入。
**Dependencies**: 無
**Files**: `backend/app/db/models.py`, `backend/tests/test_recording.py`

#### Step 1：在 models.py 加 job_id 欄位

**What**: 在 `GeneratedImage` class 加入 `job_id = Column(String(128), nullable=True)`，確認 String 已 import。
**Goal**: `GeneratedImage` 有 job_id 欄位，型別為 `String(128)`, nullable
**Verify**:
- `grep -n "job_id" backend/app/db/models.py` → 有輸出，包含 `Column` 與 `String`

#### Step 2：更新 test_recording.py 驗證 job_id 被儲存

**What**: 新增或更新測試呼叫 `save(..., job_id="test-job-123")`，斷言 `record.job_id == "test-job-123"`
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
- `grep -n "denoise" backend/app/schemas/generate.py` → 有輸出，包含 `Field`

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

**What**: 將 `class GenerateCustomRequest(BaseModel)` 改為 `class GenerateCustomRequest(GenerateRequest)`，移除已繼承的重複欄位，只保留：
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

**What**: 所有建立 `TrainStartRequest` 的地方都必須提供 `generate_after` 參數
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
