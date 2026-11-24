# Current

2026-11-24 · `main` · Phase 0 done · Active: **Phase 1 — MCP that agents use smoothly**, kickoff and Mac baseline ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Gallery retrieval only | Mixed response formats; no wait tool; no end-to-end run |
| 2. One-sentence image flow | Partly | No | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

macOS not rerun since the cleanup; that run is the first step of [p1-00](tasks/p1-00-mcp-friction-run-mac/task.md).

## Phase 0

Done 2026-11-24 (`1898378`).

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Next work

[Execution plan and native backlog](tasks/p1-planning-2026-11-24/plan.md), [AID-141](/AID/issues/AID-141). CTY's [later instruction](requests/2026-11-24-proceed-within-project-boundaries.md) authorizes executable work inside existing boundaries and delegates routine reference choices; no ordinary-choice confirmation is pending.

Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target for p1-00/p1-05. Backend and Mac ComfyUI list the checkpoint; real compatibility is still unverified.

QA kickoff [AID-147](/AID/issues/AID-147) is first; after CLEAR, Producer [AID-142](/AID/issues/AID-142) dispatches the Mac Backend suite and today's MCP generate/retrieve/revise friction baseline. No fixes inside the baseline. Native sequence then continues through AID-143 (p1-01/02 ship together), AID-144 (wait), AID-145 (health/workers), AID-146 (three real Mac runs and demo). Exact-commit independent review precedes each software merge. Phase boundaries and exit rules are unchanged.

## Team

Producer resumed; Coding and Auto Dreamer idle. QA kickoff is the first released assignment; other production specialists remain paused. This planning round checked source and live read-only health/resources, and dispatched the kickoff path. No suite rerun, real generation or new artifact retrieval is claimed yet.
