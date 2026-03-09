# Slack Socket Mode 實作指南

> 遠端觸發生圖：手機透過 Slack 頻道傳送訊息 → 本地後端監聽 → 觸發生圖 API。無需公網 IP 或 ngrok。

**規範**：實作時須遵循 [`.cursor/rules/slack-trigger.mdc`](../.cursor/rules/slack-trigger.mdc)。

**整體進度**：5 / 5 完成 · 實作完成：2026-03-09

---

## 前置：Slack App 設定

在開始程式碼前，需先完成 Slack 後台設定：

| 項目 | 說明 | 狀態 |
|------|------|------|
| 建立 App | 至 [api.slack.com/apps](https://api.slack.com/apps) 建立或選用既有 App | [v] |
| Socket Mode | Settings → Socket Mode → Enable | [v] |
| App-Level Token | 建立 Token，需 `connections:write` 權限 | [v] |
| Bot Token Scopes | `channels:history`、`channels:read`、`chat:write`；私密頻道加 `groups:history`、`groups:read` | [v] |
| Event Subscriptions | 訂閱 `message.channels` 或 `message.groups` | [v] |
| 安裝 App | 安裝至 workspace，取得 Bot User OAuth Token | [v] |
| 邀請 Bot | 目標頻道輸入 `/invite @Bot名稱` | [v] |

---

## 實作步驟與進度

### 步驟 1：新增依賴

| 項目 | 說明 | 狀態 |
|------|------|------|
| 1.1 | 於 `backend/requirements.txt` 新增 `slack-bolt>=1.18.0` | [v] |
| 1.2 | 執行 `pip install slack-bolt` 或 `pip install -r requirements.txt` | [v] |

**檔案**：`backend/requirements.txt`

---

### 步驟 2：擴充 Config

| 項目 | 說明 | 狀態 |
|------|------|------|
| 2.1 | 於 `Settings` 類別新增 `slack_app_token: str = ""` | [v] |
| 2.2 | 於 `Settings` 類別新增 `slack_bot_token: str = ""` | [v] |
| 2.3 | 確認環境變數對應 `SLACK_APP_TOKEN`、`SLACK_BOT_TOKEN` | [v] |

**檔案**：`backend/app/config.py`

---

### 步驟 3：建立 slack_handler.py

| 項目 | 說明 | 狀態 |
|------|------|------|
| 3.1 | 建立 `handle_message(client, event, logger)` 簽名 | [v] |
| 3.2 | 過濾 bot 自身訊息，避免迴圈 | [v] |
| 3.3 | 解析指令（如 `!generate <描述> [張數]` 或 `生圖 <描述>`） | [v] |
| 3.4 | 可選：結合 character_style 將描述映射為 prompt | [ ] |
| 3.5 | 組成 GenerateParams，呼叫 `queue.submit(params)` | [v] |
| 3.6 | 以 chat.postMessage 回覆 Slack（成功／佇列滿／解析失敗） | [v] |
| 3.7 | 錯誤處理：QueueFullError、解析失敗、ComfyUI 不可用，一律回覆友善訊息並紀錄 log | [v] |

**檔案**：`backend/app/services/slack_handler.py`（新建）

Handler 僅可呼叫 `queue.submit()` 或 HTTP `POST /api/generate/`，不可直接呼叫 ComfyUI。

---

### 步驟 4：整合到 main.py lifespan

| 項目 | 說明 | 狀態 |
|------|------|------|
| 4.1 | 讀取 `slack_app_token`、`slack_bot_token`，任一為空則跳過 Slack | [v] |
| 4.2 | 建立 `slack_bolt.App`（Socket Mode 設定） | [v] |
| 4.3 | 註冊 `message` 事件 handler → `slack_handler.handle_message` | [v] |
| 4.4 | 於背景 thread 執行 `app.start()`（非 blocking） | [v] |
| 4.5 | lifespan 關閉時停止 Socket Mode | [v] |

**檔案**：`backend/app/main.py`

---

### 步驟 5：確認 .env.example

| 項目 | 說明 | 狀態 |
|------|------|------|
| 5.1 | 確認已包含 Slack 區塊與占位符 | [v] |
| 5.2 | 僅放占位符，勿使用真實 Token | [v] |

**預期內容**：

```
# Slack（遠端觸發生圖，Socket Mode）
SLACK_APP_TOKEN=xapp-xxx
SLACK_BOT_TOKEN=xoxb-xxx
```

**檔案**：`.env.example`

---

## 檔案對應總覽

| 職責 | 檔案 | 狀態 |
|------|------|------|
| Slack 依賴 | `backend/requirements.txt` | [v] |
| 設定 | `backend/app/config.py` | [v] |
| 訊息解析與觸發 | `backend/app/services/slack_handler.py` | [v] |
| 任務失敗通知 | `backend/app/services/slack_notifier.py` | [v] |
| Socket Mode 啟動 | `backend/app/main.py` | [v] |
| 環境變數範例 | `.env.example` | [v] |

---

## 回覆 Slack 的資料格式

| 情境 | 回覆內容 |
|------|----------|
| 成功加入佇列 | `已加入生圖佇列，job_id: xxx` |
| 佇列滿 (QueueFullError) | `生圖佇列已滿，請稍後再試` |
| 解析失敗 | `無法理解，請輸入生圖描述，例如：!generate 初音 5` |
| ComfyUI 不可用 | `生圖服務暫不可用` |
| **任務執行中失敗** | 主動發送失敗通知：`生圖任務 {job_id} 執行失敗：ComfyUI 連線失敗，請確認服務已啟動`（queue 捕獲錯誤後透過 `slack_notifier` 發送） |

---

## 相關文件

- [README 遠端觸發生圖](../README.md#遠端觸發生圖-slack-trigger)
- [slack-trigger.mdc 規範](../.cursor/rules/slack-trigger.mdc)
- [API 契約：POST /api/generate](api-contract.md#1-生圖模組-apigenerate)
