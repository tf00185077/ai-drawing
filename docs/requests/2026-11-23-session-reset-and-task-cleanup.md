# Owner request — fresh sessions, residual-task cleanup and main publication

Source: CTY, AI Drawing project Discord conversation, 2026-11-23.

## Exact owner wording

Earlier instruction:

```text
把這輪producer的工作暫停，若有程式碼修改就還原。
```

Latest instruction:

```text
將agent都重新建立新session並且paperclip現在有的任務殘留刪掉。然後將本機main推上遠端我同步進度
```

## Executed facts before publication

- The current Producer round and dependent QA were stopped. The native AID-4 task tree retains manual pause hold `604647da-c0ed-48c2-99f8-7cd4c8b3c23f`.
- Current-round AID-138 source and package-manifest commits were reverted without rewriting history. Rollback commit `aa7bd009bc8e5363b8632422e3baae78c55d8c54` restores the exact `cd92ad4d8b0ef74e8d8ce62b1d4770217fc4dc27` tree on that isolated branch. Canonical main was not changed by the candidate or rollback.
- The native session-reset API cleared all task-session continuations for the four roles discussed with CTY: Producer, coding agent, QA agent and Auto Dreamer. Their cleared counts were respectively 7, 43, 45 and 18. Readback confirmed no saved task sessions, null runtime session IDs and empty runtime state for each, with configurations and readiness unchanged. This prepares fresh sessions for their next actual assigned runs; it does not claim new provider threads have already started.
- No work was launched. No task or task attachment was deleted.

## Unresolved deletion scope

The live inventory contains 139 AI Drawing tasks: 17 unfinished and 122 done. The installed native delete route removes task attachments as well. AID-4 contains historical owner decisions and delivered-image records.

Hermes asked CTY to choose between: (1) deleting AID-135 through AID-139 plus blocked daily-curation residue while preserving AID-4 and earlier history; (2) deleting all 17 unfinished tasks, including AID-4 and its attachments; or (3) deleting all 139 AI Drawing tasks and their attachments. No answer was received before this publication. These are proposed scopes, not approved choices. Deletion remains pending; the session reset and requested main publication proceed independently.

## Publication scope

Publish this repository's existing main worktree documentation and role-binding changes plus the factual stop/reset status. Retain source code at the already-published checkpoint; do not merge the withdrawn candidate. No unrelated repository, agent identity, model, dataset, artwork, runtime secret or service configuration is part of the Git publication.
