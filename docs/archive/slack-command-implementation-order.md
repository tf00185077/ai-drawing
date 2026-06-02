# Slack 指令實作順序

> 以 `docs/slack-command-scheme.md` 與 `docs/api-contract.md` 為基底，規劃實作步驟。
>
> **規格唯一來源**：觸發關鍵字、必填/選填參數、範例皆以 `backend/app/services/slack_commands.py` 的 `COMMAND_SPECS` 為準。
>
> **最終目標**：5 個可用指令 + 1 個列出指令，全部串接對應 API。
>
> **Agent 追蹤**：AI Agent 請依 **[docs/slack-command-agent-tracker.md](./slack-command-agent-tracker.md)** 執行任務、更新進度、檢查依賴。

---

## 一、指令與 API 對應表

| # | cmd_key | 對應 API（api-contract） |
|---|---------|--------------------------|
| 0 | `help` | 無，純回覆 `build_help_message()` |
| 1 | `generate` | `POST /api/generate/` |
| 2 | `generate_pose` | `POST /api/generate/custom` |
| 3 | `train_lora` | `POST /api/lora-train/start` |
| 4 | `query_gallery` | `GET /api/gallery/` |
| 5 | `rerun` | `POST /api/gallery/{image_id}/rerun` |

**觸發格式、範例**：見 `COMMAND_SPECS`。

---

## 二、實作階段與依賴關係

```
Phase 1: 基礎架構
    │
    ├─ Step 1.1: slack_commands.py（指令定義、help 文案）
    └─ Step 1.2: config 擴充（internal_api_base_url，可選）
         │
         ▼
Phase 2: Handler 框架
    │
    └─ Step 2.1: slack_handler 重構（指令路由、過濾非指令訊息）
         │
         ▼
Phase 3: 依序串接指令
    │
    ├─ Step 3.1: !給我可用指令
    ├─ Step 3.2: !生圖片 → POST /api/generate/
    ├─ Step 3.3: !用指定動作生圖片 → POST /api/generate/custom
    ├─ Step 3.4: !訓練lora → POST /api/lora-train/start
    ├─ Step 3.5: !查詢圖片 → GET /api/gallery/
    └─ Step 3.6: !重新生成圖片 → POST /api/gallery/{id}/rerun
         │
         ▼
Phase 4: 測試與文件
    │
    ├─ Step 4.1: 單元測試
    └─ Step 4.2: 更新 slack-trigger.mdc
```

---

## 三、分步實作說明

### Step 1.1：新增 `slack_commands.py`

**檔案**：`backend/app/services/slack_commands.py`

**內容**：
- `COMMAND_SPECS`: 6 個指令的定義（關鍵字、說明、JSON schema 必填欄位、範例）
- `build_help_message()`: 回傳「給我可用指令」的完整文案
- `parse_command(text)`: 辨識訊息是否為指令，回傳 `(cmd_key, json_str | None)`
- `validate_params(cmd_key, data)`: 檢查必填欄位

**輸出**：可被 `slack_handler` import 的模組，尚不呼叫 API。

---

### Step 1.2：config 擴充（可選）

**檔案**：`backend/app/config.py`

**新增**：
```python
internal_api_base_url: str = "http://127.0.0.1:8000"  # Slack handler 呼叫 Backend 用
```

**說明**：若 Backend 跑在不同 host/port，可由 `.env` 覆寫。

---

### Step 2.1：slack_handler 重構

**檔案**：`backend/app/services/slack_handler.py`

**變更**：
1. 觸發辨識：依 `COMMAND_SPECS.triggers`（由 `parse_command` 統一處理，無需硬編碼關鍵字）
2. 新增 `_is_slack_command(text) -> bool`：若 `parse_command(text)[0]` 非 None 則回傳 True
3. 重構 `handle_message` 流程：
   - 過濾 bot 自身、子類型（維持原邏輯）
   - 若 `_is_slack_command(text)` 為 False → `return`（不處理）
   - 呼叫 `slack_commands.parse_command(text)` 取得 `(cmd_key, json_str)`
   - 依 `cmd_key` 分支處理（此時尚未實作 API 呼叫，可先 stub 回覆）

**保留**：`!generate 初音 5`、`生圖 初音 5` 作為簡易格式，可選擇保留或移除（若移除則改由 `!生圖片 {"prompt":"初音", "batch_size":5}` 取代）。

---

### Step 3.1：!給我可用指令

**邏輯**：
- `cmd_key == "help"` 時，呼叫 `slack_commands.build_help_message()`
- 使用 `say(channel=..., text=help_msg)`

**無 API 呼叫**，僅組字串回覆。

---

### Step 3.2：!生圖片 → POST /api/generate/

**JSON**：必填/選填見 `COMMAND_SPECS`（cmd_key: `generate`）。對應 api-contract §1 生圖模組。

**邏輯**：
1. `validate_params("generate", data)` 檢查 `prompt` 存在
2. `httpx.post(f"{base_url}/api/generate/", json=data)` 
3. 成功 201 → `say("已加入生圖佇列，job_id: xxx")`
4. 503 → `say("生圖佇列已滿，請稍後再試")`
5. 400 → `say("參數錯誤：{detail}")`

---

### Step 3.3：!用指定動作生圖片 → POST /api/generate/custom

**JSON**：必填/選填見 `COMMAND_SPECS`（cmd_key: `generate_pose`）

**邏輯**：
1. `validate_params("generate_pose", data)` 檢查 `prompt`、`image_pose`
2. 需取得 workflow：`httpx.get(f"{base_url}/api/generate/workflow-templates/controlnet_pose")` 或使用 `default` 若專案無 controlnet_pose
3. 組 body：`{ "workflow": workflow_json, "prompt": ..., "image_pose": ..., ... }`
4. `httpx.post(f"{base_url}/api/generate/custom", json=body)`
5. 回覆同上

**注意**：`controlnet_pose.json` 存在於 `backend/workflows/`，且 `get_workflow_template` 回傳 JSON，需確認路徑為 `/api/generate/workflow-templates/{name}`（依 generate.py 實際路由而定，若無則用 `core/workflow.load_template` 直接載入）。

**修正**：generate API 的路由是 `get_workflow_template(name)`，掛在 generate router 下。需確認完整路徑。依 generate.py，router prefix 為 `/api/generate`，則完整路徑為 `GET /api/generate/workflow-templates/{name}`。但 api-contract 未列此 endpoint，屬內部使用。

---

### Step 3.4：!訓練lora → POST /api/lora-train/start

**JSON**：必填/選填見 `COMMAND_SPECS`（cmd_key: `train_lora`）。對應 api-contract §4 LoRA 訓練。

**邏輯**：
1. `validate_params("train_lora", data)` 檢查 `folder`
2. `httpx.post(f"{base_url}/api/lora-train/start", json=data)`
3. 202 → `say("已加入訓練佇列，job_id: xxx")`
4. 400/409 → `say("操作失敗：{detail}")`

---

### Step 3.5：!查詢圖片 → GET /api/gallery/

**JSON**：必填/選填見 `COMMAND_SPECS`（cmd_key: `query_gallery`）。對應 api-contract §2 圖庫 GET。

**邏輯**：
1. 將 data 轉為 query string：`?limit=10&offset=0&checkpoint=xxx&...`
2. `httpx.get(f"{base_url}/api/gallery/?{params}")`
3. 200 → 簡化回覆：`say("共 {total} 筆，最近 {n} 筆：id=1 checkpoint=... prompt=...")` 或摘要格式

---

### Step 3.6：!重新生成圖片 → POST /api/gallery/{image_id}/rerun

**JSON**：必填/選填見 `COMMAND_SPECS`（cmd_key: `rerun`），如 `{"image_id": 123}`

**邏輯**：
1. `validate_params("rerun", data)` 檢查 `image_id` 為整數
2. `httpx.post(f"{base_url}/api/gallery/{data['image_id']}/rerun")`
3. 202 → `say("已加入生圖佇列，job_id: xxx")`
4. 404 → `say("找不到該圖片")`

---

### Step 4.1：單元測試

**檔案**：`backend/tests/test_slack_commands.py` 或擴充 `test_slack_handler.py`

**至少 2 條用例**（依 testing-requirement.mdc）：
- `parse_command` 正確辨識各指令並解析 JSON
- `build_help_message` 回傳包含 6 個指令的文案

可選：mock `httpx` 測試 API 轉發邏輯。

---

### Step 4.2：更新 slack-trigger.mdc

**檔案**：`.cursor/rules/slack-trigger.mdc`

**新增**：
- 指令格式表（與本文件對應）
- 回覆格式補充（查詢圖片、訓練狀態等）
- 相關檔案：`slack_commands.py`

---

## 四、實作檢查清單

依序完成後可逐項打勾：

- [ ] Step 1.1: `slack_commands.py` 建立完成
- [ ] Step 1.2: config 擴充（可選）
- [ ] Step 2.1: `slack_handler` 重構完成，能辨識 6 種指令
- [ ] Step 3.1: !給我可用指令 可正常回覆
- [ ] Step 3.2: !生圖片 串接 POST /api/generate/
- [ ] Step 3.3: !用指定動作生圖片 串接 POST /api/generate/custom
- [ ] Step 3.4: !訓練lora 串接 POST /api/lora-train/start
- [ ] Step 3.5: !查詢圖片 串接 GET /api/gallery/
- [ ] Step 3.6: !重新生成圖片 串接 POST /api/gallery/{id}/rerun
- [ ] Step 4.1: 單元測試通過
- [ ] Step 4.2: slack-trigger.mdc 已更新

---

## 五、指令關鍵字對照

**見 `COMMAND_SPECS` 之 `triggers` 欄位**（`slack_commands.py`）。`parse_command()` 依此辨識指令。

---

## 六、help 回覆

**見 `slack_commands.build_help_message()` 輸出**。由 `COMMAND_SPECS` 動態產生，不在此重複定義。
