# AI 自動化出圖系統 - 設定與快速上手

> 從環境設定、啟動程式到完成「放入圖片 → 產生 .txt → 訓練 LoRA → 產圖」的完整流程。

---

## 一、前置需求

| 項目 | 說明 |
|------|------|
| **ComfyUI** | 需能獨立啟動，提供 REST API `http://127.0.0.1:8188` |
| **Kohya sd-scripts** | 含 `train_network.py`、`finetune/tag_images_by_wd14_tagger.py` |
| **accelerate** | `pip install accelerate`（LoRA 訓練用） |
| **Checkpoint** | 至少一個 .safetensors 模型檔（ComfyUI 可讀取） |

### 需「啟動」 vs「存在即可」

| 項目 | 是否需獨立啟動 | 說明 |
|------|----------------|------|
| **ComfyUI** | ✅ 必須 | 需先啟動 ComfyUI 伺服器，backend 透過 REST API 觸發產圖 |
| **Kohya sd-scripts** | ❌ 不需要 | 不是常駐程式，由 backend 以 subprocess 呼叫 |
| **WD Tagger** | ❌ 不需要 | 內建於 Kohya sd-scripts，由 backend 呼叫 `tag_images_by_wd14_tagger.py` |

---

## 二、參數與環境設定

### 參數位置

| 來源 | 說明 |
|------|------|
| `backend/.env` | 主要設定檔（複製 `.env.example` 後修改） |
| `backend/app/config.py` | 預設值與環境變數對應 |

### 完整參數表

| 環境變數 | 預設值 | 必填 | 說明 |
|----------|--------|------|------|
| **資料庫** | | | |
| `DATABASE_URL` | `sqlite:///./auto_draw.db` | 否 | SQLite 路徑 |
| **ComfyUI** | | | |
| `COMFYUI_BASE_URL` | `http://127.0.0.1:8188` | 是 | ComfyUI REST API 位址 |
| `COMFYUI_WS_URL` | `ws://127.0.0.1:8188/ws` | 否 | WebSocket（若未用到可略） |
| **輸出目錄** | | | |
| `OUTPUT_DIR` | `./outputs` | 否 | 產圖輸出根目錄 |
| `GALLERY_DIR` | `./outputs/gallery` | 否 | Gallery 圖片存放目錄 |
| **LoRA 訓練** | | | |
| `LORA_TRAIN_DIR` | `./lora_train` | 是 | 訓練圖片與 LoRA 輸出根目錄 |
| `LORA_TRAIN_THRESHOLD` | `10` | 否 | 自動觸發訓練門檻（圖片數） |
| `LORA_DEFAULT_CHECKPOINT` | *(空)* | **是** | 預設 checkpoint 路徑或檔名 |
| `LORA_AUTO_PROMPT` | `1girl, solo, high quality` | 否 | 訓練完成後自動產圖的 prompt |
| `SD_SCRIPTS_PATH` | `./sd-scripts` | **是** | Kohya sd-scripts 目錄的絕對或相對路徑 |
| `LORA_RESOLUTION` | `512` | 否 | 訓練解析度，API 未帶入時使用 |
| `LORA_BATCH_SIZE` | `4` | 否 | 訓練 batch size |
| `LORA_LEARNING_RATE` | `1e-4` | 否 | 學習率 |
| `LORA_CLASS_TOKENS` | `sks` | 否 | 觸發詞 |
| `LORA_KEEP_TOKENS` | `1` | 否 | caption 保留 token 數 |
| `LORA_NUM_REPEATS` | `10` | 否 | 每張圖重複次數 |
| `LORA_MIXED_PRECISION` | `fp16` | 否 | fp16 / bf16 / fp32 |
| **watchdog** | | | |
| `WATCH_DIRS` | `./lora_train` | 否 | 監聽目錄，逗號分隔 |

### 一次性設定步驟

**1. 複製並編輯 `.env`**

```powershell
cd backend
copy .env.example .env
```

**必填項目**：

```env
LORA_DEFAULT_CHECKPOINT=v1-5-pruned-emaonly.safetensors
SD_SCRIPTS_PATH=D:/path/to/your/sd-scripts
```

（`LORA_DEFAULT_CHECKPOINT` 使用 ComfyUI `models/checkpoints/` 內的檔名）

**2. 讓 ComfyUI 讀取訓練後的 LoRA**

在 **ComfyUI 目錄** 建立 `extra_model_paths.yaml`：

```yaml
loras: |
  D:/AI/ai-drawing/backend/lora_train/output
```

將路徑改為你專案 `{LORA_TRAIN_DIR}/output` 的絕對路徑。

**3. 初始化資料庫（首次）**

```powershell
python backend/scripts/init_db.py
```

---

## 三、路徑與檔案對應

### Kohya sd-scripts 目錄結構

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

### Checkpoint 路徑

`LORA_DEFAULT_CHECKPOINT` 會用於：
1. **LoRA 訓練**：作為 `--pretrained_model_name_or_path`
2. **訓練完成後產圖**：作為 ComfyUI CheckpointLoader 的 `ckpt_name`

ComfyUI 從 `models/checkpoints/` 讀取，建議填檔名（如 `v1-5-pruned-emaonly.safetensors`）或透過 `extra_model_paths` 設定的完整路徑。

### WD Tagger 相依（無需手動啟動）

| 觸發時機 | 說明 |
|----------|------|
| 上傳圖片 | `POST /api/lora-docs/upload` 完成後 |
| 拖檔入監聽目錄 | watchdog 偵測到新圖時 |

首次執行會從 Hugging Face 下載 `SmilingWolf/wd-swinv2-tagger-v3`，需網路連線。若 Kohya sd-scripts 環境未安裝：

```bash
pip install onnx onnxruntime-gpu
# 或無 GPU：pip install onnx onnxruntime
```

---

## 四、啟動順序

```
1. 啟動 ComfyUI
2. 啟動本專案後端
3. （選用）啟動前端
```

### 1. 啟動 ComfyUI

```powershell
cd D:\path\to\ComfyUI
python main.py
```

確認瀏覽器可開啟 `http://127.0.0.1:8188`。

### 2. 啟動後端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

後端啟動後會自動：啟動 watchdog 監聽、生圖佇列 worker、LoRA 訓練完成後的自動產圖回呼。

### 3. 啟動前端（選用）

```powershell
cd frontend
npm install
npm run dev
```

開啟 `http://localhost:5173` 可使用 UI。

---

## 五、操作流程：圖片 → .txt → LoRA → 產圖

### 步驟 1：建立訓練子資料夾

在 `backend/lora_train` 下建立**子資料夾**，例如：

```
backend/lora_train/
└── my_char/          ← 子資料夾名稱即為 LoRA 名稱
```

**重要**：圖片必須放在子資料夾內，不能直接放在 `lora_train` 根目錄。

### 步驟 2：放入圖片

將訓練用圖片（.png、.jpg、.jpeg、.webp 等）複製到該子資料夾。

### 步驟 3：自動產生 .txt（WD Tagger）

- **watchdog** 會偵測到新圖片
- 約 2 秒後自動執行 **WD Tagger**，在相同目錄產生同名 `.txt` caption
- 後端 log 出現 `WD Tagger 完成` 即表示成功

### 步驟 4：觸發 LoRA 訓練

當子資料夾內**含 .txt 的圖片數 ≥ LORA_TRAIN_THRESHOLD**（預設 10 張）時，可觸發訓練。

**方式 A：API 自動檢查**

```powershell
curl -X POST http://127.0.0.1:8000/api/lora-train/trigger-check
```

**方式 B：指定資料夾手動訓練**（最少 1 張即可）

```powershell
curl -X POST http://127.0.0.1:8000/api/lora-train/start -H "Content-Type: application/json" -d "{\"folder\": \"my_char\", \"epochs\": 10}"
```

**方式 C：自訂訓練參數**（解析度、batch、學習率等）

```powershell
curl -X POST http://127.0.0.1:8000/api/lora-train/start -H "Content-Type: application/json" -d "{\"folder\": \"my_char\", \"epochs\": 15, \"resolution\": 768, \"batch_size\": 2, \"learning_rate\": \"2e-4\", \"class_tokens\": \"ohwx\", \"num_repeats\": 15, \"mixed_precision\": \"bf16\"}"
```

| 參數 | 說明 | 範例 |
|------|------|------|
| folder | 必填，相對 lora_train 的子資料夾 | my_char |
| checkpoint | 選填，未填用 .env 預設 | v1-5-pruned-emaonly.safetensors |
| epochs | 訓練輪數 | 10 |
| resolution | 解析度 (256–2048) | 512、768 |
| batch_size | 每批圖片數 | 4 |
| learning_rate | 學習率 | 1e-4、2e-4 |
| class_tokens | 觸發詞 | sks、ohwx |
| keep_tokens | caption 保留 token 數 | 1 |
| num_repeats | 每張圖重複次數 | 10 |
| mixed_precision | fp16 / bf16 / fp32 | fp16 |

### 步驟 5：查看訓練進度

```powershell
curl http://127.0.0.1:8000/api/lora-train/status
```

或在前端 **LoRA 訓練** 頁面查看。

### 步驟 6：訓練完成後自動產圖

- 訓練完成後，系統會**自動**將新 LoRA 提交至生圖佇列
- ComfyUI 使用 `default_lora.json` workflow 產圖
- 圖片會存到 `outputs/gallery/`，並寫入資料庫

```powershell
curl http://127.0.0.1:8000/api/generate/queue
```

### 生圖 API：自訂解析度、採樣器

`POST /api/generate/` 支援傳入生圖參數：

```powershell
curl -X POST http://127.0.0.1:8000/api/generate/ -H "Content-Type: application/json" -d "{\"prompt\": \"1girl, solo\", \"width\": 768, \"height\": 768, \"steps\": 30, \"cfg\": 7.5, \"sampler_name\": \"dpmpp_2m\", \"scheduler\": \"karras\"}"
```

| 參數 | 說明 | 範例 |
|------|------|------|
| prompt | 必填，正向 prompt | 1girl, solo |
| checkpoint | 選填 | v1-5-pruned-emaonly.safetensors |
| lora | 選填 | my_char.safetensors |
| negative_prompt | 負向 prompt | lowres, blur |
| seed | 隨機種子，不傳則隨機 | 12345 |
| steps | 採樣步數 | 20 |
| cfg | CFG scale | 7.0 |
| width | 圖寬 (256–2048) | 768 |
| height | 圖高 | 768 |
| batch_size | 一次產圖張數 | 2 |
| sampler_name | 採樣器 | 預設 dpmpp_2m；euler、ddim 等 |
| scheduler | 調度器 | normal、karras、exponential |

未傳的參數使用 workflow 模板預設值。

### 流程圖總覽

```
[1] 放入圖片到 lora_train/{子資料夾}/
         ↓
[2] watchdog 偵測 → WD Tagger 產生同名 .txt
         ↓
[3] POST /api/lora-train/trigger-check 或 /start
         ↓
[4] Kohya sd-scripts 訓練 → 輸出 lora_train/output/{folder}.safetensors
         ↓
[5] 訓練完成回呼 → 自動提交至生圖佇列
         ↓
[6] ComfyUI 產圖 → 存至 outputs/gallery/ + 寫入資料庫
```

---

## 六、常見問題

### Q: 放入圖片後沒有產生 .txt？

- 確認後端已啟動，且 `WATCH_DIRS` 包含該目錄
- 確認圖片在 **子資料夾** 內（如 `lora_train/my_char/`）
- 檢查 log 是否有 `WD Tagger 完成` 或錯誤訊息
- 確認 `SD_SCRIPTS_PATH` 正確，且 `finetune/tag_images_by_wd14_tagger.py` 存在

### Q: 訓練失敗 / 找不到 checkpoint？

- 確認 `.env` 已設定 `LORA_DEFAULT_CHECKPOINT`
- 檔名需與 ComfyUI `models/checkpoints/` 內的檔名一致
- 或透過 ComfyUI `extra_model_paths.yaml` 設定 checkpoint 路徑

### Q: 訓練完成但 ComfyUI 產圖失敗？

- 確認 ComfyUI 已啟動
- 確認 `extra_model_paths.yaml` 已加入 `lora_train/output` 路徑
- 檢查 `COMFYUI_BASE_URL` 是否正確

### Q: 門檻 10 張太多，想用更少圖片測試？

- 直接用 `POST /api/lora-train/start` 並指定 `folder`，最少 1 張含 .txt 的圖片即可

---

## 七、檢查清單（首次啟動前）

- [ ] ComfyUI 已啟動，`http://127.0.0.1:8188` 可連線
- [ ] `.env` 已設定 `LORA_DEFAULT_CHECKPOINT`
- [ ] `.env` 已設定 `SD_SCRIPTS_PATH` 指向正確 Kohya 目錄
- [ ] `SD_SCRIPTS_PATH/train_network.py` 存在
- [ ] `SD_SCRIPTS_PATH/finetune/tag_images_by_wd14_tagger.py` 存在
- [ ] `accelerate` 已安裝
- [ ] ComfyUI 的 `extra_model_paths.yaml` 已加入 `lora_train/output`（或已處理 LoRA 路徑）
- [ ] Checkpoint 檔案可被 ComfyUI 讀取
- [ ] 已執行 `python backend/scripts/init_db.py`

---

## 八、仍硬編碼的參數（備註）

以下參數目前無法透過 API 或 .env 設定，若需修改須改程式碼。

### LoRA 訓練

| 項目 | 寫死值 | 位置 |
|------|--------|------|
| network_module | `networks.lora` | `lora_trainer.py` |
| save_model_as | `safetensors` | `lora_trainer.py` |
| cache_latents | 固定啟用 | `lora_trainer.py` |
| gradient_checkpointing | 固定啟用 | `lora_trainer.py` |
| caption_extension | `.txt` | `lora_trainer.py` (dataset TOML) |
| LoRA 輸出子目錄 | `output` | `lora_trainer.py`（`{LORA_TRAIN_DIR}/output`） |

### Workflow

| 項目 | 寫死值 | 位置 |
|------|--------|------|
| workflow 模板名 | `default`、`default_lora` | `queue.py` |
| workflows 目錄 | `backend/workflows/` | `workflow.py` |

### 生圖佇列

| 項目 | 寫死值 | 位置 |
|------|--------|------|
| MAX_PENDING | 50 | `queue.py` |
| worker 輪詢間隔 | 2.0 秒 | `queue.py` |

### WD Tagger

| 項目 | 寫死值 | 位置 |
|------|--------|------|
| repo_id | `SmilingWolf/wd-swinv2-tagger-v3` | `wd_tagger.py` |
| batch_size | 4 | `wd_tagger.py` |
| thresh | 0.35 | `wd_tagger.py` |
| timeout | 120 秒 | `wd_tagger.py` |

### Watchdog

| 項目 | 寫死值 | 位置 |
|------|--------|------|
| DEBOUNCE_SECONDS | 2.0 | `watcher.py` |
