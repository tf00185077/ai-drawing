# Discord MiniMax H3 I2V：Argus MLX 取代設計

日期：2026-09-01
狀態：使用者已批准方案 A
範圍：只替換 `/minimax_h3_i2v`；`/animegen_i2v` 與 `/wan22_animate` 不變

## 1. 目標

將現有 `/minimax_h3_i2v` 從 ComfyUI/PyTorch MiniMax H3 固定工作流改為本機 `Argus-AiTeam/minimax-h3-mac` PR #4 的 Apple MLX 低記憶體 I2V 路線。Discord 使用者仍以單一指令完成：

1. 上傳一張圖片；
2. 指定輸出寬、高；
3. 輸入 Prompt；
4. 指定 1–5 秒時長；
5. 取得 job ID，完成後沿用 `/result` 下載影片。

不得回退舊 PyTorch/MPS、ComfyUI 或 Windows Worker。

## 2. 使用者介面

保留 slash command 名稱 `/minimax_h3_i2v`。

Slash command 第一階段：

- `image`：PNG/JPEG/WebP，沿用現有 20 MiB 與 MIME／副檔名驗證。
- `width`：256–1024，必須是 32 的倍數。
- `height`：256–1024，必須是 32 的倍數。

額外限制：`width × height <= 786432`。

Modal 第二階段：

- `prompt`：必要，去除首尾空白後不可為空。
- `total_seconds`：整數 1–5，預設 5。

移除 MiniMax H3 UI 中的：

- `execution_target`；
- `negative_prompt`；
- `film_target_frames`。

Bot 回覆 queued job ID、原生 H3 對齊後幀數、實際容器長度，以及 `/result id:<job-id>` 用法。產品文案明確指出此路線固定在 Mac MLX 執行。

## 3. Backend API 契約

保留 `POST /api/generate/video/minimax-h3-i2v` URL，避免不必要的外部命令與文件遷移；其 multipart 契約改為：

- `image`
- `prompt`
- `width`
- `height`
- `total_seconds`

Backend 重做全部驗證，不信任 Bot：

- 圖片 MIME、後綴、檔頭、大小；
- Prompt 非空及長度上限；
- 寬高範圍、32 倍數、總像素上限；
- 秒數為 1–5。

舊欄位不再由 Bot 傳送。未知 multipart 欄位依 FastAPI 行為不構成執行語意；執行器只讀取新契約。

## 4. 執行架構

新增 Backend-owned `ArgusMlxI2VRunner`，負責：

1. 驗證設定中的 runtime、Python、生成腳本、模型目錄及外接碟輸出根存在；
2. 以 Python argv list 啟動程序，不經 shell，不把使用者 Prompt 拼成 shell command；
3. 固定使用已驗證的 PR #4 runtime 與模型棧：
   - official FL2VA；
   - Argus calibrated INT8 transformer；
   - native MLX Turbo LoRA，scale 1.0；
   - quality profile；
   - low-memory；
   - stream-blocks；
   - image anchor first；
   - 9 CLI steps（8 NFE）；
   - memory-pressure-guard；
   - no-block-cache；
   - require-muxed-mp4；
4. Backend 產生隨機 seed 並保存於 artifact metadata；
5. 將來源圖放在既有安全 staging root；輸出／profile／log 放在外接碟工作根的 job-specific 目錄；
6. 捕捉 bounded stdout/stderr 摘要供 job failure 回報；不得將 secrets 或完整環境輸出寫入使用者錯誤；
7. 成功後以 ffprobe/ffmpeg 驗證 MP4 可完整解碼、含 H.264 video 與 AAC audio、尺寸正確、24 FPS、幀數與 H3 對齊規則相符；
8. 驗證通過才移入 Gallery 並建立 `GeneratedArtifact`。

Argus 執行分支不使用 ComfyUI `prompt_id`。artifact 仍以 `source_node_type="SaveVideo"` 持久化，保持現有 `/result` 與 operator delivery 契約。

## 5. Job 與並行生命週期

沿用 public job 狀態：`queued → running → completed|failed`。

在既有 Backend queue 中新增明確 engine discriminator，例如 `execution_engine="argus_mlx_i2v"`；queue worker 看到此值時進入 Argus runner，不走 ComfyUI upload/submit/history 分支。

首版規則：

- Argus MLX 同時最多執行 1 個；
- 其他既有 ComfyUI job 不被重新路由；
- 不回退 local ComfyUI 或 Windows Worker；
- Backend 結束時，正在執行的 child process 需被終止並回收；
- 成功前不建立 completed artifact；
- 失敗或取消清理 staged input 與 partial MP4/profile，保留 bounded log 診斷；
- completed artifact 由既有 DB/Gallery 路徑在 Backend 重啟後仍可查詢。

首版不新增完整 durable running-job DB migration；因此 Backend 重啟期間的 queued/running Argus job 不宣稱可自動恢復。這是既有 in-memory generation queue 的限制，需在產品錯誤與文件中如實呈現。

## 6. 時間與幀數語意

H3 固定 24 FPS，合法原生幀數為 `17k+5`。Backend 以使用者指定秒數計算：

1. `requested_frames = round(total_seconds × 24)`；
2. 向上對齊到合法 `17k+5`；
3. 實際容器時長為 `source_frames / 24`；
4. 首末幀跨度為 `(source_frames - 1) / 24`。

不再執行 FILM。回覆與 metadata 同時保存 requested seconds、native frames、timeline span、container duration，避免把名義秒數與實際 MP4 時長混為一談。

## 7. 設定

Backend Settings 新增可由環境覆寫的 Argus 路徑，預設指向目前已驗證的外接碟安裝：

- runtime root / Python executable；
- generate script；
- FL2VA checkpoint；
- INT8 transformer；
- Turbo LoRA；
- Argus output/work root；
- Hugging Face cache root；
- 最大並行數（首版固定／驗證為 1）；
- subprocess timeout（需高於 5 秒 768×512 的實測 41 分鐘，採明確有限值）。

所有模型、cache、log、profile、partial output 都留在 `/Volumes/AI-Drawing-16T/ai-drawing`；不得默默改用內建 SSD。

## 8. 錯誤處理

- 外接碟未掛載／不可寫：job fail，錯誤明確指出 storage unavailable。
- runtime/model 缺失：job fail，列出缺少的設定項，不自動下載。
- 輸入不合法：API 422，不建立 job。
- subprocess 非零：job fail，保存 exit code 與 bounded sanitized tail。
- timeout：終止 process group，job fail。
- MP4 缺失、不可解碼、codec/尺寸/幀數不符：job fail，不建立 artifact。
- Gallery/DB recording 失敗：job fail，不把 raw output冒充 completed。

## 9. 測試策略

嚴格 RED → GREEN：

### Discord Bot

- `/minimax_h3_i2v` 保留、AnimeGen/Wan 不變；
- 不再提供 execution target；
- 寬高／像素上限驗證；
- Modal 只含 Prompt 與 1–5 秒；
- API client multipart 只送新契約；
- queued 回覆含 job ID 與原生時序摘要；
- `/result` 仍可交付 `SaveVideo` MP4。

### Backend

- API 接受新 multipart，拒絕非法圖片、解析度、像素、Prompt、秒數；
- Argus argv 精確、無 shell；
- seed 由 Backend 產生並記錄；
- queue engine 分支不碰 ComfyUI client；
- 同時最多一個 Argus runner；
- subprocess success + valid fake MP4 才建立 Gallery artifact；
- nonzero/timeout/missing/invalid MP4 不建立 artifact並清理；
- job status 與 `/result` artifact contract 維持相容。

### 真實驗收

在自動測試全綠且 live queue idle 後，執行一次 64×64、1 秒的真實 Argus MLX smoke（預估約 11 分鐘），驗證 API job 由 queued 到 completed、Gallery artifact、完整解碼、H.264/AAC、尺寸、幀數與 `/result` 可取得。這是 runtime integration smoke，不作視覺品質 PASS。

## 10. 部署

受影響服務只有 Backend 與 Discord Bot；ComfyUI 不變、不重啟。

部署前：

- 再次檢查 Git dirty set，避免混入並行修改；
- 確認 Backend generation/LoRA queue 與 Argus runner idle；
- 跑 focused tests、Discord Bot全套、Backend受影響測試、compileall、`git diff --check`。

部署後：

- Backend `/health` 200；
- generation queue 可讀；
- Bot process存活並建立 Discord TLS；
- guild command sync成功且仍包含 `/minimax_h3_i2v`；
- 新 command schema 不再顯示 execution target；
- ComfyUI queue/health維持原狀。

本地部署可來自未提交 working tree，但必須明確回報；不自動 commit、push、PR 或發布。

## 11. 非目標

- 不刪除 `/animegen_i2v` 或 `/wan22_animate`；
- 不整合尚未成熟的 ComfyUI MLX wrapper；
- 不支援 Windows Worker；
- 不新增 T2V；
- 不新增 Negative Prompt 或 FILM；
- 不自動下載模型；
- 不承諾 Backend 重啟後恢復 running Argus job；
- 不以影格逐張不同取代實際動作品質判定。
