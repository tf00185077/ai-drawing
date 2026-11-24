# Current

2026-11-24 · `main` · Phase 0 done · Active: **Phase 1 — MCP that agents use smoothly**, response envelopes and tool consolidation next ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Original/revision bytes + lineage; colocated Mac host paths | Mixed responses; no wait tool; zero-intervention exit proof pending |
| 2. One-sentence image flow | Partly | No | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

macOS, 2026-11-24: [p1-00](tasks/p1-00-mcp-friction-run-mac/manifest.md) full Backend suite `1900 passed, 124 skipped, 77 warnings in 43.84s`; independent [QA rerun](tasks/p1-00-mcp-friction-run-mac/review.md) `1900 passed, 124 skipped, 77 warnings in 44.13s`. Both exited 0 with `--timeout=60`; QA confirmed every skip requires Windows. Tests/skips were unchanged. That baseline ran no full MCP, Frontend or Windows suite.

Accepted repair `b6d5846`, [QA round 2 AID-154](/AID/issues/AID-154): reused independent [round-1](tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md) full Backend `1900 passed, 124 skipped, 76 warnings in 42.40s` and MCP `314 passed, 4 skipped in 1.10s`, exit 0 with isolated roots and `--timeout=60`. Round 2 verified source/test/root-input/package/platform equivalence and repeated the read-only schema audit; no extra suite/generation. Backend skips require Windows; MCP skips require exported HTTP fixtures. No new Frontend/Windows result.

## Phase 0

Done 2026-11-24 (`1898378`).

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Next work

[Execution plan and native backlog](tasks/p1-planning-2026-11-24/plan.md), [AID-141](/AID/issues/AID-141). CTY's [later instruction](requests/2026-11-24-proceed-within-project-boundaries.md) authorizes executable work inside existing boundaries and delegates routine reference choices; no ordinary-choice confirmation is pending.

Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target for p1-00/p1-05. The exact small baseline model/graph/parameter combination completed a real local original; broader compatibility is unverified.

[Coding AID-148](/AID/issues/AID-148) delivered no-repair evidence commit `3081952`; [QA AID-149](/AID/issues/AID-149) independently returned [PASS for that evidence-only record](tasks/p1-00-mcp-friction-run-mac/review.md). Producer accepted that unchanged record plus QA's report/registry `c377a02`. Baseline remains **23 intervention units across eight incidents**, one completed original and Gallery metadata only. At measurement time the relative URL failed locally before HTTP and the old Backend lacked the revision contract; its loaded commit remains unknown. Later repair evidence does not rewrite that no-repair result.

[AID-142](/AID/issues/AID-142) accepts the bounded [p1-00a repair](tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md) at **`b6d5846`** after [QA AID-154](/AID/issues/AID-154)'s independent [D1-D5 PASS](tasks/p1-00a-mac-runtime-and-retrieval/review.md). [Kickoff AID-150](/AID/issues/AID-150) cleared fixed spec `4ac3d56`; one [round-1 rejection](tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md) remains recorded. [Coding AID-153](/AID/issues/AID-153) corrected the complete startup-schema inventory, and QA repeated its read-only audit: all old values preserved, added training fields NULL, reservation table empty. Corrected delivery and QA report/evidence/registry `3d5d890` are integrated unchanged. No product/test source changed.

The identified Backend and configured Mac client completed a fresh original/revision pair with persisted canonical lineage and decoded bytes from unchanged returned host paths. The original used ComfyUI cache; proof is one colocated-client pair, with byte reads outside MCP disclosed. F4/F5/F8 are resolved for that boundary. F1/F2 environment binding, F3 response parsing, F6 polling and F7 visibility remain mapped to later Phase 1 work. No three-run exit or aesthetic/demo acceptance.

[QA AID-155](/AID/issues/AID-155) returned [p1-01 CLEAR](tasks/p1-01-mcp-response-envelope/kickoff-review-round-1.md) and [p1-02 AMBIGUITY](tasks/p1-02-mcp-tool-consolidation/kickoff-review-round-1.md) at fixed `d1ffb8d`. [AID-143](/AID/issues/AID-143) checked the actual reports/source and adopted [clarification 1](tasks/p1-02-mcp-tool-consolidation/kickoff-clarification-1.md): read-only composition rejects legacy `save_as`; saving returned fragments uses `prompt_write(save)` with existing revision/ETag semantics. Required MCP tests cover the no-write boundary, rejection and replacement save/conflict path. No Backend change; p1-01 task bytes and all eight friction mappings remain unchanged. One kickoff ambiguity/clarification round 1 is retained, with no implementation delivery/rejection. Fresh fixed-spec round-2 verdicts are required before Coding, which has not been released. Both changes ship together after exact-commit PASS; wait, health/workers and three real Mac runs/demo retain their native sequence. Phase scope/order/exit and delegated routine-choice authority are unchanged.

## Team

Producer coordinates p1-01/02 kickoff round 2 under AID-143 (recipient/review links in its native plan); the adverse first review is complete on QA's own card. Retain the active AID-151 worktree/private configuration and canonical Backend venv until reviewed deployment replaces that runtime; publishing docs does not relabel the recorded launch source. Auto Dreamer is idle; other production specialists remain paused. This round checks actual kickoff uploads/source, records the bounded clarification and prepares fresh independent review; no software suite, live product probe, restart, generation or live image-byte read.
