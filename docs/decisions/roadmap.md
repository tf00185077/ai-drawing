# Decisions · roadmap

## Settled
- Inside the existing project boundaries, Producer adopts routine recommended/reference options and proceeds after kickoff; ask CTY about boundary changes · why: avoid turning ordinary choices into new approval gates · owner-confirmed · [follow-through request](../requests/2026-11-24-proceed-within-project-boundaries.md)
- Core purpose: one sentence to an agent → Civitai resources found, downloaded and registered → matching workflow → image or short clip; consistent characters through owner-trained LoRAs · why: the project's original need · owner-confirmed
- Phase order: MCP basics → one-sentence image flow → LAN Windows workers → image-to-video clip → LoRA training → prompt dashboard · why: core before support, support before add-ons; video and LoRA need the NVIDIA worker · owner-confirmed
- Layers: core = MCP, Civitai tools and resource record, workflow selection, fixed image-to-video, LoRA training; support = Windows workers (Mac too slow); add-on = prompt dashboard · owner-confirmed
- This project provides Civitai search, download and registration tools through MCP, using the free public API; the agent decides what to search for · owner-confirmed
- Video scope: one fixed image-to-video workflow with frame interpolation · owner-confirmed
- Phase 0 (clean foundation) comes first · why: integration was frozen and docs were unusable · owner-confirmed
- Docs are English only and rebuilt from scratch · why: owner preference; AI translates on demand · owner-confirmed
- Nearly all operations are allowed by default · why: owner removed approval gates · owner-confirmed · [policy](../OPERATING-POLICY.md)
- The repo adapts to the `project-roadmap-steering` skill (ROADMAP, CURRENT, PROGRESS, requests, decisions), not the other way round · why: the skill is fixed · owner-confirmed
- Every phase states Role, Depends on, Scope, Remove, Unknowns, First check, Exit and Demo · why: the project drifted by adding without removing; each phase must also shrink what is outside its scope · owner-confirmed · [phase rules](../roadmap/ROADMAP.md#phase-rules)
- A phase exit needs 3 consecutive real runs with zero manual fixes (any human action, retry, workaround or non-MCP call) · why: past runs worked only after repeated manual fixes · owner-confirmed
- The owner reviews the roadmap at every phase close, before the next phase is activated · why: stop the roadmap drifting from the owner's intent · owner-confirmed
- Project memory follows the `project-memory-curation` skill shape (one question per topic: Context, Why, How to apply, Evidence, `curated_on`); outdated docs are distilled into memory and then trimmed to current facts; `.codex/` removed · why: old content misled agents about the current state · owner-confirmed
- Escalation thresholds: 3 non-advancing tasks in a row, a blocker over 2 days, or 3 review rejections of one task · owner-confirmed · [ROADMAP](../roadmap/ROADMAP.md#thresholds)
- Not now: non-Windows workers and paid cloud, workflow engines, UI redesign beyond the dashboard phase (now Phase 6) · owner-confirmed · [ROADMAP](../roadmap/ROADMAP.md#not-now)
- No OpenSpec: task specs in `docs/tasks/<task>/task.md` are the only spec format; durable behavior rules live in the topic docs · owner-confirmed
- Paperclip team continues in lean form; all eight roles kept; Hermes delegated-decision flow removed; any agent may update memory · owner-confirmed · [team](../team/README.md)

## Log (newest first)

### 2026-11-24 · Continue executable work after planning
- Decision: proceed with the existing Phase 1 scope and adopt routine reference options; preserve CLEAR kickoff and independent exact-commit delivery review. Boundary changes still go to CTY.
- Why: the owner explicitly authorized action after planning instead of waiting for ordinary-choice confirmation.
- Supersedes: the earlier planning-only intake framing and pending routine task-review/resource confirmation wait. It does not supersede phase scope/order, artistic acceptance or the phase-close review.
- Provenance: owner-confirmed@"跟producer補充，如果規畫完可以直接開工就開工，除非涉及專案邊界，不然若只有建議參考選項，直接用參考選項，然後完成時一併回報即可。" — authenticated board relay on AID-141, not an inferred response.
- Link: [owner request](../requests/2026-11-24-proceed-within-project-boundaries.md), [execution plan](../tasks/p1-planning-2026-11-24/plan.md)

### 2026-11-24 · Outdated docs distilled into memory
- Decision: facts a next agent needs were moved into 14 memory topics in the curation-skill shape; README goal, INDEX, PROGRESS (re-keyed by phase), team roster and the worker, Discord, workflow and style-preset READMEs trimmed to current facts; the 2026-11-23 rebuild plan and `.codex/` deleted.
- Why: old and superseded content led agents to misjudge the current state.
- Supersedes: the 2026-11-23 documentation rebuild plan (in git history).
- Provenance: owner-confirmed@"只保留結構，有關舊的或是過期的內容先進行整理後全部刪除，整理方法是，只保留有助於下次agent接手的事實" · @".codex整個資料夾刪掉"
- Link: [memory](../memory/MEMORY.md)

### 2026-11-24 · Phase rules
- Decision: every phase has Remove and First check fields; exits need 3 consecutive real runs with zero manual fixes; the roadmap is reviewed at each phase close. First checks added to Phase 5 (LoRA) and Phase 6 (dashboard); p1-05 now runs 3 times.
- Why: the project became cluttered over several iterations and runs needed repeated manual fixes.
- Supersedes: the open questions on measurable exit targets and on reviewing the roadmap at phase close.
- Provenance: owner-confirmed@"三個都寫進去"
- Link: [ROADMAP phase rules](../roadmap/ROADMAP.md#phase-rules)

### 2026-11-24 · Video split out of Phase 2
- Decision: Phase 2 ends at the image; image-to-video with interpolation becomes Phase 4, after workers. LoRA moves to Phase 5 and the dashboard to Phase 6. Order: P1 MCP → P2 one-sentence image → P3 workers → P4 clip → P5 LoRA → P6 dashboard.
- Why: the clip probably needs the NVIDIA machine; keeping it in Phase 2 could block that phase until workers exist.
- Supersedes: the same-day Phase 2 that included the fixed image-to-video workflow.
- Provenance: owner-confirmed@"拆，影片放在 workers 後"
- Link: [ROADMAP](../roadmap/ROADMAP.md)

### 2026-11-24 · macOS rerun moved to p1-00
- Decision: the macOS Backend rerun is the first step of p1-00 (friction run) instead of p1-05.
- Why: Phase 1 now starts with a real Mac run; the suite result should come before any code change.
- Supersedes: the same-day move into p1-05.
- Provenance: owner-confirmed@"你提到的都改"
- Link: [p1-00](../tasks/p1-00-mcp-friction-run-mac/task.md)

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
- Remove, rather than freeze, the video code outside the fixed image-to-video workflow? Frozen for now; decided in Phase 4 (its Remove field).
