# 內部模組介面

> 各後端模組之間的函式簽名與回呼契約。並行開發時，依此介面實作或 mock，對接時零歧義。

---

## 1. 資料流總覽

```
[Generate API]     → queue.submit() → workflow.apply() → comfyui.submit_prompt()
                                                              ↓
[ComfyUI 完成]     → queue.on_done() → recording.save() → DB
                                                              ↓
[LoRA 訓練完成]    → lora_trainer callback → comfyui + recording.save()
```

---

## 2. 生圖核心

### `core/workflow.py` — Workflow 模板

```python
def load_template(name: str) -> dict:
    """載入 workflow JSON 模板"""
    ...

def apply_params(
    workflow: dict,
    *,
    checkpoint: str | None = None,
    lora: str | None = None,
    prompt: str = "",
    negative_prompt: str = "",
    seed: int | None = None,
    steps: int = 20,
    cfg: float = 7.0,
) -> dict:
    """
    將參數替換進 workflow，回傳可提交的 prompt dict。
    ComfyUI prompt 格式為 { "node_id": { "inputs": {...} }, ... }
    """
    ...
```

**可替換參數**: `checkpoint`, `lora`, `prompt`, `negative_prompt`, `seed`, `steps`, `cfg`

---

### `core/queue.py` — 批次生圖排程器

```python
from typing import Protocol

class GenerateParams(TypedDict, total=False):
    checkpoint: str
    lora: str
    prompt: str
    negative_prompt: str
    seed: int
    steps: int
    cfg: float

def submit(params: GenerateParams) -> str:
    """
    提交生圖任務至佇列。
    Returns: job_id
    Raises: QueueFullError 若佇列已滿
    """
    ...

def get_status() -> dict:
    """
    取得佇列狀態。
    Returns: {
        "queue_running": [{"job_id": str, "prompt_id": str, "status": str, "submitted_at": str}],
        "queue_pending": [{"job_id": str, "status": str, "submitted_at": str}]
    }
    """
    ...

def get_job_status(job_id: str) -> dict | None:
    """取得單一任務狀態，None 表示不存在"""
    ...
```

**相依**: `workflow`, `comfyui` (ImageGenerationClient), `recording`

---

### `core/recording.py` — 自動記錄

```python
def save(
    image_path: str,
    *,
    checkpoint: str | None = None,
    lora: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    db: Session,
) -> GeneratedImage:
    """
    寫入 GeneratedImage 至資料庫。
    圖片檔必須已存至 gallery_dir。
    Returns: 新增的 GeneratedImage 實例
    """
    ...
```

**相依**: `db`, `config.gallery_dir`

**呼叫時機**: 生圖完成後、LoRA 訓練完成後產圖

---

### `core/comfyui.py` — 既有介面

```python
# ImageGenerationClient Protocol（已實作）
def submit_prompt(prompt: dict, *, client_id: str | None = None) -> str:  # -> prompt_id
def get_history(prompt_id: str) -> dict:
def get_queue() -> dict:
def fetch_image(filename: str, *, subfolder: str = "", ftype: str = "output") -> bytes:
```

---

## 3. LoRA 文件

### `services/watcher.py` — 資料夾監聽

```python
def start_watching() -> None:
    """
    啟動 watchdog 監聽 config.watch_dirs。
    新圖寫入時觸發 on_new_image。
    """
    ...

def on_new_image(image_path: Path) -> None:
    """
    新圖寫入時被呼叫。
    實作：呼叫 WD Tagger / BLIP2 產生同名 .txt。
    image_path 為絕對路徑。
    """
    ...
```

**相依**: `config.watch_dirs`, `config.sd_scripts_path`（WD Tagger 腳本路徑）

**WD Tagger 呼叫**: subprocess 執行 `tag_images_by_wd14_tagger.py`，見 `wd-tagger` skill。

---

## 4. LoRA 訓練

### `services/lora_trainer.py` — 訓練執行器

```python
from typing import Callable

# 訓練完成時的回呼： (output_lora_path: str, folder: str) -> None
OnCompleteCallback = Callable[[str, str], None]

def enqueue(
    folder: str,
    *,
    checkpoint: str | None = None,
    epochs: int = 10,
) -> str:
    """
    加入訓練佇列。
    folder: 相對 lora_train_dir 的路徑。
    Returns: job_id
    Raises: ValueError 若資料夾不存在或圖片數不足
    """
    ...

def get_status() -> dict:
    """
    Returns: {
        "status": "idle" | "running" | "queued",
        "current_job": {...} | None,
        "queue": [...]
    }
    """
    ...

def register_on_complete(callback: OnCompleteCallback) -> None:
    """
    註冊訓練完成回呼。
    完成時會呼叫 callback(output_lora_path, folder)。
    實作 4c 時：在此回呼中呼叫 comfyui 產圖 + recording.save()
    """
    ...
```

**相依**: `config.sd_scripts_path`, `config.lora_train_dir`, `config.lora_train_threshold`（自動觸發）

**Kohya 呼叫**: subprocess `train_network.py`，見 `kohya-sd-scripts` 與 `lora-train-docs` skill。

---

## 5. 訓練觸發邏輯

### watcher 與 lora_trainer 整合

```
watcher 監聽到新圖 → WD Tagger → .txt 產生
     ↓
定期或事件觸發 trigger-check
     ↓
遍歷 watch_dirs 下各子資料夾，計算圖片數
     ↓
若某資料夾 ≥ lora_train_threshold → lora_trainer.enqueue(folder)
```

**避免重複觸發**: 同一 folder 若已在 queue 或 running，不再 enqueue。

---

## 6. 對接檢查清單

| 模組 | 實作時需 | 對接時需 |
|------|----------|----------|
| workflow | 讀取 `workflows/*.json`，定義替換 key | 與 queue、comfyui 參數一致 |
| queue | 使用 `GenerateParams`，完成後呼叫 `recording.save` | job_id 格式、status 欄位 |
| recording | 使用 `GeneratedImage` model | 與 gallery API 回傳一致 |
| watcher | 呼叫 WD Tagger subprocess | image_path 與 lora_train_dir 關係 |
| lora_trainer | 註冊 on_complete，呼叫 comfyui + recording | output_lora_path 傳給 workflow |

---

## 7. Mock 開發建議

各軌道可先建立 stub：

```python
# core/recording.py stub
def save(*args, **kwargs) -> "GeneratedImage":
    return Mock(spec=GeneratedImage)

# services/lora_trainer.py stub
def enqueue(folder: str, **kwargs) -> str:
    return "mock-job-id"
def get_status() -> dict:
    return {"status": "idle", "queue": []}
```

測試時注入真實實作即可。
