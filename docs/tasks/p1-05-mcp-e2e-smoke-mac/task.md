# Task specification

## Task
Prove the Phase 1 exit on the Mac: an agent generates, retrieves and revises an image through MCP alone, with no manual fixes.

## Purpose
All MCP behavior from p1-01 to p1-04 is verified with mocks. Phase 1 is done only when the flow that needed manual fixes in [p1-00](../p1-00-mcp-friction-run-mac/task.md) runs cleanly against a real ComfyUI ([ROADMAP Phase 1 exit](../../roadmap/ROADMAP.md)). The owner chose the Mac ComfyUI first; the Windows worker follows in Phase 3.

## Outcome
A script, and CTY in a demo, can run the full flow on the Mac and see the image, its revision and their Gallery records, in 3 consecutive runs with zero manual fixes, against the p1-00 baseline ([phase rules](../../roadmap/ROADMAP.md#phase-rules)).

## Scope
Included: a repeatable script under `scripts/` that drives the MCP server over stdio: `health` → `list_resources` → `generate` → `wait_for_job` → `gallery_get` → `generate` with revision context (`parent_artifact_id`) → `wait_for_job` → `gallery_get`; the same checkpoint and template as p1-00; a short run guide in `docs/mcp.md`.
Excluded: Windows worker runs (Phase 3); aesthetic judgment (CTY).
Open questions: none (checkpoint and template are fixed in p1-00).
Read first: the p1-00 friction log, p1-01 to p1-04 results, [docs/mcp.md](../../mcp.md), [docs/setup.md](../../setup.md).

## Done when
- [ ] The script completes 3 times in a row on the Mac against the real Backend and ComfyUI, each run printing both artifact IDs and file paths; a failed run resets the count. Check: manual runs. Evidence: command, full output and timestamps of each run.
- [ ] In every run, the revised image's Gallery record links to the first image as its parent. Check: manual (`gallery_get` output). Evidence: both records.
- [ ] No step in any of the 3 runs needed a manual fix, a retry or a call outside MCP; every p1-00 friction item is listed as gone or explained. Check: manual (QA reviews the script and the p1-00 log). Evidence: the script and the checked list.
- [ ] CTY sees the demo and both images. Check: owner-demo. Evidence: CTY's reply in the project channel.

## Delivery
- Artifact: script, run guide, `manifest.md` with the output of all 3 runs and the friction comparison.
- Known limitations: Mac only; one template.
