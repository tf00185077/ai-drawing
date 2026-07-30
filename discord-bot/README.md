# ai-drawing Discord Bot

用 Discord slash 指令直接呼叫本機 backend 生圖，不經過 LLM。

## 設定

1. `cp .env.example .env`，填入：
   - `DISCORD_TOKEN`：Discord Developer Portal → 你的 App → Bot → Token
   - `GUILD_ID`：你的伺服器 ID（開啟 Discord 開發者模式後右鍵伺服器 → 複製 ID）
   - `BACKEND_BASE_URL`：預設 `http://localhost:8000`
2. Bot 需勾選 `applications.commands` scope 邀進伺服器。
3. 安裝依賴並啟動：

```bash
cd discord-bot
python -m venv .venv && . .venv/Scripts/activate   # Windows；macOS/Linux 用 . .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

## 指令

- `/draw` — 選 preset（有 profile 再選 profile）→ 填 prompt/寬/高/張數 → 回 job id
- `/result id:<job_id>` — 反查；完成就把所有持久化結果貼回來

## Operator / MCP result delivery（選用）

設定 `DISCORD_OPERATOR_TOKEN` 與 `DISCORD_DESTINATION_ALIASES` 後，Bot 會在
`127.0.0.1:8765` 提供受驗證、用途固定的 result-delivery endpoint。它只接受已完成的
`job_id`、allowlisted destination alias 與 explicit `force_resend`，不能傳任意訊息、檔案或
channel ID。MCP 端另設定相同的 `MCP_DISCORD_OPERATOR_TOKEN`（以及需要時的
`MCP_DISCORD_OPERATOR_URL`），即可呼叫 `deliver_generation_result_to_discord`。成功回傳
Discord message IDs；相同 job/alias 預設去重，只有 `force_resend=true` 才重送。

## 測試

```bash
cd discord-bot && python -m pytest -v
```

## 手動 smoke（需先啟動 backend + ComfyUI）

1. 啟 backend：`cd ../backend && uvicorn app.main:app --reload`
2. 啟 bot：`python -m bot.main`，確認 console 印出 commands synced
3. Discord 打 `/draw` → 下拉出現 12 個 preset → 選一個 → （有 profile 則選）→ 填 prompt/寬高/張數 → 送出取得 job id
4. 等數十秒後 `/result id:<job_id>` → 應貼回張數對應的圖

## 已知限制

- preset 超過 25 個需改分頁（目前 12 個）。
- `/result` 以 `job_id` 前 8 碼過濾 gallery，理論上相撞會誤撈（個人自用機率極低）。
- 6–8 張且單張偏大、合計超過 ~24MB 時，改回貼 gallery 連結而非附件。
