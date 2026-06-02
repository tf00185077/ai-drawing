---
name: wd-tagger
description: WD Tagger (WD14Tagger) Python 呼叫方式與參數 - subprocess 整合 Kohya sd-scripts tag_images_by_wd14_tagger.py，產生圖片 caption .txt。Use when implementing image tagging, watcher auto-caption, lora_docs upload caption, or integrating WD Tagger into the auto-draw project.
---

# WD Tagger (WD14Tagger) 介面參考

Kohya sd-scripts 的 `tag_images_by_wd14_tagger.py` 用於自動為訓練圖片產生 caption（`.txt`）。無 REST API，透過 **CLI + subprocess** 呼叫。

來源：kohya-ss/sd-scripts `finetune/tag_images_by_wd14_tagger.py`  
文件：https://github.com/kohya-ss/sd-scripts/blob/main/docs/wd14_tagger_README-en.md

---

## 1. 呼叫方式

### 基本命令

```bash
# 需在 sd-scripts 目錄，或使用絕對路徑
cd /path/to/sd-scripts

python finetune/tag_images_by_wd14_tagger.py \
  --onnx \
  --repo_id SmilingWolf/wd-swinv2-tagger-v3 \
  --batch_size 4 \
  /path/to/train_data
```

### Python subprocess 範例

```python
import subprocess

sd_scripts_path = "./sd-scripts"  # 或 config.sd_scripts_path
train_data_dir = "./lora_train/my_folder"

cmd = [
    "python",
    f"{sd_scripts_path}/finetune/tag_images_by_wd14_tagger.py",
    "--onnx",
    "--repo_id", "SmilingWolf/wd-swinv2-tagger-v3",
    "--batch_size", "4",
    "--thresh", "0.35",
    "--recursive",
    train_data_dir,
]

proc = subprocess.Popen(
    cmd,
    cwd=sd_scripts_path,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
stdout, _ = proc.communicate()
# 或 asyncio.create_subprocess_exec 處理非同步
```

輸出：每張圖片旁產生同名 `.txt` caption 檔。

---

## 2. 必備參數

| 參數 | 位置 | 說明 |
|------|------|------|
| `train_data_dir` | 位置參數 | 訓練圖片目錄（必填） |

---

## 3. 模型與推論

### 推論模式

| 參數 | 預設 | 說明 |
|------|------|------|
| `--onnx` | - | 使用 ONNX 推論（**建議**，需 `pip install onnx onnxruntime-gpu`） |
| `--repo_id` | `SmilingWolf/wd-v1-4-convnext-tagger-v2` | Hugging Face 模型 ID |
| `--model_dir` | `wd14_tagger_model` | 模型下載/快取目錄 |
| `--force_download` | - | 強制重新下載模型 |
| `--batch_size` | `1` | 批次大小，依 VRAM 調整（建議 4） |

### 常用 repo_id

- `SmilingWolf/wd-swinv2-tagger-v3`：V3 SwinV2，較新
- `SmilingWolf/wd-vit-tagger-v3`：V3 ViT
- `SmilingWolf/wd-v1-4-convnext-tagger-v2`：預設 V2

---

## 4. 閾值 (Thresholds)

| 參數 | 預設 | 說明 |
|------|------|------|
| `--thresh` | `0.35` | 全域 tag 閾值，越低 tag 越多、準度越低 |
| `--general_threshold` | 同 thresh | general 類別閾值 |
| `--character_threshold` | 同 thresh | character 類別閾值，>1 可停用 |
| `--meta_threshold` | 同 thresh | meta 類別閾值 |
| `--model_threshold` | 同 thresh | model 類別閾值 |
| `--copyright_threshold` | 同 thresh | copyright 類別閾值 |
| `--artist_threshold` | 同 thresh | artist 類別閾值 |

---

## 5. 輸出與路徑

| 參數 | 預設 | 說明 |
|------|------|------|
| `--caption_extension` | `.txt` | caption 副檔名 |
| `--output_path` | `None` | 若指定，輸出為單一 JSON 檔，而非每圖一個 .txt |
| `--max_data_loader_n_workers` | `None` | DataLoader worker 數，>0 可加速讀圖 |
| `--recursive` | - | 遞迴處理子資料夾 |
| `--append_tags` | - | 追加到既有 .txt，不覆寫 |

---

## 6. 標籤編輯

| 參數 | 說明 |
|------|------|
| `--remove_underscore` | 將 tag 中 `_` 替換為空格 |
| `--undesired_tags` | 逗號分隔，要排除的 tag（例：`black eyes,black hair`） |
| `--use_rating_tags` | rating tag 放最前 |
| `--use_rating_tags_as_last_tag` | rating tag 放最後 |
| `--use_quality_tags` | quality tag 放最前 |
| `--use_quality_tags_as_last_tag` | quality tag 放最後 |
| `--character_tags_first` | character tag 放 general 前 |
| `--character_tag_expand` | `chara_name_(series)` → `chara_name, series` |
| `--always_first_tags` | 逗號分隔，指定時強制置前（例：`1girl,1boy`） |
| `--caption_separator` | tag 分隔符，預設 `, ` |
| `--tag_replacement` | 替換規則 `source1,target1;source2,target2`，`,` `;` 用 `\` 跳脫 |

---

## 7. 其他

| 參數 | 說明 |
|------|------|
| `--frequency_tags` | 輸出 tag 出現頻率 |
| `--debug` |  debug 模式 |
| `--caption_extention` | 舊版拼字，同 `--caption_extension` |

---

## 8. 範例：Animagine XL 風格

```bash
python finetune/tag_images_by_wd14_tagger.py \
  --onnx --repo_id SmilingWolf/wd-swinv2-tagger-v3 \
  --batch_size 4 --remove_underscore \
  --undesired_tags "PUT,YOUR,UNDESIRED,TAGS" --recursive \
  --use_rating_tags_as_last_tag --character_tags_first --character_tag_expand \
  --always_first_tags "1girl,1boy" \
  /path/to/train_data
```

---

## 9. 專案整合要點

### 檔案對應

| 用途 | 檔案 |
|------|------|
| 監聽觸發 | `backend/app/services/watcher.py` |
| 上傳觸發 | `backend/app/api/lora_docs.py` |
| 設定 | `sd_scripts_path`（與 lora_trainer 共用） |

### 流程

```
watch_dirs → watchdog → 新圖 → WD Tagger subprocess → 同名 .txt
```

### 建構 subprocess 時

1. 確認 `sd_scripts_path`、`train_data_dir` 路徑
2. 建議：`--onnx`、`--batch_size 4`、`--recursive`
3. `cwd` 設為 sd-scripts 目錄
4. 首次執行會從 Hugging Face 下載模型到 `--model_dir`

---

## 10. 相依套件

```bash
pip install onnx onnxruntime-gpu  # ONNX 模式
# 或
pip install tensorflow  # 非 ONNX 模式（不推薦）
```
