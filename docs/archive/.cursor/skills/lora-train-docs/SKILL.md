---
name: lora-train-docs
description: LoRA 模組完整參考 - 文件工具、訓練 API、lora_trainer 實作、subprocess 呼叫 Kohya、dataset_config 生成、佇列進度、watcher、產圖串接。Use when implementing lora_docs, lora_train, lora_trainer, watcher, or LoRA-related features in the auto-draw project.
---

# LoRA 模組 - Agent 參考

本專案 LoRA 分為兩塊：**文件工具**（素材管理）與 **訓練與產圖**（執行、觸發、Pipeline）。Kohya sd-scripts 詳參 `kohya-sd-scripts` skill。

---

## 1. 模組對應檔案

| 模組 | 職責 | 檔案路徑 |
|------|------|----------|
| LoRA 文件 | API | `backend/app/api/lora_docs.py` |
| LoRA 文件 | 監聽 | `backend/app/services/watcher.py` |
| LoRA 文件 | 前端 | `frontend/src/pages/LoraDocs.tsx` |
| LoRA 訓練 | API | `backend/app/api/lora_train.py` |
| LoRA 訓練 | 執行器 | `backend/app/services/lora_trainer.py` |
| LoRA 訓練 | 前端 | `frontend/src/pages/LoraTrain.tsx` |

---

## 2. LoRA 文件 API

Router: `/api/lora-docs`

| 端點 | 方法 | 用途 |
|------|------|------|
| `/upload` | POST | 上傳圖片，產生 .txt |
| `/caption/{image_id}` | PUT | 編輯 .txt |
| `/batch-prefix` | POST | 批次加 trigger word（body: `images`, `prefix`） |
| `/download-zip` | GET | 打包下載（query: `folder`） |

每張圖需同名 `.txt` caption。

---

## 3. LoRA 訓練 API

Router: `/api/lora-train`

| 端點 | 方法 | 用途 |
|------|------|------|
| `/start` | POST | 觸發訓練（`folder`, `checkpoint?`, `epochs?`） |
| `/status` | GET | 進度與佇列 |
| `/trigger-check` | POST | 檢查是否達自動觸發門檻 |

---

## 4. 配置

```python
# backend/app/config.py
lora_train_dir: str = "./lora_train"
lora_train_threshold: int = 10   # 自動觸發門檻（圖片數）
sd_scripts_path: str = "./sd-scripts"
watch_dirs: str = "./lora_train"  # 逗號分隔
```

`.env`：`LORA_TRAIN_DIR`, `LORA_TRAIN_THRESHOLD`, `SD_SCRIPTS_PATH`, `WATCH_DIRS`。

---

## 5. 資料流

```
watch_dirs → watchdog → 新圖 → WD Tagger/BLIP2 → 同名 .txt
     ↓
圖片數 ≥ 門檻 → lora_trainer → Kohya sd-scripts
     ↓
完成 → comfyui.trigger(新 LoRA) → recording.save()
```

- 完成後：自動產圖、寫入 `GeneratedImage`
- 避免重複觸發：佇列狀態追蹤

---

## 6. 訓練執行器 (lora_trainer)

### 架構

```
lora_train.py → lora_trainer.enqueue() → subprocess → train_network.py
```

### subprocess 呼叫

```python
# backend/app/services/lora_trainer.py
import subprocess
from pathlib import Path

def run_training(folder: str, checkpoint: str, output_name: str, epochs: int = 10, sd_scripts_path: str = "./sd-scripts"):
    toml_path = _write_dataset_config(folder, output_name)
    output_dir = Path(folder).parent / "output"
    cmd = [
        "accelerate", "launch", "--num_cpu_threads_per_process", "1",
        str(Path(sd_scripts_path) / "train_network.py"),
        "--pretrained_model_name_or_path", checkpoint,
        "--dataset_config", str(toml_path),
        "--output_dir", str(output_dir),
        "--output_name", output_name,
        "--network_module", "networks.lora",
        "--max_train_epochs", str(epochs),
        "--learning_rate", "1e-4",
        "--save_model_as", "safetensors",
        "--mixed_precision", "fp16",
        "--cache_latents",
        "--gradient_checkpointing",
    ]
    return subprocess.Popen(cmd, cwd=sd_scripts_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
```

要點：`cwd` 必須為 `sd_scripts_path`；`image_dir` 用絕對路徑。

### dataset_config 動態生成

```python
def _write_dataset_config(image_dir: str, output_name: str, class_tokens: str = "sks") -> Path:
    image_path = Path(image_dir).resolve()
    toml_path = image_path.parent / f"{output_name}_dataset.toml"
    content = f"""[general]
shuffle_caption = true
caption_extension = ".txt"
keep_tokens = 1

[[datasets]]
resolution = 512
batch_size = 4

  [[datasets.subsets]]
  image_dir = "{image_path.as_posix()}"
  class_tokens = "{class_tokens}"
  num_repeats = 10
"""
    toml_path.write_text(content, encoding="utf-8")
    return toml_path
```

TOML 完整選項見 `kohya-sd-scripts` skill。

### 佇列與進度

```python
# 狀態
class TrainStatus(str, Enum):
    IDLE = "idle"; RUNNING = "running"; QUEUED = "queued"; DONE = "done"; FAILED = "failed"

# 從 stdout 解析 epoch/step
def _parse_progress(line: str) -> float | None:
    m = re.search(r"epoch\s+(\d+)/(\d+)", line, re.I)
    if m: return int(m.group(1)) / int(m.group(2))
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*\[", line)
    if m: return int(m.group(1)) / int(m.group(2))
    return None
```

背景讀 `proc.stdout` 更新進度。async 可用 `asyncio.create_subprocess_exec`。

### API 整合

```python
# lora_train.py
@router.post("/start")
async def start_training(folder: str, checkpoint: str | None = None, epochs: int = 10):
    job = lora_trainer.enqueue(folder=folder, checkpoint=checkpoint or get_default_checkpoint(), epochs=epochs)
    return {"job_id": job.id, "status": "queued"}

@router.get("/status")
async def get_training_status():
    return lora_trainer.get_status()
```

### 實作 checklist

1. [ ] `sd_scripts_path` 存在且含 `train_network.py`
2. [ ] `image_dir` 絕對路徑
3. [ ] `cwd` 設為 sd_scripts_path
4. [ ] 佇列：同時只跑一個
5. [ ] 完成後：comfyui 產圖、recording 寫入

---

## 7. 資料夾監聽 (watcher)

- 技術：watchdog
- 依賴：`config.watch_dirs`
- 邏輯：新圖 → WD Tagger/BLIP2 → 同名 .txt
- WD Tagger subprocess 參數與範例 → 見 `wd-tagger` skill

---

## 8. 資料庫

```python
# GeneratedImage
lora = Column(String(256), nullable=True)
```

篩選：`GET /api/gallery/?lora=xxx`。

---

## 9. MCP Tool 對應

| MCP Tool | API |
|----------|-----|
| `lora_train_start` | POST /api/lora-train/start |
| `lora_train_status` | GET /api/lora-train/status |

---

## 10. 實作順序

| Phase | 任務 | 檔案 |
|-------|------|------|
| 3a | 監聽 .txt | watcher.py |
| 3b | 上傳介面 | LoraDocs.tsx, lora_docs.py |
| 3c | Caption 編輯 | 同上 |
| 3d | 打包下載 | lora_docs.py |
| 4a | 訓練執行器 | lora_trainer.py |
| 4b | 觸發邏輯 | lora_trainer, watcher |
| 4c | 完成 → 產圖 | lora_trainer → comfyui + recording |
| 4d | 狀態佇列 | lora_train.py, LoraTrain.tsx |

---

## 11. 相依

1. watcher → `watch_dirs`
2. lora_trainer → `sd_scripts_path`；完成後 → comfyui + recording
3. Workflow 支援動態替換 LoRA（見 comfyui-api-client）

---

## 12. See Also

- `kohya-sd-scripts` - Kohya CLI 參數、TOML 格式、進階選項
- `wd-tagger` - WD Tagger Python 呼叫方式與參數、subprocess 整合
- `comfyui-api-client` - LoRA 替換、產圖 API
