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
- `/animegen_i2v` — 先選一張起始圖片，再在彈窗填寫動作 Prompt、負面 Prompt、秒數、原始幀數與 FILM 目標幀數
- `/wan22_animate` — 先選角色參考圖與必要的 driver 影片，再在彈窗填寫其餘影片設定
- `/result id:<job_id>` — 反查圖片或影片工作；完成後貼回所有 Backend 已持久化的結果

### 固定影片互動流程

| 指令第一步 | 彈窗第二步 |
|------|------|
| `/animegen_i2v image:<起始圖片>` | 動作 Prompt、可選負面 Prompt、`total_seconds`、`source_frames`、`film_target_frames` |
| `/wan22_animate reference_image:<角色圖> driver_video:<driver影片>` | 動作 Prompt、可選負面 Prompt、`total_seconds`、`source_frames`、`film_target_frames` |

- Discord Modal 不提供可靠的附件上傳元件，因此圖片／driver 在 slash command 第一步選取；其餘可輸入選項集中在下一步彈窗。
- 彈窗預設為 3 秒、49 原始幀、FILM 97 最終幀，使用者可自行修改。
- `source_frames` 是模型原始生成的**總幀數**，必須介於 17–321 並符合 `4n+1`（例如 17、49、65、81）；`film_target_frames` 介於原始幀數與 1921。
- `total_seconds` 是**首幀到末幀的時間跨度**，不是 MP4 容器 duration。原始與 FILM 輸出 FPS 分別為 `(source_frames-1)/total_seconds` 與 `(film_target_frames-1)/total_seconds`。
- FILM 可輸出範圍內的**任意精確目標總幀數**；`film_target_frames` 本身不受 `4n+1` 限制。
- 指令只負責排入佇列並回傳 job id；之後使用 `/result id:<job_id>` 取得已持久化的最終影片。

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
