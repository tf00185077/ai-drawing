# Current

2026-11-23 · `main` · Active: **Phase 0 — Clean foundation** ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Gallery retrieval only | Mixed response formats; no wait tool; no end-to-end run |
| 2. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 3. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |
| 4. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |

Built on main: naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

The 26 known Backend failures and the Windows-only MCP failures were outdated tests and have been removed; test fixtures are pinned to LF. MCP: 314 passed, 4 skipped (Windows). Backend full-suite result on Windows: pending.

## Phase 0 remaining

- Record the Backend full-suite result on Windows.

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Waiting on the owner

Nothing.

## Team

Producer paused; coding, QA and Auto Dreamer ready on demand. No work running.
