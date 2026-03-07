# AI 自動化出圖系統 - 完整運行設定指南

> 從上傳圖片、LoRA 訓練到 ComfyUI 產圖的完整流程所需參數與啟動項目。

---

## 一、需要「開啟」的程式

| 項目 | 是否需獨立啟動 | 說明 |
|------|----------------|------|
| **ComfyUI** | ✅ 必須 | 需先啟動 ComfyUI 伺服器，backend 透過 REST API 觸發產圖 |
| **Kohya sd-scripts** | ❌ 不需要 | 不是常駐程式，由 backend 以 subprocess 呼叫 |
| **WD Tagger** | ❌ 不需要 | 內建於 Kohya sd-scripts，由 backend 呼叫 `tag_images_by_wd14_tagger.py` |

### 總結

- **必須啟動**：ComfyUI
- **必須存在**：Kohya sd-scripts 目錄（含 `train_network.py`、`tag_images_by_wd14_tagger.py`）
- **WD Tagger**：隨上傳/監聽觸發自動執行，無需手動啟動

---

## 二、參數總覽

### 參數位置

| 來源 | 說明 |
|------|------|
| `backend/.env` | 主要設定檔（複製 `.env.example` 後修改） |
| `backend/app/config.py` | 預設值與環境變數對應 |

### 完整參數表

| 環境變數 | 預設值 | 必填 | 說明 |
|----------|--------|------|------|
| **資料庫** |
| `DATABASE_URL` | `sqlite:///./auto_draw.db` | 否 | SQLite 路徑 |
| **ComfyUI** |
| `COMFYUI_BASE_URL` | `http://127.0.0.1:8188` | 是 | ComfyUI REST API 位址 |
| `COMFYUI_WS_URL` | `ws://127.0.0.1:8188/ws` | 否 | WebSocket（若未用到可略） |
| **輸出目錄** |
| `OUTPUT_DIR` | `./outputs` | 否 | 產圖輸出根目錄 |
| `GALLERY_DIR` | `./outputs/gallery` | 否 | Gallery 圖片存放目錄 |
| **LoRA 訓練** |
| `LORA_TRAIN_DIR` | `./lora_train` | 是 | 訓練圖片與 LoRA 輸出根目錄 |
| `LORA_TRAIN_THRESHOLD` | `10` | 否 | 自動觸發訓練門檻（圖片數） |
| `LORA_DEFAULT_CHECKPOINT` | *(空)* | **是** | 預設 checkpoint 路徑或檔名，訓練與產圖皆會用到 |
| `LORA_AUTO_PROMPT` | `1girl, solo, high quality` | 否 | 訓練完成後自動產圖的 prompt |
| `SD_SCRIPTS_PATH` | `./sd-scripts` | **是** | Kohya sd-scripts 目錄的絕對或相對路徑 |
| **watchdog** |
| `WATCH_DIRS` | `./lora_train` | 否 | 監聽目錄，逗號分隔（拖檔案入此目錄會觸發 WD Tagger） |

---

## 三、啟動順序與指令

```
1. 啟動 ComfyUI
2. 啟動本專案後端
3. （選用）啟動前端
```

### 1. 啟動 ComfyUI

```bash
# 進入 ComfyUI 目錄後
python main.py
# 或使用 run_nvidia_gpu.bat / run_cpu.bat 等
```

確認 ComfyUI 可從瀏覽器開啟：`http://127.0.0.1:8188`

### 2. 設定 `.env`

```bash
cd backend
cp .env.example .env
# 編輯 .env，至少設定：
# LORA_DEFAULT_CHECKPOINT=你的 checkpoint 檔名或路徑
# SD_SCRIPTS_PATH=你的 Kohya sd-scripts 絕對路徑
```

### 3. 初始化資料庫（首次）

```bash
python backend/scripts/init_db.py
```

### 4. 啟動後端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 5. 啟動前端（選用）

```bash
cd frontend
npm install
npm run dev
```

---

## 四、路徑與檔案對應

### Kohya sd-scripts 目錄結構（需存在）

```
SD_SCRIPTS_PATH/
├── train_network.py          # LoRA 訓練
├── accelerate                # 或透過 pip 全域安裝
└── finetune/
    └── tag_images_by_wd14_tagger.py   # WD Tagger（產生 .txt caption）
```

### LoRA 輸出路徑

訓練完成後，LoRA 會輸出到：

```
{LORA_TRAIN_DIR}/output/{folder名稱}.safetensors
```

例如：`./lora_train/output/my_char.safetensors`

### ComfyUI 讀取 LoRA

ComfyUI 的 `LoraLoader` 預設從 `models/loras/` 讀取。要讓產圖 Pipeline 正確載入訓練出的 LoRA，需二擇一：

**作法 A：extra_model_paths（建議）**

在 ComfyUI 目錄建立 `extra_model_paths.yaml`：

```yaml
loras: |
  D:/AI/ai-drawing/backend/lora_train/output
```

將上述路徑改為你專案的 `{LORA_TRAIN_DIR}/output` 絕對路徑。

**作法 B：符號連結**

將 `lora_train/output` 連結到 ComfyUI 的 `models/loras`，或訓練完成後手動複製 `.safetensors` 到該目錄。

---

## 五、Checkpoint 路徑

`LORA_DEFAULT_CHECKPOINT` 會用於：

1. **LoRA 訓練**：作為 `--pretrained_model_name_or_path`
2. **訓練完成後產圖**：作為 ComfyUI CheckpointLoader 的 `ckpt_name`

ComfyUI 從 `models/checkpoints/` 讀取 checkpoint，所以建議填：

- 檔名：`v1-5-pruned-emaonly.safetensors`（若檔在 `models/checkpoints/`）
- 或完整路徑（若 ComfyUI 有透過 `extra_model_paths` 設定該路徑）

---

## 六、WD Tagger 相依（無需手動啟動）

WD Tagger 由 backend 在以下情況自動呼叫：

| 觸發時機 | 說明 |
|----------|------|
| 上傳圖片 | `POST /api/lora-docs/upload` 完成後 |
| 拖檔入監聽目錄 | watchdog 偵測到新圖時 |

**首次執行**：會從 Hugging Face 下載 `SmilingWolf/wd-swinv2-tagger-v3`，需網路連線。

**相依套件**（若 Kohya sd-scripts 環境未安裝）：

```bash
pip install onnx onnxruntime-gpu
# 或無 GPU：pip install onnx onnxruntime
```

---

## 七、檢查清單

上線前可依此檢查：

- [ ] ComfyUI 已啟動，`http://127.0.0.1:8188` 可連線
- [ ] `.env` 已設定 `LORA_DEFAULT_CHECKPOINT`
- [ ] `.env` 已設定 `SD_SCRIPTS_PATH` 指向正確 Kohya 目錄
- [ ] `SD_SCRIPTS_PATH/train_network.py` 存在
- [ ] `SD_SCRIPTS_PATH/finetune/tag_images_by_wd14_tagger.py` 存在
- [ ] `accelerate` 已安裝（`pip install accelerate` 或於 sd-scripts 環境內）
- [ ] ComfyUI 的 `extra_model_paths.yaml` 已加入 `lora_train/output`（或已處理 LoRA 路徑）
- [ ] Checkpoint 檔案可被 ComfyUI 讀取
