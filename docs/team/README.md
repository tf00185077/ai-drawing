# Team

AI Drawing is operated by a Paperclip company (`AID`) of AI agents. CTY is the owner. This page is the single team guide; role pages under [roles/](roles/) add per-role detail.

## Roster

| Role | State | Owns |
|---|---|---|
| [Producer](roles/producer.md) | Active | Intake, priorities, task specs, dispatch, reporting to CTY |
| [Coding agent](roles/platform-engineer.md) | Active | All software changes |
| [QA agent](roles/engineering-qa.md) | Active | Independent review of every software change |
| [Auto Dreamer](../../agents/auto-dreamer/AGENTS.md) | Active | Periodic memory cleanup |
| [Generation / workflow specialist](roles/generation-workflow.md) | Paused | Prompts, workflows, generation, workflow research |
| [LoRA training specialist](roles/lora-training.md) | Paused | Datasets, captions, training runs |
| [Art requirements designer](roles/art-specification.md) | Paused | Turning requests and feedback into briefs |
| [Environment / resource manager](roles/environment-resource-manager.md) | Paused | ComfyUI nodes, models, dependencies |

All roles report to Producer; Producer reports to CTY. Paused roles keep their identity and history and can be resumed by CTY.

## How work flows

1. **Intake** — requests arrive in the project Discord channel (see [channel routing](channel-routing.md)). Producer turns them into Paperclip issues.
2. **Plan** — Producer picks work from the [roadmap](../roadmap/ROADMAP.md) and [status](../STATUS.md), and writes a task spec in `docs/tasks/<task>/task.md` with a clear "Done when".
3. **Build** — the coding agent implements it on its own branch/worktree, with tests, and delivers `docs/tasks/<task>/manifest.md`.
4. **Review** — the QA agent reviews that exact commit independently and writes `docs/tasks/<task>/review.md`. Changes after review need a new review.
5. **Merge** — after a passing review, the change is merged to `main` and pushed.
6. **Report** — Producer posts the result in the project channel and moves to the next item without waiting for confirmation.

Art and LoRA work follow the same pattern with the matching specialist instead of the coding agent.

## Rules

- [Operating policy](../OPERATING-POLICY.md) defines what any agent may do.
- **Questions for CTY** go directly to the project channel. Ask only when a decision is CTY's (direction, aesthetics, architecture); otherwise decide and continue.
- **Aesthetics** — CTY alone judges style, image selection and training results. Technical checks do not imply artistic acceptance.
- **Workspaces** — the shared checkout stays on `main`. Engineering changes use a separate worktree. QA reviews a fixed commit, not a moving directory.
- **Memory** — any agent may add or fix entries in [project memory](../memory/MEMORY.md) when it learns a durable fact useful to future agents. No logs or incident history.
- **Reporting** — say what was actually verified (tests, running service, real generation, retrieved artifact) and what was not.

## Skills

Each active role loads shared skills from the owner's skill library; see [skill bindings](skill-bindings.md).
