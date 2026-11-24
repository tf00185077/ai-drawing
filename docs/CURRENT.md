# Current

2026-11-24 · `main` · Phase 0 done · Active: **Phase 1 — MCP that agents use smoothly**, Mac baseline repairs ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | One original generated; Gallery metadata | Runtime revision mismatch; byte retrieval/revision blocked; mixed responses; no wait tool |
| 2. One-sentence image flow | Partly | No | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

macOS, 2026-11-24: [p1-00](tasks/p1-00-mcp-friction-run-mac/manifest.md) full Backend suite `1900 passed, 124 skipped, 77 warnings in 43.84s`; independent [QA rerun](tasks/p1-00-mcp-friction-run-mac/review.md) `1900 passed, 124 skipped, 77 warnings in 44.13s`. Both exited 0 with `--timeout=60`; QA confirmed every skip requires Windows. Tests/skips were unchanged. No new full MCP, Frontend or Windows verification is claimed.

## Phase 0

Done 2026-11-24 (`1898378`).

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Next work

[Execution plan and native backlog](tasks/p1-planning-2026-11-24/plan.md), [AID-141](/AID/issues/AID-141). CTY's [later instruction](requests/2026-11-24-proceed-within-project-boundaries.md) authorizes executable work inside existing boundaries and delegates routine reference choices; no ordinary-choice confirmation is pending.

Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target for p1-00/p1-05. The exact small baseline model/graph/parameter combination completed a real local original; broader compatibility is unverified.

[Coding AID-148](/AID/issues/AID-148) delivered no-repair evidence commit `3081952`; [QA AID-149](/AID/issues/AID-149) independently returned [PASS for that evidence-only record](tasks/p1-00-mcp-friction-run-mac/review.md). Producer accepted the reviewed record and integrated its unchanged files plus QA's report/registry from `c377a02`. Baseline: **23 intervention units across eight incidents**, one completed original, Gallery metadata only, no retrieved image bytes or revision. The relative URL failed locally before HTTP; the live Backend lacks the current revision contract, and its loaded commit is unknown. No end-to-end success or phase exit is claimed.

[AID-142](/AID/issues/AID-142) coordinates bounded [p1-00a runtime/retrieval repair](tasks/p1-00a-mac-runtime-and-retrieval/task.md). [QA kickoff AID-150](/AID/issues/AID-150) returned [CLEAR](tasks/p1-00a-mac-runtime-and-retrieval/kickoff-review.md) for fixed specification `4ac3d5653d7bffee2698809d32d0f5ea0f506cbc`; Producer read the actual verdict and verified its official report/archive/patch against `9bd0029`. No specification change or owner answer is needed.

[Coding AID-151](/AID/issues/AID-151) is executing the repair on an isolated engineering branch from published `eaf11b8`; the task is unchanged from the cleared snapshot. [QA delivery AID-152](/AID/issues/AID-152) waits natively on Coding and reviews its exact final commit. Both native plans were read back and QA's prerequisite verified. AID-142 now waits on AID-152 and stays open through actual repair acceptance. AID-141 and AID-143 remain natively blocked by AID-142. Kickoff CLEAR does not satisfy the repair: decoded bytes and persisted lineage for a fresh original/revision pair are still required.

The existing sequence continues only after repair PASS: AID-143 (p1-01/02 ship together), AID-144 (wait), AID-145 (health/workers), AID-146 (three real Mac runs and demo). Exact-commit independent review precedes each software merge. Phase boundaries and exit rules are unchanged.

## Team

Coding is executing AID-151; QA completed AID-150 and next owns AID-152. Auto Dreamer is idle; other production specialists remain paused. Producer verified kickoff and native dispatch only in this follow-through, with no new software suite, service probe, generation or image-byte retrieval. No repair delivery has been accepted yet.
