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
- **Questions for CTY** go to the project channel through `paperclip-hermes-notify`, with options and a recommendation. Ask when a milestone looks done, when work falls outside the active milestone or would change the roadmap, when a roadmap threshold is reached, or when the approved scope, architecture or constraints would change. Otherwise decide and continue; finish in-flight work while waiting.
- **Aesthetics** — CTY alone judges style, image selection and training results. Technical checks do not imply artistic acceptance.
- **Workspaces** — the shared checkout stays on `main`. Engineering changes use a separate worktree. QA reviews a fixed commit, not a moving directory.
- **Memory** — any agent may add or fix entries in [project memory](../memory/MEMORY.md) when it learns a durable fact useful to future agents. No logs or incident history.
- **Reporting** — say what was actually verified (tests, running service, real generation, retrieved artifact) and what was not.

## Skills

Each active role loads shared skills from the owner's skill library; see [skill bindings](skill-bindings.md).
