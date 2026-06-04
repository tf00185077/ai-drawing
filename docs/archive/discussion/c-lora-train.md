# C. LoRA 訓練參數補齊

## generate_after 決策

`generate_after` 是訓練完成後用新 LoRA 自動生圖的參數（prompt、張數、checkpoint 等）。
- **改為必填**：`generate_after: GenerateAfterParams`（移除 `| None`）
- `GenerateAfterParams.count` 預設值保持 1
- agent 觸發訓練時必須提供 prompt，明確指定生圖意圖

## save_every_n_epochs

不加。訓練期間電腦滿載，中間產物無實際用途。

## MCP lora_train_start 參數分層

**常用（agent 一定要配置）**：

| 參數 | 說明 |
|------|------|
| `folder` | 訓練資料夾名稱（必填） |
| `checkpoint` | 基礎模型檔名 |
| `sdxl` | True=SDXL/PDXL，False=SD1.x |
| `epochs` | 訓練輪數，預設 10 |
| `class_tokens` | Trigger word（如 sks、ohwx） |
| `generate_after` | 訓練後自動生圖（必填，含 prompt / count） |

**細節（不給有預設值，進階調校用）**：

| 參數 | 說明 | 預設 |
|------|------|------|
| `resolution` | 訓練圖片裁切解析度 | 512 |
| `batch_size` | 每次迭代圖片數 | 4 |
| `learning_rate` | 學習率（如 1e-4） | 1e-4 |
| `keep_tokens` | 不打亂的前 N 個 token | 0 |
| `num_repeats` | 每 epoch 每張圖重複次數 | 10 |
| `mixed_precision` | fp16 / bf16 / fp32 | fp16 |
| `network_dim` | LoRA rank，表達力大小 | 16 |
| `network_alpha` | LoRA 強度係數，通常=dim | 16 |

## Schema 調整項目

- `generate_after` 從 `Optional` 改為必填
- `mixed_precision` 加 `Literal["fp16", "bf16", "fp32"]` 枚舉驗證
- 不加 optimizer / lr_scheduler / save_every_n_epochs（進階用，預設夠用）
- `learning_rate` 保持 `str`（Kohya 直接使用，支援科學記號格式）

## UI 補充項目

- `keep_tokens` 欄位補進 LoraTrain.tsx
- `mixed_precision` 加 select 下拉（fp16 / bf16 / fp32）
- `generate_after` 加入 UI（至少 prompt 和 count 欄位）

## 影響範圍

- `backend/app/schemas/lora_train.py` — generate_after 必填、mixed_precision 枚舉
- `mcp-server/mcp_server/tools/lora_train.py` — 補齊所有 schema 參數（常用+細節分層）
- `frontend/src/pages/LoraTrain.tsx` — 補 keep_tokens / mixed_precision / generate_after

---

→ 相關實作項目：[checklist.md](checklist.md) #11–12, #17, #19
