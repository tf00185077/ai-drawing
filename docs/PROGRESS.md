# 進度追蹤

## 2026-07-24 Discord Bot 直呼本機生圖

新增 `discord-bot/`（discord.py），使用者用 `/draw` 從既有 style preset（含 profile 變體）選畫風、
填 prompt/寬/高/張數（1–8）後直接呼叫 backend 生圖，全程不經 LLM；`/result id:<job_id>` 反查並貼回圖。
Bot 只做互動↔HTTP 轉譯，生圖決策（prompt 合併、KSampler 參數、workflow）仍由 backend 端點負責，
**未改動 backend**。batch 經 compose `overrides.batch_size` 帶入；`/result` 以
`GET /api/gallery/?image_name=<job_id[:8]>` 撈回同 job 全部圖。指令只註冊到指定 GUILD_ID。
設計與計畫見 `docs/superpowers/{specs,plans}/2026-07-24-discord-bot*.md`。驗證：`discord-bot` pytest 全綠。

## 2026-07-24 Discord Bot 組裝與 slash 指令（Task 6 完成）

discord-bot `bot/main.py` 與 `tests/test_main.py` 實作完成：

1. `build_bot(config: Config) -> tuple[discord.Client, discord.app_commands.CommandTree, ApiClient]`：
   - 註冊 `/draw`（列 preset、選擇後顯示 PresetView）、`/result id:<job_id>`（查詢生圖結果）到 `config.guild_id`
   - 網路隔離：建構不需 token 或網路連線，測試直接驗證命令註冊
2. `/draw` 命令：list_presets → BackendError/例外/空清單/成功四種路徑，錯誤回訊皆為繁體中文 ephemeral message
3. `/result` 命令：defer(thinking) → collect_job_result；BackendError 404 → "找不到"；其他 BackendError/例外 → ❌ 訊息；狀態 queued/running → ⏳；failed → ❌ 錯誤詳情；completed → 若總檔案 > 24 MB 貼連結、否則貼 discord.File 附件；空圖檔 → "完成但找不到"
4. TDD 完成：test_main.py 失敗 → 實作 → 全通過；36/36 全套 pass、import smoke 通過
5. 常數 `DISCORD_UPLOAD_LIMIT_BYTES = 24 * 1024 * 1024`、entry `main()` 完成

驗證：
- Step 2 RED（ModuleNotFoundError）→ Step 4 GREEN（test PASSED）
- 全套測試 36 passed，import smoke 通過
- 提交：1fdddbd `feat(discord-bot): bot entrypoint with /draw and /result`

## 2026-07-24 Prompt Library 雙語軟性偵測 + Entry 增刪改查

背景：詞庫改由 agent 經 MCP 寫入後，agent 不知道使用者需要「有意義的中文對照」，可能把 name_zh
照抄英文或機械拼接。經討論確認不適合用 i18n（i18n 是「切換語言」，需求是「中英同時對照」；另立 i18n
store 會與詞條 JSON 形成雙重來源）。改以「MCP 軟性提醒 + 操作台兜底編輯」解決。

1. MCP `prompt_library_save` 加契約 docstring 並在成功後附 `warnings`（name_zh 無 CJK，或 entry 的
   name_zh 照抄英文 prompt），永不擋、`ok` 恆 True，符合「寬進嚴出、錯誤是修復指南」。
2. 前端新增共用啟發式 `suspectChinese.ts`（與 Python 版行為對齊：先 echoes 後 missing），操作台詞條區
   對可疑 name_zh 標 ⚠️。
3. 操作台補齊 entry 增刪改查：新增 `PromptEntryEditor`，`PromptEntryBrowser` 加編輯／封存／新增，
   `PromptWorkbench` 串接 `PUT .../entries/{id}` 與 `POST /archive`。entry 樂觀鎖以「分類 revision + etag」
   為單位（後端契約），寫入後重載分類刷新 token。刪＝封存（可復原），未做實體刪檔。
4. 實作期修正一個設計缺陷：編輯詞條原本只帶回 name_zh，會把 description_zh／aliases／keywords／order
   清空（且後端 `description_zh` min_length=1 會 422）。已把 `BrowserEntry` 擴充為攜帶完整詞條資料
   （分類 GET 本就回傳），編輯表單改以真實值預填，只改 name_zh 也不會動到其他欄位；並加了保存驗證測試。
5. backend 端點與 schema 未動；未引入 i18n。
6. 驗證：MCP `pytest` 新增 4 條（全套 81 passed）；前端 vitest 新增啟發式／編輯器／Browser CRUD／
   Workbench 串接測試，`tsc --noEmit` 與 Vite build 通過。註：`PromptComposerPanel.test.tsx` 有一個
   與本次無關、base 分支即存在的失敗（grid 5 vs 6），未在本次範圍處理。

## 2026-07-23 MCP spec/catalog 對齊（OpenSpec: reconcile-mcp-spec-catalog）

- 盤點：code 內 34 個 `@mcp.tool`（含 `mcp_ping`）與 `tool_catalog.py` **完全雙向對齊**（34=34，無幽靈/遺漏）；Change 1 已使 dataset_list/inspect/smoke_test 落地。
- `lora-training-mcp-tools` spec 移除 6 個 code 從未實作的漂移工具需求：`lora_dataset_prepare`、`lora_dataset_validate`、`lora_dataset_caption_assess`、metadata（get/validate/update）、`lora_dataset_agent_inspect`（已併入 `lora_dataset_inspect`）、curation；每項附 Reason + Migration（改走 backend HTTP 端點）。
- `mcp-tool-catalog` spec 需求改為 catalog 與實際註冊集「雙向對齊（無幽靈工具）」。
- 修掉 `mcp-tool-catalog` 與 `lora-training-mcp-tools` 的 `TBD` Purpose 佔位為正式描述。
- 其餘 MCP-referencing specs（video/style/custom-workflow/workflow-template）掃描後無真正工具漂移（`lora_strength`/`lora_name`/`gallery_dir` 等為欄位/設定名，非工具）。
- 驗證：`openspec validate --specs` 12 passed；mcp-server catalog 稽核測試通過。

## 2026-07-22 Anima LoRA 訓練支援（OpenSpec: add-anima-lora-training-support）

- 統一模型檔解析器 `_resolve_model_file`：接受絕對路徑／純檔名／HuggingFace id 三種形態。純檔名依 model_family 跨目錄搜尋——checkpoint 用 `LORA_CHECKPOINT_DIRS`＋（Anima）`COMFYUI_DIFFUSION_MODELS_DIR` 或（SD/SDXL）`COMFYUI_CHECKPOINTS_DIR`，qwen3/t5 用 `COMFYUI_TEXT_ENCODERS_DIR`、vae 用 `COMFYUI_VAE_DIR`，複用既有生成端設定，不新增平行 config。SDXL 純檔名解析行為維持不變（`LORA_CHECKPOINT_DIRS` 仍為第一順位）。
- Checkpoint 存在性 preflight：本機路徑／純檔名在建立 durable job 前驗證存在，失敗回 `checkpoint_not_found` 並附 `searched_dirs`；遠端/HF 參照豁免；`allow_unverified_checkpoint` 可繞過。qwen3/vae/t5 亦改走解析器，純檔名不再相對 CWD 失敗。
- Smoke test 改為 model-family-aware：Anima job 依 job params 組 `{template:"anima", diffusion_model, text_encoder, vae, lora}`（可 per-request 覆寫），其他家族維持 checkpoint-only。已比對 `backend/workflows/anima.json` 確認訓練 `qwen3` 即生成 `text_encoder`（CLIPLoader.clip_name）。
- 重建漂移的 MCP 工具：`lora_dataset_list`（GET /datasets）、`lora_dataset_inspect`（GET /datasets/{folder}/agent-inspect）、`lora_train_smoke_test`（POST /jobs/{id}/smoke-test，含 Anima 元件覆寫），並登錄 `tool_catalog.py` 與 README／mcp-setup catalog 表。
- 驗證：backend `test_lora_trainer.py`/`test_lora_train_workflow_api.py` 與 mcp-server 全套（81）通過；backend 全套 1026 passed（1 個 civitai import-alias 測試為既有 test-isolation flake，單獨執行通過，與本次無關）。
- 後續：`reconcile-mcp-spec-catalog`（依賴本 change）處理全專案 MCP spec/catalog 對齊與其餘漂移工具（prepare/validate/curation/metadata）去留。
## 2026-07-21 Prompt Library Git persistence

- Docker Compose now bind-mounts the repository `prompt_library/` at `/workspace/prompt_library`; `/data/prompt_library` is no longer the default library.
- Launcher-generated configuration uses `PROMPT_LIBRARY_DIR=/workspace/prompt_library` so reconfiguration preserves the same deployment contract.
- Prompt Workbench saves combinations directly to `prompt_library/combinations/<id>.json`, where Git can track, commit, and push them.
- Existing `data/prompt_library/` files are retained without automatic deletion or migration, but the default Docker configuration no longer uses them.

## 2026-07-21 Prompt Workbench UI 重構完成

後續微調：可選 Prompt 詞條改為橫向 `flex-wrap`、依內容寬度排列並限制最大寬度，長文字在 option 內換行，不再每筆佔滿整列。

後續微調：Positive／Negative 已選片段各自改為每頁 5 筆、3 欄 × 最多 2 列的獨立分頁 grid；修正最終文字跨片段手動修改只更新顯示字串的狀態缺陷，現在會同步成工作台片段，後續加入新 Prompt 不會再覆蓋手改內容。

雙向綁定修正：最終文字現在依括號外逗號解析成獨立 Prompt options，逐項同步文字與 `(prompt:weight)` 權重；修改多個片段不再把全部內容折成單一 Prompt。

組合儲存修正：Workbench 會使用 catalog 內既有 combination 的 revision/etag，而非一律送 `expected_revision: 0`；儲存成功後同步更新 concurrency token，支援同頁連續修改與儲存。

1. Prompt Library 拆成 `/prompt-library/workbench` 與 `/prompt-library/categories` 兩個獨立畫面，並加入頁內 sidebar；`/prompt-library` 會自動導向工作台。
2. Workbench 上層改為左側詞條加入區、右側正負向總覽；加入區以正向／負向 nav 控制篩選與加入目的地，右側 Positive／Negative Prompt 永遠上下同時顯示。
3. 選取詞條或自由文字後立即組合，不再需要額外按「組合」。片段可編輯、刪除、排序與設定可選權重；空權重輸出原文，有權重才輸出 ComfyUI `(prompt:weight)` 格式。
4. 最終整段 Prompt 可直接編輯，透過字元範圍做 best-effort 雙向同步；工作台修改只影響前端副本，不回寫 Prompt Library JSON。儲存已修改的來源詞條時會轉成 literal，避免後端重新套回原始詞條。
5. Workflow 生圖移到下方獨立區塊，送出時直接讀取畫面當下的 positive／negative 文字，不再依賴舊 compose result。
6. 驗證：frontend focused `15 passed`、完整 suite `26 passed`、`npx tsc --noEmit` 通過、Vite production build 通過。

## 2026-07-20 跨平台 Docker 一鍵啟動

完成 Windows `setup.ps1` 與 macOS/Linux `setup.sh`，一般使用者 clone 後不需理解 Python、Node 或容器內部即可設定並啟動 Frontend/Backend。啟動器會檢查 Docker/Compose/ports、原子產生 `.env` 與本機 Compose override、保存程序 ownership，並提供 `setup`、`start`、`stop`、`status`、`reconfigure`、`logs`、`update-comfyui` 與唯讀 `dry-run`。

2026-07-21 Windows 首次實機 smoke 發現 Compose build 期間沒有前景回饋，且 Docker 的 UTF-8 進度字元會被系統 CP950 解碼成 background reader exception。launcher 現在會在 Compose build 前提示首次執行可能需要數分鐘，完成後提示正在等待 health check；所有 subprocess capture 固定使用 UTF-8 並以 replacement 處理無法解碼的 byte。針對解碼與進度順序的 2 個離線回歸測試通過，未重新建置容器或執行 ComfyUI 安裝。

ComfyUI 維持選用：可拒絕、連接 external、使用既有 managed 目錄，或安裝固定版 ComfyUI。launcher 預設自動偵測 Windows/Linux NVIDIA、Apple Silicon MPS 或 CPU，顯示結果並允許 `--device` 明確覆寫；只涵蓋 ComfyUI 與必要 Python 套件，明確不下載模型或 custom nodes。程序停止前會比對 PID 與完整身分；Linux loopback relay 有獨立 lock/state/identity。Backend `/api/system/status` 與 Frontend Dashboard 呈現 connected、not_configured、unreachable、no_models、degraded 五種狀態；CLI `status` 則只依主機 probe 回報 not_configured、unreachable、no_models 或 connected，不宣稱 degraded。其中 `no_models` 顯示「ComfyUI 已連線，尚無模型」。MCP 不屬於這次啟動範圍。

後續 review 強化三個 bootstrap 邊界：POSIX wrapper 在 cold cache 先檢查 `curl`，再安全 fallback 到 `wget`，兩者皆無時回穩定錯誤；Apple Silicon 的 x86_64 程序以 structured `sysctl -in sysctl.proc_translated` 辨識 Rosetta，回報 `1` 時以 `UNSUPPORTED_NATIVE_ARCHITECTURE` 中止，不會默默改 CPU 或安裝 x86 runtime；managed ComfyUI 的具體 install boundary 會 canonicalize 目標與 repository root，拒絕 repository 本身、子目錄及經 symlink parent 指回 repository 的未存在路徑，且在 clone/staging 前完成。文件 clone URL 已改為可直接複製的 public HTTPS。`dry-run` 不安裝 ComfyUI、不寫專案設定、不改變服務，但 cold-cache wrapper 仍可能先把固定版 uv/Python bootstrap 到使用者 cache。

最終安全複查再強化 ownership/transaction 邊界：ComfyUI 安裝使用 stdlib 隨機建立的唯一 sibling staging，既有固定或相似 staging 目錄不會被改動。`update-comfyui` 明確要求 `stop → update-comfyui → start`；live verified PID 以 `COMFYUI_UPDATE_REQUIRES_STOP` 拒絕，stale/mismatch ownership 也在 uv、Git 與檔案變更前保守拒絕。停止後，固定版 source 與 launcher-managed `.venv` 以唯一 backup/new-env 更新；rollback 必須完成舊 commit、exact 舊 `.venv` 與 restored runtime smoke，否則保留 recovery material 並回報 rollback failure。

後續安全 review 將 cleanup 收斂為全平台 fail-closed：程式不再對 owned temp 使用 pathname-based delete，連空目錄也不呼叫 `rmdir`；只在 `lstat` 可證明 path 不存在時回報 cleaned，任何 existing/broken/permission-unknown staging/backup/new-env 都保留並回報精確 pending path。更新前有 exact Git top-level 與 `.git` 驗證；即使 state 沒有 PID，也會先 probe ComfyUI API。啟用新 `.venv` 後不再嘗試 pathname-based 自動搬移 rollback，避免 check/replace window 誤搬 concurrent unknown path。

`setup`、`start`、`stop`、`reconfigure`、`update-comfyui` 現在從 state load 前就共用 relay OS lock 所在的同一個 bounded project lifecycle lock，跨程序競爭會在任何 mutation 前以 stable timeout code 結束。核心 update 與 provenance save outcome 也已分離：filesystem 成功但 state 保存失敗會以 `COMFYUI_UPDATE_SUCCEEDED_STATE_SAVE_FAILED` 回報版本及所有 pending recovery paths；CPU recovery install 同樣保留 `COMFYUI_INSTALL_CLEANUP_PENDING` 的 code/path。

第三輪 review 將 lifecycle acquire、body、release 三階段明確分離。body 已拋 typed error 時，後續 unlock error 會被視為次要錯誤，原 code/hint/recovery path 保持不變；body 成功才發生 unlock failure 時，使用 `LAUNCHER_LIFECYCLE_UNLOCK_FAILED_AFTER_MUTATION` 誠實指出核心操作可能已完成，要求先 `status`／檢查 state，禁止直接重跑。terminal complete/error audit 已移到 lock release 前，audit failure 仍不影響主流程。

全分枝 review 再修正三個啟動邊界：POSIX wrapper 對齊 uv installer 的 direct-root layout（`UV_UNMANAGED_INSTALL/uv`），並以離線 fake-installer 契約測試；Backend filesystem model inventory 為零時 bounded 查詢 `/object_info` 的 checkpoint/UNET enum，external 有 live models 即回 connected，查詢失敗不影響 status API；ComfyUI/relay spawn 後若 initial identity unavailable，改以 exact `Popen` handle 執行 bounded terminate→wait→kill 並驗證退出，reason 區分 terminated/killed/failed，cleanup failure 的 stable CLI error/hint 包含 spawned PID且不會操作其他未驗證 PID。

持久化使用 `data/database`、`data/prompt_library`、`data/gallery`、`data/outputs`、`data/lora_train`、`data/logs` 的明確 bind mounts。設定先以 `docker compose config` 驗證才整組替換，Compose/readiness/update 失敗有 rollback；secret 只保留在被 Git 忽略的 `.env`，log 與診斷會遮罩。

### 本次實際自動驗證

- Launcher（所有安裝／更新／程序／HTTP/Docker 邊界皆為 fake runner、static Compose runner 或暫存目錄）：`344 passed, 2 skipped`；skips 是 Windows directory-symlink 權限案例與僅在 POSIX 執行的離線 fake uv-installer 動態測試，另有 Windows static direct-root wrapper 契約。故障注入另涵蓋 exact-Popen terminate success、timeout→kill、cleanup failure/no-state、spawned PID stable CLI errors，以及既有 lifecycle/update safety cases。`python -m compileall -q scripts` 與 Git Bash `bash -n setup.sh` 通過。依使用者要求，本輪沒有執行真實網路、uv/ComfyUI/PyTorch/模型/custom-node 安裝下載、Git fetch/checkout、Docker build/up/pull。
- Backend 全套：`1013 passed, 4 skipped, 76 warnings`；新增 external live `/object_info` inventory service/API、dedupe/count 與 failure fallback 覆蓋。
- Frontend：`16 passed`；TypeScript `npx tsc --noEmit` 與 Vite production build 通過。
- Docker Compose CLI `v5.1.1`：沒有 `.env` 的 base config 與暫存 connected generated `.env`/override 都通過 `config --quiet`。
- disabled/no_models/Compose contract mocks：`11 passed`；Backend status、entrypoint 與暫存 persistence contracts：`40 passed`。
- Windows 本機唯讀 `dry-run --non-interactive --comfyui-mode disabled` 與 `status` 通過；沒有寫設定、安裝或啟停服務。
- `npm ci` 依 lockfile 成功；audit 回報既有 `12 vulnerabilities`（1 low、6 moderate、4 high、1 critical），本任務未升級依賴。

Docker daemon 的 Windows engine pipe 不存在，因此沒有啟動 Docker Desktop，也沒有建置 image、啟動 container 或把 mock persistence 當成 runtime persistence pass。依使用者要求，本次完全沒有執行真實 ComfyUI、PyTorch、模型或 custom-node 安裝／下載／啟動測試。

### 真實平台 smoke matrix

| 流程 | 結果 | 原因 |
|------|------|------|
| Windows NVIDIA：setup/start/status/stop | **NOT RUN** | 目前 Docker daemon 不可用，且未執行真實 ComfyUI 安裝。 |
| Linux NVIDIA：setup/start/status/stop | **NOT RUN** | 沒有 Linux/NVIDIA 主機。 |
| Linux CPU：setup/start/status/stop | **NOT RUN** | 沒有 Linux 主機。 |
| Intel macOS CPU：setup/start/status/stop | **NOT RUN** | 沒有 Intel macOS 主機。 |
| Apple Silicon MPS：setup/start/status/stop | **NOT RUN** | 沒有 Apple Silicon 主機。 |
| 拒絕 ComfyUI 後的完整 Compose 啟停 | **NOT RUN** | 只執行 Windows 唯讀 dry-run/status；Docker daemon 不可用。 |
| Docker image/container/recreate persistence | **NOT RUN** | 未啟動 Docker daemon；暫存 contract tests 不算實機 pass。 |

> **唯一來源**。完成的任務要同步修改這個文件（`docs/PROGRESS.md`），且不需同步改 README.md 或 AGENTS.md。
> 寫進度時以「人看得懂」為準：一項工作一段，講清楚做了什麼、為什麼、下一步；不要貼雜湊值稽核日誌。
> （2026-07-14 以前的稽核式進度原文保存在 `docs/archive/2026-07-legacy/PROGRESS-2026-07-14-audit-log.md`。）

---

## 2026-07-17 Prompt Workbench、Workflow 生圖與 MCP 對齊完成

Prompt Library 剩餘的兩條使用路徑已接通，前端操作與 agent 呼叫共用同一套後端資料：

1. `/prompt-library` 加入 Prompt Workbench，可瀏覽／搜尋詞條、建立詞條、加入正負片段、調整權重、加入自由文字、即時 compose 並儲存組合。
2. 新增 workflow generation-form descriptor；工作台只列出適合純文字生圖的 workflow，並可保留 workflow 的 steps、CFG、seed 等預設值或要求隨機 seed 後直接排入生圖佇列。
3. MCP 新增 `prompt_library_search`、`prompt_library_save`、`prompt_library_compose`、`prompt_library_archive`；`generate_image` 與 `list_available_resources` 同步支援 workflow defaults、seed mode 與 generation forms。
4. 驗證：Backend 全套 `965 passed, 4 skipped`、MCP `77 passed`、Frontend `5 passed`，Vite production build 通過。

## 2026-07-17 Prompt Library 前端新增分類介面

使用者已可從主導覽進入`/prompt-library`自行建立正向或負向Prompt分類：

1. 頁面即時讀取並分列現有正／負分類，顯示名稱、ID、說明與詞條數，方便建立前避免ID重複。
2. 新增分類表單支援slug ID、中文名稱、說明、別名、搜尋關鍵字與排序；送出時呼叫既有`PUT /api/prompt-library/categories/{polarity}/{category_id}`，建立成功後刷新清單。
3. 前端先驗證slug與排序，Backend的revision／etag衝突會保留`message + hint`顯示給使用者；未繞過既有optimistic concurrency契約。
4. 驗證：Frontend `5 passed`、Vite production build通過；瀏覽器實機建立臨時分類後清單由14增至15，封存臨時資料後回到14。

## 2026-07-17 Prompt Library service 完成

Prompt Library 後端服務階段已完成，可由後續 React 工作台與 MCP tools 共用同一份 provider／API 合約：

1. 完成 project-scoped JSON schema 與安全 file provider：原始 bytes SHA-256 etag、FileLock、原子替換、路徑 confinement、cache-aware stable snapshot 與壞檔 diagnostics 隔離。
2. 完成正負 prompt 組合與中英文 weighted fuzzy search；寫入採 revision + etag optimistic concurrency，entry 修正會 eager 更新所有 active combination 快照，部分更新中斷時由 combination read lazy repair。
3. 新增 `/api/prompt-library` 十個 FastAPI 操作，涵蓋 catalog、category／entry／combination CRUD、archive、search 與 compose optional save；錯誤維持 `code + message + hint + details`。
4. 新增 393 條中英雙語 starter catalog（14 個 positive、8 個 negative 分類）與三個精確保留舊字串的 legacy combinations；舊 `/api/prompt-templates` 已改由 `legacy_template=true` combinations 提供，不再有硬編碼第二來源。
5. 驗證：Prompt Library 全套 `89 passed, 1 skipped`；Backend regression `964 passed, 4 skipped`（Windows 無 symlink 權限的安全案例依環境 skip）；`docker compose config` 確認 `PROMPT_LIBRARY_DIR=/app/prompt_library` 且 bind mount target 為 `/app/prompt_library`。
6. 回歸過程順手修正四個既有跨平台測試問題：錯用 `MagicMock.not_called`、兩處 Windows 路徑 separator assertion，以及三個無 symlink 權限時應 skip 的安全測試 setup；未修改相關 production behavior。

尚未完成的是完整React Prompt Workbench其餘功能（分類內詞條編輯、Prompt選取／組合與workflow-default生圖整合），以及MCP Prompt Library parity。

## 2026-07-17 Prompt Library 後端核心 checkpoint

已完成第一個可獨立合併的後端核心收斂點：

1. 新增 project-scoped、folder-backed Prompt Library 的嚴格 JSON models、API DTO、設定、Docker mount 與結構化錯誤契約。
2. 新增安全檔案 provider：raw-byte SHA-256 etag、原子替換、FileLock、cache-aware stable snapshot、壞檔 diagnostics 隔離，以及 symlink／junction path confinement。
3. 新增唯一的 backend prompt composer：正負 prompt 對稱、多選排序、權重、literal、重複 ref、missing／archived snapshot fallback、saved combination 匯入與 lazy in-memory repair。
4. 新增中英文 weighted fuzzy search：NFKC、alias／keyword／description／prompt、resource type／polarity／category／archived filters、穩定排序與 bounded limit。

此 checkpoint 尚未完成寫入協調器與 eager combination propagation、FastAPI routes、初始約 393 條 seed、legacy adapter、React 工作台、workflow-default 生圖整合及 MCP parity；後續由既有三份 implementation plan 繼續。

## 目前聚焦

**2026-07-15 大重構：從「法務級精確重現系統」轉向「口述生圖的傻瓜模式」（程式完成，待實機驗證）**

背景：先前的 Civitai 整合把最高等級的嚴謹放在生圖路徑上（fail-closed、不准重試、一次一張、
每次呼叫重算 6.9 GB SHA），導致 agent 為了生一張圖跑了 11 個回合、多數以 blocked 告終。
本次依「嚴謹放在紀錄層，寬容放在呼叫層」原則全面調整：

1. **SHA-256 快取**（`backend/app/services/file_digest_cache.py`）：算一次後以
   (size, mtime_ns, inode) 比對，不變即信任快取，消除每次 resolve 重讀大檔造成的 ReadTimeout。
   舊 strict resolver 與 safe_download 均已接上。
2. **資源自動下載**（`backend/app/services/civitai_resource_acquire.py`、
   `POST /api/civitai/resources/acquire`）：給模型頁連結/模型 ID/版本 ID 一次到位——inspect、
   選檔、背景下載到外接硬碟（`/Volumes/AI-Drawing-16T/ai-drawing/models/…`）、SHA 驗證、寫入
   `downloaded_resources` 帳本。病毒掃描不過、SHA 不符仍硬性阻擋；license 欄位缺漏改為
   「照常下載＋標記 license_verified=false 警告」。部分模型下載需要 Civitai API key：
   在 `.env` 設 `CIVITAI_AUTHORIZATION=<key>`（`.env.example` 已加占位）。
3. **generate-like 一條龍**（`backend/app/services/civitai_easy.py`、
   `POST /api/civitai/generate-like`、`GET /api/civitai/source-info`）：給 Civitai 圖片連結＋
   新 prompt → 自動取回原圖參數（sampler/steps/cfg/尺寸/負向詞照抄，A1111 sampler 名稱自動
   轉 ComfyUI，見 `civitai_sampling.split_sampler_scheduler`）、分層資源比對（精確同檔 →
   檔名比對 → 可自動下載 → 本地預設模型代替，每層都在回傳中註明）、缺模型預設先自動下載
   （回 `acquiring_resources`，agent 輪詢 installed 後重呼叫；`download_missing=false` 則立即
   用替代模型生）、預設一次抽 4 張。走既有一般生圖佇列，完成後 job 狀態直接回 gallery
   image_id/path，可用 `gallery_rerun` 迭代。
4. **MCP 工具 75 → 27**（`mcp-server/mcp_server/tool_catalog.py`）：Civitai 低階工具鏈
   （inspect/select/install、import/resolve/build/run、variant/variation-set、source-alias
   全家桶共 37 個）、workflow catalog 維護、ComfyUI node 查詢、LoRA dataset 工具組、
   style preset 維護（create/reindex/validate）移出 MCP。Civitai 流程只剩四個意圖級工具：
   `civitai_source_info`、`civitai_generate_like`、`civitai_resource_acquire`、
   `civitai_resource_status`。經確認為實際使用中而保留／恢復的：custom workflow 兩個
   （img2img/ControlNet/inpaint 與影片）、`free_comfyui_memory`、style preset 日常路徑
   （create/list/get/compose；reindex/validate 留在 backend）。舊 strict 管線的 backend HTTP 路由（`/api/civitai-recipes/*`）
   保留未動，需要精確重現稽核時仍可用。MCP client 預設 timeout 30→60 秒，Civitai import
   路徑 300 秒。
5. **測試**：刪除 R1–R11 稽核證據型測試與 fixtures、已移除工具的 MCP 測試；新增 digest
   cache / sampler 對照 / 分層規劃 / generate-like / acquire 的離線測試
   （`backend/tests/test_civitai_easy.py`、`mcp-server/tests/test_civitai_tools.py`）。
   回歸：Backend `875 passed`、MCP `77 passed`、pipeline `46 passed`。
6. **文件**：本檔重寫；根目錄雜物與過時 spec 移入 `docs/archive/2026-07-legacy/`；
   `docs/` 只留 GOAL、PROGRESS、mcp-setup、setup-guide、LoRA runbook。
7. **Hermes skills 同步**（`~/.hermes/skills/`，repo 外）：主 skill `creative/ai-drawing` 重寫為 v3.0
   （意圖→工具對照＋prompt 判斷＋紅線，199→~80 行；舊版與稽核時代 references 歸檔至
   `skill-archive/ai-drawing-v2.1-strict-20260715` 與 `references/archive-strict-era/`）；
   discord-menu v2.1（保留輕量 preset 選單＋新增 Civitai 連結入口）；ai-video-generation、
   comfyui、image-generation-prompting 的過時工具引用逐一修正或加註 superseded banner。

**2026-07-15 補強：下載資源按模型家族明確分類（Anima 拆件自動分流）**

需求：checkpoint 依家族（Illustrious／SDXL／Anima）明確辨識，下載路徑維持外接硬碟、
使用者不填任何路徑。實作（backend `880 passed`、MCP `77 passed`）：

1. **家族辨識加入 Anima**：`normalize_model_family`（civitai_resource_acquire）與帳本
   `_audited_model_family`（civitai_local_identity_ledger）都認得 `anima`；家族依 Civitai
   `baseModel` 標籤判定並記錄在資源 notes 的 `model_family`。
2. **Anima 拆件包自動分流**：Civitai 把 Anima 的 diffusion／`_txt` text encoder／VAE
   統一標成 checkpoint。`civitai_resource_acquire` 遇到「checkpoint＋家族 anima」時改抓
   該版本全部檔案，依檔名慣例（`_txt`→text_encoders、`vae`→vae、其餘→diffusion_models）
   各自分流到 `.env` 的 `COMFYUI_*_DIR`（全在外接硬碟），一次呼叫裝齊整組；回傳新增
   `resources` 陣列（每檔一筆帳本紀錄）。單檔資源行為不變。
3. **generate-like 同家族替代**：原圖 checkpoint 本地沒有需要替代時，先從 AIR urn 的
   生態系段解析原圖家族，優先挑帳本中同家族的本地 checkpoint，沒有才退回預設模型；
   替代訊息會註明是同家族替代。
4. **Skill 同步**：Hermes `creative/ai-drawing`（英＋zh-TW 鏡像）更新下載與 Anima 拆件
   說明——工具已自動抓齊分流，skill 保留的是拆件 workflow 接線與
   `clip input is invalid: None` 診斷知識。

**2026-07-15 修正：站上生成圖的 checkpoint/LoRA 抓不到（civitaiResources 解析）**

問題：Civitai 站上生成器產的圖（現在佔新圖絕大多數）在 `/api/v1/images` 的
`meta.resources` 是空陣列，真正的資源清單放在 `meta.civitaiResources`
（只有 `type`＋`modelVersionId`＋`weight`，沒有名稱與 hash）。acquisition 只解析
`meta.resources`，導致網頁明明顯示 checkpoint／LoRA，agent 卻判定「來源沒有標註
checkpoint」而改用本地預設模型。修正（`backend/app/services/civitai_acquisition.py`）：

1. **解析 `civitaiResources`**：`_resources_from_api_meta` 新增第二段解析，以
   `modelVersionId` 對既有 `resources` 去重；LoRA `weight` 超出 schema 範圍（0–2，
   實際看過 5.9 的 slider LoRA）時略過強度、保留身分，不會讓整份 recipe 掛掉。
2. **名稱/hash 補齊**：新增 `_enrich_civitai_resource_identities`，對缺名稱的項目
   逐一呼叫 `/api/v1/model-versions/{id}` 補回檔名、完整 SHA256、modelId、fileId；
   已刪除/受限的版本（404）容忍失敗，以合成名 `civitai-version-<id>` 保留身分——
   帳本比對與自動下載走 version ID，不受影響。
3. **驗證**：新增 4 個離線測試（識別解析／404 容錯／去重／超界 weight）；
   backend `879 passed`、MCP `77 passed`；並以真實 API 實測 image 136790238，
   checkpoint（WAI-illustrious v17）＋2 個 LoRA 全數帶檔名與 SHA256 解出。

**2026-07-16 修正：generate-like 規劃層不認得 Anima 拆件包（誤判缺模型改用 Illustrious）**

問題：image 135643885 的 source-info 已能解析出 `anima_baseV10.safetensors`，本地也已裝好
整組拆件（diffusion／`_txt`／VAE），但 `plan_generation` 只拿 `list_checkpoints()`
（checkpoints 目錄）比對，Anima 主權重實際在 `diffusion_models` 目錄且帳本 kind 是
`diffusion_model`，於是被判「缺少、需下載」並改用 Illustrious-XL 替代；generate-like
還會對已安裝的資源回 `acquiring_resources` 空等。修正（`backend/app/services/civitai_easy.py`）：

1. **拆件視角二次比對**：checkpoint 資源用 checkpoint 視角比不到時，改以
   `diffusion_model` 視角再比一次（帳本身分優先、檔名次之）；比到即視為本地已有，
   並解析同版本的 text encoder／VAE 伴隨檔（帳本同 version id 優先，退而用
   `<模型>_txt` 檔名慣例）。
2. **計畫帶 workflow 路由**：plan／source-info 的 `local_plan` 新增 `template`、
   `diffusion_model`、`text_encoder`、`vae`——Anima 依 LoRA 數挑 `anima`／
   `gen_txt2img_anima_lora_model_only`／`..._multi_lora` 模板；傳統家族帶 LoRA 時也
   明確指定 `default_lora`（先前 generate-like 只設 `loras` 不設 `lora`，queue 推斷不到
   LoRA 模板，LoRA 會被靜默丟棄）。generate-like 把這些參數原樣傳入佇列。
3. **LoRA 槽位對齊**：LoRA 多於模板節點數時裁掉並警告；少於時以強度 0 的重複項
   填滿多餘槽，避免模板內建 LoRA 畫風滲入結果。
4. **同家族替代涵蓋 diffusion model**：原模型真的沒有時，家族替代除了本地 checkpoint
   也會找帳本中同家族的 diffusion model（如 anima_preview3Base），一樣註明同家族替代。
5. **already_installed 不再空等**：自動下載遇到帳本回「已安裝」（規劃時對不上檔名，
   例如檔案被改名）時不再回 `acquiring_resources`，改用替代模型直接生圖並警告。
6. **驗證**：新增 9 個離線測試（拆件比對／帳本身分／模板選擇／槽位填補／家族退回／
   already_installed）；backend `892 passed`、MCP `77 passed`。以真實 API 實測
   image 135643885：`local_plan` 正確回 `anima_baseV10` + `anima_baseV10_txt` +
   multi-lora 模板，`needs_download` 只剩真正缺的 1 個 LoRA，不再退回 Illustrious。

**下一步（實機驗證清單）**：
- [ ] 啟動 backend + ComfyUI，用 MCP 實跑：`civitai_source_info(一張喜歡的圖)` →
      `civitai_generate_like(同圖, prompt="想要的主題")`，確認 4 張圖進 gallery。
- [ ] 實測缺模型情境：挑一張用未下載模型的圖 → 確認自動下載進外接硬碟 → installed 後
      重呼叫 generate_like 用上原模型。
- [ ] 若下載回 401/403，到 civitai.com 帳號設定產 API key 填入 `.env` 的
      `CIVITAI_AUTHORIZATION` 後重試。

---

## 已完成（時間倒序）

- **2026-07-24 自帶 Compose fallback（已實作）**：安裝時系統 Docker Compose 太舊/缺 plugin/
  只有 v1 會被 `COMPOSE_VERSION_UNSUPPORTED` 擋下。改為 `preflight` 解析 `ComposeRuntime`：
  系統 compose ≥ 2.24 直接沿用；否則下載釘死版 2.32.4 standalone compose 到私有 cache
  （`<CACHE>/ai-drawing/compose/<版本>/`）、比對釘死 SHA256 後才用絕對路徑呼叫，**絕不碰
  PATH 與 `~/.docker`**。status/dry-run 不觸發下載；setup/start/reconfigure 才會。實作於
  `scripts/launcher/{constants,docker,cli}.py`，新增 39 個 docker 測試全綠。Spec/Plan 見
  `docs/superpowers/{specs,plans}/2026-07-24-bundled-compose-fallback*.md`。
- **2026-07-15 Civitai best-effort 重構**：見「目前聚焦」。
- **2026-07-12～14 Civitai 精確重現管線（CIV-A～F、CIV-V-*、CIV-SA-*）**：GenerationRecipe
  schema、取得/資源解析/相容性/compiler/佇列/出處稽核/變體/variation set/source alias 全套
  strict 管線與 HTTP 路由。曾以正式 stdio MCP 實跑完成單張與變體生圖（gallery 1、3、4 等）。
  管線仍在 backend 服役，但因對 agent 過度嚴苛已從 MCP 工具面移除；細節見
  `docs/archive/2026-07-legacy/PROGRESS-2026-07-14-audit-log.md` 與 git history。
- **2026-07-07 LoRA 訓練 agent 工作流**：訓練決策 preflight、dataset curation（dry-run/
  apply/rollback）、agent handoff runbook（`docs/lora-training-agent-handoff-runbook.md`）。
- **2026-06 影片生成 MVP**：Wan 多 keyframe 單 workflow 影片生成
  （`generate_video_wan_keyframes`）、artifacts 紀錄與 gallery 交付；custom workflow 失敗時
  回結構化 node_errors、佇列失敗不重試不阻塞。
- **基座**：FastAPI backend（生圖佇列、gallery、recording、watchdog、WD Tagger、Kohya LoRA
  訓練）、React 前端、MCP server（FastMCP/stdio）、SQLite。

---

## 卡住 / 待決策

（無。舊清單中的 queue 隊首阻塞已於 2026-06 修復；R5–R7 的 COMBO/catalog blockers 隨
strict 工具面移除而不再適用。）
