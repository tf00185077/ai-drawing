# Current

2026-11-24 · `main` · Phase 0 done · Active: **Phase 1 — MCP that agents use smoothly**, Mac baseline repairs ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Fresh original/revision bytes + lineage verified on unaccepted repair | Runtime inventory incomplete (D5); mixed responses; no wait tool |
| 2. One-sentence image flow | Partly | No | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

macOS, 2026-11-24: [p1-00](tasks/p1-00-mcp-friction-run-mac/manifest.md) full Backend suite `1900 passed, 124 skipped, 77 warnings in 43.84s`; independent [QA rerun](tasks/p1-00-mcp-friction-run-mac/review.md) `1900 passed, 124 skipped, 77 warnings in 44.13s`. Both exited 0 with `--timeout=60`; QA confirmed every skip requires Windows. Tests/skips were unchanged. That baseline ran no full MCP, Frontend or Windows suite.

Unmerged repair candidate `00ebb4d`, [QA AID-152](/AID/issues/AID-152): independent full Backend `1900 passed, 124 skipped, 76 warnings in 42.40s` and MCP `314 passed, 4 skipped in 1.10s`, both exit 0 with isolated roots and `--timeout=60`. Backend skips require Windows; MCP skips require separately exported HTTP fixtures. Product/test source is unchanged. D4 passes, but the delivery fails D5; no new Frontend/Windows result is implied.

## Phase 0

Done 2026-11-24 (`1898378`).

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Next work

[Execution plan and native backlog](tasks/p1-planning-2026-11-24/plan.md), [AID-141](/AID/issues/AID-141). CTY's [later instruction](requests/2026-11-24-proceed-within-project-boundaries.md) authorizes executable work inside existing boundaries and delegates routine reference choices; no ordinary-choice confirmation is pending.

Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target for p1-00/p1-05. The exact small baseline model/graph/parameter combination completed a real local original; broader compatibility is unverified.

[Coding AID-148](/AID/issues/AID-148) delivered no-repair evidence commit `3081952`; [QA AID-149](/AID/issues/AID-149) independently returned [PASS for that evidence-only record](tasks/p1-00-mcp-friction-run-mac/review.md). Producer accepted that unchanged record plus QA's report/registry `c377a02`. Baseline remains **23 intervention units across eight incidents**, one completed original and Gallery metadata only. At measurement time the relative URL failed locally before HTTP and the old Backend lacked the revision contract; its loaded commit remains unknown. Later repair evidence does not rewrite that no-repair result.

[AID-142](/AID/issues/AID-142) coordinates bounded [p1-00a runtime/retrieval repair](tasks/p1-00a-mac-runtime-and-retrieval/task.md). [QA kickoff AID-150](/AID/issues/AID-150) returned [CLEAR](tasks/p1-00a-mac-runtime-and-retrieval/kickoff-review.md) for fixed specification `4ac3d5653d7bffee2698809d32d0f5ea0f506cbc`; Producer read the actual verdict and verified its official report/archive/patch against `9bd0029`. No specification change or owner answer is needed.

[Coding AID-151](/AID/issues/AID-151) delivered runtime/client-configuration/docs-only candidate `00ebb4d`; it remains **unmerged**. [QA delivery AID-152](/AID/issues/AID-152#comment-c64c55d7-ac7c-4849-94cf-8447f62d3e2b) returned **FAIL: D1-D4 PASS, D5 FAIL**. QA independently verified the identified Backend, unmodified returned host-path consumption/decoded bytes, fresh pair and persisted canonical lineage. The cached original and colocated-client limit remain disclosed.

D5's inventory omits eight nullable training columns and the empty `lora_output_reservations` table added by existing startup code. QA found all old values preserved; Producer verified the official report/audit against startup source. [Delivery correction 1](tasks/p1-00a-mac-runtime-and-retrieval/repair-round-1.md), fixed at `c41815c`, stays under unchanged original D5; no product change, restart or extra generation is indicated. [Coding AID-153](/AID/issues/AID-153) owns that correction; [QA round 2 AID-154](/AID/issues/AID-154) waits natively on Coding and reviews its exact final candidate. Both saved native plans and the QA prerequisite were read back. This is one delivery rejection, below the owner escalation threshold. AID-142 now waits on AID-154; AID-141/AID-143 remain gated until actual repair acceptance.

The existing sequence continues only after repair PASS: AID-143 (p1-01/02 ship together), AID-144 (wait), AID-145 (health/workers), AID-146 (three real Mac runs and demo). Exact-commit independent review precedes each software merge. Phase boundaries and exit rules are unchanged.

## Team

Coding and QA completed delivery/review round 1; Coding owns AID-153 and QA next owns AID-154. Retain the active AID-151 worktree and canonical Backend venv until reviewed deployment replaces that runtime; correction uses a separate worktree. Auto Dreamer is idle; other production specialists remain paused. Producer inspected delivered documents/audits and verified correction dispatch only this round, with no new software suite, live probe, generation or live image-byte read. Repair acceptance remains pending.
