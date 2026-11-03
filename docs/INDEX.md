# Document map

- [Project memory](memory/MEMORY.md) — durable key facts and reusable knowledge; Auto Dreamer-curated, read by every agent at task start/resume.
- [Auto Dreamer memory ownership](../agents/auto-dreamer/AGENTS.md) — sole routine curator for both workstreams; Producer and peers supply evidence-backed candidates or `None`.

## Current project facts and use

Planning reads are role-scoped: [Producer](team/roles/producer.md#required-roadmap-steering-skill) must load `project-roadmap-steering` and read `docs/roadmap/ROADMAP.md` and `docs/CURRENT.md` at every planning turn and task start/resume, using PROGRESS only for relevant history. Follow the skill's proposal/escalation rules if planning documents are missing or incomplete; paths listed here are not a claim of existence or owner approval. Other workers use their assigned task contract and its named specifications/evidence, plus shared startup and role authorities. Universal memory-index reads and Auto Dreamer's relevant-evidence access remain unchanged; planning/history files are not universal startup prerequisites.

- [Goal and approved preparation](GOAL.md)
- Producer direction/work-selection rules: `docs/roadmap/ROADMAP.md`
- Producer present-state summary, blockers and next decisions: `docs/CURRENT.md`, backed by named native task/decision records
- [Relevant history](PROGRESS.md), not a universal startup read
- [Setup, persistent data and configuration](setup-guide.md)
- [MCP connection and source-supported tools](mcp-setup.md)
- [Prompt Workbench, authored prompts and saved workflow resources](prompt-and-workflow-resources.md)
- [Windows worker source behavior and unresolved recovery](windows-worker.md)
- [Training implementation status — not an automation runbook](training-status.md)
- [Approved team responsibilities and lifecycle](team/README.md)
- [AI Drawing channel binding, handoff and native decision writeback](team/channel-routing.md)

Source/API schemas define behavior, role contracts define ownership and owner approval grants execution authority. Documentation does not verify the installed Windows host or authorize deployment.

## Conditional technical references

- [Artifact recovery and runtime preflight evidence](archive/staged-delivery/references/runtime-preflight-and-existing-artifact-recovery.md)
- [Backend queue observation](archive/staged-delivery/references/ai-drawing-backend-head-of-line-blocking.md) and [submission evidence](archive/staged-delivery/references/backend-queue-submission-evidence-addendum.md)
- [Native Discord engineering reference](archive/discord-menu-engineering/INDEX.md)

Case references are diagnostic background, not current bug/runtime evidence or authorization. `superpowers` designs are historical inputs, not tasks; verify them against source. Removed training manuals and superseded Worker/updater plans are not operating instructions.
