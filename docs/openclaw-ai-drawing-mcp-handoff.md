# OpenClaw × ai-drawing 本地繪圖 MCP 交接計畫

> 目的：讓任一 agent 讀取本文件後，可以恢復 CTY 對 `ai-drawing` / OpenClaw 本地繪圖整合的上下文、目前進度、下一步與驗證標準。
>
> 建立時間：2026-06-11 11:03 CST
> 狀態來源：本文件是這條 OpenClaw × ai-drawing MCP 整合任務的交接記憶文件；專案總進度仍以 `docs/PROGRESS.md` 為準。

---

## 0. 背景與強制約束

CTY 的目標是讓 OpenClaw agent 可以透過 `ai-drawing` 專案進行本地 AI 繪圖。

關鍵約束：

1. **LLM 與 ComfyUI 都必須本地運行。**
   - 不採用遠端 LLM 或雲端 ComfyUI 作為主要方案。
2. **核心策略是分時 / 序列化，而不是並行滿載。**
   - OpenClaw agent 先完成 prompt / 參數 / workflow 決策。
   - `ai-drawing` backend 或 MCP 再呼叫 ComfyUI 生圖。
   - 生圖完成後釋放 ComfyUI 記憶體。
3. **ComfyUI 應盡量限制記憶體壓力。**
   - 優先考慮 `--reserve-vram`、`--cache-none`、`--cpu-vae` 等保守啟動策略。
4. **MCP 是最終 agent 介面；backend HTTP endpoint 是第一階段驗證介面。**
   - 不能直接跳到 MCP；必須先確認 backend 端點能實際繪圖。
5. **agent 使用繪圖功能時，必須避免同時丟多個 generation job。**
   - 第一版應採單任務鎖 / 單任務佇列策略。

---

## 1. 執行順序總覽

| 順序 | 階段 | 狀態 | 目標 |
|---:|---|---|---|
| 1 | 透過 ai-drawing backend 端點進行繪圖 | **已完成** | 已證明 backend → ComfyUI → gallery 的繪圖閉環可用 |
| 2 | 教 OpenClaw 使用 backend 繪圖 | **已完成** | 已整理 HTTP endpoint SOP，MCP 完成前可照文件操作 |
| 3 | 將 ai-drawing 功能做成 MCP | **已完成** | 最小閉環五個 MCP tools 已齊，並已通過單元測試與本機 smoke test |
| 4 | 由 Hermes / agent 實際使用 MCP 驗證功能 | **已完成** | 已由 Hermes 透過 MCP tools 完成一次真實生圖、查詢、取圖與 `/free` 驗證 |
| 5 | 教 OpenClaw agent 使用 MCP | **已完成** | 已整理 OpenClaw 可遵守的 MCP 操作 SOP |

目前執行位置：**Phase 1~5 已完成文件化整理。`docs/openclaw-mcp-drawing-sop.md` 已建立，將已驗證的 MCP 最小閉環整理成 OpenClaw 可直接遵守的操作 SOP。**

---

## 2. 詳細任務拆解

### Phase 1：透過 ai-drawing backend 端點進行繪圖

狀態：`completed`

目的：不用 MCP，直接透過 backend HTTP API 讓 `ai-drawing` 呼叫 ComfyUI 並產出圖片。

執行項目：

1. 確認 ComfyUI 正常運行。
   - 預期：`GET http://127.0.0.1:8188/system_stats` 回傳 JSON。
2. 確認 ai-drawing backend 正常運行。
   - 常見本機 port：`8001` 或 `8002`，不要假設一定是 `8000`。
   - 先查 `/health`。
3. 查詢 backend 可用資源。
   - endpoint 參考：`GET /api/generate/available-resources`。
   - 目的：確認 backend 實際能看到 checkpoints / LoRAs / workflow templates。
4. 選擇一個低負載測試參數進行生圖。
   - batch size 必須為 1。
   - 解析度不要一開始太大。
   - steps 使用 smoke-test 等級即可。
5. 追蹤 job 狀態或 queue。
   - 確認 job 不是只 enqueue，而是真的完成。
6. 確認輸出圖片存在。
   - 要確認 backend 回傳的 image path 與實際 gallery 檔案一致。
   - 注意：本機曾出現 backend cwd 影響 SQLite / gallery 相對路徑的情況。
7. 生圖完成後呼叫 ComfyUI 釋放記憶體。
   - `POST http://127.0.0.1:8188/free`
   - body：`{"unload_models": true, "free_memory": true}`
8. 記錄結果到本文件「執行紀錄」。

驗證標準：

- [x] backend health OK
- [x] available resources 可列出至少一個 checkpoint
- [x] generate request 成功送出
- [x] job completed
- [x] 圖片檔案存在且可讀
- [x] ComfyUI `/free` 呼叫成功
- [x] 記錄實際 backend port、job id、圖片路徑、使用 checkpoint

---

### Phase 2：教 OpenClaw 使用 backend 進行繪圖

狀態：`completed`

目的：在 MCP 完成前，先讓 OpenClaw agent 可以用 backend HTTP endpoint 畫圖。

執行項目：

1. 根據 Phase 1 的實測結果，整理 backend base URL。
2. 整理 OpenClaw 可用的 HTTP 操作 SOP：
   - 查 health
   - 查 available resources
   - submit generation
   - 查 job status / queue
   - 找 gallery output
   - 呼叫 ComfyUI `/free`
3. 明確告訴 OpenClaw 限制：
   - 不要並行提交多個 generation job。
   - 預設 batch size = 1。
   - 生圖完成後必須釋放 ComfyUI memory。
   - 如果 ComfyUI busy，等待，不要堆疊任務。
4. 將 SOP 寫成 agent 可直接讀的文件。

建議輸出文件：

- `docs/openclaw-backend-drawing-sop.md`

驗證標準：

- [x] 文件包含實測可用的 curl / HTTP 範例
- [x] 文件包含成功/失敗判斷方式
- [x] 文件包含資源限制規則
- [x] OpenClaw agent 讀取後可照步驟操作，不需要猜 endpoint

---

### Phase 3：將 ai-drawing 功能做成 MCP

狀態：`completed`

目的：將 backend 功能包成 MCP tools，讓 OpenClaw agent 不需要手寫 HTTP 細節。

可驗收實作計畫：`docs/openclaw-mcp-implementation-plan.md`。

第一批最小閉環已完成，並已通過：
- MCP tool 單元測試
- MCP server import / registration 測試
- 本機 backend `8001` + ComfyUI `8188` smoke test

已完成的第一批 MCP tools：

1. `list_resources`
   - 列出 checkpoints、LoRAs、workflow templates。
2. `generate_image`
   - prompt、negative_prompt、checkpoint、width、height、steps、cfg、LoRA 等參數。
3. `get_generation_status`
   - 以 job id 查詢 queued / running / completed / failed。
4. `get_gallery_image`
   - 以 job id 或 image id 找輸出圖片與 metadata。
5. `free_comfyui_memory`
   - 呼叫 ComfyUI `/free`。

第二批 MCP tools（第一批穩定後再做）：

- custom workflow generation
- gallery search
- prompt / parameter history
- LoRA training
- LoRA docs / caption tools
- batch generation
- image variation / img2img
- analytics
- model management

實作注意：

- MCP tool 應該呼叫 backend API，而不是每個 tool 重新實作 backend logic。
- MCP 回傳格式要簡潔、穩定、適合 agent 判斷下一步。
- `generate_image` 應避免一口氣同步等待過久；必要時回傳 job id，再由 `get_generation_status` 輪詢。
- 必須考慮本地 GPU / unified memory 壓力，預設不允許並行 generation。

驗證標準：

- [x] MCP server 可啟動
- [x] `list_resources` 可回傳實際 backend 資源
- [x] `generate_image` 可建立 job
- [x] `get_generation_status` 可追蹤到 completed
- [x] `get_gallery_image` 可取得實際輸出
- [x] `free_comfyui_memory` 可成功呼叫

---

### Phase 4：由 Hermes / agent 實際使用 MCP 驗證功能

狀態：`completed`

目的：確認 MCP 不是只有程式碼存在，而是真的能被 agent 用來完成繪圖。

2026-06-12 已由 Hermes 透過 MCP tools 完成一次低負載繪圖驗證：`list_resources → generate_image → get_generation_status → get_gallery_image → free_comfyui_memory`，job `c99167aa-4370-47e1-ae09-2b97d5f18978`、image `2`、輸出 PNG 512×512，backend queue 驗證後為空。

執行項目：

1. 啟動 ai-drawing backend。
2. 啟動 ComfyUI。
3. 啟動 MCP server。
4. 透過 MCP 呼叫：
   - `list_resources`
   - `generate_image`
   - `get_generation_status`
   - `get_gallery_image`
   - `free_comfyui_memory`
5. 確認圖片檔案存在。
6. 確認生成 metadata 與實際圖片一致。
7. 將結果寫回本文件「執行紀錄」。

驗證標準：

- [x] agent 不是透過 curl，而是透過 MCP 完成一次繪圖
- [x] MCP 回傳 job id / image path / metadata
- [x] 圖片存在
- [x] 生圖完成後有釋放 ComfyUI memory
- [x] 若失敗，有明確錯誤來源：backend、ComfyUI、MCP、路徑、DB、模型資源

---

### Phase 5：教 OpenClaw agent 使用 MCP

狀態：`completed`

目的：將 MCP 使用方式整理成 OpenClaw agent 可遵守的操作規則。

輸出文件：

- `docs/openclaw-mcp-drawing-sop.md`（已建立，2026-06-15）

OpenClaw agent SOP 應包含：

```text
當使用者要求畫圖時：
1. 先用 list_resources 確認可用模型與 LoRA。
2. 選擇合適 checkpoint / workflow。
3. 呼叫 generate_image，batch size 預設為 1。
4. 使用 get_generation_status 等待 completed。
5. 使用 get_gallery_image 取得輸出圖片。
6. 呼叫 free_comfyui_memory 釋放 ComfyUI 記憶體。
7. 回覆使用者圖片與主要參數。
```

限制規則：

- 一次只允許一個 generation job。
- 除非使用者明確要求，不要 batch。
- ComfyUI busy 時等待，不要追加大量任務。
- 生圖完成後必須釋放 memory。
- 如果模型不可用，先重新查 `list_resources`，不要猜 checkpoint 名稱。
- 如果 generation failed，回報具體錯誤，不要重試超過合理次數。

驗證標準：

- [x] OpenClaw agent 讀取 SOP 後可描述正確使用流程
- [x] 已有真 stdio MCP 閉環驗證可作為 SOP 依據
- [x] SOP 已明確限制不可並行亂丟任務
- [x] SOP 已要求完成後釋放 ComfyUI memory

---

## 3. ComfyUI 本地負載控制建議

本任務的預設限制策略：

1. ComfyUI 啟動時優先使用保守參數：

```bash
cd ~/comfyui
/opt/homebrew/bin/python3.11 main.py \
  --reserve-vram 24 \
  --cache-none \
  --cpu-vae
```

2. 生圖完成後呼叫：

```bash
curl -X POST http://127.0.0.1:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": true, "free_memory": true}'
```

3. 從 backend / MCP 層實作真正的行為限制：
   - 單任務鎖
   - 單任務 queue
   - 預設 batch size = 1
   - 限制預設解析度
   - 完成後自動釋放 memory

注意：`--reserve-vram` 在 Apple Silicon unified memory 上不是硬體級 quota；它是 ComfyUI 層面的保守策略。真正可靠的限制應由 backend/MCP queue 與流程規則保證。

---

## 4. 已知本機事實

- ai-drawing 專案路徑：`~/Desktop/ai-drawing`
- ComfyUI 路徑：`~/comfyui`
- ComfyUI base URL：`http://127.0.0.1:8188`
- ComfyUI WebSocket URL：`ws://127.0.0.1:8188/ws`
- checkpoint 目錄：`~/comfyui/models/checkpoints`
- LoRA 目錄：`~/comfyui/models/loras`
- backend 可能使用不同 port；已知本機曾使用 `8001` / `8002`。
- 注意 backend SQLite / gallery path 曾受 current working directory 影響。

---

## 5. 下一個 agent 的啟動步驟

如果你是接手的 agent，請照這個順序開始：

1. 閱讀本文件。
2. 閱讀：
   - `AGENTS.md`
   - `docs/PROGRESS.md`
   - `docs/setup-guide.md`
   - `docs/mcp-setup.md`
   - `docs/internal-interfaces.md`
3. 確認目前 task 狀態表。
4. 從第一個 `pending` 的 phase 開始。
5. 每完成一個 phase：
   - 更新本文件的狀態表。
   - 在「執行紀錄」新增具體結果。
   - 如影響專案總進度，同步更新 `docs/PROGRESS.md`。
6. 不要跳過實測驗證。

---

## 7. 狀態更新模板

後續 agent 更新本文件時，請使用以下格式：

```markdown
### YYYY-MM-DD HH:mm TZ

- 執行 phase：Phase N - <名稱>
- 狀態：pending / in_progress / completed / blocked
- 實際操作：
  - ...
- 驗證結果：
  - ...
- 產物：
  - job id：...
  - image path：...
  - 文件：...
- 下一步：...
- 阻塞點：若無則寫「無」
```
