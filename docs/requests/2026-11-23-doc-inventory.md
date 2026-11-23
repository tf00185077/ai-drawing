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
  CURRENT.md          one-screen current state (format set by project-roadmap-steering)
  PROGRESS.md         history with links
  decisions/, requests/ decisions log and owner words verbatim
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
| 4 | CURRENT (was STATUS) | Done; per-goal detail moved into topic docs |
| 5 | ROADMAP | Done |
| 6 | Five topic docs | Done |
| 7 | Team/governance | Done; aligned with project-roadmap-steering |
| 8 | Memory pruning | Done (Paperclip card entry waits for item 7) |
| 9 | Specs and history consolidation | Done; OpenSpec dropped (facts moved to topic docs); PROGRESS table done |

## Item 9 proposal — specs and history

Everything removed stays recoverable from git history.

| Group | Size | Used by code/tests? | Proposal |
|---|---|---|---|
| `openspec/specs/` (14 specs) | — | Yes: Backend modules cite them as contracts | **Keep** as the spec system; link from INDEX |
| `openspec/changes/` (6 open changes + 23 archived) | ~0.8 MB total | No | **Archive** finished changes (`harden-lora-training-start-contract`); list the other 5 in CURRENT as open spec work |
| `.codex/`, `.agents/`, `.claude/` skills | — | OpenSpec tooling | **Keep** |
| `SPEC.md` + `pipeline/` | 3 KB + 72 KB | No | **Delete**: Civitai autopilot with a separate JUDGE/EXECUTOR dispatcher, superseded by the Paperclip team |
| `docs/superpowers/` | 0.7 MB | No | **Delete**: July implementation plans, already built |
| `.superpowers/sdd/` | 38 KB | No | **Delete**: old worker-updater task reports |
| `engineering/aid56-method/` | 1.8 MB | No | **Delete**: maintenance-method evidence |
| `tools/m1_bounded`, `tools/m2_sqlite`, `tools/g09_isolated` | ~0.2 MB | No | **Delete**: maintenance controls |
| `tools/offline_pytest.py`, `verify_offline.py`, `isolation_checks.py` | small | Yes: Backend/Discord test support | **Keep** |
| `docs/checkpoints/` | 0.75 MB incl. zip | No | **Keep** `2026-11-23-progress-consolidation.md/.json` (linked from CURRENT/PROGRESS); **delete** the rest |
| `docs/archive/`, `docs/tasks/2026-11-23-m1-gallery-checkpoint/` | 0.13 MB | No | **Delete** (keep `docs/tasks/REGISTRY.md`, generated by the review skill) |
| `docs/progress/` (old PROGRESS files) | 50 KB | No | **Keep** as linked history from PROGRESS |
| `docs/GOAL.md`, `docs/decisions/m1-source-integration.md` | 20 KB | No | **Delete** GOAL (replaced by README goals and ROADMAP destination); mark the old decision file outdated |
| `docs/requests/` older files | small | No | **Keep** (owner words) |
| `experiments/` | 41 MB | `.dockerignore` only | **Keep**, documented in INDEX as workflow research for the generation specialist |
| `research/`, `model_benchmarks/` | 2.4 MB | No | **Keep**, documented in INDEX with `experiments/` |
| `dist/` (built worker package + zip) | 0.4 MB | No | **Delete** and add to `.gitignore`; `scripts/build-windows-worker.py` rebuilds it |
| `roadmap.tsx` | 16 KB | No | **Delete**: early roadmap UI mock |
| `resource_inventory_models.json` | 64 KB | No | **Delete**: stale model inventory snapshot |
| Root `tmp_*.py`, `tmp_*.json` (18) | — | No | **Delete**: video experiment scratch |
