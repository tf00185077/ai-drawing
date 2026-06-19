# OpenClaw MCP Drawing SOP

> 目的：讓 OpenClaw 本地 agent 透過 `ai-drawing` 的 MCP server 進行本地繪圖，且遵守本機資源限制。
>
> 本文件以 **2026-06-15 實際 stdio MCP 驗證** 為基礎整理，不是只根據程式碼或 README 推測。

---

## 0. 先講結論：要怎麼教 OpenClaw agent

如果你要直接教 OpenClaw agent，核心不是叫它「去畫圖」，而是明確教它遵守這個固定閉環：

```text
0. 判斷模式：
   - 使用者指名某個風格 preset → preset 模式
   - 使用者直接指定 checkpoint / LoRA → 手動模式
1. 先 call list_available_resources（手動模式必做；preset 模式可改用 validate_style_presets 確認資源）
2. preset 模式：list_style_presets → compose_style_preset(preset_id, content_prompt[, profile])
   取得 generation payload；手動模式：直接決定 checkpoint / LoRA
3. 確認 queue 空閒（generate_queue_status）
4. 選 checkpoint / 套用 generation payload，預設 batch_size=1
5. call generate_image（preset 模式餵入 compose 回傳的 generation 欄位）
6. 用 get_generation_status 輪詢到 completed 或 failed
7. completed 後 call get_gallery_image
8. 最後一定 call free_comfyui_memory
9. 回覆使用者時附上 image_path / image_url / 主要參數
```

> **何時問使用者要不要建立新 preset**：只有當使用者指名某個風格／創作者，但 `list_style_presets`
> 裡找不到對應 preset 時，才詢問是否要新增一筆食譜。**日常生圖不要每次都叫使用者填模板**——
> 有 preset 就用 preset，沒指名 preset 就走手動模式。建立新 preset 屬於另一條 curation 流程，
> 不是例行生圖的一部分。

你真正要灌輸給 agent 的不是「某個 prompt 怎麼寫」，而是：

- **不要猜模型名**，先查 `list_available_resources`
- **不要並行送多張**，一次只送一個 job
- **不要看到 queued 就當完成**，一定要輪詢 `get_generation_status`
- **不要忘了 free memory**
- **失敗時要回報具體工具與錯誤，不要無限重試**

---

## 1. 本機已驗證設定

### OpenClaw 版本

```text
OpenClaw 2026.5.4
```

### ai-drawing MCP 設定（來自 `openclaw mcp show`）

```json
{
  "ai-drawing": {
    "command": "/Users/tf00185088/Desktop/ai-drawing/mcp-server/.venv/bin/ai-drawing-mcp",
    "env": {
      "MCP_BACKEND_API_URL": "http://127.0.0.1:8001",
      "MCP_COMFYUI_API_URL": "http://127.0.0.1:8188",
      "MCP_GALLERY_DIR": "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery"
    },
    "cwd": "/Users/tf00185088/Desktop/ai-drawing/mcp-server"
  }
}
```

### 重要限制

- `8001` 才是本機 ai-drawing backend
- `8188` 是 ComfyUI
- **不要把 `8000` 當 ai-drawing backend**；本機 `8000` 可能是其他本地 LLM / MLX 服務
- gallery 實體路徑是：

```text
/Users/tf00185088/Desktop/ai-drawing/outputs/gallery
```

---

## 2. 如何在 OpenClaw 註冊 ai-drawing MCP server

這版 OpenClaw CLI 使用的是：

- `openclaw mcp list`
- `openclaw mcp show`
- `openclaw mcp set`
- `openclaw mcp unset`

不是較新文件常見的 `mcp add/status/doctor/probe` 那套。

### 設定指令

```bash
openclaw mcp set ai-drawing '{
  "command": "/Users/tf00185088/Desktop/ai-drawing/mcp-server/.venv/bin/ai-drawing-mcp",
  "cwd": "/Users/tf00185088/Desktop/ai-drawing/mcp-server",
  "env": {
    "MCP_BACKEND_API_URL": "http://127.0.0.1:8001",
    "MCP_COMFYUI_API_URL": "http://127.0.0.1:8188",
    "MCP_GALLERY_DIR": "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery"
  }
}'
```

### 驗證指令

```bash
openclaw mcp list
openclaw mcp show
```

成功標誌：`show` 裡能看到 `ai-drawing`，而且 `command/cwd/env` 與上面一致。

---

## 3. 啟動前提

OpenClaw agent 要能用這個 MCP server，前提不是只有 MCP config 正確，還包含下游服務已經活著：

### backend health

```bash
curl -sS http://127.0.0.1:8001/health
```

預期：

```json
{"status":"healthy"}
```

### ComfyUI health

```bash
curl -sS http://127.0.0.1:8188/system_stats
```

預期：有 JSON，且包含 `comfyui_version` 與 `devices`。

如果這兩個沒起來，OpenClaw agent 就算看得到 MCP tools，也只是得到 backend/comfyui error。

---

## 4. OpenClaw agent 應遵守的最小閉環

### Step 0：判斷 preset 模式或手動模式

- **使用者指名某個風格 / 創作者 preset**（例如「用 creator-a 風格」）→ **preset 模式**：
  1. `list_style_presets` 找到對應 preset id（找不到才詢問使用者是否要建立新 preset）
  2. （建議）`validate_style_presets` 確認該 preset 的資源都已安裝
  3. `compose_style_preset(preset_id, content_prompt[, profile, overrides])` 取得 `generation` payload
  4. 把 `generation` 的欄位（prompt、checkpoint、lora、diffusion_model、steps、cfg…）餵給 `generate_image`
- **使用者直接指定 checkpoint / LoRA** 或沒指名 preset → **手動模式**：照 Step 1 起的流程走。

`compose_style_preset` 只組裝、不送出生圖；可先把 `generation.prompt` 與參數回報使用者確認，再 `generate_image`。

### Step 1：先查資源

先呼叫：

- `list_available_resources`

目的：

- 拿到 `checkpoints`
- 拿到 `workflows`
- 知道 `default_checkpoint`
- 避免猜不存在的 checkpoint 名稱

### Step 2：查 queue

呼叫：

- `generate_queue_status`

規則：

- 若有 running / pending job，**不要再提交新的 generation**
- 回報 busy，或等待完成後再送

### Step 3：提交單張低負載任務

呼叫：

- `generate_image`

最低要求：

- `batch_size=1`
- 先用保守尺寸，例如 `512x512`
- smoke test 可用較低 steps

### Step 4：輪詢狀態

呼叫：

- `get_generation_status(job_id)`

規則：

- `queued` / `running` 不算完成
- 只有 `completed` 才能進下一步
- 若失敗，回報 `error/where/tool`，不要一直重送

### Step 5：取圖

呼叫：

- `get_gallery_image(image_id)`

應從回傳中取：

- `image_id`
- `image_path`
- `image_url`
- `local_path`
- `metadata`

### Step 6：釋放 ComfyUI 記憶體

呼叫：

- `free_comfyui_memory`

這一步是強制的。

---

## 5. 2026-06-15 實際驗證結果

本次不是只看文件，而是透過 **真 stdio MCP client** 連到：

```bash
uv run ai-drawing-mcp
```

並實際完成以下閉環：

```text
list_available_resources
→ generate_queue_status
→ generate_image
→ get_generation_status (輪詢)
→ get_gallery_image
→ free_comfyui_memory
```

### 驗證結果

- MCP 可見 tool 數：`23`
- default checkpoint：`novaAnimeXL_ilV190.safetensors`
- submit job：`3a18d370-3726-4fcf-b91b-b838fb6e4b87`
- 最終 image id：`6`
- image path：`2026-06-15/ComfyUI_00012__3a18d370_0.png`
- local path：`/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-15/ComfyUI_00012__3a18d370_0.png`
- 圖片存在：`True`
- 完成後 `/free` 成功：`ok=true`

### 本次實測提交參數

```json
{
  "prompt": "1girl, solo, simple portrait, looking at viewer",
  "checkpoint": "novaAnimeXL_ilV190.safetensors",
  "negative_prompt": "low quality, blurry",
  "steps": 4,
  "cfg": 4.5,
  "batch_size": 1,
  "width": 512,
  "height": 512
}
```

這證明：

- MCP transport 是通的
- tool registration 是完整的
- backend `8001` 是通的
- ComfyUI `8188` 是通的
- gallery 路徑是對的
- `free_comfyui_memory` 可以在結尾成功執行

---

## 6. 建議你給 OpenClaw agent 的指令模板

如果你要直接對 OpenClaw agent 下指令，我建議不要只說「幫我畫圖」，而是說成：

```text
Use the ai-drawing MCP server for this task.
Before generating, first call list_available_resources and generate_queue_status.
Do not assume checkpoint names.
Submit only one generation job (batch_size=1).
Poll with get_generation_status until completed.
Then call get_gallery_image.
After success or failure, always call free_comfyui_memory.
Report the final image_path, image_url, checkpoint, steps, cfg, and any error if generation fails.
```

如果你要中文版本給 agent：

```text
請使用 ai-drawing MCP server 完成這次繪圖。
如果我指名了某個風格 preset，先 list_style_presets 找到它，再 compose_style_preset 取得 generation
payload，把該 payload 餵給 generate_image；找不到對應 preset 時才問我要不要新增一筆。
如果我沒指名 preset，就走手動模式：先呼叫 list_available_resources 與 generate_queue_status，不要猜 checkpoint 名稱。
一次只允許一個 generation job，batch_size 固定為 1。
提交後用 get_generation_status 輪詢到 completed。
完成後呼叫 get_gallery_image 取得結果。
不論成功或失敗，最後都必須呼叫 free_comfyui_memory。
回報時附上 image_path、image_url、checkpoint、steps、cfg；若失敗則回報具體錯誤。
```

---

## 7. 我對「怎麼教他們」的建議

我的建議是：**教流程，不要教印象。**

也就是說，不要只教：

- 「你可以用 ai-drawing 畫圖」

要教成：

- 「你必須先查資源」
- 「你只能一次送一個 job」
- 「你必須輪詢到 completed」
- 「你最後必須 free memory」

原因很直接：

1. OpenClaw agent 最容易犯的錯不是不會叫 tool，而是**太早假設自己知道 checkpoint / 狀態**。
2. 本機是本地 LLM + 本地 ComfyUI，共用資源，**並行亂送 job 會把機器拖死**。
3. `queued`、`running`、`completed` 是不同狀態；如果不明講，它很容易把 submit 當成功出圖。
4. `free_comfyui_memory` 不寫成硬規則，agent 很容易忘。

所以最有效的教法不是「給它更多描述詞」，而是給它**明確工作協議**。

---

## 8. 已知坑

1. **真 MCP transport 驗證要優先用 `uv run ai-drawing-mcp`**
   - 不要把 `python -m mcp_server.server` 當完全等價。
2. **repo 雖然這次把很多 tool 說明改成英文，但回傳內容仍有中英混用。**
   - 所以 agent 應依賴 JSON 欄位如 `ok/tool/status/next/error`，不要只靠自然語言句子判斷。
3. **不要把 `8000` 當 backend。**
4. **不要略過 queue 檢查。**
5. **不要在完成前省略 `get_gallery_image`。**
   - `image_id` / `image_path` / `local_path` 要實際拿到才算交付。

---

## 9. 下一步

如果之後要再往前走，我建議的順序是：

1. 先讓 OpenClaw agent 實際讀這份 SOP
2. 指派它做一次低負載 smoke test
3. 看它是否真的遵守：
   - `list_available_resources`
   - `generate_queue_status`
   - `generate_image`
   - `get_generation_status`
   - `get_gallery_image`
   - `free_comfyui_memory`
4. 若它有偷步或亂猜，再把這份 SOP 的規則寫得更硬
