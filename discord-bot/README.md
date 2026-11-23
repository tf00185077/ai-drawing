# ai-drawing Discord Bot

用 Discord slash 指令直接呼叫本機 backend 生圖，不經過 LLM。

## 設定

1. 在 process env 或明示的絕對 `DISCORD_CONFIG_FILE` 填入：
   - `DISCORD_TOKEN`：Discord Developer Portal → 你的 App → Bot → Token
   - `GUILD_ID`：你的伺服器 ID（開啟 Discord 開發者模式後右鍵伺服器 → 複製 ID）
   - `BACKEND_BASE_URL`：預設 `http://localhost:8000`
   - `DISCORD_DELIVERY_LEDGER_PATH`：明示絕對路徑，必須有已核准且正確綁定的歷史；見下方維護契約。
2. Bot 需勾選 `applications.commands` scope 邀進伺服器。
3. 安裝依賴並啟動：

```bash
cd discord-bot
python -m venv .venv && . .venv/Scripts/activate   # Windows；macOS/Linux 用 . .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

## 指令

- `/draw` — 選執行位置與 preset（有 profile 再選 profile）→ 填 prompt/寬/高/張數 → 回 job id
- `/animegen_i2v` — 選執行位置、起始圖片與輸出寬高，再在彈窗填寫動作 Prompt、負面 Prompt、秒數、原始幀數與 FILM 目標幀數
- `/minimax_h3_i2v` — 選起始圖片與 256–1024 的 32 倍數寬高，再填 Prompt 與整數 1–5 秒；固定在 Mac Argus MLX 執行
- `/wan22_animate` — 選執行位置、角色參考圖與必要的 driver 影片，再在彈窗填寫其餘影片設定
- `/result id:<job_id>` — 反查圖片或影片工作；完成後貼回所有 Backend 已持久化的結果

### 固定影片互動流程

| 指令第一步 | 彈窗第二步 |
|------|------|
| `/animegen_i2v image:<起始圖片> width:<輸出寬度> height:<輸出高度>` | 動作 Prompt、可選負面 Prompt、`total_seconds`、`source_frames`、`film_target_frames` |
| `/minimax_h3_i2v image:<起始圖片> width:<輸出寬度> height:<輸出高度>` | Prompt、`total_seconds`（整數 1–5） |
| `/wan22_animate reference_image:<角色圖> driver_video:<driver影片>` | 動作 Prompt、可選負面 Prompt、`total_seconds`、`source_frames`、`film_target_frames` |

- Discord Modal 不提供可靠的附件上傳元件，因此圖片／driver 在 slash command 第一步選取；其餘可輸入選項集中在下一步彈窗。
- `/draw`、AnimeGen 與 Wan 提供 Mac/Windows 執行位置；MiniMax H3 固定 Mac Argus MLX，沒有 Worker、ComfyUI、PyTorch 或 FILM fallback，也沒有 Negative Prompt。
- H3 原生幀數公式：`requested=round(seconds*24)`，再向上對齊 `17k+5`；首末幀跨度 `(frames-1)/24`，容器長度 `frames/24`。
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
Discord message IDs；相同 job/實際 channel 預設去重；`force_resend=true` 只可重送完整 completed attempt，不能越過 uncertain hold。

## 測試

```bash
cd discord-bot && python -m pytest -v
```

## 手動 smoke（需先啟動 backend + ComfyUI）

1. 啟 backend：`cd ../backend && uvicorn app.main:app --reload`
2. 啟 bot：`python -m bot.main`，確認 console 印出 commands synced
3. Discord 打 `/draw` → 選 Mac 或 Windows 執行位置 → 下拉出現 preset → 選一個 → （有 profile 則選）→ 填 prompt/寬高/張數 → 送出取得 job id
4. 等數十秒後 `/result id:<job_id>` → 應貼回張數對應的圖

## 已知限制

- Backend queue 為 process memory；restart 不恢復 queued/running H3 job。已完成的 Gallery/GeneratedArtifact 可在 restart 後繼續由 `/result` 查詢。

- preset 超過 25 個需改分頁（目前 12 個）。
- `/result` 以 `job_id` 前 8 碼過濾 gallery，理論上相撞會誤撈（個人自用機率極低）。
- 6–8 張且單張偏大、合計超過 ~24MB 時，改回貼 gallery 連結而非附件。

## 維護 admission 與交付歷史（source contract）

新版本須明示絕對 `DISCORD_DELIVERY_LEDGER_PATH`。設定僅讀 process env，或明示的絕對
`DISCORD_CONFIG_FILE`；process env 優先，不再搜尋 repo/cwd `.env`，不展開 dotenv interpolation。
這是設定遷移，舊啟動方式須由 Environment 在另案核准後調整。

ledger 是 schema v1 的 attempt history，連同 `.checkpoint` 校驗檔及 `.owner` lock 綁定
有效 cwd、state root、非秘密設定、source hash 與 Python/依賴版本。缺失、舊 completed-only
格式、損壞、錯誤 binding 或第二 owner 均保持 closed，沒有自動初始化／遷移／restore。
只有已授權的全新空歷史可離線呼叫
`DeliveryLedger.provision(path, binding=ledger_binding(config))`；此方法拒絕覆寫，不能用來
把既有或未知歷史當空。Production 不呼叫 provision。

所有 slash、select、modal、submit、operator delivery 和 reconnect 先登記 admission。
close 與登記在同一鎖內線性化；已進入者可完成，lock waiters 也在 active counts。
closed callback 不另送拒絕回覆。一般回覆無確認時只保留 hold、不重播。
每次 artifact send 前先 fsync intent，逐 chunk 保存 message receipt（含 batch warning），
全部完成才 final。cancel／crash／I/O 失敗與缺 receipt 會留下 no-resend hold；force_resend
只可重送已完整完成的結果，不能越過 hold。slash/operator 都綁實際 guild/channel，alias
改名不能換掉目的地歷史。成功 response schema 和讀取已完成 Backend 結果的契約維持。

同一 loopback bearer 認證提供 `GET /operator/v1/maintenance/status` 與
`POST /operator/v1/maintenance/close`，close body 為 `{"timeout":0}`（0–30秒）。
status 僅有 schema/version/owner/epoch/state 與分種類 counts，無 token、路徑、job 或目的地。
close 在讀取 body 前先關閉入站，等待 active 後，以與 status 相同的持久歷史檢查產生回覆。
缺失、損壞、不一致、已關閉或無法檢查的 ledger/checkpoint 均保留 `uncertain_closed` 與
ledger hold，不能因 active 為空而回報 clean closure，也不依賴先呼叫 status。
有 active 時回 HTTP 202，無 active 時回 HTTP 200；200 本身不代表沒有 uncertainty。
重複 close/status 不清除 hold、不修復 history；`legacy_process_certified` 仍為 false。
沒有公開控制面或 reopen endpoint。drain timeout 保持 closed，不取消 send 或清除 handles。
ManagedClient shutdown 在 active 清零後才清 HTTP/client/ledger；partial 時 runner 保持存活，
等待下一次明示 stop，沒有自動 retry/reopen。`AI_DRAWING_MAINTENANCE=closed` 啟動不登入
Discord、不 sync，只可提供已設定的本機管理 API。release 需另案授權的新 normal startup。

checkpoint 可偵測 ledger 單檔回滾及不一致 restore；整個 root 和 checkpoint 一起回滾無法由
同一本機狀態自證，須外部可信 checkpoint、cutoff/hold 決策與恢復授權。舊 process 未採用
此能力，不能回此能力的 receipt；remote acceptance 與 legacy uncertainty 均不保證清零。
這些是待獨立 QA 的 source/offline 能力，不是部署、真 Discord exactly-once 或 runtime 驗收。
