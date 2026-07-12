# Civitai Recipe Reproduction — Product Specification

## Goal
讓 ai-drawing MCP 能從 Civitai 公開圖片 URL／ID 取得可稽核的生成配方，按精確版本與 SHA-256 對應本機資源，判定可重現等級，並以 ComfyUI 建立、執行及保存可重跑 workflow。

## Roles and control plane
- JUDGE：OpenAI Codex `gpt-5.6-sol`，規劃、review、驗收。
- EXECUTOR：OpenAI Codex `gpt-5.6-terra`，依 stage spec 實作；不得 commit。
- deterministic dispatcher：唯一可轉換 state、執行 validators 與 commit 的角色。
- 每 stage：READY → RUNNING → AWAITING_REVIEW → ACCEPTED → validators → COMMITTED。

## Reproduction levels
- `exact_ready`：完整 workflow、精確資源 hash、必要輸入與依賴均確認。
- `workflow_ready_but_runtime_may_differ`：完整／可重建 workflow，但 runtime 或未鎖定節點版本可能造成差異。
- `approximate_only`：只能做品質／風格近似。
- `not_reproducible`：缺少關鍵資源、metadata 或依賴。

## Functional requirements
1. 解析 Civitai image/post/model/CDN URL 與純 ID；取得 Images API `withMeta=true`，保留 raw payload。
2. 解析 PNG/JPEG/WebP embedded metadata；未知欄位不得丟棄。
3. 建立 versioned `GenerationRecipe`：source、resources、sampling、passes、control inputs、detailers、postprocess、raw/confirmed/inferred/missing。
4. 以 model/version/file ID、AIR、SHA-256 對應本機資源；strict mode mismatch 必須 fail closed。
5. 支援 checkpoint、VAE、embedding、多 LoRA 順序與 model/clip 雙權重、clip skip、hires/upscale/detailer/control units。
6. Civitai importer、inspector、resolver、validator、workflow builder、run/export 需由 backend API 與 MCP tools 暴露。
7. Gallery 保存完整 recipe snapshot、workflow、所有輸入 SHA、資源 lock、runtime provenance；可 export/rerun。
8. 先支援 SDXL／Illustrious recipe reconstruction，再擴充其他 model family；不假裝未知 workflow 已精確還原。
9. 下載需續傳、原子 rename、SHA 驗證、scan/license/availability 診斷；不得輸出 token。
10. 每張 runtime smoke 圖完成後交付 CTY；只標示原圖／參考圖／結果、流程類型、控制來源與路徑。除非 CTY 明確要求，不做圖片分析或合格判定。

## Non-functional requirements
- TDD；backend/MCP tests 全過。
- 不破壞既有 generate/gallery/rerun/style preset/MCP contract。
- 外部 HTTP fixture 可離線重跑；429/5xx 有 bounded retry/backoff。
- 大 seed 使用 64-bit-safe persistence。
- 完整 raw metadata 與 normalization provenance 可稽核。
- runtime smoke 前先確認 ComfyUI health；只做低成本 smoke，完成後不主動 free memory。

## Completion gate
- 所有 task specs committed。
- `pytest backend/tests/ mcp-server/tests/ -x -q` 通過。
- contract tests、Civitai fixtures、hash mismatch、multi-LoRA roundtrip、hires multi-pass、pose/control rerun 均有證據。
- 以至少一張有 metadata 的公開 Civitai 圖完成 import → resolve → workflow → ComfyUI smoke → gallery export。
- CTY 收到每張 smoke 圖，但視覺是否採用由 CTY決定。
