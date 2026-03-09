# Slack 指令實作 · Agent 追蹤文件

> **AI Agent 專用**：本文件供 Agent 依序執行任務、追蹤進度、檢查依賴。實作完成後請將 `[ ]` 改為 `[v]` 並填寫完成者。

**規格來源**：`docs/slack-command-scheme.md`、`docs/api-contract.md`

---

## 0. Agent 使用說明

### 0.1 執行前

1. 閱讀 `docs/slack-command-scheme.md`（指令格式、JSON schema）
2. 閱讀 `docs/api-contract.md` 第 1、2、4 節（生圖、圖庫、LoRA 訓練）
3. 閱讀 `.cursor/rules/slack-trigger.mdc`（架構原則、回覆格式）

### 0.2 執行規則

- **依賴**：僅在「依賴」欄所有任務為 `[v]` 時執行
- **完成標記**：完成後將該任務 `[ ]` 改為 `[v]`，並在「完成者」欄填寫
- **驗證**：執行「驗證方式」確保通過後再標記完成

### 0.3 依賴圖（執行順序）

```
S1.1 ──┐
       ├──► S2.1 ──► S3.1 ──► S3.2 ──► S3.3 ──► S3.4 ──► S3.5 ──► S3.6 ──► S4.1 ──► S4.2
S1.2 ──┘
```

---

## 1. 任務總表

| 任務 ID | 說明 | 實作檔案 | 依賴 | 驗證方式 | 狀態 | 完成者 |
|---------|------|----------|------|----------|------|--------|
| **S1.1** | 新增 slack_commands.py（指令定義、parse、validate、build_help） | `backend/app/services/slack_commands.py` | 無 | `from app.services.slack_commands import parse_command, build_help_message; parse_command("!生圖片 {}")` 不拋錯；`build_help_message()` 含 6 指令 | [v] | Agent |
| **S1.2** | config 擴充 internal_api_base_url | `backend/app/config.py` | 無 | `get_settings().internal_api_base_url` 可讀，預設 `http://127.0.0.1:8000` | [v] | Agent |
| **S2.1** | slack_handler 重構（指令路由、parse_command 整合） | `backend/app/services/slack_handler.py` | S1.1 | 打 `!給我可用指令` 可被辨識（可先 stub 回覆「開發中」） | [v] | Agent |
| **S3.1** | !給我可用指令 實作 | `backend/app/services/slack_handler.py` | S2.1 | 打 `!給我可用指令` 回覆完整 help 文案 | [v] | Agent |
| **S3.2** | !生圖片 → POST /api/generate/ | `backend/app/services/slack_handler.py` | S2.1, S1.2 | 打 `!生圖片 {"prompt":"test"}` 回覆 job_id 或佇列滿 | [ ] | |
| **S3.3** | !用指定動作生圖片 → POST /api/generate/custom | `backend/app/services/slack_handler.py` | S3.2 | 打 `!用指定動作生圖片 {"prompt":"1girl", "image_pose":"2026-03-08/x.png"}` 回覆 job_id | [ ] | |
| **S3.4** | !訓練lora → POST /api/lora-train/start | `backend/app/services/slack_handler.py` | S2.1 | 打 `!訓練lora {"folder":"test"}` 回覆 job_id 或錯誤 | [ ] | |
| **S3.5** | !查詢圖片 → GET /api/gallery/ | `backend/app/services/slack_handler.py` | S2.1 | 打 `!查詢圖片 {"limit":5}` 回覆筆數或列表摘要 | [ ] | |
| **S3.6** | !重新生成圖片 → POST /api/gallery/{id}/rerun | `backend/app/services/slack_handler.py` | S2.1 | 打 `!重新生成圖片 {"image_id":1}` 回覆 job_id 或 404 | [ ] | |
| **S4.1** | 單元測試 | `backend/tests/test_slack_commands.py` | S1.1, S3.6 | `cd backend && pytest tests/test_slack_commands.py -v` 至少 2 條通過 | [ ] | |
| **S4.2** | 更新 slack-trigger.mdc | `.cursor/rules/slack-trigger.mdc` | S3.6 | 檔內含指令格式表、slack_commands.py 路徑 | [ ] | |

---

## 2. 任務細規（Agent 實作參照）

### S1.1：slack_commands.py

| 項目 | 內容 |
|------|------|
| **輸出** | `COMMAND_SPECS`、`parse_command(text)->tuple[str, str|None]`、`validate_params(cmd_key, data)->str|None`、`build_help_message()->str` |
| **COMMAND_SPECS** | 每項含 `cmd_key`、`triggers`（關鍵字 list）、`required`（必填欄位）、`example`、`desc` |
| **cmd_key** | `help`, `generate`, `generate_pose`, `train_lora`, `query_gallery`, `rerun` |
| **parse_command** | 正則或關鍵字匹配，回傳 `(cmd_key, json_str)`，無 JSON 時 `json_str` 可為 `"{}"`（help）或 `None`（無效） |
| **validate_params** | 缺必填回傳錯誤字串，否則回傳 `None` |

**依賴**：無

---

### S1.2：config 擴充

| 項目 | 內容 |
|------|------|
| **新增欄位** | `internal_api_base_url: str = "http://127.0.0.1:8000"` |
| **env 對應** | `INTERNAL_API_BASE_URL`（可選） |

**依賴**：無

---

### S2.1：slack_handler 重構

| 項目 | 內容 |
|------|------|
| **變更** | import `slack_commands`；`_is_slack_command(text)` 涵蓋 6 種指令；`handle_message` 先 `parse_command` 再分支 |
| **觸發前綴** | `!給我可用指令`、`!生圖片`、`!用指定動作生圖片`、`!訓練lora`、`!查詢圖片`、`!重新生成圖片`（及別名，見 slack-command-scheme 五節） |
| **保留** | 可選保留 `!generate`、`生圖` 簡易格式，或移除改由 `!生圖片` 取代 |

**依賴**：S1.1

---

### S3.1：!給我可用指令

| 項目 | 內容 |
|------|------|
| **邏輯** | `cmd_key=="help"` → `say(build_help_message())` |
| **API** | 無 |

**依賴**：S2.1

---

### S3.2：!生圖片

| 項目 | 內容 |
|------|------|
| **API** | `POST {base}/api/generate/` |
| **契約** | api-contract §1，Request Body 同 GenerateRequest |
| **必填** | `prompt` |
| **回覆** | 201→`已加入生圖佇列，job_id: xxx`；503→`生圖佇列已滿`；400→`參數錯誤：{detail}` |

**依賴**：S2.1, S1.2

---

### S3.3：!用指定動作生圖片

| 項目 | 內容 |
|------|------|
| **API** | 先 `GET {base}/api/generate/workflow-templates/controlnet_pose`（404 則試 `default`），再 `POST {base}/api/generate/custom` |
| **body** | `workflow`（上 GET 結果）、`prompt`、`image_pose`、其他選填 |
| **必填** | `prompt`, `image_pose` |

**依賴**：S3.2（共用 httpx、base_url 邏輯）

---

### S3.4：!訓練lora

| 項目 | 內容 |
|------|------|
| **API** | `POST {base}/api/lora-train/start` |
| **契約** | api-contract §4 POST /start |
| **必填** | `folder` |
| **回覆** | 202→`已加入訓練佇列`；400/409→`操作失敗：{detail}` |

**依賴**：S2.1

---

### S3.5：!查詢圖片

| 項目 | 內容 |
|------|------|
| **API** | `GET {base}/api/gallery/?limit=10&offset=0&...` |
| **契約** | api-contract §2 GET / |
| **回覆** | 簡化摘要，如 `共 {total} 筆，最近：id=1 prompt=...` |

**依賴**：S2.1

---

### S3.6：!重新生成圖片

| 項目 | 內容 |
|------|------|
| **API** | `POST {base}/api/gallery/{image_id}/rerun` |
| **契約** | api-contract §2 POST /{id}/rerun |
| **必填** | `image_id`（int） |
| **回覆** | 202→`已加入生圖佇列`；404→`找不到該圖片` |

**依賴**：S2.1

---

### S4.1：單元測試

| 項目 | 內容 |
|------|------|
| **至少 2 條** | `test_parse_command_recognizes_commands`、`test_build_help_message_contains_all` |
| **規範** | testing-requirement.mdc |

**依賴**：S1.1, S3.6（全功能完成後補測試）

---

### S4.2：更新 slack-trigger.mdc

| 項目 | 內容 |
|------|------|
| **新增** | 指令格式表、回覆格式、`slack_commands.py` 路徑 |

**依賴**：S3.6

---

## 3. 指令關鍵字對照（parse_command 用）

| cmd_key | 觸發關鍵字 |
|---------|------------|
| `help` | `!給我可用指令`, `給我可用指令`, `!help` |
| `generate` | `!生圖片`, `!用文字生圖片` |
| `generate_pose` | `!用指定動作生圖片`, `!用文字生圖片指定動作` |
| `train_lora` | `!訓練lora`, `!進行lora訓練` |
| `query_gallery` | `!查詢圖片`, `!查詢圖片參數` |
| `rerun` | `!重新生成圖片`, `!重現圖片` |

---

## 4. API 契約對照

| 指令 | api-contract 章節 | HTTP Method | Path |
|------|-------------------|-------------|------|
| 生圖片 | §1 生圖 | POST | /api/generate/ |
| 用指定動作生圖片 | §1 + GenerateCustomRequest | POST | /api/generate/custom |
| 訓練lora | §4 LoRA 訓練 | POST | /api/lora-train/start |
| 查詢圖片 | §2 圖庫 | GET | /api/gallery/ |
| 重新生成圖片 | §2 圖庫 | POST | /api/gallery/{image_id}/rerun |

---

## 5. 完成後註記規範

完成任務後請：

1. 將該任務「狀態」欄 `[ ]` 改為 `[v]`
2. 在「完成者」欄填寫識別（如 `Agent`、日期）
3. 若修改 README 進度區塊，請同步更新

---

## 6. 相關文件索引

| 文件 | 路徑 | 用途 |
|------|------|------|
| 指令方案 | `docs/slack-command-scheme.md` | 指令格式、JSON schema、help 文案 |
| API 契約 | `docs/api-contract.md` | Request/Response 規格 |
| 實作順序（原版） | `docs/slack-command-implementation-order.md` | 詳細步驟說明 |
| Slack 規範 | `.cursor/rules/slack-trigger.mdc` | 架構、回覆、錯誤處理 |
| 測試規範 | `.cursor/rules/testing-requirement.mdc` | 單元測試要求 |
