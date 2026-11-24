# Current

2026-11-24 · `main` · Phase 0 done · Active: **Phase 1 — MCP that agents use smoothly**, real Mac smoke, demo and three-run exit proof next ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Original/revision bytes + lineage; colocated Mac host paths | Runtime/client setup and zero-intervention exit proof pending |
| 2. One-sentence image flow | Partly | No | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: common MCP envelopes and **31 intent tools**, including health/configured-worker visibility ([p1-04 acceptance](tasks/p1-04-mcp-health-and-workers/acceptance.md), feature `72f4834`, independent PASS `3422ccd`), plus bounded wait/results ([p1-03 acceptance](tasks/p1-03-mcp-wait-and-result/acceptance.md), feature `77e3e3c`, independent PASS `d088c32`); the earlier 29-tool consolidation ([combined acceptance](tasks/p1-01-mcp-response-envelope/acceptance.md), integration `7ba2059f7e46920eaf860e19e61aa84bae8bf02c`); naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

macOS, 2026-11-24: [p1-00](tasks/p1-00-mcp-friction-run-mac/manifest.md) full Backend suite `1900 passed, 124 skipped, 77 warnings in 43.84s`; independent [QA rerun](tasks/p1-00-mcp-friction-run-mac/review.md) `1900 passed, 124 skipped, 77 warnings in 44.13s`. Both exited 0 with `--timeout=60`; QA confirmed every skip requires Windows. Tests/skips were unchanged. That baseline ran no full MCP, Frontend or Windows suite.

Accepted repair `b6d5846`, [QA round 2 AID-154](/AID/issues/AID-154): reused independent [round-1](tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md) full Backend `1900 passed, 124 skipped, 76 warnings in 42.40s` and MCP `314 passed, 4 skipped in 1.10s`, exit 0 with isolated roots and `--timeout=60`. Round 2 verified source/test/root-input/package/platform equivalence and repeated the read-only schema audit; no extra suite/generation. Backend skips require Windows; MCP skips require exported HTTP fixtures. No new Frontend/Windows result.

Historical first candidate `b1082a8` (before correction), [independent QA AID-158](/AID/issues/AID-158): Backend **1900 passed, 124 Windows-only skips, 76 warnings in 42.93s**; MCP **458 passed, 2 unchanged optional smoke-export skips**, final restored run 1.81s; LoRA parity **5 passed**; extra QA boundary cases **15 passed**. All full suites used isolated roots and `--timeout=60`. The false-admin-read mutant also passes 458/2, so these green results do not satisfy p1-02 D2. No new Frontend/Windows/live-service/generation result. That first-round gap is resolved in the accepted corrected candidate below.

Accepted corrected feature `616f67f`, [independent QA round 2 AID-160](/AID/issues/AID-160): fresh Backend **1900 passed, 124 Windows-only skips, 76 warnings in 41.60s**; restored full MCP **460 passed, 2 unchanged optional smoke-export skips in 1.95s**; parity **5 passed**, extra boundaries **15 passed**. Full suites used isolated roots/`--timeout=60` and fresh Backend exports. The false-admin-read fault now fails both guards/full MCP; source is restored before GREEN. No prior Backend result was reused. Producer verified exact integration/documentation/publication, with no extra suite on identical code/test inputs. No new Frontend/Windows/live-service/generation result.

Accepted p1-03 `77e3e3c`, [independent QA AID-164](/AID/issues/AID-164): fresh Backend **1900 passed, 124 Windows-only skips, 76 warnings in 44.39s**; restored full MCP **540 passed, 2 unchanged optional smoke-export skips in 2.80s**; targeted wait **77 passed**, additional registered QA **28 passed**. Fresh Backend exports/pinned imports and `--timeout=60` are recorded. Seven meaningful faults fail and restore before GREEN; 13 QA registry rows retain all nine prior rows. Actual client limit remains **unverified**, with approved **50-second overall fallback**; short mocked deadlines include SDK/setup overhead and are not live client-limit measurements. Producer verified source/document/package/integration/publication, with no extra suite or live product/generation/retrieval run.

Accepted p1-04 `72f4834`, [independent QA AID-168](/AID/issues/AID-168): fresh final restored Backend **1916 passed, 124 Windows-only skips, 76 warnings in 42.21s**; full MCP **606 passed, two unchanged optional smoke-export skips in 3.27s**. Fresh Backend exports, pinned imports and --timeout=60 are recorded. Ten meaningful faults fail and restore before full GREEN; independent 51-call/107-GET probe and 28 fresh wait cases pass. All 13 earlier registry rows survive; three additions yield **16 active** items. No new Frontend/native Windows/runtime/generation/retrieval result. Producer verified official packages/Git/publication and unchanged reviewed inputs, without repeating full suites. Two affected documentation/catalog guards pass after topic status edits.

## Phase 0

Done 2026-11-24 (`1898378`).

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Next work

[Execution plan and native backlog](tasks/p1-planning-2026-11-24/plan.md), [AID-141](/AID/issues/AID-141). CTY's [later instruction](requests/2026-11-24-proceed-within-project-boundaries.md) authorizes executable work inside existing boundaries and delegates routine reference choices; no ordinary-choice confirmation is pending.

Producer adopted `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA, local target for p1-00/p1-05. The exact small baseline model/graph/parameter combination completed a real local original; broader compatibility is unverified.

[Coding AID-148](/AID/issues/AID-148) delivered no-repair evidence commit `3081952`; [QA AID-149](/AID/issues/AID-149) independently returned [PASS for that evidence-only record](tasks/p1-00-mcp-friction-run-mac/review.md). Producer accepted that unchanged record plus QA's report/registry `c377a02`. Baseline remains **23 intervention units across eight incidents**, one completed original and Gallery metadata only. At measurement time the relative URL failed locally before HTTP and the old Backend lacked the revision contract; its loaded commit remains unknown. Later repair evidence does not rewrite that no-repair result.

[AID-142](/AID/issues/AID-142) accepts the bounded [p1-00a repair](tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md) at **`b6d5846`** after [QA AID-154](/AID/issues/AID-154)'s independent [D1-D5 PASS](tasks/p1-00a-mac-runtime-and-retrieval/review.md). [Kickoff AID-150](/AID/issues/AID-150) cleared fixed spec `4ac3d56`; one [round-1 rejection](tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md) remains recorded. [Coding AID-153](/AID/issues/AID-153) corrected the complete startup-schema inventory, and QA repeated its read-only audit: all old values preserved, added training fields NULL, reservation table empty. Corrected delivery and QA report/evidence/registry `3d5d890` are integrated unchanged. No product/test source changed.

The identified Backend and configured Mac client completed a fresh original/revision pair with persisted canonical lineage and decoded bytes from unchanged returned host paths. The original used ComfyUI cache; proof is one colocated-client pair, with byte reads outside MCP disclosed. F4/F5/F8 are resolved for that boundary. F1/F2 environment binding, F3 response parsing, F6 polling and F7 visibility remain mapped to later Phase 1 work. No three-run exit or aesthetic/demo acceptance.

[QA AID-156](/AID/issues/AID-156) returned fresh [p1-01 CLEAR](tasks/p1-01-mcp-response-envelope/kickoff-review.md) and [p1-02 CLEAR](tasks/p1-02-mcp-tool-consolidation/kickoff-review.md) at fixed specification/source `496cee2`, report commit `9d79d20`. [AID-143](/AID/issues/AID-143) read the actual reports and verified all four official uploads, 29 indexed archive members, fixed snapshots and exact Git bytes. K2-1 is resolved at specification level: read-only composition rejects legacy `save_as`; returned fragments are saved through `prompt_write(save)` with existing concurrency/provenance. The [first ambiguity](tasks/p1-02-mcp-tool-consolidation/kickoff-review-round-1.md) and [clarification 1](tasks/p1-02-mcp-tool-consolidation/kickoff-clarification-1.md) remain intact. Accounting remains one kickoff ambiguity/clarification round 1/kickoff round 2; the first implementation delivery result is recorded below.

[Coding AID-157](/AID/issues/AID-157) delivered combined candidate `b1082a855a66eedba6a4f11fbd4fcec0e9e867ab`. [Independent QA AID-158](/AID/issues/AID-158) returned **p1-01 PASS / p1-02 FAIL**, exact report/evidence commit `1001586`. F2-1 (P1, D2) is a demonstrated test gap: the correct ComfyUI admin label can be changed to read while the full suite stays green and registered restart still sends its mocked HTTP request. Producer read both actual manifests/reports and mutation evidence, verified the official packages/Git identities and accepts the adverse finding. That first candidate was withheld pending correction; its exact historical reports/evidence remain in the accepted delivery.

[Coding AID-159](/AID/issues/AID-159) delivered [correction round 1](tasks/p1-02-mcp-tool-consolidation/repair-round-1.md) at **`616f67ff68fc27070e85861e94d70de1baf5082a`**. [Independent QA AID-160](/AID/issues/AID-160) returned fresh **p1-01 PASS / p1-02 PASS**, report/evidence/registry `28cd4512b8ec7d6594ec972ab81161b8c2d09d03`. The independent literal all-29 risk map now catches the demonstrated false label in catalog and real discovery. Producer read both actual manifests/verdicts and mutation/restoration proof, verified all official packages and integrates reviewed source/evidence unchanged. [Combined acceptance](tasks/p1-01-mcp-response-envelope/acceptance.md) records feature integration **`7ba2059f7e46920eaf860e19e61aa84bae8bf02c`**; [AID-143's publication ledger](/AID/issues/AID-143#document-plan) pins final published main. Cleared tasks/decisions stay unchanged; one p1-02 delivery rejection/correction round 1/review round 2 PASS is retained separately from kickoff/p1-00a history.

[QA AID-161](/AID/issues/AID-161) returned **p1-03 kickoff AMBIGUITY K3-1** at fixed `7a46cb7`, exact [report/evidence](tasks/p1-03-mcp-wait-and-result/kickoff-review-round-1.md) `b3276dc`. Producer verified the actual report/uploads/source shapes and adopted [clarification 1](tasks/p1-03-mcp-wait-and-result/kickoff-clarification-1.md): preserve real canonical identities and separate legacy image IDs; return a recoverable locator-unavailable error when generation cannot supply supported Gallery locators, retaining completed Backend status. Training output/smoke state stays truthful and separate. Original specification/report/evidence are preserved; one kickoff ambiguity is not an implementation rejection.

[QA AID-162](/AID/issues/AID-162) returned independent **p1-03 kickoff round-2 CLEAR** for fixed `522c2f10b550d90f7b88ab1a3c9d1f6352439c8e`, exact [report/evidence](tasks/p1-03-mcp-wait-and-result/kickoff-review.md) `3bbcb9cdd30397c497c71da50ce83482642302e7`. K3-1 is resolved at specification level; all five requirements are implementable/testable. Producer read the actual report and verified five official uploads, binary patch/bundle and 90 indexed payloads/92 archive members against hashes/Git. Clarified task SHA-256 remains `0d25f752ed4f17b28a01109c10c163e57532ae4b7e11832b8361f63a67af6688`; normative decision, original task/report/evidence and nine standing registry items are unchanged. QA's selected Backend 3 passed/one warning, MCP 19 passed and expanded isolated shape probe are source-contract evidence, not wait implementation or live proof.

[Coding AID-163](/AID/issues/AID-163) delivered exact `77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce`; [QA AID-164](/AID/issues/AID-164) independently returned [D1-D5 PASS](tasks/p1-03-mcp-wait-and-result/review.md), report/evidence/registry `d088c3258ab782623631d60daaaccc8ce6fcb6dc`. Producer read the actual manifest/report and verified ten official uploads, both binary patches/bundles and 465 indexed payloads against hashes/Git. Reviewed product/tests/manifest/evidence and QA report/registry are integrated unchanged; [acceptance](tasks/p1-03-mcp-wait-and-result/acceptance.md) and [publication ledger](/AID/issues/AID-144#document-plan) record the final main identity. One kickoff ambiguity/clarification 1/kickoff 2 CLEAR and delivery review 1 PASS with zero delivery rejections are preserved.

[QA AID-165](/AID/issues/AID-165) returned p1-04 kickoff **AMBIGUITY K4-1** at fixed `c70162d`, exact [report/evidence](tasks/p1-04-mcp-health-and-workers/kickoff-review-round-1.md) `3a980ec`. Producer read the actual report and verified all five official uploads and 59 indexed payloads against Git/hashes. [Clarification 1](tasks/p1-04-mcp-health-and-workers/kickoff-clarification-1.md) permits an additive extension of existing worker status and separates configured/expected identity from nullable current observations. Configured-down stays one entry; Backend-read failure is an error, never an inferred empty list. Original task/report/evidence remain intact. One kickoff ambiguity/clarification 1/next round 2 is separate from delivery rejections (zero).

[QA AID-166](/AID/issues/AID-166) returned independent **kickoff round-2 CLEAR** at fixed `5cf158b65d924a9508a3b5bfb7b47adb92eff7a1`, exact [report/evidence](tasks/p1-04-mcp-health-and-workers/kickoff-review.md) `e75a94ec63a507bac194b702a87eb369ea1ccb20`. K4-1 is resolved at specification level; all four requirements are implementable/testable. Producer read the actual report and verified five official uploads, exact patch/bundle and 78 indexed payloads/80 members against pinned Git. Cleared task/decision/clarification and original task/report/evidence remain unchanged; one kickoff ambiguity/clarification 1/round-2 CLEAR and zero implementation delivery rejections are retained. Fresh selected Backend 10/one warning, catalog 14 and 11-case/12-GET existing-route probe are offline source-contract evidence, not feature acceptance.

[Coding AID-167](/AID/issues/AID-167) delivered exact **72f483418524a613fb104b92ab483e39f7432bfc**; [QA AID-168](/AID/issues/AID-168) returned independent **D1-D4 PASS**, report/evidence/registry **3422ccda7a66514fe7dadf7d3c8785a5718ba472**. Producer read both actual deliverables and verified ten official uploads, both binary patches/bundles and all 455 indexed payloads against immutable Git. Reviewed product/tests/manifest/evidence and QA registry are integrated unchanged; [acceptance](tasks/p1-04-mcp-health-and-workers/acceptance.md) records behavior, tests and limits, and [AID-145's publication ledger](/AID/issues/AID-145#document-plan) pins final main. One kickoff ambiguity/clarification 1/round-2 CLEAR and delivery review 1 PASS with zero rejections remain.

[QA AID-169](/AID/issues/AID-169) completed p1-05 kickoff **AMBIGUITY** for fixed
`d95f1a3`, actual [report/evidence](tasks/p1-05-mcp-e2e-smoke-mac/kickoff-review-round-1.md)
`039c0aee181b2a78588f7b02cb89b575157c581f`. K5-1 identifies missing actual MCP
bytes; K5-2 identifies wait/preparation/zero-retry accounting. Producer read the
full report, verified five official uploads and all 83 indexed payloads/84 members,
and adopts [clarification 1](tasks/p1-05-mcp-e2e-smoke-mac/kickoff-clarification-1.md)
under delegated technical authority: bounded canonical static-PNG content on the
existing Gallery read intent, strict one submit/one bounded wait per image,
reset on every timeout/retry, and complete preparation/recovery/audit ledgers.
No owner rule or phase boundary is relaxed. Original task/report/evidence and
16 registry rows are preserved. One kickoff ambiguity event/two P1 findings,
clarification 1/next kickoff round 2; zero implementation delivery rejections.

Next: [Producer AID-146](/AID/issues/AID-146)'s native plan pins the clarified
published source and recipient for fresh independent round-2 kickoff of the
[refreshed p1-05 task](tasks/p1-05-mcp-e2e-smoke-mac/task.md). Actual CLEAR precedes
Coding and exact-final-commit delivery-QA dispatch. Gallery content remains a
specified target, not delivered or deployed. Source publication does not identify
loaded runtime/client contracts. Retain active runtime/private configuration and
canonical venvs. Illustrious/default, explicit local and no LoRA remain; four-step
512×512 smoke parameters are predeclared technical choices, not aesthetics or a
performance guarantee. Three real zero-intervention original/revision pairs,
actual MCP bytes/lineage, CTY's explicit demo reply and later phase-close roadmap
review remain unaccepted. Phase 2 is inactive; no routine owner confirmation.

## Team

Producer owns AID-146 and the bounded K5-1/K5-2 resolution; QA owns its completed
AID-169 report and the next independent fixed-source kickoff on a separate card.
Coding waits for actual CLEAR. Preserve AID-151's active runtime/worktree/private
configuration and canonical environments until a controlled reviewed replacement.
Auto Dreamer is idle; other specialists stay paused. This round integrates QA
report/evidence and specification/status documents only. QA's 32 selected MCP
passes and one Backend persisted-lineage fixture pass/one existing warning are
offline implementability checks. Producer performs document/source/evidence/Git
verification, without a new suite, live service probe/restart/deployment, generation
or live Gallery-byte retrieval.
