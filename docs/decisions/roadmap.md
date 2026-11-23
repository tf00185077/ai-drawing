# Decisions · roadmap

## Settled
- Four goals in order: MCP for agents → prompt dashboard → LAN Windows workers → LoRA training · why: owner's product priorities · owner-confirmed
- Phase 0 (clean foundation) comes first · why: integration was frozen and docs were unusable · owner-confirmed
- Docs are English only and rebuilt from scratch · why: owner preference; AI translates on demand · owner-confirmed
- Nearly all operations are allowed by default · why: owner removed approval gates · owner-confirmed · [policy](../OPERATING-POLICY.md)
- The repo adapts to the `project-roadmap-steering` skill (ROADMAP, CURRENT, PROGRESS, requests, decisions), not the other way round · why: the skill is fixed · owner-confirmed
- Escalation thresholds: 3 non-advancing tasks in a row, a blocker over 2 days, or 3 review rejections of one task · owner-confirmed · [ROADMAP](../roadmap/ROADMAP.md#thresholds)
- Not now: non-Windows workers and paid cloud, workflow engines, UI redesign beyond Phase 2 · owner-confirmed · [ROADMAP](../roadmap/ROADMAP.md#not-now)
- No OpenSpec: task specs in `docs/tasks/<task>/task.md` are the only spec format; durable behavior rules live in the topic docs · owner-confirmed
- Paperclip team continues in lean form; all eight roles kept; Hermes delegated-decision flow removed; any agent may update memory · owner-confirmed · [team](../team/README.md)

## Log (newest first)

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

### 2026-11-23 · Queue limitations scheduled for Phase 3
- Decision: in-memory queue, one job at a time and persist-on-completion are marked "to optimize" and planned in Phase 3.
- Why: they block parallel workers.
- Supersedes: —
- Provenance: owner-confirmed@"以上要標記成待優化"
- Link: [ARCHITECTURE](../ARCHITECTURE.md#known-limitations-to-optimize)

## Open questions
- None.
