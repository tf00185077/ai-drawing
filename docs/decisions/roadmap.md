# Decisions · roadmap

## Settled
- Core purpose: one sentence to an agent → Civitai resources found, downloaded and registered → matching workflow → image or short clip; consistent characters through owner-trained LoRAs · why: the project's original need · owner-confirmed
- Phase order: MCP basics → one-sentence flow → LAN Windows workers → LoRA training → prompt dashboard · why: core before support, support before add-ons · owner-confirmed
- Layers: core = MCP, Civitai tools and resource record, workflow selection, fixed image-to-video, LoRA training; support = Windows workers (Mac too slow); add-on = prompt dashboard · owner-confirmed
- This project provides Civitai search, download and registration tools through MCP, using the free public API; the agent decides what to search for · owner-confirmed
- Video scope: one fixed image-to-video workflow with frame interpolation · owner-confirmed
- Phase 0 (clean foundation) comes first · why: integration was frozen and docs were unusable · owner-confirmed
- Docs are English only and rebuilt from scratch · why: owner preference; AI translates on demand · owner-confirmed
- Nearly all operations are allowed by default · why: owner removed approval gates · owner-confirmed · [policy](../OPERATING-POLICY.md)
- The repo adapts to the `project-roadmap-steering` skill (ROADMAP, CURRENT, PROGRESS, requests, decisions), not the other way round · why: the skill is fixed · owner-confirmed
- Escalation thresholds: 3 non-advancing tasks in a row, a blocker over 2 days, or 3 review rejections of one task · owner-confirmed · [ROADMAP](../roadmap/ROADMAP.md#thresholds)
- Not now: non-Windows workers and paid cloud, workflow engines, UI redesign beyond the dashboard phase (now Phase 5) · owner-confirmed · [ROADMAP](../roadmap/ROADMAP.md#not-now)
- No OpenSpec: task specs in `docs/tasks/<task>/task.md` are the only spec format; durable behavior rules live in the topic docs · owner-confirmed
- Paperclip team continues in lean form; all eight roles kept; Hermes delegated-decision flow removed; any agent may update memory · owner-confirmed · [team](../team/README.md)

## Log (newest first)

### 2026-11-24 · Phase 0 closed; macOS rerun moved to p1-05
- Decision: Phase 0 is done on the Windows test result; the macOS Backend rerun becomes part of p1-05 (real Mac smoke).
- Why: the Windows exit is met, and p1-05 already runs on the Mac.
- Supersedes: "Rerun the Backend suite on macOS" as Phase 0 remaining work.
- Provenance: owner-confirmed@"先 commit、Mac 重跑併入 p1-05"
- Link: [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md)

### 2026-11-24 · Roadmap rebuilt around the one-sentence flow
- Decision: Destination rewritten around the original need; new Phase 2 "one-sentence flow" (Civitai search/download/register tools, resource record, workflow selection, one fixed image-to-video workflow with interpolation); LoRA training is core and moves ahead of the dashboard. Order: P1 MCP → P2 one-sentence flow → P3 workers → P4 LoRA → P5 dashboard.
- Why: the roadmap had lost the original purpose; the free Civitai public API covers search, version details, image metadata, hash lookup and downloads (API key only for login-required files); LoRA training was always meant to keep characters and styles consistent.
- Supersedes: 2026-11-23 order MCP → workers → dashboard → LoRA; the earlier view that this project does not connect to Civitai.
- Provenance: owner-confirmed@"Civitai的API在免費情況下支援這些功能嗎?支援的話我會想完善" · @"一個固定的 image-to-video workflow，要包含補偵" · @"LoRA訓練是我一開始想配合圖片固定腳色風格設計的，算是核心" · phase placement and LoRA-before-dashboard chosen in session
- Link: [ROADMAP](../roadmap/ROADMAP.md)

### 2026-11-23 · Workers before dashboard
- Decision: phase order is MCP (1) → LAN Windows workers (2) → prompt dashboard (3) → LoRA (4).
- Why: owner reprioritized.
- Supersedes: MCP → dashboard → workers → LoRA.
- Provenance: owner-confirmed@"1->3->2->4，修改一下順序。"
- Link: [ROADMAP](../roadmap/ROADMAP.md)

### 2026-11-23 · OpenSpec removed
- Decision: delete `openspec/` and its skills; keep verified behavior rules in ARCHITECTURE, mcp, prompt-dashboard and lora-training docs.
- Why: two spec systems overlapped and the July specs had drifted from the code.
- Supersedes: —
- Provenance: owner-confirmed@"不用openspec，把相關內容中有用的事實留下並移動到正確位置，剩下內容都刪掉"
- Link: [INDEX](../INDEX.md)

### 2026-11-23 · Thresholds and Not now approved
- Decision: adopt the proposed thresholds and Not now list.
- Why: completes the roadmap.
- Supersedes: the 2026-11-03 thresholds.
- Provenance: owner-confirmed@"照提案採用"
- Link: [ROADMAP](../roadmap/ROADMAP.md)

### 2026-11-23 · Repo follows the fixed roadmap-steering skill
- Decision: keep `docs/CURRENT.md` (one screen) and `docs/PROGRESS.md`; STATUS.md removed.
- Why: the skill reads these paths and will not change.
- Supersedes: the separate STATUS.md introduced earlier the same day.
- Provenance: owner-confirmed@"project-roadmap-steering是不會動的，要改動的話以這邊改動為主。"
- Link: [CURRENT](../CURRENT.md)

### 2026-11-23 · Phase 0–4 roadmap accepted
- Decision: adopt the Phase 0–4 milestones; Phase 0 active.
- Why: follows the owner's goal order.
- Supersedes: the M1/M2 roadmap of 2026-11-03 (in git history).
- Provenance: owner-confirmed@"可以，進第 6 項"
- Link: [ROADMAP](../roadmap/ROADMAP.md)

### 2026-11-23 · Queue limitations scheduled for the workers phase
- Decision: in-memory queue, one job at a time and persist-on-completion are marked "to optimize" and planned in the workers phase (now Phase 3).
- Why: they block parallel workers.
- Supersedes: —
- Provenance: owner-confirmed@"以上要標記成待優化"
- Link: [ARCHITECTURE](../ARCHITECTURE.md#known-limitations-to-optimize)

## Open questions
- Measurable exit targets per phase (for example success rate of the one-sentence flow over N runs) — proposed, not yet set.
- Review the roadmap whenever a phase closes — proposed, not yet adopted.
- Remove, rather than freeze, the video code outside the fixed image-to-video workflow? Frozen for now.
