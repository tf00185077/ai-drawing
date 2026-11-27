# Document map

## Start

- [README](../README.md) — what the system is, components, quick start
- [AGENTS.md](../AGENTS.md) — agent guide, conventions, verification
- [Project memory](memory/MEMORY.md) — durable facts for agents

## Product

| Topic | Document | State |
|---|---|---|
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) | current |
| Operating policy | [OPERATING-POLICY.md](OPERATING-POLICY.md) | current |
| Current state | [CURRENT.md](CURRENT.md) | current |
| Progress history | [PROGRESS.md](PROGRESS.md) | current |
| Decisions | [decisions/](decisions/) | current |
| Owner requests (verbatim) | [requests/](requests/) | current |
| Task specs | [tasks/](tasks/) (`p<phase>-<nn>-<name>/task.md`) | current |
| Roadmap | [roadmap/ROADMAP.md](roadmap/ROADMAP.md) | current |
| Setup | [setup.md](setup.md) | current |
| Civitai credentials | [civitai-credentials.md](civitai-credentials.md) — owner Mac key-file locator and safe loading | current |
| Phase 2 resource identity | [topic](resource-records.md), [decision](decisions/civitai-resource-record.md), [p2-02 acceptance](tasks/p2-02-resource-record/acceptance.md) | exact review10 PASS; Backend foundation accepted |
| Phase 2 download limits | [topic](civitai-downloads.md), [decision](decisions/civitai-download-limits.md), [acceptance](tasks/p2-03-bounded-download/acceptance.md) | exact review3 PASS; bounded stock execution accepted |
| Verification scope | [decision](decisions/verification-scope.md), [request](requests/2026-11-27-verification-reassessment.md) | owner-directed 2026-11-27; allowlist metadata, capped evidence |
| Phase 2 download jobs | [decision](decisions/civitai-download-jobs.md), [task](tasks/p2-04-durable-download-jobs/task.md), [owner checkpoint](tasks/p2-04-durable-download-jobs/owner-checkpoint-2026-11-27.md) | respecified 2026-11-27; fresh kickoff after p2-02a |
| Allowlist projection | [task](tasks/p2-02a-allowlist-projection/task.md) | independent kickoff dispatched to [QA AID-218](/AID/issues/AID-218) |
| MCP server | [mcp.md](mcp.md) | current |
| Prompt dashboard | [prompt-dashboard.md](prompt-dashboard.md) | current |
| Windows worker | [windows-worker.md](windows-worker.md) | current |
| LoRA training | [lora-training.md](lora-training.md) | current |

Source code and live API schemas (`/docs`, `/openapi.json` on a running Backend) are authoritative over prose.

## Team

- [Team guide](team/README.md) — roster, workflow, rules; [roles](team/roles/), [channel routing](team/channel-routing.md), [skill bindings](team/skill-bindings.md)

## History

Earlier history is in git; it is not needed to understand the current state.
