# Task specification

## Task
Prove the Phase 1 exit on the Mac: an agent generates, retrieves and revises an image through MCP alone.

## Purpose
All MCP behavior so far is verified with mocks. Phase 1 is done only when it works against a real ComfyUI ([ROADMAP Phase 1 exit](../../roadmap/ROADMAP.md)). The owner chose the Mac ComfyUI first; the Windows worker follows in Phase 2.

## Outcome
A script, and CTY in a demo, can run the full flow on the Mac and see the image, its revision and their Gallery records.

## Scope
Included: a repeatable script under `scripts/` that drives the MCP server over stdio: `health` → `list_resources` → `generate` → `wait_for_job` → `gallery_get` → `generate` with revision context (`parent_artifact_id`) → `wait_for_job` → `gallery_get`; a short run guide in `docs/mcp.md`.
Excluded: Windows worker runs (Phase 2); aesthetic judgment (CTY).
Open questions: which checkpoint and template the script uses on the Mac — CTY names one before the run.
Read first: p1-01 to p1-04 results, [docs/mcp.md](../../mcp.md), [docs/setup.md](../../setup.md).

## Done when
- [ ] The script completes on the Mac against the real Backend and ComfyUI and prints both artifact IDs and file paths. Check: manual run. Evidence: command, full output, timestamps.
- [ ] The revised image's Gallery record links to the first image as its parent. Check: manual (`gallery_get` output). Evidence: both records.
- [ ] No step needed a call outside MCP. Check: manual (QA reviews the script). Evidence: the script.
- [ ] CTY sees the demo and both images. Check: owner-demo. Evidence: CTY's reply in the project channel.

## Delivery
- Artifact: script, run guide, `manifest.md` with the run output.
- Known limitations: Mac only.
