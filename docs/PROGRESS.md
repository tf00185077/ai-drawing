# 進度追蹤

> **唯一來源**。完成的任務要同步修改這個文件（`docs/PROGRESS.md`），且不需同步改 README.md 或 AGENTS.md。
> 寫進度時以「人看得懂」為準：一項工作一段，講清楚做了什麼、為什麼、下一步；不要貼雜湊值稽核日誌。
> （2026-07-14 以前的稽核式進度原文保存在 `docs/archive/2026-07-legacy/PROGRESS-2026-07-14-audit-log.md`。）

---

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

**下一步（實機驗證清單）**：
- [ ] 啟動 backend + ComfyUI，用 MCP 實跑：`civitai_source_info(一張喜歡的圖)` →
      `civitai_generate_like(同圖, prompt="想要的主題")`，確認 4 張圖進 gallery。
- [ ] 實測缺模型情境：挑一張用未下載模型的圖 → 確認自動下載進外接硬碟 → installed 後
      重呼叫 generate_like 用上原模型。
- [ ] 若下載回 401/403，到 civitai.com 帳號設定產 API key 填入 `.env` 的
      `CIVITAI_AUTHORIZATION` 後重試。

---

## 已完成（時間倒序）

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
