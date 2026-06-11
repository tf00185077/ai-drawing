# OpenClaw Backend Drawing SOP

> 目的：在 ai-drawing MCP tools 完成前，讓 OpenClaw agent 能透過已驗證的 backend HTTP endpoint 進行本地繪圖。
>
> 狀態：已根據 2026-06-11 Phase 1 實測結果整理。
> 實測閉環：ai-drawing backend `8001` → ComfyUI `8188` → gallery → DB record → 實體 PNG。

---

## 0. 強制規則

OpenClaw agent 使用本 SOP 時必須遵守：

1. **一次只提交一個 generation job。**
   - 不要並行送多個 `POST /api/generate/`。
   - 送出前先查 queue，若已有 running / pending，等待或回報 busy。
2. **預設 batch size = 1。**
   - 除非使用者明確要求，不要 batch。
3. **低負載優先。**
   - 第一版建議使用 512×512 或其他保守尺寸。
   - smoke test 可用低 steps；正式出圖再提高品質參數。
4. **生圖完成後必須釋放 ComfyUI 記憶體。**
   - 成功或失敗後，都應嘗試呼叫 ComfyUI `/free`。
5. **不要猜 checkpoint / workflow 名稱。**
   - 每次畫圖前先查 `GET /api/generate/available-resources`。
6. **不要使用 `8000` 作為 ai-drawing backend。**
   - 本機 `8000` 可能是另一個本地 LLM / MLX 服務。
   - Phase 1 實測可用 backend 是 `8001`。

---

## 1. 已驗證端點

### ai-drawing backend

```text
http://127.0.0.1:8001
```

### ComfyUI

```text
http://127.0.0.1:8188
```

### 實測成功產物

- backend port：`8001`
- checkpoint：`novaAnimeXL_ilV190.safetensors`
- job id：`27920202-569f-4880-abc2-7a9f477d0094`
- image id：`1`
- image path：`2026-06-11/ComfyUI_00007__27920202_0.png`
- 實際檔案：`/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-11/ComfyUI_00007__27920202_0.png`
- PNG 尺寸：512×512

---

## 2. 操作流程總覽

當使用者要求 OpenClaw 畫圖時，照順序做：

1. 檢查 ComfyUI health。
2. 檢查 ai-drawing backend health。
3. 檢查 backend queue 是否空閒。
4. 查詢 available resources。
5. 選擇 checkpoint 與保守參數。
6. 提交 generation request。
7. 使用 job id 查詢狀態直到 completed / failed / timeout。
8. completed 後查 gallery detail。
9. 確認圖片 URL / path。
10. 呼叫 ComfyUI `/free` 釋放記憶體。
11. 回覆使用者圖片與主要參數。

---

## 3. 詳細 HTTP / curl 步驟

以下指令預設在本機執行。

### Step 1：確認 ComfyUI 正常

```bash
curl -sS --max-time 5 http://127.0.0.1:8188/system_stats
```

成功判斷：

- 有 JSON 回應。
- `system.comfyui_version` 存在。
- `devices` 陣列存在。

失敗處理：

- 若連不上 `8188`，不要提交 generation。
- 回報：`ComfyUI is not reachable on 127.0.0.1:8188`。
- 需要先啟動 ComfyUI。

---

### Step 2：確認 ai-drawing backend 正常

```bash
curl -sS --max-time 5 http://127.0.0.1:8001/health
```

成功範例：

```json
{"status":"healthy"}
```

失敗處理：

- 若 `8001` 不通，不要自動改用 `8000`。
- `8000` 在本機可能是 LLM / MLX 服務，不是 ai-drawing。
- 可檢查 `8002`，但 Phase 1 實測發現 `8002` health OK 但 resources 為空，因此不建議直接使用。

---

### Step 3：確認 generation queue 空閒

```bash
curl -sS --max-time 5 http://127.0.0.1:8001/api/generate/queue
```

成功且空閒範例：

```json
{
  "queue_running": [],
  "queue_pending": []
}
```

busy 判斷：

- `queue_running` 非空：已有任務執行中。
- `queue_pending` 非空：已有任務排隊。

busy 處理：

- 不要再送新的 generation job。
- 等待既有 job 完成，或回報使用者目前 busy。

---

### Step 4：查詢可用資源

```bash
curl -sS --max-time 5 http://127.0.0.1:8001/api/generate/available-resources
```

Phase 1 實測成功範例：

```json
{
  "checkpoints": [
    "novaAnimeXL_ilV190.safetensors",
    "v1-5-pruned-emaonly.ckpt"
  ],
  "loras": [],
  "workflows": [
    "controlnet_pose",
    "default",
    "default_lora",
    "img2img_lora_pose",
    "txt2img_lora_pose"
  ]
}
```

選擇規則：

- 優先使用 response 中實際存在的 checkpoint。
- 不要猜不存在的模型名。
- 若 `checkpoints` 是空陣列，停止並回報 backend resource 設定異常。

---

### Step 5：提交低負載生圖任務

保守 smoke-test request：

```bash
curl -sS --max-time 10 -X POST http://127.0.0.1:8001/api/generate/ \
  -H 'Content-Type: application/json' \
  -d '{
    "checkpoint": "novaAnimeXL_ilV190.safetensors",
    "prompt": "1girl, solo, simple background, anime style, clean lineart",
    "negative_prompt": "lowres, blurry, bad anatomy, worst quality",
    "steps": 8,
    "cfg": 6.0,
    "width": 512,
    "height": 512,
    "batch_size": 1,
    "sampler_name": "euler",
    "scheduler": "normal"
  }'
```

成功範例：

```json
{
  "job_id": "27920202-569f-4880-abc2-7a9f477d0094",
  "status": "queued",
  "message": "已加入生圖佇列"
}
```

成功判斷：

- HTTP 成功。
- response 有 `job_id`。
- `status` 是 `queued` 或 `running`。

失敗處理：

- `400`：參數錯誤。檢查 width / height / cfg / steps / checkpoint 名稱。
- `503`：ComfyUI 不可用或 queue 滿。不要重複轟炸；先查 health 和 queue。

---

### Step 6：查詢單一 job 狀態

將上一個 response 的 `job_id` 帶入：

```bash
JOB_ID="27920202-569f-4880-abc2-7a9f477d0094"
curl -sS --max-time 5 "http://127.0.0.1:8001/api/generate/job/${JOB_ID}"
```

可能回應：

#### queued / running

```json
{
  "status": "running",
  "job_id": "...",
  "prompt_id": "...",
  "submitted_at": "..."
}
```

處理：

- 等待幾秒後再查。
- 不要送第二個 job。

#### completed

```json
{
  "status": "completed",
  "job_id": "27920202-569f-4880-abc2-7a9f477d0094",
  "image_id": 1,
  "image_path": "2026-06-11/ComfyUI_00007__27920202_0.png"
}
```

處理：

- 繼續查 gallery detail。

#### 404

代表 backend 找不到此 job。

處理：

- 確認 job id 是否抄錯。
- 確認查詢的是同一個 backend port。
- 不要直接重新送 job；先查 queue 與 gallery。

---

### Step 7：查 gallery detail

若 job completed 且有 `image_id`：

```bash
IMAGE_ID=1
curl -sS --max-time 5 "http://127.0.0.1:8001/api/gallery/${IMAGE_ID}"
```

成功範例：

```json
{
  "id": 1,
  "image_path": "2026-06-11/ComfyUI_00007__27920202_0.png",
  "image_url": "/gallery/2026-06-11/ComfyUI_00007__27920202_0.png",
  "checkpoint": "novaAnimeXL_ilV190.safetensors",
  "lora": null,
  "seed": 338566325,
  "steps": 8,
  "cfg": 6.0,
  "prompt": "1girl, solo, simple background, anime style, clean lineart",
  "negative_prompt": "lowres, blurry, bad anatomy, worst quality",
  "created_at": "2026-06-11T03:56:42.367822"
}
```

使用者可看的圖片 URL：

```text
http://127.0.0.1:8001/gallery/2026-06-11/ComfyUI_00007__27920202_0.png
```

檔案系統實際位置通常是：

```text
/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/<image_path>
```

注意：OpenClaw 回覆使用者時，應回傳 gallery URL 或把圖片作為檔案附件傳送；不要只回傳 backend 內部相對路徑。

---

### Step 8：釋放 ComfyUI 記憶體

無論成功或失敗，完成一輪 generation 後都應呼叫：

```bash
curl -sS --max-time 20 -X POST http://127.0.0.1:8188/free \
  -H 'Content-Type: application/json' \
  -d '{"unload_models": true, "free_memory": true}'
```

成功判斷：

- 此 endpoint 可能沒有 body。
- 呼叫後可再查：

```bash
curl -sS --max-time 5 http://127.0.0.1:8188/system_stats
```

若 `/system_stats` 仍正常，視為 ComfyUI 服務健康。

---

## 4. 回覆使用者的建議格式

當出圖成功：

```text
已完成本地繪圖。

- checkpoint: novaAnimeXL_ilV190.safetensors
- seed: 338566325
- steps: 8
- cfg: 6.0
- size: 512x512
- image: http://127.0.0.1:8001/gallery/2026-06-11/ComfyUI_00007__27920202_0.png

已釋放 ComfyUI 記憶體。
```

當出圖失敗：

```text
本地繪圖未完成。

失敗位置：<ComfyUI health / backend health / resources / queue / submit / job status / gallery / free>
錯誤內容：<具體 HTTP status 或 response body>
下一步：<建議處理>
```

不要只說「失敗了」；必須指出失敗在哪一層。

---

## 5. 常見問題與判斷

### 8001 health OK，但 resources 空

不要直接提交生圖。這通常代表 backend effective config / cwd / model path 不對。

處理：

1. 停止使用該 port。
2. 查其他 backend port 是否有 resources。
3. 優先使用能列出 checkpoints 的 backend。

Phase 1 實測：

- `8001`：health OK，resources OK。
- `8002`：health OK，但 resources 空。

### queue 裡已有 running job

不要再送 job。等待或回報 busy。

### API completed，但圖片打不開

這不是完整成功。必須檢查：

1. `GET /api/gallery/{image_id}` 是否正常。
2. `image_url` 是否能存取。
3. 實體檔案是否存在於 `outputs/gallery/`。

### 圖片品質差，但 API 成功

這是模型 / workflow / prompt / 參數品質問題，不等於 backend 壞掉。

先確認：

- job completed
- gallery record 存在
- PNG 可讀
- checkpoint 符合預期

再調整 prompt、steps、cfg、尺寸或 workflow。

---

## 6. 進入 MCP 前的邊界

本 SOP 是 MCP 完成前的 HTTP 操作方案。

下一階段 MCP tools 應包裝同一個流程，而不是重新實作 backend logic：

1. `list_resources` → `GET /api/generate/available-resources`
2. `generate_image` → `POST /api/generate/`
3. `get_generation_status` → `GET /api/generate/job/{job_id}`
4. `get_gallery_image` → `GET /api/gallery/{image_id}`
5. `free_comfyui_memory` → `POST http://127.0.0.1:8188/free`

MCP 實作也必須保留本 SOP 的限制：單任務、batch size 1、busy 時等待、完成後釋放記憶體。

---

## 7. 最小檢查清單

OpenClaw agent 每次畫圖前後都應檢查：

- [ ] ComfyUI `/system_stats` OK
- [ ] backend `/health` OK
- [ ] backend queue 空或可接受
- [ ] available resources 至少有一個 checkpoint
- [ ] generation response 有 `job_id`
- [ ] job status 到 `completed`
- [ ] gallery detail 可讀
- [ ] 圖片 URL / 檔案路徑可用
- [ ] ComfyUI `/free` 已呼叫
- [ ] 回覆使用者時包含圖片與主要參數
