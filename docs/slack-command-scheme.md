# Slack 指令方案：統一 JSON 格式觸發 Backend API

> 目標：使用者在 Slack 用特定指令觸發後端 API，支援「給我可用指令」查詢、用文字生圖、指定動作生圖、訓練 LoRA、查詢圖庫。

**狀態**：規劃文件

---

## ⚠️ 規格唯一來源

**Slack 指令的觸發關鍵字、必填/選填參數、範例、說明，皆以 `backend/app/services/slack_commands.py` 的 `COMMAND_SPECS` 為準。**

- 新增或修改指令時：只改 `COMMAND_SPECS`，不在此文件重複定義
- help 文案由 `build_help_message()` 從 `COMMAND_SPECS` 動態產生
- 本文件僅描述架構、資料流、錯誤處理與實作步驟

---

## 一、架構原則

| 原則 | 說明 |
|------|------|
| **訊息觸發** | 使用 `!` 前綴，走 Socket Mode 訊息事件，無需公網 |
| **JSON 參數** | 各指令後接 JSON 字串，Backend 解析後呼叫對應 API |
| **統一入口** | `slack_handler` 解析指令類型，轉發至內部 HTTP API |
| **規範遵循** | `.cursor/rules/slack-trigger.mdc`，Handler 不直接操作 ComfyUI / DB |

---

## 二、指令清單與 API 對應

| cmd_key | 對應 API |
|---------|----------|
| `help` | 無，純回覆 `build_help_message()` |
| `generate` | `POST /api/generate/` |
| `generate_pose` | `POST /api/generate/custom` |
| `train_lora` | `POST /api/lora-train/start` |
| `query_gallery` | `GET /api/gallery/` |
| `rerun` | `POST /api/gallery/{id}/rerun` |

**觸發關鍵字、必填/選填參數、範例、說明**：見 `COMMAND_SPECS`（`slack_commands.py`）。

---

## 三、指令格式與參數

各指令的觸發關鍵字、必填欄位（`required`）、選填欄位（`optional`）、範例（`example`）、說明（`desc`）皆定義於 `COMMAND_SPECS`。

- **parse_command(text)**：依 `triggers` 辨識指令
- **validate_params(cmd_key, data)**：依 `required` 檢查必填
- **build_help_message()**：從 `COMMAND_SPECS` 動態產生 help 文案

詳細欄位對應 `docs/api-contract.md`（GenerateRequest、TrainStartRequest、Gallery 篩選等）。

---

## 四、實作架構

### 4.1 檔案結構

```
backend/app/
  services/
    slack_handler.py      # 擴充：指令路由、JSON 解析、HTTP 轉發
    slack_commands.py     # 新增：指令定義、參數 schema、help 文案
```

### 4.2 資料流

```
Slack message
    │
    ▼
slack_handler.handle_message()
    │
    ├─ 辨識指令類型（!給我可用指令 / !用文字生圖片 / ...）
    │
    ├─ [help] → 從 slack_commands 取得文案 → say()
    │
    └─ [其他] → 解析 JSON（可能失敗）
                    │
                    ├─ 失敗 → say("參數格式錯誤，請用 !給我可用指令 查看")
                    │
                    └─ 成功 → httpx.post/get(內部 API)
                                  │
                                  ├─ 成功 → say(簡化後的結果)
                                  └─ 失敗 → say(友善錯誤訊息)
```

### 4.3 內部 API 呼叫

Handler 使用 `httpx` 呼叫同進程的 FastAPI：

```
POST http://127.0.0.1:8000/api/generate/
POST http://127.0.0.1:8000/api/generate/custom
POST http://127.0.0.1:8000/api/lora-train/start
GET  http://127.0.0.1:8000/api/gallery/?limit=10&...
GET  http://127.0.0.1:8000/api/generate/queue
GET  http://127.0.0.1:8000/api/lora-train/status
...
```

Base URL 可從 `config` 讀取（如 `internal_api_base_url: str = "http://127.0.0.1:8000"`），預設本機。

---

## 五、help 回覆

當使用者打 `!給我可用指令` 時，Handler 呼叫 `slack_commands.build_help_message()` 並回傳其結果。

help 文案由 `COMMAND_SPECS` 動態產生，**不在此文件定義**；修改 `COMMAND_SPECS` 即可更新 help 內容。

---

## 六、錯誤處理與回覆

| 情境 | 回覆 |
|------|------|
| JSON 解析失敗 | `參數格式錯誤，請檢查 JSON。可用 !給我可用指令 查看格式` |
| 必填欄位缺失 | `缺少必填參數：xxx。可用 !給我可用指令 查看` |
| API 回傳 4xx/5xx | `操作失敗：{簡短訊息}`（詳細寫 log） |
| 佇列已滿 | `生圖佇列已滿，請稍後再試` |
| ComfyUI 不可用 | `生圖服務暫不可用` |

---

## 七、實作步驟

1. **新增 `slack_commands.py`**：定義 `COMMAND_SPECS`、help 文案、參數驗證
2. **擴充 `slack_handler.py`**：指令路由、JSON 解析、內部 HTTP 呼叫、回覆邏輯
3. **可選擴充 `config.py`**：`internal_api_base_url`（預設 `http://127.0.0.1:8000`）
4. **更新 `slack-trigger.mdc`**：加入新指令格式說明
5. **補測試**：`test_slack_handler.py` 或 `test_slack_commands.py`，至少 2 條用例

---

## 八、與既有機制並存

- **Regex 簡易格式**：可保留 `!generate 初音 5` 作為「用文字生圖片」的簡寫，解析後組 JSON 再轉發
- **LLM 模式**：若之後實作 Slack + LLM，可讓 LLM 輸出 JSON，由同一套指令邏輯處理

---

## 九、相關檔案

| 職責 | 檔案 |
|------|------|
| **規格唯一來源**：指令定義、help 文案、參數驗證 | `backend/app/services/slack_commands.py`（`COMMAND_SPECS`） |
| 訊息處理、路由、API 轉發 | `backend/app/services/slack_handler.py` |
| 規範 | `.cursor/rules/slack-trigger.mdc` |
| 生圖 API | `backend/app/api/generate.py` |
| LoRA 訓練 API | `backend/app/api/lora_train.py` |
| 圖庫 API | `backend/app/api/gallery.py` |
