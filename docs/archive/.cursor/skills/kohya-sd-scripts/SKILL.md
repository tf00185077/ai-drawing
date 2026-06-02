---
name: kohya-sd-scripts
description: Kohya sd-scripts LoRA 訓練 CLI - train_network.py 參數、dataset_config TOML 格式。Use when invoking Kohya sd-scripts, building dataset configs, or adjusting LoRA training parameters. 專案整合見 lora-train-docs。
---

# Kohya sd-scripts 介面參考

Kohya sd-scripts 無 REST API，透過 **CLI** 呼叫。專案以 subprocess 整合，見 `lora-train-docs` skill。

Repo: https://github.com/kohya-ss/sd-scripts

---

## 1. 呼叫方式

```bash
cd /path/to/sd-scripts
accelerate launch --num_cpu_threads_per_process 1 train_network.py \
  --pretrained_model_name_or_path=<checkpoint> \
  --dataset_config=<path/to/config.toml> \
  --output_dir=<output_dir> \
  --output_name=<output_name> \
  --network_module=networks.lora \
  ...
```

Python subprocess 整合、cwd、進度解析 → 見 `lora-train-docs` 訓練執行器。

---

## 2. 必備 CLI 參數

| 參數 | 說明 | 範例 |
|------|------|------|
| `--pretrained_model_name_or_path` | 基礎模型（.ckpt / .safetensors / Diffusers 目錄） | `./models/xxx.safetensors` |
| `--dataset_config` | 資料集設定檔 (.toml) | `./dataset.toml` |
| `--output_dir` | 輸出目錄 | `./output` |
| `--output_name` | 輸出名稱（不含副檔名） | `my_lora` |
| `--network_module` | 網路模組，LoRA 用 `networks.lora` | `networks.lora` |

使用 `--dataset_config` 時，`--train_data_dir`、`--reg_data_dir`、`--in_json` 會被忽略。

---

## 3. 常用訓練參數

### 模型與輸出

| 參數 | 預設 | 說明 |
|------|------|------|
| `--v2` | - | SD 2.0 模型 |
| `--v_parameterization` | - | v-parameterization |
| `--vae` | - | 自訂 VAE 路徑 |
| `--save_model_as` | safetensors | ckpt / pt / safetensors |

### 訓練步數與學習率

| 參數 | 說明 |
|------|------|
| `--max_train_steps` | 總步數 |
| `--max_train_epochs` | 總 epoch（與 steps 二擇一，epoch 優先） |
| `--learning_rate` | 學習率（LoRA 建議 1e-4 ~ 1e-3） |
| `--unet_lr` | U-Net 專用學習率 |
| `--text_encoder_lr` | Text Encoder 專用學習率 |

### LoRA 網路

| 參數 | 說明 |
|------|------|
| `--network_dim` | LoRA rank (dim) |
| `--network_alpha` | alpha，通常與 dim 相同 |
| `--network_weights` | 從既有 LoRA 繼續訓練 |
| `--network_train_unet_only` | 只訓練 U-Net |
| `--network_train_text_encoder_only` | 只訓練 Text Encoder |

### 記憶體與效能

| 參數 | 說明 |
|------|------|
| `--mixed_precision` | fp16 / bf16 / no |
| `--gradient_checkpointing` | 省 VRAM |
| `--xformers` | 使用 xformers |
| `--cache_latents` | 快取 latent |
| `--lowram` | 低 VRAM 模式 |

### 保存

| 參數 | 說明 |
|------|------|
| `--save_every_n_epochs` | 每 N epoch 存檔 |
| `--save_every_n_steps` | 每 N 步存檔 |
| `--resume` | 從 checkpoint 恢復 |

---

## 4. dataset_config (TOML) 格式

### 基本結構

```toml
[general]
shuffle_caption = true
caption_extension = ".txt"
keep_tokens = 1

[[datasets]]
resolution = 512
batch_size = 4

  [[datasets.subsets]]
  image_dir = "C:/path/to/images"
  class_tokens = "sks girl"
  num_repeats = 10
```

### 層級說明

| 層級 | 說明 |
|------|------|
| `[general]` | 全域設定，所有 dataset/subset 共用 |
| `[[datasets]]` | 單一 dataset（可多個，各自 resolution/batch_size） |
| `[[datasets.subsets]]` | 子集：一個 image_dir 或 metadata_file |

### DreamBooth 子集

- `image_dir`：圖片目錄（必填，圖片需在目錄直下）
- `class_tokens`：類別 token，無 caption 檔時使用
- `num_repeats`：重複次數
- `is_reg`：是否為正則化圖片

### Fine-tuning 子集

- `image_dir`：圖片目錄（可選）
- `metadata_file`：metadata JSON 路徑（必填）

### 子集可選欄位

| 欄位 | 說明 |
|------|------|
| `num_repeats` | 重複次數 |
| `keep_tokens` | 固定不 shuffle 的 token 數 |
| `shuffle_caption` | 是否打亂 caption |
| `flip_aug` | 水平翻轉 |
| `color_aug` | 色彩增強 |
| `random_crop` | 隨機裁切 |
| `caption_extension` | caption 副檔名（如 `.txt`） |

### 範例：混合解析度

```toml
[[datasets]]
resolution = 512
batch_size = 4
  [[datasets.subsets]]
  image_dir = "C:/data/512"
  class_tokens = "sks girl"

[[datasets]]
resolution = [768, 768]
batch_size = 2
  [[datasets.subsets]]
  image_dir = "C:/data/768"
  metadata_file = "C:/data/768/meta.json"
```

---

## 5. 整合要點

1. 確認 checkpoint、output、`dataset_config` 路徑
2. DreamBooth：`image_dir` + `class_tokens` + `num_repeats`；fine-tuning：`metadata_file`
3. 專案 lora_trainer、subprocess、產圖 pipeline → 見 `lora-train-docs`

---

## 6. SDXL 與進階

- SDXL：使用 `sdxl_train_network.py`，參數類似
- LoRA-C3Lier：`--network_args "conv_dim=4" "conv_alpha=1"`
- DyLoRA：`--network_module=networks.dylora --network_args "unit=4"`

---

## 7. 參考

- 完整 TOML：[reference.md](reference.md)
- 專案整合：`lora-train-docs` skill
