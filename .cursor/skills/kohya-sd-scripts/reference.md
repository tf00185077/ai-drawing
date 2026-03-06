# dataset_config TOML 完整選項

當 agent 需要細部設定時參考。來源：https://sd-scripts.readthedocs.io/en/latest/config_ja.html

## 資料集層級（`[[datasets]]`）

| 選項 | 範例 | 說明 |
|------|------|------|
| `batch_size` | `4` | 等同 `--train_batch_size` |
| `resolution` | `512` 或 `[768, 768]` | 解析度 |
| `enable_bucket` | `true` | 啟用 bucket |
| `min_bucket_reso` | `128` | 最小 bucket 解析度 |
| `max_bucket_reso` | `1024` | 最大 bucket 解析度 |
| `bucket_reso_steps` | `64` | bucket 步長 |
| `bucket_no_upscale` | `true` | bucket 內不放大 |

## 子集層級（`[[datasets.subsets]]`）- 共通

| 選項 | 說明 |
|------|------|
| `num_repeats` | 重複次數 |
| `keep_tokens` | 固定 token 數 |
| `shuffle_caption` | 打亂 caption |
| `flip_aug` | 水平翻轉 |
| `color_aug` | 色彩增強 |
| `random_crop` | 隨機裁切 |
| `face_crop_aug_range` | 臉部裁切範圍 `[1.0, 3.0]` |
| `caption_dropout_rate` | caption dropout 機率 |
| `caption_dropout_every_n_epochs` | 每 N epoch dropout |
| `caption_tag_dropout_rate` | tag dropout 機率 |

## DreamBooth 專用

| 選項 | 必填 | 說明 |
|------|------|------|
| `image_dir` | 是 | 圖片目錄（直下放圖） |
| `class_tokens` | 視情況 | 無 caption 時用 |
| `is_reg` | - | 正則化圖片 |
| `caption_extension` | - | `.txt` 等 |

## Fine-tuning 專用

| 選項 | 必填 | 說明 |
|------|------|------|
| `metadata_file` | 是 | metadata JSON |
| `image_dir` | 否 | 圖片目錄（metadata 有 full_path 時可省） |

## 注意

- 使用 `--dataset_config` 時，CLI 的 `--train_data_dir`、`--reg_data_dir`、`--in_json` 會被忽略
- 同名選項：subset > dataset > general
