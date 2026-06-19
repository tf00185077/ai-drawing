# F-E：LoRA 訓練完整參數

**功能**：agent 可透過 MCP 指定完整訓練參數（network_dim、mixed_precision 等）；同時移除 `generate_after`（訓練完後生圖由 agent 自行呼叫 `generate_image`，不由 backend 串接）。

**完成定義**：呼叫 `lora_train_start(folder="x", network_dim=32, mixed_precision="fp16")` 能正確啟動訓練；`generate_after` 參數不再存在。

---

## 現況確認

- `TrainStartRequest` schema 已有 `resolution/keep_tokens/mixed_precision/network_dim/network_alpha` 等所有參數
- `TrainStartRequest` 有 `generate_after`（需移除）
- MCP `lora_train_start` 只有 `folder/checkpoint/epochs/class_tokens/generate_after`
- `generate_after` 違反「訓練歸訓練，生圖歸生圖」原則

---

## Steps

### Step 1：Schema 移除 generate_after
**檔案**：`backend/app/schemas/lora_train.py`

刪除 `GenerateAfterParams` class。
從 `TrainStartRequest` 移除：
```python
generate_after: GenerateAfterParams | None = None
```

確認 `backend/app/services/lora_trainer.py` 中若有讀取 `generate_after` 的邏輯，一併移除。

**Verify**：`POST /api/lora-train/start` 傳入 `generate_after` 欄位不報錯（被忽略）或直接 422（Pydantic extra='forbid'，視現有設定）。

### Step 2：MCP tool 重寫
**檔案**：`mcp-server/mcp_server/tools/lora_train.py`

`lora_train_start` 函式簽名改為：
```python
def lora_train_start(
    folder: str,
    checkpoint: str | None = None,
    epochs: int | None = None,
    class_tokens: str | None = None,
    resolution: int | None = None,
    keep_tokens: int | None = None,
    mixed_precision: str | None = None,   # fp16 | bf16 | fp32
    network_dim: int | None = None,
    network_alpha: int | None = None,
    num_repeats: int | None = None,
    learning_rate: str | None = None,
) -> str:
```

移除 `generate_after`，補傳所有新參數（None 時不帶入 body）。

Docstring 更新：移除 generate_after 說明，加入「訓練完成後請另行呼叫 generate_image」。

**Verify**：`uv run pytest tests/ -k lora_train`

---

## End-to-End Verify

```bash
# 1. lora_train_start(folder="character/miku", network_dim=32, mixed_precision="fp16", epochs=10)
# 2. 回傳 job_id
# 3. lora_train_status() → 顯示目前 epoch 進度
# 4. 訓練完成後，agent 自行呼叫 generate_image(lora="miku.safetensors")
```
