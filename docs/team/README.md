# Team

AI Drawing is operated by a Paperclip company (`AID`) of AI agents. CTY is the owner. This page is the single team guide; role pages under [roles/](roles/) add per-role detail.

## Roster

| Role | Owns |
|---|---|
| [Producer](roles/producer.md) | Intake, priorities, task specs, dispatch, reporting to CTY |
| [Coding agent](roles/platform-engineer.md) | All software changes |
| [QA agent](roles/engineering-qa.md) | Independent review of every software change |
| [Auto Dreamer](../../agents/auto-dreamer/AGENTS.md) | Periodic memory cleanup |
| [Generation / workflow specialist](roles/generation-workflow.md) | Prompts, workflows, generation, workflow research |
| [LoRA training specialist](roles/lora-training.md) | Datasets, captions, training runs |
| [Art requirements designer](roles/art-specification.md) | Turning requests and feedback into briefs |
| [Environment / resource manager](roles/environment-resource-manager.md) | ComfyUI nodes, models, dependencies |

All roles report to Producer; Producer reports to CTY. Which roles are active or paused is in [CURRENT](../CURRENT.md#team); paused roles can be resumed by CTY.

## How work flows

1. **Intake** — requests arrive in the project Discord channel (see [channel routing](channel-routing.md)). Producer opens Paperclip issues.
2. **Plan** — Producer picks work from the active milestone in the [roadmap](../roadmap/ROADMAP.md) and the [current state](../CURRENT.md), and writes a task spec in `docs/tasks/<task>/task.md` with a clear "Done when".
3. **Kickoff review** — the QA agent checks the task spec against CTY's request in the Paperclip issue; Producer dispatches once it returns CLEAR.
4. **Build** — the coding agent implements it on its own branch/worktree, with tests, and delivers `docs/tasks/<task>/manifest.md`.
5. **Review** — the QA agent reviews that exact commit independently and writes `docs/tasks/<task>/review.md`. Changes after review need a new review.
6. **Merge** — after a passing review, the change is merged to `main` and pushed.
7. **Record and report** — Producer updates [CURRENT](../CURRENT.md) and [PROGRESS](../PROGRESS.md), saves decisions to `docs/decisions/` and lessons to memory, posts the result in the project channel and moves to the next item without waiting for confirmation.

Art and LoRA work follow the same pattern with the matching specialist instead of the coding agent.

## Rules

- [Operating policy](../OPERATING-POLICY.md) defines what any agent may do.
- **Questions for CTY** go to the project channel through `paperclip-hermes-notify`, with options and a recommendation, when a decision changes the approved project scope, order, architecture or constraints. Under [CTY's current delegation](../requests/2026-11-26-phase-2-start-and-key-file.md), Producer adopts recommended options inside the accepted roadmap, verifies actual milestone/phase exit, records its roadmap review and continues when requirements are met; report choices with results instead of opening routine start/choice/phase-close approvals. Thresholds trigger reassessment and reporting; unresolved boundary decisions still go to CTY. Artistic judgment remains CTY's, and independent kickoff/delivery QA is unchanged.
- **Aesthetics** — CTY alone judges style, image selection and training results. Technical checks do not imply artistic acceptance.
- **Workspaces** — the shared checkout stays on `main`. Engineering changes use a separate worktree. QA reviews a fixed commit, not a moving directory.
- **Memory** — any agent may add or fix entries in [project memory](../memory/MEMORY.md) when it learns a durable fact useful to future agents. No logs or incident history.
- **Reporting** — say what was actually verified (tests, running service, real generation, retrieved artifact) and what was not.

## Skills

Each active role loads shared skills from the owner's skill library; see [skill bindings](skill-bindings.md).

## MCP calls

Use the current [MCP intent catalog and flow](../mcp.md). Every tool returns
`{ok, data}` on success or `{ok: false, error: {code, message, hint}}` on failure.
Read successful fields under `data`, and preserve job IDs for status checks
after timeouts. The accepted source replaces `mcp_ping` with `health` and adds
`list_workers` as read intents (31 total). Health retains all three component
entries on failed/partial reads; an unknown worker configuration returns an
error rather than an empty list. Configured identity and current accepted
observations remain distinct. Discovery controls/submits nothing and certifies
no worker model parity or generation readiness. Bounded `wait_for_job` retains
its existing result locators and 50-second overall fallback; the actual client
limit remains unverified. `job_status` and LoRA status remain separate reads.
The [p1-04 acceptance](../tasks/p1-04-mcp-health-and-workers/acceptance.md) records
independent exact-commit PASS and integration. Source availability does not
establish deployment or real-run proof.

Accepted [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md) adds optional
bounded canonical PNG bytes to the existing Gallery read and the strict Mac
SDK driver, preserving all 31 names/risks. Exact QA, three real zero-fix flows
and native fixed-demo owner acceptance are recorded separately. CTY has since
closed Phase 1 and activated the revised Phase 2; follow the current ROADMAP and
[Civitai key-file guidance](../civitai-credentials.md). Preserve runtime-source
and data boundaries.
