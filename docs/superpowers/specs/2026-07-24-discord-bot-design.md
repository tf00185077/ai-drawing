# Discord Bot 直呼本機生圖 — 設計

- 日期：2026-07-24
- 狀態：設計定案，待實作計畫
- 範圍：新增 `discord-bot/`，**不改動 backend**

## 目標

讓使用者在 Discord 用 slash 指令，從既有的 **style preset**（含其 profile 變體）挑一個畫風、輸入
prompt 與寬高與張數，直接呼叫本機 ComfyUI 生圖，**全程不經過 LLM、不花 token**。

Bot 只做兩件事：把 Discord 互動轉成 backend HTTP 呼叫、把結果貼回 Discord。所有生圖決策
（prompt 合併、checkpoint/LoRA/KSampler 參數、workflow 選擇）仍由 backend 既有端點負責。

非目標（本次不做）：prompt library 詞庫、影片、img2img/ControlNet、生圖完成自動通知
（採 pull-by-id）、preset 超過 25 個的分頁/搜尋。

## 架構

```
Discord 使用者
   │  /draw, /result
   ▼
discord-bot (discord.py + httpx)
   │  HTTP（同機 localhost）
   ▼
backend FastAPI  ──►  ComfyUI
```

- 語言/套件：Python + discord.py（符合專案 stack、原生支援 slash / select / modal /
  autocomplete）、httpx（async HTTP）、python-dotenv。
- 部署：與 backend 同機，透過 `BACKEND_BASE_URL`（預設 `http://localhost:8000`）呼叫。
- 存取控制：slash 指令只註冊到指定 `GUILD_ID`（guild command，即時生效又防濫用）。backend
  目前無 auth，靠限定 guild + 同機呼叫作為邊界。

## 模組切分

每個檔案單一職責、可獨立理解與測試。把可測的純邏輯（寬高/張數驗證、payload 組裝、URL 組裝）
抽離 discord glue，因為 Discord UI 端到端無法自動測。

```
discord-bot/
├── bot/
│   ├── config.py        # 讀 .env：DISCORD_TOKEN / GUILD_ID / BACKEND_BASE_URL；缺就 fail-fast
│   ├── api_client.py     # backend HTTP 包裝（唯一知道 backend 契約的地方）
│   ├── validation.py     # 純函式：解析+驗證寬高與張數、組 overrides、組 gallery URL
│   ├── views.py          # PresetSelect、ProfileSelect、DrawModal 三個 UI 元件
│   └── main.py           # bot 啟動、註冊 /draw /result、串接流程
├── tests/
│   ├── test_api_client.py
│   └── test_validation.py
├── .env.example          # 只放占位符（遵守 AGENTS.md 安全規則）
├── requirements.txt      # discord.py, httpx, python-dotenv
└── README.md             # 設定與手動 smoke 步驟
```

### api_client.py 對應的 backend 端點

| 方法 | backend 端點 | 用途 |
|------|-------------|------|
| `list_presets()` | `GET /api/style-presets/` | preset 下拉來源（id / name / chinese_name / profiles[]） |
| `compose(preset_id, profile, content_prompt, overrides)` | `POST /api/style-presets/{preset_id}/compose` | 合併成可生圖的 generation payload |
| `submit_generate(generation)` | `POST /api/generate/` | 排入生圖佇列 → 回 `job_id` |
| `get_job(job_id)` | `GET /api/generate/job/{job_id}` | 查狀態（queued/running/failed/completed） |
| `list_job_images(job_id)` | `GET /api/gallery/?image_name=<job_id[:8]>&limit=8` | 撈回該 job 全部圖（每筆有 `image_url`） |
| `download(image_url)` | `GET {BACKEND_BASE_URL}{image_url}` | 下載圖 bytes（`/gallery` 靜態掛載） |

## 指令與資料流

### `/draw`（方案 B：兩層下拉 + Modal）

```
/draw
 → 回 ephemeral 訊息，帶 PresetSelect（label=chinese_name 或 name，value=id）
 → 使用者選 preset：
      該 preset 有 profiles → 編輯訊息顯示第二層 ProfileSelect
      無 profiles          → 直接 send_modal(DrawModal)
 → 使用者選 profile → send_modal(DrawModal)
 → DrawModal 送出
      → interaction.response.defer()
      → compose(preset_id, profile, content_prompt=prompt,
                overrides={width, height, batch_size=count})
      → submit_generate(generation) → job_id
      → 回覆：「已排入，job id = <job_id>，用 /result id:<job_id> 查詢」
```

關鍵：select callback 本身即一個 interaction，discord.py 允許在其中 `send_modal()`，因此
**兩層下拉後可直接彈 Modal，不需額外按鈕**。`preset_id` 與 `profile` 存在 View 實例上帶進 Modal。

**DrawModal 欄位（Discord modal 上限 5 欄，用 4 欄）**

| 欄位 | 型別 | 規則 |
|------|------|------|
| prompt | 多行文字 | 必填，min_length 1 |
| width | 短文字 | 必填，解析為 int，256–2048 |
| height | 短文字 | 必填，解析為 int，256–2048 |
| count（張數） | 短文字 | 預填「4」可改；留空視為 4，解析為 int，1–8 |

KSampler 相關參數（steps / cfg / sampler / scheduler）由 preset 的 `default_params` 於 compose
時提供，profile 可再覆寫；bot 不收這些。

### `/result id:<job_id>`

```
/result id:<job_id>
 → get_job(job_id)
      queued / running → 回狀態文字
      failed           → 回 error + node_errors 摘要
      completed ↓
 → list_job_images(job_id)            # GET /api/gallery/?image_name=<job_id[:8]>&limit=8
 → 逐筆用 BACKEND_BASE_URL + image_url 下載
 → 一則訊息附上全部（≤8 張；Discord 單則附件上限 10）
```

**為何用 `image_name=<job_id[:8]>`**：batch 每張都存成獨立 `GeneratedImage`（同一 `job_id`），
但 `GET /api/generate/job/{job_id}` 只回 `.first()` 一張。輸出檔名內嵌 `job_id[:8]`
（`backend/app/core/artifacts.py:gallery_output_filename` → `{stem}_{job_id[:8]}_{index}.png`），
gallery 的 `image_name` 子字串過濾可一次撈回全部，**故不需改後端**。

## batch 決策

- compose overrides 帶 `batch_size = count`（使用者輸入，1–8）。一個 `/draw` → 一個 job →
  count 張圖，忽略 preset 自身 batch 預設。

## 錯誤處理

| 情況 | 回覆 |
|------|------|
| backend 連不上 / 5xx | 「後端連不上，請確認 backend 有啟動」 |
| compose 404（preset 不存在）/ 422（profile 不合法） | 轉傳 backend 的 message |
| generate 503（佇列滿） | 「佇列滿了，稍後再試」 |
| 寬高/張數非數字或超界 | Modal 送出後回 ephemeral 錯誤，請重跑 /draw |
| job id 查無 | 「找不到這個 job id」 |
| 6–8 張合計超過 Discord 檔案上限（約 25MB） | 改貼 gallery 連結而非附件 |

## 安全 / 設定

- `DISCORD_TOKEN` 只進被 git ignore 的 `.env`；`.env.example` 僅放占位符。
- slash 指令只註冊到指定 `GUILD_ID`。
- 遵守 AGENTS.md：secret 不進 git、不硬編碼、透過 config 於 runtime 載入。

## 測試

- `test_validation.py`：寬高/張數解析與邊界（純函式）。
- `test_api_client.py`：mock httpx，驗 compose / submit / get_job / list_job_images 的請求組裝、
  gallery URL 組裝與各錯誤碼處理。
- Discord UI 端到端無法自動測 → README 附手動 smoke 步驟（啟 backend + ComfyUI，`/draw`
  跑一輪、`/result` 反查）。

## 已知限制（記錄，非本次做）

- preset 超過 25 個需改分頁/搜尋（目前 12 個，不影響）。
- 以 `job_id[:8]` 前 8 碼過濾，理論上不同 job 前 8 碼相撞會誤撈——個人自用機率極低。
- 不做生圖完成自動通知（採 pull-by-id）。
- 6–8 張且單張偏大時，可能需退回貼連結（見錯誤處理）。
