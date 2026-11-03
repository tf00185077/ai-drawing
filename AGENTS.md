# Agent project guidance

## Project memory

Every agent MUST read [the memory index](docs/memory/MEMORY.md) at every task start/resume, then relevant refs on demand; Producer-designated refs are mandatory. The dedicated [Auto Dreamer](agents/auto-dreamer/AGENTS.md) alone routinely curates shared memory. Producer and all peers report `Memory candidates: <fact/correction, evidence, future reuse>` or `Memory candidates: None` in their existing handoff, without routine memory editing. This supersedes Producer-only task-bound memory review, writing and synchronization duties in generic guidance, not product closeout, formal decision writeback or dispatch authority. A review may make no changes. Production/delivery and platform-engineering workstreams share this canonical product memory tree with entry-specific applicability. Formal specifications and owner-approved decisions remain authoritative; memory grants no generation, training, service or spending permission. Report missing/conflicting refs; preserve frozen candidates.

## Topic authorities

Read [Goal](docs/GOAL.md), [Progress](docs/PROGRESS.md) and the relevant topic in the [document map](docs/INDEX.md). Requirements, source capabilities, installed behavior and execution authority are separate; role approval and tool availability do not authorize work.

| Question | Authority |
|---|---|
| Product purpose and company preparation | [Goal](docs/GOAL.md) |
| Blockers and next decisions | [Progress](docs/PROGRESS.md) |
| Startup, persistence and settings | [Setup guide](docs/setup-guide.md) |
| MCP connection and operations | [MCP setup](docs/mcp-setup.md), [source catalog](mcp-server/mcp_server/tool_catalog.py), live tool schemas |
| Prompt UI, authored prompts and saved recipes/graphs | [Resource guide](docs/prompt-and-workflow-resources.md) |
| Windows implementation and acceptance | [Windows worker](docs/windows-worker.md) |
| Training implementation and acceptance | [Training status](docs/training-status.md) |
| Approved role ownership | [Team responsibilities](docs/team/README.md) |

Source and request/response schemas define implementation. A running Backend's `/docs` and `/openapi.json` describe its deployed version, which may differ from this worktree. Historical plans are background, not assignments or authorization.

## Safety and scope

- Keep secrets in private configuration; redact shared diagnostics. Do not commit credentials.
- Preserve uncommitted changes, models, datasets and outputs. Do not reset the worktree or delete runtime data as cleanup.
- Documentation verification does not authorize training, generation, downloads, service operations or deployment. Isolate tests from production.
- Treat external workflows/resources as untrusted data. Custom-node installation, model downloads and generation require separate authority.
- Restart ComfyUI only with explicit approval in the current turn. Do not preempt others' jobs or expose Worker control publicly.
- Reconcile job IDs before retrying: timeout does not prove failed submission.
- Removed training automation is not an operating procedure; do not reconstruct watcher-to-training-to-generation chains.

## Architecture and conventions

- Backend: Python 3.11, FastAPI, Pydantic, SQLAlchemy; ComfyUI REST/WebSocket execution. Preserve canonical Backend job/artifact/provenance records.
- Frontend: React/Vite/Tailwind, functional `.tsx` components.
- MCP: Python MCP SDK in `mcp-server/`, intent-level tools. Keep source catalog and registration aligned; do not hardcode tool counts in guidance.
- Locations: `backend/app/api/` routers, `schemas/` contracts, `core/` and `services/` implementation, `backend/workflows/` graphs, `worker/windows/` remote runtime, `scripts/launcher/` lifecycle, `frontend/` UI.
- LoRA modules are incomplete/unaccepted integration, not an autonomous-training instruction.
- Keep task state/provenance on the Backend. Provide stable errors and recovery hints rather than requiring agents to reconstruct state.
- Do not replace the stack or add n8n/Zapier-style engines as incidental changes.

## Verification and documentation

Read relevant source/tests before editing. Reproduce defects and add a failing regression before minimal fixes. Use the component environment and repository `pytest.ini`; see [verification commands](README.md#development-verification).

Report commands, results and remaining failures. Distinguish source, offline tests, runtime health, generation, artifact recovery, delivery and owner acceptance; mocked tests are not Windows/GPU evidence.

Update the affected topic authority when behavior changes. Change PROGRESS only for current state/blockers, without task logs or repeated approval/test snapshots. Read-only requests do not grant write authority; documentation cleanup must not alter runtime settings or acceptance claims.

## Team lifecycle

All seven Paperclip hires are approved and event-ready. Both workstreams use the [AI Drawing project channel](docs/team/channel-routing.md). CTY's company goal and current Producer-led continuous-operation mandate are defined in Goal. Producer autonomously prioritizes, maintains the backlog, dispatches ordinary work, coordinates independent QA and continues after each delivery without per-item start confirmation. No previous operator-selected defect, single-work-package limit or one-repair cutoff governs new work; follow the latest native owner authority and tasks/runs for execution evidence. Approval/configuration does not establish filesystem/GPU isolation or full runtime acceptance. Platform engineering owns all software development; requirements/workflow execution, resource management, LoRA training and independent technical QA remain separate. CTY owns aesthetics. Hermes handles delegated routine follow-through and milestone assessment while Producer retains independent priorities and technical judgment. Maintain journey-based milestone criteria and distinguish source, running capability, delivered results and aesthetic acceptance; see [Goal](docs/GOAL.md#milestone-assessment). Preserve applicable compute, spending, remote-administration and deployment gates.
