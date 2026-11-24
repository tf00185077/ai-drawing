# Task specification

## Task
Run the generate → retrieve → revise flow on the Mac with today's MCP tools and record every manual fix it needs.

## Purpose
Generation through MCP already works, but past runs needed repeated manual fixes because the project drifted over several iterations. Phase 1 must remove that friction ([ROADMAP Phase 1](../../roadmap/ROADMAP.md)), so it first needs the concrete list of where an agent gets stuck. The list sets what p1-01 to p1-04 must fix and is the baseline p1-05 is measured against.

## Outcome
A friction log: every step where the run needed a human, a retry, a workaround or a call outside MCP, with the tool involved and the cause.

## Scope
Included: the full Backend suite on the Mac first (moved here from p1-05); one agent run over stdio with the current tools: check the Backend → list resources → generate → poll → retrieve the image → generate a revision with `parent_artifact_id` → poll → retrieve; a friction log in `manifest.md`, one row per incident (step, tool, what happened, manual fix, likely cause, which p1 task should fix it).
Excluded: fixing anything found (later tasks fix it; a blocker is reported, not patched); Windows worker; aesthetic judgment.
Open questions: which checkpoint and template the run uses — CTY names one before the run (the same one is reused by p1-05).
Read first: [docs/mcp.md](../../mcp.md), [docs/setup.md](../../setup.md), [memory](../../memory/MEMORY.md).

## Done when
- [ ] The full Backend suite passes on the Mac with no failures or hangs. Check: the commands in AGENTS.md with `--timeout=60`. Evidence: summary line and duration.
- [ ] The run reaches a retrieved original and a retrieved revision, or stops at a documented blocker. Check: manual run. Evidence: the tool calls in order with their raw outputs and timestamps.
- [ ] Every manual step, retry, workaround and non-MCP call is in the friction log and mapped to a p1 task, or marked "new" with a proposed task. Check: manual (QA compares the log with the call transcript). Evidence: the log.
- [ ] The number of manual fixes is stated as the Phase 1 baseline. Check: manual. Evidence: the count in the manifest.

## Delivery
- Artifact: `manifest.md` with the suite result, the call transcript and the friction log; no code changes.
- Known limitations: one run on one template; friction that appears only with other templates is not covered.
