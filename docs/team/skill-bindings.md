# Skill bindings

Active roles load skills from the owner's library at `/Users/tf00185088/Desktop/tim-project/my-skills` (unpinned local paths, so library edits apply on the next run). Every role also loads `paperclip` and `using-superpowers`.

| Role | Agent ID | Skills |
|---|---|---|
| Producer | `26a4b374-3863-4acc-a573-59800c29e4d3` | `project-roadmap-steering`, `task-spec-template`, `project-knowledge-capture`, `paperclip-task-handoff`, `paperclip-hermes-notify` |
| Coding agent | `d5b0a59f-7642-4691-ae18-dc4ef8d27e38` | `reviewspec-build`, `think-like-fable`, `reviewspec-core`, `paperclip-task-handoff` |
| QA agent | `55e4bdf2-712c-4555-8e71-2e7680597d63` | `reviewspec-review`, `reviewspec-core`, `paperclip-task-handoff` |
| Auto Dreamer | `ba0bd935-f3b8-4eaf-90dd-7225e87c6ba1` | `project-memory-curation` |

Library paths: `roles/producer/*`, `roles/coding/*`, `roles/review/*`, `roles/shared/reviewspec-core`, `roles/memory/project-memory-curation`, `roles/platforms/paperclip/*`, `cross-agent/.superpowers/skills/using-superpowers`.

Inspect live selections with `GET /api/agents/{agentId}/skills` on the Paperclip server.
