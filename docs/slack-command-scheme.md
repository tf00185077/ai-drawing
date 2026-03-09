# Slack 指令方案：統一 JSON 格式觸發 Backend API

> 目標：使用者在 Slack 用特定指令觸發後端 API，支援「給我可用指令」查詢、用文字生圖、指定動作生圖、訓練 LoRA、查詢圖庫。

**狀態**：規劃文件

---

## 一、架構原則

| 原則 | 說明 |
|------|------|
| **訊息觸發** | 使用 `!` 前綴，走 Socket Mode 訊息事件，無需公網 |
| **JSON 參數** | 各指令後接 JSON 字串，Backend 解析後呼叫對應 API |
| **統一入口** | `slack_handler` 解析指令類型，轉發至內部 HTTP API |
| **規範遵循** | `.cursor/rules/slack-trigger.mdc`，Handler 不直接操作 ComfyUI / DB |

---

## 二、指令清單與觸發格式

| 指令關鍵字 | 說明 | 對應 API |
|------------|------|----------|
| `!給我可用指令` | 列出所有可用指令與參數格式 | 無，純回覆 |
| `!用文字生圖片` | 依 prompt 生圖 | `POST /api/generate/` |
| `!用文字生圖片指定動作` | 生圖 + 姿態參考圖 | `POST /api/generate/custom`（帶 image_pose） |
| `!訓練lora` | 手動觸發 LoRA 訓練 | `POST /api/lora-train/start` |
| `!查詢圖片` | 圖庫列表（篩選） | `GET /api/gallery/` |
| `!生圖佇列` | 生圖佇列狀態 | `GET /api/generate/queue` |
| `!訓練狀態` | LoRA 訓練進度 | `GET /api/lora-train/status` |
| `!圖片詳情` | 單張圖片參數 | `GET /api/gallery/{id}` |
| `!重現圖片` | 一鍵用某張圖參數再產 | `POST /api/gallery/{id}/rerun` |

---

## 三、指令格式與 JSON Schema

### 3.1 給我可用指令

**觸發**：`!給我可用指令` 或 `給我可用指令` 或 `!help`

**行為**：Backend 回覆以下內容（可從集中定義的 `COMMAND_SPECS` 動態產生）

---

### 3.2 用文字生圖片

**觸發**：`!用文字生圖片 {"prompt":"1girl, miku", "batch_size":3}`

**JSON 參數**（對應 `GenerateRequest`）：

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `prompt` | string | ✅ | 生圖 prompt |
| `batch_size` | int | | 1～8，預設 1 |
| `checkpoint` | string | | checkpoint 檔名 |
| `lora` | string | | LoRA 檔名 |
| `negative_prompt` | string | | 負向 prompt |
| `seed` | int | | 隨機種子 |
| `steps` | int | | 1～150，預設 20 |
| `cfg` | float | | 1.0～30.0，預設 7.0 |
| `width` | int | | 256～2048 |
| `height` | int | | 256～2048 |

**範例**：
```
!用文字生圖片 {"prompt":"1girl, miku, kimono", "batch_size":3, "steps":25}
```

---

### 3.3 用文字生圖片指定動作

**觸發**：`!用文字生圖片指定動作 {"prompt":"1girl", "image_pose":"2026-03-08/ComfyUI_xxx.png"}`

**JSON 參數**：繼承「用文字生圖片」，外加

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `image_pose` | string | ✅ | 姿態參考圖路徑，相對於 gallery_dir |

**註**：需有 default 模板或 workflow，Backend 會以 `POST /api/generate/custom` 帶 `image_pose` 處理。

---

### 3.4 訓練 LoRA

**觸發**：`!訓練lora {"folder":"my_char", "epochs":10}`

**JSON 參數**（對應 `TrainStartRequest`）：

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `folder` | string | ✅ | 訓練資料夾名稱 |
| `checkpoint` | string | | checkpoint 檔名 |
| `epochs` | int | | 1～500，預設 10 |
| `resolution` | int | | 256～2048 |
| `batch_size` | int | | 1～32 |
| `learning_rate` | string | | 如 "1e-4" |
| `class_tokens` | string | | 如 "sks" |
| `generate_after` | object | | 訓練完成後自動生圖參數 |

`generate_after` 範例：
```json
{"prompt":"1girl, solo", "count":2, "batch_size":1}
```

**範例**：
```
!訓練lora {"folder":"my_char", "epochs":15, "generate_after":{"prompt":"1girl", "count":1}}
```

---

### 3.5 查詢圖片

**觸發**：`!查詢圖片 {"limit":10, "checkpoint":"xxx"}` 或 `!查詢圖片 {}`

**JSON 參數**（對應 `GET /api/gallery/` query）：

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `limit` | int | | 1～100，預設 20 |
| `offset` | int | | 分頁偏移，預設 0 |
| `checkpoint` | string | | 篩選 checkpoint |
| `lora` | string | | 篩選 LoRA |
| `from_date` | string | | ISO 日期，如 "2026-03-01" |
| `to_date` | string | | ISO 日期 |

**範例**：
```
!查詢圖片 {"limit":5}
!查詢圖片 {"checkpoint":"model", "limit":10}
```

---

### 3.6 圖片詳情

**觸發**：`!圖片詳情 {"image_id":123}`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `image_id` | int | ✅ | 圖片 ID |

---

### 3.7 重現圖片

**觸發**：`!重現圖片 {"image_id":123}`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `image_id` | int | ✅ | 要重現的圖片 ID |

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

## 五、help 回覆範例

當使用者打 `!給我可用指令` 時，回覆：

```
📋 可用指令：

• !用文字生圖片 <JSON>
  依 prompt 生圖。例：!用文字生圖片 {"prompt":"1girl, miku", "batch_size":3}
  參數：prompt(必填), batch_size, checkpoint, lora, negative_prompt, seed, steps, cfg, width, height

• !用文字生圖片指定動作 <JSON>
  生圖 + 姿態參考圖。例：!用文字生圖片指定動作 {"prompt":"1girl", "image_pose":"2026-03-08/xxx.png"}
  參數：同上 + image_pose(必填)

• !訓練lora <JSON>
  手動觸發 LoRA 訓練。例：!訓練lora {"folder":"my_char", "epochs":10}
  參數：folder(必填), checkpoint, epochs, resolution, batch_size, generate_after

• !查詢圖片 <JSON>
  圖庫列表。例：!查詢圖片 {"limit":10}
  參數：limit, offset, checkpoint, lora, from_date, to_date

• !圖片詳情 <JSON>
  單張圖片參數。例：!圖片詳情 {"image_id":123}

• !重現圖片 <JSON>
  用某張圖參數再產。例：!重現圖片 {"image_id":123}

• !生圖佇列
  查生圖佇列狀態

• !訓練狀態
  查 LoRA 訓練進度

• !給我可用指令
  顯示此清單
```

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
| 指令定義、help 文案 | `backend/app/services/slack_commands.py`（新建） |
| 訊息處理、路由、API 轉發 | `backend/app/services/slack_handler.py` |
| 規範 | `.cursor/rules/slack-trigger.mdc` |
| 生圖 API | `backend/app/api/generate.py` |
| LoRA 訓練 API | `backend/app/api/lora_train.py` |
| 圖庫 API | `backend/app/api/gallery.py` |
