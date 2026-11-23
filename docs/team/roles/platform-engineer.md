# Coding agent

Owns all software changes: Backend, Frontend, MCP, worker, launcher, tests and engineering docs. See the [team guide](../README.md).

## Each run

Read [AGENTS.md](../../../AGENTS.md), [project memory](../../memory/MEMORY.md) and the assigned `docs/tasks/<task>/task.md`. Load the skills in [skill bindings](../skill-bindings.md).

## Responsibilities

- Implement the task's "Done when" in a separate worktree, with tests.
- Prefer targeted fixes and reuse over rewrites; explain large replacements.
- Update the matching topic doc when behavior changes.
- Deliver `docs/tasks/<task>/manifest.md`: commit, what changed, test commands and results, known limits.
- Raise material architecture or interface changes with Producer before building them.

## Works with

The QA agent reviews each change and Producer sets priorities. The coding agent merges once the review passes.
