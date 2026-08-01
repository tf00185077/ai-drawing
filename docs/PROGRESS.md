## 2026-07-29 分類管理：編輯時把詞條移到其他分類

- 後端新增原子 `move_entry` 端點（`POST .../entries/{id}/move`）：單一 store 鎖內把詞條從來源分類移除、寫入目標分類，兩邊 bump revision；以來源分類 revision/etag 樂觀鎖；目標撞相同 entry id → 422 不寫檔；同 polarity 限定；`to==from` 時等同原地編輯。
- 前端詞條編輯器加「所屬分類」下拉（同 polarity 分類縮排樹）；分類詳情頁存檔時若選了不同分類即呼叫 move（連同這次的中/英文修改一起搬過去），相同分類則照舊 `putPromptEntry`。
- 組合皆 literal、不受影響。驗證：後端 move 6/6 + 回歸 41/41、前端 vitest 192/192，`tsc` 與 Vite build 通過。

## 2026-07-29 Prompt Library 資料校正（中文校正＋重新分類）

- 修正大量「中文不夠準確」：atomic 遷移遺留的名稱如「狗爬式・第 1 詞（on all fours）」全部改成正確的單一 tag 中文（on all fours→四肢著地、ahegao→阿黑顏、creampie→中出…），共 150 筆。
- 去除重複：同分類內 prompt 完全相同的重複詞條移除 155 筆（clothing 曾有「opaque clothes」×10），並解開內嵌權重（如「(tongue out:1.4)」→ tongue out）。quality-ratings 刻意保留同英文多家族變體。
- 重新分類（用 parent_id 樹）：body-appearance 拆成 人物與身形／男性特徵／性器官（並原子化其含逗號詞條，修好長期無效的分類）；accessories 的過膝襪/連褲襪/網襪移到新的 襪類/腿部服飾（掛在 服裝 下）；environment 拆出 氛圍與光線（掛在 場景/地點 下）；clothing 拆出 著裝狀態/暴露程度。
- 結果：全庫 534 個詞條、16 個分類（含子分類），全部通過嚴格 schema，無任何含逗號詞條，分類樹 0 個壞連結，5 個組合（皆 literal）不受影響。
- 純資料變更（prompt_library/ JSON），後端/前端程式不動。

# 進度追蹤

## 2026-08-01 Windows Worker 首次 managed bootstrap 實機修正

- Windows 11 實機升級重現兩個 deterministic installer blocker：`uv pip install --python` 對 uv-managed standalone Python 回 externally-managed error，但舊 Setup 未檢查 exit code；其後 `uv python install` 建立的內部版本 alias junction 又被首次 managed inventory 以 `MIGRATION_REPARSE_POINT` 正確拒絕。
- 新增可獨立測試的 `WorkerInstall.ps1`：所有必要 pip 安裝對專用 standalone interpreter 明確使用 `--system --break-system-packages` 並將非零 exit code 轉成 terminating `INSTALL_DEPENDENCY_FAILED`；Python install 也以 checked command gate 處理。首輪只使用 `--system` 的實機重試仍被 uv PEP 668 gate 正確拒絕，依 uv 官方 CLI contract 補上後者。
- Python executable 現在只從符合 manifest 完整版本、非 reparse 的實體安裝目錄選取。首次 bootstrap 前只移除名稱符合 uv alias、target 位於同一 `runtime/python`、target 本身非 reparse 且與選定 executable 一致的 junction；外部 target、未知名稱或巢狀 reparse 一律 `INSTALL_PYTHON_REPARSE_UNSAFE`，migration 原有 no-follow/fail-closed 規則未放寬。
- 首次完整 Setup 另重現 ComfyUI requirements 先安裝同版本 CPU-only PyTorch、後續 CUDA index 因版本相同只做 `Checked` 而未覆蓋的問題。Installer 與 future updater 現在都在全部 requirements 後以 CUDA index 對 `torch/torchvision/torchaudio` 使用逐套件 forced reinstall，並以真實 `torch.cuda.is_available()` 作 terminating activation gate；CPU runtime 不再能被宣告安裝或 update 成功。
- 完成 CUDA 修復後再由實機抓出 Windows PowerShell 5.1 `Resolve-Path current` 不會解參考 junction，導致 Worker 自身 reparse 防線拒絕 `AI_DRAWING_WORKER_RELEASE_ROOT`。新增 `WorkerPaths.ps1`：只接受 `current` 為 junction、target 為 `releases/<40-char commit>` 下的單層實體目錄，啟動時傳入 concrete target；外部或巢狀 reparse 維持 fail-closed。Setup 與 migration surface 同步部署此 helper。
- README 的 D 槽正式 migration 命令同步修正為 `C:\AI-Drawing-Worker-Source\worker\windows\Migrate-Worker.ps1`。Focused fake-uv／真實 Windows junction／CUDA wheel ordering 與 activation gate RED→GREEN；首輪實機另抓出 manifest minor selector `3.12` 與實體 patch 目錄 `3.12.13` 的差異，補為 minor selector 僅匹配唯一 `3.12.x`、完整 patch selector 仍精確匹配。Worker focused gate：`267 passed, 1 skipped`，Python compileall 與 `git diff --check` 通過。source/dist/ZIP 共 28 檔逐位元一致；concrete current resolver 第五版修正 ZIP SHA-256：`04c4b471fe92e1f9d24a8a60ae0071e1aa3c01f573b6ea640f2c9e9325f7699d`。實機 Setup/migration 結果待本節後續補記。

## 2026-08-01 Mac 自動更新 NVIDIA Worker coordinator（Task 6，non-live）

- Backend 只信任本機 `HEAD == origin/main^{commit}` 的完整 commit，Git 查詢有 10 秒 timeout，且絕不自動 fetch/pull；Worker mismatch 才透過固定 authenticated update API 請求更新。
- 單一 process-local `Condition` 讓 FastAPI startup background check 與 Worker submission 合流；多 Backend process 由 Worker 既有 same-target request reuse 收斂。收到 request ID 後才容忍 restart outage，預設最多 1800 秒，最後嚴格要求 `ready`、精確 commit、整數 protocol/capability 與成功 preflight。
- Worker submission 採非遞迴 gate：更新完成後只送出原 prompt 一次，失敗時不退回 local。`.env` 新增預設關閉的 `NVIDIA_WORKER_AUTO_UPDATE` 與 `NVIDIA_WORKER_UPDATE_TIMEOUT`；`/api/workers/status` 只公開安全的 enabled/state/error code。FastAPI event loop 不執行同步 Git/HTTP polling。
- Non-live 驗證：Task 6 測試 `20 passed`；Task 6 + pairing/routing `27 passed`；全部 Worker/main 相關測試 `281 passed, 1 skipped`。未連線或修改真實 Mac、Windows Worker、ComfyUI、GPU、Scheduled Task 或部署環境。
- Fix round 1：Mac poller 現在接受 Worker canonical `installing` 狀態；accepted request 後每個 status/final-health/preflight 呼叫都取得遞減的剩餘 deadline，client 以 `min(configured timeout, remaining)` 限制 HTTP，且 call 回傳後重新檢查 clock。Task 6 + pairing/routing `36 passed`；Worker/main regression `290 passed, 1 skipped`。
- Fix round 2：`nvidia_worker_timeout` 與 update timeout 以 Pydantic before/after validators 保留合法 env numeric strings，拒絕 bool、NaN/±inf、零與負值；direct Worker client、request configured/override/effective timeout 與 coordinator deadline/remaining 亦重複執行 finite-positive 防線。Task 6/config/pairing/routing `78 passed`；Worker/main/config regression `332 passed, 1 skipped`。

## 2026-08-01 NVIDIA Worker 同 /24 自動發現與 runtime failover

- Mac Backend 在已配對 Worker URL 發生 connect failure 時，僅掃描設定 URL 同一個明確 IPv4 `/24` 的 `8791` port；只對 TCP 開放候選以既有 Bearer Token 查 `/v1/worker/status`，並要求唯一候選同時符合 `hostname=DESKTOP-AV90PQ4` 與 `protocol_version=1`。
- status、preflight、資源 plan/content、prompt、history、queue、view、upload 全部共用 discovery-aware request 層；發現成功後原請求只重試一次，runtime URL cache 供後續 client（含 `/api/workers/status`）沿用，不寫回 `.env`。停用 discovery 或非 connect 類錯誤不會掃描。
- `local` 路徑維持原行為；明確選擇 Worker 仍 fail-closed，不會 fallback Mac。驗證為 non-live：focused Worker/config/API `48 passed, 1 deselected`；Backend 排除缺少可選 `mcp` 套件而無法 collection 的 parity test 後為 `1363 passed, 18 failed`，18 筆皆為既有 Prompt Library inventory/migration、multi-LoRA 與 Worker dist/source不一致，與本功能無關。未啟動／重啟服務、未操作 GPU 或真實 Worker。

## 2026-07-31 NVIDIA Worker 路由效能與錯誤呈現加固

- **Mac 端 digest 快取**：`nvidia_worker._digest` 以 `(path, size, mtime_ns)` 快取 SHA256，長駐 queue worker 行程內每個模型檔一生只 hash 一次；不再每次送生成就把整個 checkpoint/LoRA 全量重讀重算。任何真實編輯（size 或 mtime 變動）自動失效。
- **Worker 端 sidecar sha**：`resource_plan` 對已存在的大檔改用 `cache/verified/` 的 sidecar（`{size, mtime_ns, sha256}`）做純字串比對，不再每次 rehash 24GB；缺/過期 sidecar 時 hash 一次自我修復（相容既有安裝）。同名同 size 但內容不同仍由 sha 比對抓出並回報 missing，正確性不退。LRU 觸碰改為 `_touch_atime`（保留 mtime，避免自我失效）；ingest finalize 後寫 sidecar。
- **Worker 路徑 node_errors**：`NvidiaWorkerClient.submit_prompt` 的 `/prompt` 不再經 `_request` 的 `raise_for_status`，改為解析非 2xx body 包成 `ComfyUIError(error, node_errors=...)`，與 local 路徑同型別同欄位，缺模型/參數錯誤能忠實呈現給前端與 Discord。
- 驗證（non-live）：新增/回歸測試——worker_resources 4、worker_runtime 5（含 sidecar 命中不讀檔、同名不同內容回報 missing、缺 sidecar 自我修復）、worker_routing/pairing、queue，合計 `46 passed`。未跑 ComfyUI／GPU／真實 worker E2E。既有兩筆失敗（`get_comfy_client` 空 base_url、worker manifest 需 `dist/` 產物）為環境問題、pristine commit 亦紅，與本次無關。

## 2026-07-31 Prompt Library 髮型子分類建置

- 在 `髮型`（hair，掛於 人物與身形 下）底下新增 7 個子分類（`parent_id: "hair"`）：長度（hair-length, 11）、瀏海（hair-bangs, 6）、綁髮（hair-tied, 16）、捲度（hair-texture, 9）、分線（hair-parting, 3）、髮尾（hair-ends, 4）、特殊髮型（hair-special, 8），共 57 個原子詞條。
- 每個詞條為單一無逗號 tag，`id` 由英文 slug 化（如 shoulder-length hair→shoulder-length-hair），`name_zh`/`description_zh` 帶中文，`order` 以 10 遞增；子分類 `order` 10~70。
- 純資料變更（prompt_library/positive/ 新增 7 檔），後端/前端程式不動。驗證：全部通過嚴格 `PromptCategory` schema、無含逗號詞條，分類樹整合測試 `15 passed`。

## 2026-07-31 Discord 固定影片指令與精確 FILM 補幀（non-live）

- Backend 新增兩條固定、server-owned 影片流程：AnimeGen 單圖 I2V，以及 Wan2.2 Animate 角色參考圖＋必要 driver 影片的臉部／身體動作轉移。兩者皆驗證附件、限制原始總幀數為 `4n+1`，依首幀到末幀的 `total_seconds` 計算 FPS，完成後以 FILM 產生呼叫者指定的任意精確目標總幀數；原始影片或 FILM 失敗的部分結果不會持久化為成功 artifact。
- Discord Bot 新增 `/animegen_i2v`、`/wan22_animate`，只做附件／參數驗證與 Backend multipart 呼叫；工作排入後沿用 `/result id:<job_id>` 交付 Backend 已持久化的最終影片。README 已記載完整參數、`4n+1`、driver、時間跨度與 FILM 目標幀語意。
- FILM metadata 明確分開 `timeline_span_seconds`（使用者指定的首末幀跨度）與 `container_duration_seconds`（`frame_count / fps`）；`GeneratedArtifact.duration` 保存後者，不再把跨度誤記為 MP4 容器時長。
- Non-live 驗證：Backend fixed-video focused `10 passed`；Discord Bot 全套 `68 passed`；Backend／Discord Python `compileall` 與 `git diff --check` 通過。本項沒有啟動／重啟 Discord runtime，亦沒有執行 ComfyUI、GPU 或重型影片 E2E；live command sync 與真實模型生成仍待另行驗證。

## 2026-07-30 Discord 結果統一交付與 Operator/MCP escape-hatch

- `/result` 與新的 operator endpoint 共用單一 `ResultDeliveryService`：只讀取既有 completed job，分批附加所有 Backend 回傳的持久化 SaveImage artifacts（每訊息最多 10 檔且受 upload byte limit 約束），過大檔案使用完整 gallery links；mixed batch warning 沿用 bounded/sanitized failure 摘要。
- Discord Bot 選用的 loopback-only endpoint 只接受 `job_id`、allowlisted destination alias 與 boolean `force_resend`，以 server-side bearer secret 驗證；不接受任意訊息、檔案或 channel ID，且會確認 channel 屬於 configured guild。完成交付以 atomic ledger 按 job/destination 去重，explicit force 才重送，回傳可驗證 Discord message IDs。
- MCP 新增意圖級 `deliver_generation_result_to_discord`，token 使用 `SecretStr` 且只從 MCP server env 取用；回應與 transport error 不回顯 token。工具不生成、不取消、不變更 job，僅呼叫 Discord Bot 的受限 operator endpoint。
- 驗證：Discord Bot 全套 `61 passed`、MCP Server 全套 `126 passed`；Discord Bot 與 OpenClaw Gateway 已在 queue/agent idle 後重啟，Backend／Bot operator／Gateway 健康。兩筆既有 completed job 經 operator/MCP 路徑各交付 4 個 artifacts；同 job/alias 第二次呼叫回傳相同 message receipt 且 `deduplicated=true`，未重複發送。未提交 GPU 工作。

## 2026-07-29 LoRA Start 契約加固（OpenSpec 第一批）

- 完成 `harden-lora-training-start-contract`：Backend 與 MCP 的 public Start 現在都要求 `expected_dataset_hash`、`expected_profile_hash`，保留呼叫者選定的 `batch_size`，Backend 以 `extra="forbid"` 拒絕未知欄位。MCP 的 Backend 422 與 FastMCP protocol-level 缺欄位錯誤都正規化為穩定的 `request_validation_failed`，只保留安全 constraint context，不回顯 submitted input／URL／任意例外文字。
- Preflight 的 `decision="train"` suggestion 現在是可直接提交的完整 Start payload，包含雙 hash、`batch_size` 與 family/runtime 欄位；profile/config family 衝突回 `needs_review`＋`model_family_mismatch`。Bundled frontend 逐資料夾 preflight，只有 `train` 才 Start，保留使用者欄位並帶入 UI 無法表示的 preflight runtime；stale hash、field 422 與其他 Start 錯誤皆顯示結構化修復資訊。
- `lora_training_jobs` 新增 nullable `profile_hash` 與 `error_details_json`，含 idempotent SQLite additive migration、歷史 row 相容、durable params/status 與 Start response。queued 後的 hash/profile race 會保存 expected/current hash；舊 caller 必須先 preflight，再原樣提交兩個 approval hashes。
- Dataset approval identity 現在涵蓋圖片 bytes、圖片/字幕 membership、caption 內容與 profile。Trainer 統一使用 absolute／rooted／traversal／symlink-escape-safe resolver，並在 resolve 後立即正規化成 root-relative POSIX locator，讓驗證、durable identity、duplicate detection 與輸出命名一致。
- Worker 取得 dataset lock 後才做最終 profile/hash/full validation 與 family check，並持鎖通過 subprocess、輸出註冊、callback 與 terminal status。Upload、caption edit、batch prefix、LLM caption 與 watcher WD Tagger 共用同一把鎖；watcher 的 check-then-act race 已關閉，鎖衝突會做最多三次 1／2／4 秒退避重試。`trigger_check()` 僅 discovery，production 中只有 explicit `/api/lora-train/start` 可 enqueue。
- Runbook、MCP setup/README 與 machine-readable handoff contract 已同步雙 hash，以及 missing/stale/422/family/path recovery 的「停止並重新審批」規則。新增 root `pytest.ini` 的 importlib mode＋兩個 package path，使 Backend/MCP 可在同一次 pytest 執行而不發生兩個 `tests` package 撞名。
- 最終驗證：target OpenSpec strict valid；focused Backend LoRA＋watcher `171 passed, 1 skipped`；MCP 全套 `114 passed`；Frontend 全套 `189 passed`，TypeScript typecheck、Vite build、Python compileall、`git diff --check` 均通過；排除共享工作樹正在校正的 Prompt Library／comma-atomic 測試後，Backend＋MCP `1194 passed, 4 skipped`。原始不排除命令亦已執行，於 `477 passed, 3 skipped` 後只停在本批範圍外的固定庫存斷言：測試仍要求 683 entries、目前資料為 538。
- 獨立 code review 最終確認無剩餘 Critical／Important blocker；其指出的 protocol redaction、image-byte identity、durable mismatch details、writer locks、Windows locator 與 watcher defer 邊界均已補測並修正。
- 下一個執行批次依既定順序為 `make-lora-training-recipe-explicit`；其後才是 runtime lifecycle 與 clients/verification 兩批。後三批目前只保留 confirmed gaps，未提前寫實作方法或完成目標。

## 2026-07-29 Prompt Workbench 快速新增自訂詞條

- 工作台「加入 Prompt」面板新增「新增詞條到詞庫」小表單：選任一層分類（縮排樹下拉）＋中文名稱＋英文 prompt，即把自訂詞條存入該分類。
- 自動處理其餘欄位：由英文自動產生 slug（同分類撞名加 `-2`/`-3` 後綴，不覆蓋既有詞條）、`description_zh` 帶中文名、`order` 預設、別名/關鍵字留空；英文含逗號會擋下（一個詞條＝一個 tag）。送出前先讀該分類目前 revision/etag 與既有 id 做去重與樂觀鎖。
- 依決策：建立後**只存入詞庫、不自動加入目前組合**；成功後把新詞條併入跨樹搜尋資料、若正停在該分類則重載，使其立即可瀏覽/搜尋/手動加入。
- 純前端；沿用既有 `getPromptCategory`／`putPromptEntry`，後端/API 不動。驗證：前端 vitest 全綠、`tsc` 與 Vite build 通過。

## 2026-07-27 Prompt Library 分類樹 Phase 3（工作台瀏覽器樹狀）

- 工作台左側「加入 Prompt」由扁平分類 chip 列改為**鑽入式＋麵包屑**：頂層列出 root 分類資料夾，點入後顯示其子分類資料夾與該分類詞條 chip（30/頁沿用）；麵包屑可跳回任一層或頂層。
- **跨整棵樹搜尋**：輸入關鍵字即攤平該 polarity 全樹，列出命中詞條並標示其分類路徑，點擊即以「該詞所屬分類」加入（`onAddEntry(category, entry)`）；某分類若載入失敗其詞條不入搜尋，但不影響其他分類。
- 純前端；後端沿用 Phase 1 的 `parent_id`。分類樹三階段（資料/排序、管理 UX、瀏覽器）至此完成。驗證：前端 vitest 全綠、`tsc` 與 Vite build 通過。

## 2026-07-27 Prompt Library 分類樹 Phase 2（管理 UX）

- 前端分類寫入路徑接上 `parent_id`（先前 `categoryWriteBody` 會丟棄）；`putPromptCategory` 現會送出 `parent_id`（可為 null 以設為頂層）。新增純函式 `categoryTree`（樹列前序、祖先鏈、子孫集）。
- 分類管理頁：「新增分類」表單加「父分類」選擇器（同 polarity 縮排選項，留空＝頂層）；「現有分類」清單改縮排樹呈現。
- 分類詳情頁：顯示分類路徑麵包屑；可搬移父分類（選項排除自己與所有子孫，避免明顯成環，最終防環由後端把關）；**編輯任何欄位都會保留既有 parent**，不會誤清。
- 純前端；後端沿用 Phase 1 的 parent_id 寫入與驗證。畫面工作台瀏覽器樹狀（Phase 3）另行。驗證：前端 vitest 全綠、`tsc` 與 Vite build 通過。

## 2026-07-27 Prompt Library 分類樹 Phase 1（地基）

- `PromptCategory` 新增選填 `parent_id`（指向同 polarity 分類）；詞的身分 `(polarity, category_id, entry_id)` 不變，組合/provenance/comma-atomic/生圖/輸出全不動、零 migration。
- 寫入分類的 parent 嚴格驗證：父存在且同 polarity、非自我、不成環，違反回結構化 422 不寫檔。
- 讀取 catalog 容錯：懸空/跨 polarity/成環的 parent 一律降級為 root 並附 `category_parent_demoted` diagnostic，library 照常載入（寬進嚴出）。
- 前端組裝排序改「祖先路徑」字典序：`rankOf` 回傳從 root 到該詞每層 order 的陣列＋詞 order，`sortFragmentsByRecommendation` 逐層比較。扁平分類（皆 root）行為與先前逐字相同。
- 畫面此階段仍為扁平（Phase 2 管理 UX、Phase 3 瀏覽器樹狀另行）。驗證：後端 pytest、前端 vitest 全綠，`tsc` 與 Vite build 通過。

## 2026-07-26 Prompt Workbench UI 優化：詞條 chips · 已選 filter+分頁 · 加入組合

- 左側「加入 Prompt」詞條由全寬列表改為內容寬度 chips（prompt 移到 tooltip、保留 ⚠️ 可疑中文標記），每頁最多 30 個、超過分頁；搜尋或切換分類回第 1 頁。
- 已選片段檢視由常駐分類區塊改為「分類 filter + 每頁 3×3（9 張）分頁」：預設「全部」、可只看某分類，每卡加分類標籤；卡片保留內容/權重/上移下移/刪除，最終文字 textarea 與輸出不變。移除前版 `groupFragmentsByCategory`，改用 `distinctCategoriesOf` 建 filter。
- 「載入組合」改名「加入組合」，行為由取代改為 append：把選中組合片段接進目前工作區、自動去重同來源 entry ref（literal 不去重）、清掉目前組合身分變未儲存草稿、並套既有自動排序狀態機（auto 重排／manual 接尾）。
- 純前端；後端/API/schema 零改動，送 ComfyUI 的最終字串邏輯不變。驗證：前端 vitest 全綠、`tsc --noEmit` 與 Vite build 通過。

## 2026-07-26 Prompt Workbench 系列標註 · 推薦排序 · 分類分區

- 品質與分級的品質詞 `name_zh` 補上家族後綴（Pony / Illustrious / NoobAI / Anima / SD1.5），台上可分辨同名品質詞屬哪個系列；分級詞本就有系列故不動。純資料變更，`name_zh` 非 snapshot，不影響任何已存組合的生圖。
- positive 分類 `order` 依 Pony / Illustrious / Animagine 官方與主流指南調成推薦順序（品質→人物身形→服裝→內衣褲→配件→表情→姿勢→動作→場景→鏡頭構圖→身體效果），作為組裝排序依據；場景/背景依研究放後段。
- Workbench 加入詞條/自由文字時，若該 polarity 為 `auto` 會依（分類 order → entry order → 加入序）自動排序；一旦手動上/下移即切 `manual` 不再自動重排，並提供「重新套用推薦排序」切回 auto。載入既有組合為 manual（尊重存檔順序），新建空白為 auto。
- 最終文字卡片區改為依分類分組檢視（品質/場景/動作…各一區，literal 歸「自訂文字」），方便一眼看到各分類選了哪些；最終文字 textarea 仍是單一 raw 逗號字串，送 ComfyUI 的輸出逐字不變。後端 `PromptComposer` 與 API/schema 零改動。
- 驗證：前端 vitest 全綠、`tsc --noEmit` 與 Vite build 通過；prompt library JSON 通過 Pydantic 嚴格 schema 驗證。
- **Review fix（`feature/prompt-workbench-series-ordering`）**：分類分區改為「依全域片段順序走訪、分類 key 一變就開新區塊」的 contiguous-run 分組，取代先前「依分類桶裝再依 order 排序」的做法——manual 模式下卡片分區現在會跟 上移/下移／「第 N 段」所依賴的全域 index 同步；同一分類非相鄰出現時會拆成兩個區塊（此為預期行為，忠實反映真實順序）。auto 模式視覺不變。同步修正 `PromptComposerPanel.tsx` 的 React key（改用 `` `${group.key}-${groupIndex}` ``，因同一分類 key 現在可能出現在多個群組）、移除已死的 `categoryInfoOf ?? (() => null)` fallback，並在 `PromptWorkbench.tsx` 的 composite-rank 計算加註解說明 entry order 上限假設。更新 `compositionState.test.ts` 分組測試為新行為並新增鄰接合併測試。驗證：`compositionState.test.ts` 18 passed、`PromptComposerPanel.test.tsx` 7 passed、全套前端 137 passed、`tsc --noEmit` 通過、Vite build 通過。詳細報告見 `.superpowers/sdd/task-5-report.md`「Review fixes」段落。

## 2026-07-26 Prompt Library ASCII 逗號原子化與 migration-first 交付

- Prompt Library 現以每個 ASCII 逗號（U+002C）作為無條件 atomic Prompt 邊界；前導、尾端與連續逗號會保留成可編輯的空白卡片。Save、Update、Save As 與 Generate 皆在任何 request 前攔截空白片段，列出 polarity 與 1-based 位置；Backend 仍拒絕空白或含逗號的 persisted atom。
- 既有詞庫由 297 entries（146 個含逗號、151 個既有 atomic entries）migration 為 683 個非空且不含逗號的 entries；532 個 derived atoms 使用 checked-in deterministic curation，四個既有 combinations 原子化為 2／25／5／4 fragments，共 36 fragments。最終 dry-run 為 0 mutations、0 diagnostics，且 151 個 retained entries 與真實 predecessor bytes 均經 hash 驗證。
- Backend 實作 fail-closed migration marker、privileged dry-run/apply/resume/rollback/finalize、atomic enforcement、weighted canonical rendering，以及 unresolved legacy provenance 的 blocking resolution。隔離資料已驗證真實 predecessor 的 gate、`dry-run → apply → activate → finalize → rollback`、byte-exact restore 與第二次 dry-run idempotency。
- Workbench 使用 lossless weighted fragment state；自由文字、final textarea 與卡片編輯皆依 ASCII 逗號即時 atomize。Update 保留既有 combination metadata；replacement source 必須實際取代對應 fallback；Frontend／Backend 權重統一為最多三位小數的 canonical rendering。
- Offline 最終驗證：Backend `1193 passed`、MCP `104 passed`、Frontend `130 passed`，TypeScript typecheck、Vite production build、`git diff --check`、target strict OpenSpec 與全體 OpenSpec `14 passed, 0 failed` 均通過。兩輪務實獨立 review 最終皆無正常產品路徑 release blocker。
- 依 CTY 指示，本次不由 agent 重啟或操作 live Backend、Discord Bot、ComfyUI 或 Hermes Gateway，也不提交真實生圖。Live migration gate、真實 browser／Discord／generation E2E 由 CTY 在 merge/push 後自行驗證；本節不宣稱 live pass。

## 2026-07-25 Prompt Workbench 最終文字直接編輯與單一 CompositionState

- Positive／Negative 的「最終文字」永遠是可直接編輯的 controlled textarea；已移除自由文字 mode、套用、取消以及獨立 raw draft。每次 `onChange` 立即以 `materializeRawText` 更新該 polarity 唯一的 `CompositionState`，不 trim、不拆逗號、不 parse、不 debounce，因此尾端逗號／空白與暫時未閉合括號都會逐字保留。
- 第一次從結構片段直接編輯時會立即移除全部 source refs，改成單一「自訂文字」literal；後續 direct keystrokes 重用同一 literal ID，避免 card remount。片段內容／weight／刪除直接作用於目前 literal；單一 card 的移動自然 disabled，新增來源詞條則接在 literal 後方。
- 空字串與純空白 direct text 保留畫面上的 exact `CompositionState.text`，但使用零 fragments，故 `serializeFragments` 與 save/update/save-as payload 都是 `[]`，符合 Backend 的空 Prompt 契約。非空白 direct text 則序列化為一個 exact literal。
- 儲存直接序列化目前 CompositionState，生圖直接使用目前 `state.text`，沒有隱式 materialization／async flush。任何新編輯都會由 `markDirty` 使 pending operation token 失效，舊 load/save response 不可覆蓋較新的本機文字。
- Load 與 New 經 dirty confirm guard 後直接安裝／重置兩個 CompositionState；`beforeunload` 僅由 `document.dirty` 控制。
- Non-live 驗證：focused Prompt tests `34 passed`、完整 Frontend suite `116 passed`、TypeScript `tsc --noEmit` 與 Vite production build 均通過。全程未操作或重啟 live Backend、Discord、ComfyUI 或 Gateway。

## 2026-07-25 Prompt Library 管理與 Workbench 組合生命週期

已在隔離 branch `feature/prompt-library-management` 完成 source/offline 實作與雙層審查：

- Backend 新增分類／詞條 restore contract、樂觀鎖與結構化錯誤；MCP 新增 audited `prompt_library_restore` 工具與文件。
- Frontend 改為 typed Prompt Library API；分類清單提供 active/archived filter 與獨立詳情 route，分類 metadata 與詞條 create/edit/archive/restore 全移至詳情頁。
- Workbench 詞庫來源維持唯讀，只能複製進組合；片段卡以 `name_zh` 顯示，缺中文時回退 Prompt，再缺才回退 entry ID，不再顯示「片段 N」。
- 自由文字改為明確 draft／套用交易，保留原始逗號與空白；final text 唯讀，錯誤不破壞 canonical fragments。
- 新增已儲存組合 selector、detail load、建立空白、更新、另存、dirty/raw-draft guard；更新使用 detail revision/etag，另存使用 revision 0，成功後安裝 Backend canonical response。
- 補齊 category/catalog/route/load/save stale-response ownership、NFC Unicode ID、cross-polarity refs、空白 order 驗證與人類可讀 label fallback。

隔離完整驗證：Backend `1147 passed`、MCP `99 passed`、Frontend `128 passed`，`tsc --noEmit` 與 Vite production build 通過。第二輪 fail-closed 靜態審查結論為 source/offline code readiness APPROVED，無具體 release blocker。

目前尚未整合至主 checkout／遠端，也未重啟或操作 live Backend、Discord Bot、ComfyUI 或 Hermes Gateway。真實 browser management/Workbench smoke、Gateway schema activation、live MCP restore 與 Discord E2E 仍依使用者 no-service 限制保持 blocked/unverified。

## 2026-07-25 Discord 獨立批次 Seed（OpenSpec: discord-independent-batch-seeds）

已完成核准的 non-live 實作：Discord 維持既有 `/draw`、張數控制、單一公開
parent job ID 與 `/result id:<job-id>`，最終 normal generation payload 改為
`batch_seed_mode="independent"`。Backend 會在同一把 queue lock 內一次保留全部
child slots、配置互不重複的 backend-owned seeds、建立 durable parent/member
ledger，並依序排入 private execution ID 的 `batch_size=1` children。既有 API/MCP
省略此欄位時仍走一個 shared ComfyUI batch；fixed、workflow-default、custom 與
audited 路徑不會被重新解讀成 independent。

Parent 從第一個 child 開始後保持 `running`，直到所有 members terminal；mixed
結果只要至少一張成功即為 `completed`，全失敗才是 `failed`。child 失敗不取消
siblings；計數、實際 seed、bounded/sanitized failure 與 restart reconciliation
均持久化。成功 artifacts 只會從 completed members 回傳，按 child ordinal 再按
artifact ID 排序；filename 使用完整 sanitized parent ID、child ordinal 與
artifact index，metadata 保存 `batch_index`/seed 且保留 `source_node_type`。
Discord 僅下載 parent 的 `SaveImage`，排除 preview，mixed 時先送成功檔案再送
精簡警告，全失敗時亦呈現 durable aggregate counts 與 bounded member reasons，
不會被最後一個 child 的 raw `node_errors` 取代。Independent child 只有實際
`SaveImage` artifact 才算成功；preview-only child 失敗但不取消 siblings，Discord
也不會讓 independent job 重新走 legacy Gallery fallback。ComfyUI `/queue` 暫時
malformed 時保留 running slot 並用已知 prompt ID 查 history；terminal history
照常處理，只有連續 15 次仍無法判定才 terminalize/release。

### Non-live 驗證證據

- 基線：`openspec validate --all --strict` 為 `12 passed, 0 failed`；Backend 為
  `1084 passed, 1 failed`，唯一失敗是既有
  `test_import_alias_failures_are_redacted_and_have_zero_registry_build_queue_side_effects`
  的 `invalid_payload` code mismatch；Discord Bot 隔離依賴環境為 `44 passed`。
- TDD/self-review 對 direct queue seed controls、malformed node/execution/history
  responses、failed-member partial artifact/image leakage、legacy queue JSON shape、
  full-parent filename identity與 all-failed Discord reporting 都先取得 RED，再做
  focused GREEN。本輪另對 transient malformed queue 不提早啟動 sibling、terminal
  history fallback、persistent queue/history uncertainty 最終釋放、aggregate
  all-failed 與 preview-only/legacy-fallback 取得 RED→GREEN 證據。
- 最終 focused Backend（generate、queue、completion/failure、durability、
  recording、artifacts、ComfyUI、audited compatibility）為
  `105 passed, 2 warnings`。
- 最終完整 Backend 為 `1127 passed, 1 unchanged baseline failure, 77 warnings`；
  feature focused tests 全綠，未修改該無關 Civitai alias failure。
- 最終完整 Discord Bot 為 `49 passed, 6 warnings`；command set 仍精確為
  `draw`、`result`。
- Backend 與 Discord `compileall` 均通過；原始 generation-batch Alembic
  revision 直接透過 Alembic Operations 在 isolated in-memory SQLite 完成
  upgrade/downgrade。第二輪新增的完整 Alembic CLI environment/config 與
  round-trip test infrastructure 不在目前產品範圍，已移除；repo 未配置額外
  Python mypy/ruff/pyright gate。
- `openspec validate discord-independent-batch-seeds --strict` valid；
  `openspec validate --all --strict` 為 `13 passed, 0 failed`；
  `git diff --check` 通過。
- Worktree interpreter 未安裝 `discord.py`；完整 Discord suite 使用既有
  read-only Hermes/Homebrew package paths 離線執行，未安裝依賴或連線 Gateway。

Scoped review 已覆蓋 queue identity/status、不重啟遺失既有 terminal 3/1 結果、
sibling continuation、output collision、seed uniqueness、cancel/capacity lock
ordering、malformed queue/history 的 bounded slot retention/release、
secret-bearing failure persistence，以及 shared/custom/audited/Discord command
相容性。OpenSpec tasks 為 `30/33`：只有需要另行 CTY 核准的 live deployment/GPU E2E、
archive，以及 integrate/push 三個 gates 保持未勾選。本輪未呼叫 live Backend
或 ComfyUI、未提交 GPU job、未 restart/reload service、未釋放 ComfyUI 記憶體。

## 2026-07-24 Discord Bot 直呼本機生圖

新增 `discord-bot/`（discord.py），使用者用 `/draw` 從既有 style preset（含 profile 變體）選畫風、
填 prompt/寬/高/張數（1–8）後直接呼叫 backend 生圖，全程不經 LLM；`/result id:<job_id>` 反查並貼回圖。
Bot 只做互動↔HTTP 轉譯，生圖決策（prompt 合併、KSampler 參數、workflow）仍由 backend 端點負責，
**未改動 backend**。batch 經 compose `overrides.batch_size` 帶入；`/result` 以
`GET /api/gallery/?image_name=<job_id[:8]>` 撈回同 job 全部圖。指令只註冊到指定 GUILD_ID。
設計與計畫見 `docs/superpowers/{specs,plans}/2026-07-24-discord-bot*.md`。驗證：`discord-bot` pytest 全綠。

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
## 2026-07-24 成功出圖 Workflow 明確保存為 Style Preset

已完成 `save-successful-style-preset-workflow` 的 deterministic 實作。使用者明確指定一筆已成功、
且 Gallery 已記錄 `workflow_json` 的 image／image artifact／completed job 後，backend 會接受
LLM 提供的精簡正負關鍵字，只做逗號／換行切分、trim、去空值與保序去重；接著 deep-copy 原圖
的 ComfyUI API graph，沿 `KSampler`／`KSamplerAdvanced` conditioning links 泛用向上追蹤，
只替換實際正負 conditioning text semantics。直接字串留在原欄位替換；link-valued text 只在上游
Primitive／String carrier 有唯一字串欄位，且其全部 consumers 都是同 polarity 的 targeted text
input 時保留 link 並替換 carrier，其他情形拒絕而不猜。checkpoint、diffusion、多 loader 等不同
graph 形狀走同一條結構化路徑，沒有 preset／模型家族／template／node id／loader 數量分支。

Prompt confidentiality 以來源 `GeneratedImage`／`GeneratedArtifact` 同一筆 record 的非空
`prompt`／`negative_prompt`，加上原始 graph 中 sampler-linked target conditioning 在修改前的文字，
共同作 fail-closed evidence；因此即使 Gallery metadata 缺失，仍不會靜默關閉檢查。targeted
replacement 後會先從 evidence copy 清空已證明的 target conditioning／exclusive carrier，再遞迴
掃描完整其餘 graph（含 orphan encoder、metadata、mapping keys 與 nested values）；任一 exact full
source prompt 仍存在即回 `prompt_confidentiality_unproven`。這也允許使用者有意把 final prompt
設成與 source prompt 相同，因為合法 target carrier 不視為洩漏位置。系統不刪除或改寫其他洩漏
位置，所以無法在不動非 conditioning semantics 的前提下證明乾淨時，會在建立 temp file 前停止，
既有 target 也不會被取代。共用正負 encoder、找不到 conditioning、來源未完成、非圖片或無 graph
同樣回 `code + message + hint` 且不寫檔。

保存位置固定由 backend 推導為
`style_presets/agent/workflows/<preset-id>/<profile-or-__base__>.api.json`。內容只有 raw graph；
temporary file 完成 JSON parse-back 與 node shape 檢查後才以 `os.replace` 原子發布，後續明確保存
會直接取代同一路徑，不建立 hash、snapshot、manifest 或版本 registry。新增 save/raw GET/test
HTTP routes；test route 讀 server-owned graph 後走獨立 queue branch，送往 ComfyUI 的 graph 與
保存內容 deeply equal，不呼叫 `apply_params`、不注入 `1girl, solo`、seed、sampler、尺寸或資源。
此 branch 的 ComfyUI submit 若遇非 JSON 4xx `HTTPStatusError`、缺失／非字串／空白
`prompt_id`、malformed `node_errors` 或其他 exception，都會先釋放 `_running`、再以 best-effort
整理 node error 並記錄 terminal failed status，讓下一筆 pending 繼續；既有 custom／audited／
default 成功語意未改。Civitai Source Alias 行為未修改。Discord Bot 的 Style Preset Modal
現在分開預填完整 composed 正向／負向 Prompt，讓使用者送出前可查看與逐字修改；任一欄超過
Discord 4000 字限制即 fail-closed，不靜默截斷。提交時兩欄直接覆寫最終 generation payload，
不再次拼接 preset；空白 `content_prompt` sentinel 只用於通過 compose 輸入驗證，backend trim 後
不會進入最終 Prompt。

MCP 新增 `save_successful_workflow_as_style_preset` 與
`test_saved_style_preset_workflow`。前者 docstring 明訂只能在使用者明確要求、且已有成功結果時呼叫；
兩個工具只傳 short locator／keywords 或 preset／profile，不傳 graph，並穩定回傳 parseable JSON
與 backend repair hint。audited catalog 與兩份 MCP 文件已同步為 36 個意圖級工具。

### Deterministic 驗證

- Repair RED：confidentiality focused 為 `5 failed, 32 passed`，精確失敗在缺 source evidence、
  orphan／metadata 未拒絕、link carrier 被覆蓋及 unsafe consumer 未拒絕；queue focused 為
  `3 failed, 4 passed`，三種 submit exception 均直接穿出、未釋放 running slot。
- Self-review RED：metadata 包裹完整 source prompt 的 selector 為 `1 failed`；evidence gate 改為
  搜尋任一 graph string 是否包含整段 exact source prompt 後，納入下列 `37 passed` GREEN。
- Repair GREEN：save/API file `37 passed`；verbatim queue 加鄰近 custom／audited/default regression
  `34 passed`。5.1 focused backend（style presets、Gallery、queue、generate/recording）`158 passed`；
  5.2 focused MCP（style preset、catalog、latest-main LoRA tools）`33 passed`。
- Discord Bot 全套 `40 passed, 6 warnings`；包含 Style Preset/profile 完整正負 Prompt 預填、
  4000 字 fail-closed、逐字 payload 覆寫與 compose→generate contract。
- Catalog 獨立稽核：catalog 36、實際 registered 36、duplicates 0；README 與 mcp-setup marker
  區段各列全 36；latest-main 的 `lora_dataset_list`、`lora_dataset_inspect`、
  `lora_train_smoke_test` 三項均保留。
- 完整 MCP：`91 passed`。
- 完整 Backend：`1083 passed, 77 warnings`。
- 獨立 fail-closed review 找到兩個 release blocker：Gallery prompt metadata 缺失時 evidence gate
  可能退化，以及 malformed `prompt_id`／`node_errors` 可能佔住 queue slot。新增 6 個針對性
  測試先得到 `6 failed` RED；修正後 focused workflow save/retest 為 `52 passed`，再納入上述
  `1083 passed` 全套 GREEN。
- 真實產品 E2E：盤點 12 個正式 Style Preset、28 個 preset × profile；compose `28/28`、
  資源 preflight `12/12 valid`。每個 profile 都完成成功來源 materialization、raw workflow 保存與
  server-owned verbatim retest，最終 `BATCH_DONE=28`、`BATCH_FAILED=0`。使用者明確要求後，
  28 份均再經真實 FastMCP `save_successful_workflow_as_style_preset` 呼叫保存：`28/28 ok=true`，
  保存前後 workflow SHA-256 `28/28` 相同。固定 preset/profile 路徑共 28 份、無重複 key；
  臨時 `smoke-workflow-save-20260724` preset/workflow 已刪除並 reindex，正式 catalog 保持 12 個。
  Evidence 位於 `.hermes/evidence/style-preset-batch-20260724/`。
- OpenSpec：target strict valid；`openspec validate --all --strict` 為
  `13 passed, 0 failed`；`git diff --check` 通過。
## 2026-07-23 shampoohatslime Anima V1 訓練後八條件正式驗收完成

- 已實證 Anima 訓練完整跑完 8 epochs／1600 steps；Epoch 2、Epoch 4、Epoch 6 與 Final safetensors 均有永久外接碟權重、bytes 與 SHA-256 紀錄，且訓練證據確認為 DiT-only LoRA。
- 評測權重以不搬移原檔的方式註冊到外接碟 ComfyUI LoRA inventory；乾淨 Base 固定使用 `anima_baseV10` diffusion／text encoder 與 Qwen Image VAE，未疊加 Moonlit 推論 LoRA。
- 正式矩陣為 8 條件 × Emma／Karin／Kanata = 24 張：Base、Epoch 2／4／6、Final 0.5／0.7／1.0 與 Final 0.7 無 Trigger。固定 seed `3174638636`、1448×2048、30 steps、CFG 5.5、DPM++ 2M／normal；Trigger 為 `connexion`（控制組移除）。24 個 job 全部 completed，每個 job 僅採一個永久 `SaveImage` PNG，已排除 `PreviewImage` 重複 artifact；未做視覺評分、挑圖或因美觀重生。
- 每條件建立一份獨立 ZIP，共 8 包；每包正好含 `emma.png`、`karin.png`、`kanata.png`、`INDEX.txt`、`MANIFEST.json`。8 包皆通過 entry-count、`testzip`、SHA-256 與 `<10 MiB` 驗證；本輪原圖直接打包即符合限制，未需重新壓縮。最終 job/result/effective-payload master manifest 與交付驗證保存在外接碟指定輸出目錄。
- 全程未直接修改 DB、Gallery 或 queue internals，也未卸載 ComfyUI 模型；先前 7 組檔案保留，但此 8 組版本為正式交付。

### 測試產物整理

- Git 收錄初始 7 條件／21 張的歷史可續跑與封裝工具：
  `scripts/run_anima_v1_initial_7_matrix.py`、
  `scripts/package_anima_v1_initial_7_matrix.py`；檔名與 module docstring 明確標示不包含後補的 Epoch 2。
- 最終 8 條件／24 張的 authoritative manifest 位於外接碟
  `training/lora/output/style_shampoohatslime-first50-anima-v1-matrix-jobs-final-8-conditions.json`，
  8 個 ZIP 位於 `training/lora/output/shampoohatslime-anima-v1-comparison-by-condition-8/`。
- PNG、ZIP 與大型 JSON evidence 是實機產物，保留於 16TB 外接碟，不複製進 Git；repository 只保存可讀工具與驗收說明。

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
