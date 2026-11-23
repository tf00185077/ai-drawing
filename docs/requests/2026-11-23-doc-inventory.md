# Documentation inventory and rebuild plan (Phase 0)

> Status: working plan. Existing docs are rebuilt from scratch, one group at a time, after discussion with the owner.

## Owner decisions (2026-11-23)

- Documentation is **English only**. Users ask an AI to translate when needed.
- Content is **rebuilt from scratch**, not edited in place.
- Team and governance docs: discuss which meaningful parts to extract before writing.
- Project memory keeps **only facts valuable to future agents**; running logs and incident residue are deleted.
- ComfyUI restart and custom-node installation are **allowed by default**.

## Current reading chain (before rebuild)

```
CLAUDE.md ─► AGENTS.md ─┬─► docs/agent-reading.md   (role reading rules, skill bindings)
README.md ─(parallel)─┐ ├─► docs/memory/MEMORY.md   (17 entries)
                      │ ├─► docs/GOAL.md            (product goal + company/role preparation)
                      └►├─► docs/INDEX.md           (document map)
                        ├─► [Producer only] ROADMAP.md, CURRENT.md, PROGRESS.md
                        ├─► topic docs: setup-guide, mcp-setup, prompt-and-workflow-resources,
                        │               windows-worker, training-status
                        └─► docs/team/ (README, roles/*, skill-bindings, channel-routing)
```

Other document groups:

| Group | Location | Size | Nature |
|---|---|---|---|
| Historical plans/designs | `docs/superpowers/` | 35 files, ~700 KB | July implementation plans |
| OpenSpec | `openspec/changes/` (7), `openspec/specs/` | 157 + 14 files | Worker/LoRA changes, status unclear |
| Root spec | `SPEC.md` | 1 | Civitai recipe reproduction; linked from nowhere |
| History | `PROGRESS.md`, `progress/`, `checkpoints/`, `decisions/`, `tasks/`, `archive/` | many | Governance/acceptance history |
| Root scratch | `tmp_*.py`, `tmp_*.json` | 18, tracked | Video experiment scratch |
| Other | `roadmap.tsx`, `resource_inventory_models.json` at root; `pipeline/` | — | Unclear ownership |

## Problems

1. Entry docs lead with governance (role reading rules, Paperclip, approvals) instead of what the system is and how to run it.
2. The same rules are repeated in 4–5 places.
3. Status docs depend on Paperclip (31 `127.0.0.1:3100` links) and internal record jargon.
4. Docs describe accepted candidates that are not in main.
5. Permission rules are scattered and conflict with the new default-open decision (`AGENTS.md`, `mcp-setup.md`, `team/roles/generation-workflow.md`).
6. Three spec systems coexist: `SPEC.md`, `openspec/`, `docs/superpowers/`.
7. Memory is mostly process/incident lessons.
8. No architecture document.

## Target structure

```
README.md             what it is, components, quick start, doc links
AGENTS.md             agent essentials: layout, conventions, policy, verification
CLAUDE.md             pointer to AGENTS.md
docs/
  INDEX.md            document map
  ARCHITECTURE.md     components and data flow
  OPERATING-POLICY.md single permission/safety policy
  STATUS.md           plain per-pillar status (replaces CURRENT.md)
  roadmap/ROADMAP.md  Phase 0–4 after discussion
  setup.md, mcp.md, prompt-dashboard.md, windows-worker.md, lora-training.md
                      fixed sections: Purpose → Usage → Status → Verified → Gaps
  team/               extracted governance essentials (after discussion)
  memory/             pruned
  history/            PROGRESS, checkpoints, decisions, tasks, superpowers, archive
```

## Discussion order

| # | Item | State |
|---|---|---|
| 1 | Entry: README / AGENTS / CLAUDE / INDEX | Done |
| 2 | OPERATING-POLICY | Adopted |
| 3 | ARCHITECTURE | Done |
| 4 | STATUS | Done (Mac pushed candidates to main as 32b59fd) |
| 5 | ROADMAP | Done |
| 6 | Five topic docs | Draft written, under review |
| 7 | Team/governance | Pending |
| 8 | Memory pruning | Done (Paperclip card entry waits for item 7) |
| 9 | Specs and history consolidation | Pending |
