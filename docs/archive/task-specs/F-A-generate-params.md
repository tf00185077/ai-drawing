# F-A：生圖完整參數

**功能**：`generate_image` MCP tool 支援所有進階參數，agent 可精確控制取樣器、LoRA 強度、denoise 等。

**完成定義**：透過 MCP 呼叫 `generate_image(sampler_name="euler", lora_strength=0.7, denoise=0.8)` 能提交 job，且 ComfyUI workflow 內對應節點數值正確。

---

## 現況確認

| 層 | sampler_name / scheduler | width / height | lora_strength | denoise |
|----|--------------------------|----------------|---------------|---------|
| Schema (`GenerateRequest`) | ✅ 已有 | ✅ 已有（上限 2048） | ❌ 不存在 | ❌ 不存在 |
| API (`api/generate.py`) | ✅ 已傳遞 | ✅ 已傳遞 | ❌ | ❌ |
| Workflow (`apply_params`) | ✅ 已套用 | ✅ 已套用 | ❌ | ✅ 已套用 |
| MCP (`generate_image`) | ❌ 未暴露 | ❌ 未暴露 | ❌ | ❌ |

---

## Steps

### Step 1：Schema 加 lora_strength / denoise
**檔案**：`backend/app/schemas/generate.py`

在 `GenerateRequest` 加：
```python
lora_strength: float | None = Field(default=None, ge=0.0, le=2.0)
denoise: float | None = Field(default=None, ge=0.0, le=1.0)
```
`GenerateCustomRequest` 同步加相同兩個欄位。

**Verify**：`pytest backend/tests/ -k generate` 通過，schema 可接收這兩個欄位。

### Step 2：API 傳遞 lora_strength / denoise
**檔案**：`backend/app/api/generate.py`

`trigger_generate()` 的 params dict 補：
```python
if body.lora_strength is not None:
    params["lora_strength"] = body.lora_strength
if body.denoise is not None:
    params["denoise"] = body.denoise
```
`trigger_generate_custom()` 同步處理。

**Verify**：POST `/api/generate/` 傳 `lora_strength=0.7` → params dict 含該值。

### Step 3：Workflow 套用 lora_strength
**檔案**：`backend/app/core/workflow.py`

`apply_params()` 加 `lora_strength: float | None = None` 參數，在 LoraLoader 節點：
```python
if ct == "LoraLoader" and lora_strength is not None:
    inputs["strength_model"] = lora_strength
    inputs["strength_clip"] = lora_strength
```
`queue.py` 的 `apply_params(...)` 呼叫補傳 `lora_strength=job.params.get("lora_strength")`。

**Verify**：單元測試確認含 LoraLoader 節點的 workflow 套用後 `strength_model == 0.7`。

### Step 4：MCP tool 暴露所有進階參數
**檔案**：`mcp-server/mcp_server/tools/generate.py`

`generate_image` 函式簽名補：
```python
width: int | None = None,
height: int | None = None,
sampler_name: str | None = None,
scheduler: str | None = None,
lora_strength: float | None = None,
denoise: float | None = None,
```
body dict 的 None 判斷補上這六個參數。

**Verify**：MCP tool 呼叫 `generate_image(sampler_name="euler", lora_strength=0.7)` → HTTP body 含對應欄位 → 後端 201。

---

## End-to-End Verify

```bash
# MCP 測試（不啟動後端）
cd mcp-server && uv run pytest tests/ -k generate -v

# 整合（需後端 + ComfyUI）
# 1. 呼叫 generate_image(prompt="1girl", sampler_name="euler", lora_strength=0.7, denoise=0.9)
# 2. 確認回傳 job_id
# 3. 查詢 ComfyUI history，確認 KSampler.sampler_name=="euler", LoraLoader.strength_model==0.7
```
