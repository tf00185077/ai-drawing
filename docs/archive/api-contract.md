# API 契約文件

> 後端與前端對接的唯一規格來源。各模組實作時須遵循此契約，確保並行開發後順利整合。

**Base URL**: `/api`（前端 proxy 至 `http://localhost:8000/api`）

---

## 1. 生圖模組 `/api/generate`

### POST `/`

觸發圖片生成。

**Request Body** (`application/json`):

```json
{
  "checkpoint": "path/to/model.safetensors",
  "lora": "path/to/lora.safetensors",
  "prompt": "1girl, solo, ...",
  "negative_prompt": "lowres, blur",
  "seed": 12345,
  "steps": 20,
  "cfg": 7.0,
  "width": 768,
  "height": 768,
  "batch_size": 2,
  "sampler_name": "dpmpp_2m",
  "scheduler": "karras"
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| checkpoint | string | 否 | Checkpoint 路徑或檔名 |
| lora | string | 否 | LoRA 路徑或檔名，可多個（依 workflow 規格） |
| template | string | 否 | 指定 workflow 模板名稱（如 `anima`）；省略時依是否有 lora 選 `default` / `default_lora` |
| diffusion_model | string | 否 | UNETLoader.unet_name（diffusion-model 家族，如 Anima）；省略時沿用模板內嵌值 |
| text_encoder | string | 否 | CLIPLoader.clip_name；省略時沿用模板內嵌值 |
| vae | string | 否 | VAELoader.vae_name；省略時沿用模板內嵌值 |
| prompt | string | 是 | 正向 prompt |
| negative_prompt | string | 否 | 負向 prompt |
| seed | integer | 否 | 隨機種子，不傳則隨機 |
| steps | integer | 否 | 採樣步數，預設 20 |
| cfg | float | 否 | CFG scale，預設 7.0 |
| width | integer | 否 | 圖寬 256–2048，不傳用 workflow 預設 |
| height | integer | 否 | 圖高 |
| batch_size | integer | 否 | 一次產圖張數 |
| sampler_name | string | 否 | 採樣器（euler、dpmpp_2m、ddim 等） |
| scheduler | string | 否 | 調度器（normal、karras、exponential 等） |

> `diffusion_model` / `text_encoder` / `vae` 讓 diffusion-model 家族（如 Anima）的 preset
> 也能走這條一般生圖路徑，而不必改用 `POST /custom`。省略時保留 workflow 模板內嵌值。

**Response** `201 Created`:

```json
{
  "job_id": "uuid-string",
  "status": "queued",
  "message": "已加入生圖佇列"
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| job_id | string | 佇列任務 ID，可查詢進度 |
| status | string | `queued` / `running` |
| message | string | 可選，提示訊息 |

**Error**:
- `400`: 參數錯誤
- `503`: ComfyUI 不可用或佇列已滿

---

### GET `/queue`

取得生圖佇列狀態。

**Response** `200 OK`:

```json
{
  "queue_running": [
    {
      "job_id": "uuid",
      "prompt_id": "comfy-prompt-id",
      "status": "running",
      "submitted_at": "2024-01-15T10:00:00Z"
    }
  ],
  "queue_pending": [
    {
      "job_id": "uuid",
      "status": "queued",
      "submitted_at": "2024-01-15T10:01:00Z"
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| queue_running | array | 執行中的任務 |
| queue_pending | array | 等候中的任務 |

---

## 2. 圖庫模組 `/api/gallery`

### GET `/`

圖庫列表，支援篩選。

**Query Parameters**:

| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| checkpoint | string | 否 | 篩選 checkpoint |
| lora | string | 否 | 篩選 LoRA |
| from_date | string | 否 | ISO 日期，如 `2024-01-01` |
| to_date | string | 否 | ISO 日期 |
| image_id | integer | 否 | 依圖片 ID 精確查詢 |
| image_name | string | 否 | 依圖片路徑/檔名關鍵字模糊查詢 |
| limit | integer | 否 | 每頁筆數，預設 20 |
| offset | integer | 否 | 分頁偏移，預設 0 |

**Response** `200 OK`:

```json
{
  "items": [
    {
      "id": 1,
      "image_path": "/outputs/gallery/2024-01/xxx.png",
      "checkpoint": "model.safetensors",
      "lora": "lora.safetensors",
      "seed": 12345,
      "steps": 20,
      "cfg": 7.0,
      "prompt": "1girl, ...",
      "negative_prompt": "lowres",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 42
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| items | array | 圖片記錄陣列 |
| total | integer | 符合篩選條件的總筆數 |

---

### GET `/{image_id}`

取得單張圖片完整參數。

**Path**: `image_id` (integer) - 資料庫 `GeneratedImage.id`

**Response** `200 OK`:

```json
{
  "id": 1,
  "image_path": "/outputs/gallery/2024-01/xxx.png",
  "checkpoint": "model.safetensors",
  "lora": "lora.safetensors",
  "seed": 12345,
  "steps": 20,
  "cfg": 7.0,
  "prompt": "1girl, solo, ...",
  "negative_prompt": "lowres, blur",
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Error**: `404` - 找不到該 ID

---

### POST `/{image_id}/rerun`

一鍵重現：載入該圖參數再次生成。

**Path**: `image_id` (integer)



**Response** `202 Accepted`:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "已加入生圖佇列"
}
```

**Error**: `404` - 找不到該 ID

---

### GET `/{image_id}/export`

匯出參數為 JSON 或 CSV。

**Path**: `image_id` (integer)

**Query Parameters**:

| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| format | string | 否 | `json` 或 `csv`，預設 `json` |

**Response** `format=json` `200 OK`:
- Content-Type: `application/json`
- Body: 同上 `GET /{image_id}` 的 JSON

**Response** `format=csv` `200 OK`:
- Content-Type: `text/csv`
- Body: CSV 內容，欄位為 id, image_path, checkpoint, lora, seed, steps, cfg, prompt, negative_prompt, created_at

**Error**: `404` - 找不到該 ID

---

## 3. LoRA 文件模組 `/api/lora-docs`

### POST `/upload`

上傳訓練圖片，自動產生 .txt caption。

**Request**: `multipart/form-data`

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| files | file[] | 是 | 多個圖片檔案 |
| folder | string | 否 | 目標資料夾（相對於 lora_train_dir），預設根目錄 |

**Response** `200 OK`:

```json
{
  "uploaded": 3,
  "items": [
    {
      "filename": "img1.png",
      "path": "my_lora/img1.png",
      "caption_path": "my_lora/img1.txt"
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| uploaded | integer | 成功上傳數量 |
| items | array | 可選，每張圖的檔名與路徑 |

---

### PUT `/caption/{image_path}`

編輯單張圖片的 .txt 內容。

**Path**: `image_path` (string) - 相對路徑，如 `my_lora/img1.png` 或 `my_lora/img1`

**Request Body** (`application/json`):

```json
{
  "content": "1girl, solo, long hair, ..."
}
```

**Response** `200 OK`:

```json
{
  "path": "my_lora/img1.txt",
  "updated": true
}
```

**Error**: `404` - 找不到該圖片或 .txt

---

### POST `/batch-prefix`

批次加入 trigger word 前綴。

**Request Body** (`application/json`):

```json
{
  "images": ["my_lora/img1.png", "my_lora/img2.png"],
  "prefix": "sks "
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| images | string[] | 是 | 圖片路徑陣列（相對 lora_train_dir） |
| prefix | string | 是 | 要加在 .txt 最前面的前綴 |

**Response** `200 OK`:

```json
{
  "updated": 2,
  "failed": []
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| updated | integer | 成功更新數量 |
| failed | string[] | 更新失敗的路徑 |

---

### GET `/download-zip`

打包圖片 + .txt 成 ZIP 下載。

**Query Parameters**:

| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| folder | string | 是 | 要打包的資料夾（相對 lora_train_dir） |

**Response** `200 OK`:
- Content-Type: `application/zip`
- Content-Disposition: `attachment; filename="my_lora.zip"`
- Body: ZIP 二進位

**Error**: `404` - 資料夾不存在

---

## 4. LoRA 訓練模組 `/api/lora-train`

### GET `/folders`

列出可訓練的資料夾（含至少 1 張圖+對應 .txt caption）。

**Response** `200 OK`:

```json
{
  "folders": [
    { "folder": "my_lora", "image_count": 10 },
    { "folder": "chars/hero", "image_count": 5 }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| folders | array | 可訓練的子資料夾列表 |
| folders[].folder | string | 相對 lora_train_dir 的路徑 |
| folders[].image_count | integer | 該資料夾內含 .txt 的圖片數量 |

---

### POST `/start`

手動觸發 LoRA 訓練。

**Request Body** (`application/json`):

```json
{
  "folder": "my_lora",
  "checkpoint": "path/to/base_model.safetensors",
  "epochs": 10,
  "resolution": 512,
  "batch_size": 4,
  "learning_rate": "1e-4",
  "class_tokens": "sks",
  "keep_tokens": 1,
  "num_repeats": 10,
  "mixed_precision": "fp16"
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| folder | string | 是 | 訓練資料夾（相對 lora_train_dir） |
| checkpoint | string | 否 | Base model 路徑，不傳則用 config 預設 |
| epochs | integer | 否 | 訓練 epoch 數，預設 10 |
| resolution | integer | 否 | 解析度 256–2048，不傳用 config |
| batch_size | integer | 否 | 每批圖片數 |
| learning_rate | string | 否 | 學習率 |
| class_tokens | string | 否 | 觸發詞 |
| keep_tokens | integer | 否 | caption 保留 token 數 |
| num_repeats | integer | 否 | 每張圖重複次數 |
| mixed_precision | string | 否 | fp16 / bf16 / fp32 |

**Response** `202 Accepted`:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "已加入訓練佇列"
}
```

**Error**:
- `400`: 資料夾不存在或圖片數不足
- `409`: 已有訓練在執行

---

### GET `/status`

訓練進度與佇列狀態。

**Response** `200 OK`:

```json
{
  "status": "running",
  "current_job": {
    "job_id": "uuid",
    "folder": "my_lora",
    "progress": 0.45,
    "epoch": 5,
    "total_epochs": 10
  },
  "queue": [
    {
      "job_id": "uuid2",
      "folder": "other_lora"
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| status | string | `idle` / `running` / `queued` |
| current_job | object | 可選，目前執行的任務詳情 |
| queue | array | 等候中的任務 |

---

### POST `/trigger-check`

檢查是否符合自動觸發條件（圖片數 ≥ 門檻）。

**Response** `200 OK`:

```json
{
  "should_trigger": true,
  "candidates": [
    {
      "folder": "my_lora",
      "image_count": 12
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| should_trigger | boolean | 是否有資料夾達門檻 |
| candidates | array | 符合條件的資料夾列表 |

---

## 5. Prompt 模板模組 `/api/prompt-templates`

### GET `/`

取得所有 prompt 模板。

**Response** `200 OK`:

```json
{
  "items": [
    {
      "id": "portrait",
      "name": "人像基礎",
      "template": "1girl, {人物}, {風格}, solo",
      "variables": ["人物", "風格"]
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| items | array | 模板陣列 |
| items[].id | string | 模板 ID |
| items[].name | string | 顯示名稱 |
| items[].template | string | 模板內容，變數以 `{名稱}` 表示 |
| items[].variables | string[] | 變數名稱列表 |

---

### POST `/apply`

依 template_id 與 variables 產出最終 prompt。

**Request Body** (`application/json`):

```json
{
  "template_id": "portrait",
  "variables": {
    "人物": "sks",
    "風格": "anime"
  }
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| template_id | string | 是 | 模板 ID |
| variables | object | 否 | 變數名 → 值的對應，未提供者以空字串取代 |

**Response** `200 OK`:

```json
{
  "prompt": "1girl, sks, anime, solo"
}
```

**Error**: `404` - 找不到該 template_id

---

## 5b. 生成統計分析 `/api/analytics`

### GET `/summary`

取得生成統計摘要：參數分佈、checkpoint / LoRA 使用頻率、最常使用的 seed。

**Query Parameters**:

| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| from_date | string | 否 | ISO 日期起，如 `2024-01-01` |
| to_date | string | 否 | ISO 日期迄 |
| limit | integer | 否 | 各類別取前 N 筆，預設 20 |

**Response** `200 OK`:

```json
{
  "total_count": 42,
  "checkpoint_usage": [{"name": "model.safetensors", "count": 20}],
  "lora_usage": [{"name": "style.safetensors", "count": 15}],
  "steps_stats": {"min": 20, "max": 30, "avg": 25.5, "count": 40},
  "cfg_stats": {"min": 7.0, "max": 9.0, "avg": 7.5, "count": 40},
  "top_seeds": [{"seed": 12345, "count": 3}]
}
```

**Error**: `400` - from_date 或 to_date 格式無效

---

## 5c. 風格預設目錄 `/api/style-presets`

創作者／風格「食譜」：記錄 checkpoint / LoRA / diffusion 元件、base/negative prompt、預設參數與
profiles。執行期來源為 `backend/style_presets/catalog.json`（Obsidian/Markdown 僅作人類筆記，透過
`note_path` 參照，不在請求時解析）。compose 產出可直接交給 `POST /api/generate` / `generate_image`
的 `generation` payload，但**不會送出生圖**（compose first, generate second）。

### GET `/`

列出所有 preset（輕量條目，不需讀取 Obsidian / Markdown）。

**Response** `200 OK`:

```json
{
  "items": [
    {
      "id": "creator-a",
      "name": "Creator A",
      "profiles": ["portrait", "full-body"],
      "note_path": "docs/style-presets/creator-a.md",
      "template": "default_lora",
      "checkpoint": "model.safetensors",
      "lora": "creator-a.safetensors",
      "diffusion_model": null
    }
  ]
}
```

---

### GET `/validate`

驗證每個 preset 參照的資源（checkpoint / lora / diffusion_model / text_encoder / vae / template）是否
已安裝，並檢查 `note_path` 是否存在、Markdown frontmatter 的 `preset_id` 是否與 catalog `id`
一致。invalid preset **仍會被列出**，以便修復目錄。

**Response** `200 OK`:

```json
{
  "items": [
    {
      "preset_id": "creator-a",
      "valid": false,
      "checked": {"checkpoint": "model.safetensors", "lora": "creator-a.safetensors"},
      "missing": [{"resource_type": "lora", "name": "creator-a.safetensors"}]
    }
  ]
}
```

---

### GET `/{preset_id}`

取得單一 preset 的完整食譜（resource references、base/negative prompt、default_params、profiles、note）。

**Response** `200 OK`：包含 `id`、`name`、`note_path`、`template`、`checkpoint`、`lora`、
`lora_strength`、`diffusion_model`、`text_encoder`、`vae`、`base_prompt`、`negative_prompt`、
`default_params`、`profiles[]`。

**Error**: `404` - 找不到該 preset_id

---

### POST `/{preset_id}/compose`

將 preset 與使用者 `content_prompt` 組成 generation payload。

**Request Body** (`application/json`):

```json
{
  "content_prompt": "a girl in a raincoat",
  "profile": "portrait",
  "overrides": {"seed": 123}
}
```

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| content_prompt | string | 是 | 使用者想在這張圖中呈現的內容（非最終完整 prompt） |
| profile | string | 否 | 具名 profile（如 `portrait`）；改變 prompt 前後綴並覆寫部分參數 |
| overrides | object | 否 | 覆寫生成參數（如 seed、steps），優先序最高 |

最終 prompt 組裝順序：preset `base_prompt` → profile `prompt_prefix` → `content_prompt` →
profile `prompt_suffix`（空白片段略過、以逗號合併）。負面 prompt 合併 preset 與 profile 兩層。

**Response** `200 OK`:

```json
{
  "preset_id": "creator-a",
  "profile": "portrait",
  "generation": {
    "template": "default_lora",
    "checkpoint": "model.safetensors",
    "lora": "creator-a.safetensors",
    "lora_strength": 0.75,
    "prompt": "creator_a_style, anime illustration, upper body, a girl in a raincoat",
    "negative_prompt": "low quality, bad anatomy",
    "steps": 32,
    "cfg": 6.5,
    "seed": 123
  }
}
```

**Error**:
- `404`: 找不到該 preset_id
- `422`: preset 無此 profile（回傳訊息含可用 profiles）

---

## 6. 共通錯誤格式（所有模組適用）

所有 API 錯誤回傳:

```json
{
  "detail": "錯誤訊息或欄位說明"
}
```

或 FastAPI 預設的 `{"detail": [...]}` 驗證錯誤格式。

---

## 7. 型別對應（Pydantic → 前端）

| 後端型別 | 前端（TypeScript） |
|----------|---------------------|
| `GenerateRequest` | `interface GenerateRequest { ... }` |
| `GalleryItem` | `interface GalleryItem { ... }` |
| `TrainStartRequest` | `interface TrainStartRequest { ... }` |
| `PromptTemplateItem` | `interface PromptTemplateItem { ... }` |
| `PromptTemplateApplyRequest` | `interface PromptTemplateApplyRequest { ... }` |
| `AnalyticsSummaryResponse` | `interface AnalyticsSummaryResponse { ... }` |

建議：在 `frontend/src/types/api.ts` 定義與本契約一致的 TypeScript 介面，並在 API 呼叫時使用。
