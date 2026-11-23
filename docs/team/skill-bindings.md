# Live role skill bindings

## Canonical sources

The maintained library is `/Users/tf00185088/Desktop/tim-project/my-skills`. Paperclip selects the role packages below as unpinned `local_path` sources: `sourceRef` and each selected `versionId` are null. Each selected agent explicitly binds its own `CODEX_HOME` under the company's `agents/<agentId>/codex-home/`; the native adapter mounts direct symlinks from that home's `skills/` to these live directories. This avoids the installed adapter's legacy shared-company skill directory. A local source update is read on the next applicable read or invocation; there is no maintained company snapshot to refresh.

Source folders are registered as non-primary workspaces in both AI Drawing projects. The primary product workspace remains this repository on `main`. Historical registrations remain available for history; current assignments use the exact keys below. Keep the source directory available rather than relying on a missing-source fallback.

## Role selections

All four roles also select native `paperclip` and live `using-superpowers`.

| Native role | Agent ID | Role methods |
| --- | --- | --- |
| Producer | `26a4b374-3863-4acc-a573-59800c29e4d3` | `project-roadmap-steering`, `task-spec-template`, `project-knowledge-capture`, `paperclip-task-handoff`, `paperclip-hermes-notify` |
| coding agent | `d5b0a59f-7642-4691-ae18-dc4ef8d27e38` | `reviewspec-build`, `think-like-fable`, `reviewspec-core`, `paperclip-task-handoff` |
| QA agent | `55e4bdf2-712c-4555-8e71-2e7680597d63` | `reviewspec-review`, `reviewspec-core`, `paperclip-task-handoff` |
| Auto Dreamer — AI Drawing | `ba0bd935-f3b8-4eaf-90dd-7225e87c6ba1` | `project-memory-curation` |

The QA agent is the independent Review role named by the role methods. The coding and QA agent IDs retain their existing task histories and reporting chain. Producer's decision capture and memory-candidate handoff follow this product's existing Auto Dreamer curation ownership.

## Package locators

Paths in this table are relative to the maintained library.

| Skill | Live path | Selected native key |
| --- | --- | --- |
| project-roadmap-steering | `roles/producer/project-roadmap-steering` | `local/73a2838ea9/project-roadmap-steering` |
| task-spec-template | `roles/producer/task-spec-template` | `local/3738ff7bad/task-spec-template` |
| project-knowledge-capture | `roles/producer/project-knowledge-capture` | `local/0dad6908b8/project-knowledge-capture` |
| reviewspec-build | `roles/coding/reviewspec-build` | `local/2669205ded/reviewspec-build` |
| think-like-fable | `roles/coding/think-like-fable` | `local/07394234c0/think-like-fable` |
| reviewspec-review | `roles/review/reviewspec-review` | `local/03bae80c28/reviewspec-review` |
| reviewspec-core | `roles/shared/reviewspec-core` | `local/b5c8352f68/reviewspec-core` |
| project-memory-curation | `roles/memory/project-memory-curation` | `local/0227820119/project-memory-curation` |
| paperclip-task-handoff | `roles/platforms/paperclip/paperclip-task-handoff` | `local/e2764893ae/paperclip-task-handoff` |
| paperclip-hermes-notify | `roles/platforms/paperclip/paperclip-hermes-notify` | `local/f27fd42f75/paperclip-hermes-notify` |
| using-superpowers | `cross-agent/.superpowers/skills/using-superpowers` | `local/3884ffd975/using-superpowers` |

Native `paperclip` uses `paperclipai/paperclip/paperclip` from `/Users/tf00185088/Desktop/tim-project/paperclip/skills/paperclip`.

## Runtime entry

Each role's Paperclip-managed `AGENTS.md` reads its canonical product role contract and these live methods at task start/resume. Current selections can be inspected through `GET /api/agents/{agentId}/skills`; resolved source files through `GET /api/companies/{companyId}/skills/{skillId}/files?path=SKILL.md`. Match actual run mounts and source reads when assessing runtime adoption.

CTY's [activation request](../requests/2026-11-23-role-skills-and-first-reasoning.md) selects Producer, coding agent, QA agent and Auto Dreamer. Other specialist identities and histories are retained while paused. Timed heartbeats remain off; the four selected roles accept native on-demand work. Producer makes the first project-work assessment through its assigned native task.
