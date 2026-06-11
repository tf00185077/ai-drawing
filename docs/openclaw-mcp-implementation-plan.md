# OpenClaw MCP Drawing Implementation Plan

> 目的：把 ai-drawing 已驗證的 backend HTTP 繪圖閉環包成 OpenClaw / agent 穩定可用的 MCP tools。
>
> 原則：每一個 step 都必須可驗收。不要用「程式碼已寫」當完成標準；必須有測試、實際輸出或明確檢查結果。
>
> 前置成果：
> - Phase 1 backend HTTP 繪圖閉環已驗證。
> - Phase 2 OpenClaw backend HTTP SOP 已完成：`docs/openclaw-backend-drawing-sop.md`。

---

## 0. 範圍與非目標

### 本 phase 目標

完成「繪圖最小閉環」MCP tools：

1. `list_resources`
2. `generate_image`
3. `get_generation_status`
4. `get_gallery_image`
5. `free_comfyui_memory`

這五個 tools 應讓 agent 可以完成：

```text
查資源 → 送出生圖 → 查 job → 取 gallery 圖片 → 釋放 ComfyUI 記憶體
```

### 非目標

本 phase 不做：

- LoRA training MCP 重構
- frontend UI
- batch generation
- img2img / ControlNet 完整工作流
- custom workflow authoring 的大改版
- OpenClaw 最終 MCP SOP

OpenClaw 最終 MCP SOP 留到 Phase 5，必須等 Phase 4 實測通過後再寫。

---

## 1. 現況盤點

目前 `mcp-server/` 已有基礎實作：

```text
mcp-server/mcp_server/tools/generate.py
mcp-server/mcp_server/tools/gallery.py
mcp-server/mcp_server/tools/lora_train.py
mcp-server/mcp_server/server.py
mcp-server/mcp_server/client.py
mcp-server/tests/test_tools.py
```

現有相關 tools：

| 現有 tool | 狀態 | 問題 / 缺口 |
|---|---|---|
| `get_available_resources` | 已存在 | 名稱不是 Phase 3 規劃的 `list_resources`；回傳為人類文字，不夠適合 agent 穩定解析 |
| `generate_image` | 已存在 | 可送出 job，但回傳為文字；缺少明確 `ok/job_id/next` 結構 |
| `get_job_status` | 已存在 | 功能接近 `get_generation_status`，但回傳為文字；completed 時缺少穩定 JSON 格式 |
| `gallery_detail` | 已存在 | 可查 gallery，但回傳缺少 `image_url` / `local_path`，不夠適合 agent 交付圖片 |
| `generate_queue_status` | 已存在 | 可輔助 busy 檢查，應保留 |
| `free_comfyui_memory` | 缺少 | Phase 3 必補 |

因此本 phase 不是從零重寫，而是「補齊穩定 agent-facing wrapper」。

---

## 2. 設計原則

### 2.1 MCP tools 呼叫 backend API，不重寫 backend logic

MCP tools 只做：

- 呼叫 backend HTTP endpoint
- 組裝/驗證參數
- 回傳 agent-friendly 結構
- 補上本地 OpenClaw 操作規則

MCP tools 不做：

- 直接操作 ComfyUI workflow 內部邏輯
- 直接寫 DB
- 直接搬移 gallery 檔案
- 繞過 backend queue

### 2.2 回傳格式要穩定

新增或改造的最小閉環 tools 應回傳 JSON 字串，最外層至少包含：

```json
{
  "ok": true,
  "tool": "tool_name",
  "next": "下一步建議"
}
```

錯誤也要穩定：

```json
{
  "ok": false,
  "tool": "tool_name",
  "error": "具體錯誤",
  "where": "backend|comfyui|validation|gallery|unknown"
}
```

### 2.3 保留既有 tool 相容性

若現有 tools 已被文件或使用者依賴，不應直接破壞：

- 可新增 alias / wrapper。
- 可讓舊 tool 內部呼叫新 helper，再維持原文字回傳。
- Phase 3 驗收只要求新最小閉環 tools 穩定可用。

### 2.4 保留 Phase 2 的資源限制

MCP 層必須繼承 `docs/openclaw-backend-drawing-sop.md` 的規則：

- 一次只送一個 generation job。
- 預設 `batch_size = 1`。
- submit 前可查 queue / resources。
- 不使用 `8000` 當 ai-drawing backend。
- 完成或失敗後呼叫 `free_comfyui_memory`。

---

## 3. Step-by-step 實作與驗收

## Step 1：整理 MCP config 與 backend / ComfyUI base URL

### 目標

讓 MCP server 可明確知道：

- ai-drawing backend base URL
- ComfyUI base URL
- gallery 本地根目錄

### 預期變更

可能涉及：

```text
mcp-server/mcp_server/config.py
mcp-server/mcp_server/client.py
mcp-server/tests/test_client.py
```

### 建議設定

| 變數 | 預設 | 用途 |
|---|---|---|
| `MCP_BACKEND_API_URL` | `http://127.0.0.1:8001` | ai-drawing backend base URL |
| `MCP_COMFYUI_API_URL` | `http://127.0.0.1:8188` | ComfyUI API base URL |
| `MCP_GALLERY_DIR` | `/Users/tf00185088/Desktop/ai-drawing/outputs/gallery` | 本機 gallery 根目錄 |

注意：既有 `docs/mcp-setup.md` 寫 `MCP_BACKEND_API_URL` 預設為 `8000`，但本機 Phase 1/2 實測 ai-drawing backend 是 `8001`，Phase 3 應同步修正文件或讓預設/範例明確指向 `8001`。

### 驗收標準

- [x] `config.py` 可讀取 backend URL、ComfyUI URL、gallery dir。
- [x] 未設定 env 時，本機預設不會指向 `8000`。
- [x] 測試覆蓋 env override。
- [x] 不把 `.env` 或 secrets 寫進 repo。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/test_client.py tests/test_server.py -q
```

若只改 config，可新增/指定：

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/ -k 'config or client' -q
```

### 完成產物

- config 測試通過。
- 文件或 README 不再誤導 agent 使用 `8000` 作為 ai-drawing backend。

### Step 1 實測結果（2026-06-11 14:12 CST）

- 新增 `mcp-server/tests/test_config.py`，覆蓋本機預設值與 `MCP_*` env override。
- `mcp-server/mcp_server/config.py` 預設值已更新：
  - `backend_api_url = "http://127.0.0.1:8001"`
  - `comfyui_api_url = "http://127.0.0.1:8188"`
  - `gallery_dir = "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery"`
- `docs/mcp-setup.md` 與 `mcp-server/README.md` 已同步 MCP env 文件與本機 OpenClaw 注意事項。
- 移除 `mcp-server/mcp_server/server.py` 對不存在 `lora_docs` module 的 import，讓 server tests 可正常載入。
- 驗證：
  - `uv run pytest tests/test_config.py tests/test_client.py tests/test_server.py -q` → `6 passed`
  - `uv run pytest tests/ -q` → `33 passed`

---

## Step 2：新增 `list_resources`

### 目標

提供 agent-friendly 的資源查詢 tool，包裝：

```text
GET /api/generate/available-resources
```

### 預期變更

可能涉及：

```text
mcp-server/mcp_server/tools/generate.py
mcp-server/tests/test_tools.py
```

### Tool 行為

建議新增：

```python
def list_resources() -> str:
    ...
```

成功回傳 JSON 字串：

```json
{
  "ok": true,
  "tool": "list_resources",
  "backend_base_url": "http://127.0.0.1:8001",
  "checkpoints": ["novaAnimeXL_ilV190.safetensors"],
  "loras": [],
  "workflows": ["default"],
  "next": "choose a checkpoint, then call generate_image"
}
```

失敗回傳：

```json
{
  "ok": false,
  "tool": "list_resources",
  "where": "backend",
  "error": "..."
}
```

### 驗收標準

- [x] tool 名稱是 `list_resources`。
- [x] 呼叫 `generate/available-resources`。
- [x] 回傳可 JSON parse。
- [x] response 中包含 `checkpoints`、`loras`、`workflows`。
- [x] checkpoints 空時 `ok` 可以仍為 true，但 `next` 必須提示不能提交生圖。
- [x] 保留或兼容現有 `get_available_resources`。

### 單元測試

新增測試至少覆蓋：

- 正常 resources response。
- 空 resources response。
- backend client exception。
- `get_available_resources` 若保留，仍可工作。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/test_tools.py -k 'list_resources or available_resources' -q
```

### Step 2 實測結果（2026-06-11 14:41 CST）

- 新增 `list_resources` MCP tool，回傳 agent-friendly JSON 字串。
- `list_resources` 呼叫既有 backend endpoint：`generate/available-resources`。
- `list_resources` 成功時回傳：`ok`、`tool`、`backend_base_url`、`checkpoints`、`loras`、`workflows`、`next`。
- checkpoints 空時仍回傳 `ok=true`，但 `next` 明確提醒 `do not call generate_image`。
- backend exception 時回傳 `ok=false`、`where="backend"` 與具體 error。
- 保留既有 `get_available_resources` 文字輸出相容性。
- 驗證：
  - RED：`ImportError: cannot import name 'list_resources'`。
  - GREEN：`uv run pytest tests/test_tools.py -k 'list_resources or available_resources' -q` → `5 passed, 16 deselected`。

---

## Step 3：改造 / 補齊 `generate_image`

### 目標

讓 `generate_image` 可穩定提交 job，且回傳 agent 可解析的 `job_id`。

對應 endpoint：

```text
POST /api/generate/
```

### 預期變更

```text
mcp-server/mcp_server/tools/generate.py
mcp-server/tests/test_tools.py
```

### Tool 行為

成功回傳 JSON 字串：

```json
{
  "ok": true,
  "tool": "generate_image",
  "job_id": "uuid",
  "status": "queued",
  "submitted": {
    "checkpoint": "novaAnimeXL_ilV190.safetensors",
    "width": 512,
    "height": 512,
    "batch_size": 1,
    "steps": 8,
    "cfg": 6.0
  },
  "next": "call get_generation_status with this job_id"
}
```

### Parameter 規則

- `prompt` 必填或有安全預設。
- `batch_size` 預設為 `1`。
- 若 `batch_size > 1`，除非明確傳入，否則拒絕或降為 1。
- 支援既有參數：`checkpoint`、`lora`、`negative_prompt`、`seed`、`steps`、`cfg`、`width`、`height`、`sampler_name`、`scheduler`、`lora_strength`、`denoise`。

### 驗收標準

- [x] 對 backend 呼叫 `post("generate/", json=body)`。
- [x] body 包含 prompt 與指定 optional params。
- [x] 預設 `batch_size` 最終為 1 或明確記錄未傳。
- [x] 回傳可 JSON parse。
- [x] 回傳包含 `job_id`、`status`、`next`。
- [x] backend 503 / exception 時回傳 `ok=false` 且 `where="backend"`。
- [x] 不破壞 character/style prompt 解析能力。

### 單元測試

至少覆蓋：

- 最小 prompt submit。
- 含 checkpoint / width / height / batch_size / sampler / scheduler submit。
- character/style 解析仍存在。
- backend error 回傳穩定 JSON。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/test_tools.py -k 'generate_image and not custom' -q
```

### Step 3 實測結果（2026-06-11 15:07 CST）

- 改造 `generate_image`，成功時回傳 agent-friendly JSON 字串。
- `generate_image` 成功回傳包含：`ok`、`tool`、`job_id`、`status`、`submitted`、`next`。
- `generate_image` 現在預設送出 `batch_size=1`，符合 OpenClaw 單任務 / 低負載策略。
- optional params 會保留在 backend request body，並原樣回填到 `submitted`。
- backend exception 時回傳 `ok=false`、`where="backend"` 與具體 error。
- character/style prompt 解析測試保持通過。
- 驗證：
  - RED：`json.decoder.JSONDecodeError`，因原本 `generate_image` 回傳文字。
  - GREEN：`uv run pytest tests/test_tools.py -k 'generate_image and not custom and not description' -q` → `4 passed, 18 deselected`。

---

## Step 4：新增 `get_generation_status`

### 目標

提供穩定 job 查詢 tool，包裝現有：

```text
GET /api/generate/job/{job_id}
```

可內部復用現有 `get_job_status` 或把 `get_job_status` 作為相容 alias。

### 預期變更

```text
mcp-server/mcp_server/tools/generate.py
mcp-server/tests/test_tools.py
```

### Tool 行為

queued / running：

```json
{
  "ok": true,
  "tool": "get_generation_status",
  "job_id": "uuid",
  "status": "running",
  "prompt_id": "comfy-prompt-id",
  "next": "wait, then call get_generation_status again"
}
```

completed：

```json
{
  "ok": true,
  "tool": "get_generation_status",
  "job_id": "uuid",
  "status": "completed",
  "image_id": 1,
  "image_path": "2026-06-11/ComfyUI_xxx.png",
  "next": "call get_gallery_image with image_id, then free_comfyui_memory"
}
```

not found / backend error：

```json
{
  "ok": false,
  "tool": "get_generation_status",
  "where": "backend",
  "job_id": "uuid",
  "error": "Job not found"
}
```

### 驗收標準

- [ ] tool 名稱是 `get_generation_status`。
- [ ] 呼叫 `generate/job/{job_id}`。
- [ ] queued、running、completed 都有測試。
- [ ] completed response 包含 `image_id` 與 `image_path`。
- [ ] 回傳可 JSON parse。
- [ ] 保留或兼容現有 `get_job_status`。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/test_tools.py -k 'generation_status or job_status' -q
```

---

## Step 5：新增 `get_gallery_image`

### 目標

提供 agent 可直接交付圖片的 gallery tool，包裝：

```text
GET /api/gallery/{image_id}
```

與現有 `gallery_detail` 的差異：

- 必須包含 `image_url`。
- 必須推導或回傳 `local_path`。
- 必須保留 metadata。
- 回傳必須可 JSON parse。

### 預期變更

```text
mcp-server/mcp_server/tools/gallery.py
mcp-server/tests/test_tools.py
```

### Tool 行為

成功回傳：

```json
{
  "ok": true,
  "tool": "get_gallery_image",
  "image_id": 1,
  "image_path": "2026-06-11/ComfyUI_00007__27920202_0.png",
  "image_url": "http://127.0.0.1:8001/gallery/2026-06-11/ComfyUI_00007__27920202_0.png",
  "local_path": "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-11/ComfyUI_00007__27920202_0.png",
  "metadata": {
    "checkpoint": "novaAnimeXL_ilV190.safetensors",
    "lora": null,
    "seed": 338566325,
    "steps": 8,
    "cfg": 6.0,
    "prompt": "...",
    "negative_prompt": "...",
    "created_at": "..."
  },
  "next": "deliver image to user, then call free_comfyui_memory if not already called"
}
```

### 驗收標準

- [ ] tool 名稱是 `get_gallery_image`。
- [ ] 呼叫 `gallery/{image_id}`。
- [ ] 回傳可 JSON parse。
- [ ] 包含 `image_url`。
- [ ] 包含 `local_path`。
- [ ] `local_path` 以 `MCP_GALLERY_DIR` / gallery root 組出。
- [ ] metadata 包含 checkpoint、seed、steps、cfg、prompt。
- [ ] 保留或兼容現有 `gallery_detail`。

### 單元測試

至少覆蓋：

- backend 回傳含 `image_url`。
- backend 回傳只含 `image_path`，tool 能組出 URL。
- `local_path` 正確拼接。
- backend error 回傳 `ok=false`。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/test_tools.py -k 'gallery_image or gallery_detail' -q
```

---

## Step 6：新增 `free_comfyui_memory`

### 目標

提供 MCP tool 釋放 ComfyUI 記憶體，包裝：

```text
POST http://127.0.0.1:8188/free
```

body：

```json
{"unload_models": true, "free_memory": true}
```

### 預期變更

可能新增：

```text
mcp-server/mcp_server/tools/comfyui.py
```

並更新 tool import / registration。

測試：

```text
mcp-server/tests/test_tools.py
```

或新增：

```text
mcp-server/tests/test_comfyui_tools.py
```

### Tool 行為

成功回傳：

```json
{
  "ok": true,
  "tool": "free_comfyui_memory",
  "comfyui_base_url": "http://127.0.0.1:8188",
  "unload_models": true,
  "free_memory": true,
  "next": "generation cycle is complete"
}
```

失敗回傳：

```json
{
  "ok": false,
  "tool": "free_comfyui_memory",
  "where": "comfyui",
  "error": "..."
}
```

### 驗收標準

- [ ] tool 名稱是 `free_comfyui_memory`。
- [ ] POST 到 ComfyUI `/free`。
- [ ] body 包含 `unload_models=true` 與 `free_memory=true`。
- [ ] 成功時回傳可 JSON parse。
- [ ] ComfyUI 無 body 回應時也視為成功。
- [ ] 失敗時回傳 `ok=false`，不讓 exception 直接炸出。

### 單元測試

至少覆蓋：

- 成功 POST。
- 空 response body 成功。
- 連線失敗。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/ -k 'free_comfyui_memory or comfyui' -q
```

---

## Step 7：更新 MCP server tool registration / docs

### 目標

確保新增 tools 實際會被 MCP server 載入，且文件列出正確 tools。

### 預期變更

可能涉及：

```text
mcp-server/mcp_server/tools/__init__.py
mcp-server/mcp_server/server.py
mcp-server/README.md
docs/mcp-setup.md
```

### 驗收標準

- [ ] MCP server 啟動時載入新 tools。
- [ ] `docs/mcp-setup.md` 的 tool list 包含：
  - `list_resources`
  - `generate_image`
  - `get_generation_status`
  - `get_gallery_image`
  - `free_comfyui_memory`
- [ ] `MCP_BACKEND_API_URL` 範例不再只指向錯誤的本機 `8000`。
- [ ] README 或 docs 說明「MCP tools 包裝 backend HTTP API，不重寫 backend logic」。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/test_server.py -q
```

如果 MCP SDK 支援工具列舉測試，新增測試確認 tool names 存在。

---

## Step 8：執行完整單元測試

### 目標

確保 MCP server 既有功能沒有被 Phase 3 改壞。

### 驗收標準

- [ ] `mcp-server/tests/` 全部通過。
- [ ] 沒有因回傳格式調整破壞既有測試。
- [ ] 若既有 tool 仍回文字，新增 wrapper tool 的 JSON 測試也通過。

### 驗證指令

```bash
cd ~/Desktop/ai-drawing/mcp-server
uv run pytest tests/ -q
```

### 若失敗

必須記錄：

- 失敗測試名稱
- 失敗原因
- 是舊測試需要更新，還是新實作破壞相容性

不可跳過失敗測試直接宣稱 Phase 3 完成。

---

## Step 9：本機 backend / ComfyUI MCP smoke test

### 目標

在真實 backend `8001` 與 ComfyUI `8188` 下，透過 MCP tool 完成一次低負載繪圖閉環。

這一步是 Phase 3 完成前的 integration smoke test；Phase 4 會再做正式 agent-through-MCP 驗證。

### 前置條件

- ComfyUI：`http://127.0.0.1:8188/system_stats` OK
- backend：`http://127.0.0.1:8001/health` OK
- backend resources 可列出至少一個 checkpoint
- backend queue 空

### 測試流程

依序呼叫：

1. `list_resources`
2. `generate_image`
3. `get_generation_status`，輪詢直到 completed
4. `get_gallery_image`
5. `free_comfyui_memory`

### 驗收標準

- [ ] `list_resources` 回傳 checkpoints。
- [ ] `generate_image` 回傳 job id。
- [ ] `get_generation_status` 回傳 completed。
- [ ] `get_gallery_image` 回傳 image_url 與 local_path。
- [ ] local_path 對應檔案存在且可讀。
- [ ] 圖片尺寸與 request 一致。
- [ ] `free_comfyui_memory` 回傳 ok。
- [ ] 測試後 backend queue 為空。

### 建議 payload

```json
{
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
}
```

### 驗證輸出必須記錄

- backend port
- ComfyUI port
- checkpoint
- job id
- image id
- image path
- local path
- PNG dimensions
- `/free` 結果

---

## Step 10：更新進度與交接文件

### 目標

完成 Phase 3 後，文件能讓下一個 agent 直接知道狀態與下一步。

### 預期變更

```text
docs/openclaw-ai-drawing-mcp-handoff.md
docs/PROGRESS.md
```

若 Phase 3 完成，更新：

- Phase 3 狀態：`completed`
- 驗證 checklist 打勾
- 執行紀錄新增具體結果
- `docs/PROGRESS.md` 待做清單第 3 項打勾
- 下一步指向 Phase 4：透過 MCP 實際完成一次繪圖驗證

### 驗收標準

- [ ] handoff 狀態表更新。
- [ ] Phase 3 checklist 更新。
- [ ] 執行紀錄含 job id / image path / tool names。
- [ ] PROGRESS 目前聚焦改成 Phase 4。
- [ ] git diff 只包含本 phase 相關檔案。

---

## 4. 建議執行順序

不要一次做完全部；建議逐步驗收：

1. Step 1：config / URL 基礎整理。
2. Step 2：`list_resources`。
3. Step 3：`generate_image`。
4. Step 4：`get_generation_status`。
5. Step 5：`get_gallery_image`。
6. Step 6：`free_comfyui_memory`。
7. Step 7：registration / docs。
8. Step 8：完整單元測試。
9. Step 9：真 backend / ComfyUI smoke test。
10. Step 10：更新 handoff / progress。

每完成一個 step，就先跑該 step 的驗收指令，再進下一步。

---

## 5. Phase 3 完成定義

只有同時滿足以下條件，Phase 3 才能標記完成：

- [ ] 五個最小 MCP tools 都存在：
  - [ ] `list_resources`
  - [ ] `generate_image`
  - [ ] `get_generation_status`
  - [ ] `get_gallery_image`
  - [ ] `free_comfyui_memory`
- [ ] 每個 tool 回傳 agent-friendly JSON 字串。
- [ ] 每個 tool 有單元測試。
- [ ] `uv run pytest tests/ -q` 通過。
- [ ] 真 backend / ComfyUI smoke test 通過。
- [ ] 生圖後有呼叫 `free_comfyui_memory`。
- [ ] 實體圖片檔案存在且可讀。
- [ ] `docs/openclaw-ai-drawing-mcp-handoff.md` 更新。
- [ ] `docs/PROGRESS.md` 更新。

---

## 6. Phase 4 入口條件

進入 Phase 4 前必須有：

- MCP server 可啟動。
- 五個最小 tools 可被 MCP client 呼叫。
- Phase 3 smoke test 的具體結果。
- OpenClaw agent 不需要手寫 HTTP endpoint 即可完成繪圖閉環。

Phase 4 的任務才是：

```text
由 Hermes / agent 實際使用 MCP 完成一次繪圖驗證
```

不要在 Phase 3 未通過前提前撰寫 OpenClaw MCP SOP。
