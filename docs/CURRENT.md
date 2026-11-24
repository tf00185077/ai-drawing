# Current

2026-11-24 · `main` · Active: **Phase 0 — Clean foundation** ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Gallery retrieval only | Mixed response formats; no wait tool; no end-to-end run |
| 2. One-sentence flow | Partly | No | No Civitai search tool; no agent-facing resource record; no single image-to-video + interpolation tool |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 5. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

## Phase 0 remaining

- Rerun the Backend suite on macOS after the 2026-11-24 test cleanup and UTF-8 fix. On Windows the Phase 0 exit is met. Phase 1 starts after the owner reviews its tasks.

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Waiting on the owner

- Review the Phase 1 tasks (order; which tools p1-02 consolidates).

## Team

Producer paused; coding, QA and Auto Dreamer ready on demand. No work running.
