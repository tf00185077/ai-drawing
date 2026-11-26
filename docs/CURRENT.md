# Current

2026-11-27 · `main` · Phase 0 and Phase 1 done · **Phase 2 active: p2-02 review9 FAIL (outer ledger R1); correction9 next** ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Accepted p1-05: three real MCP byte/lineage pairs with zero flow interventions | Phase 1 closed 2026-11-26; client call limit still unverified (50 s fallback) |
| 2. One-sentence image flow | Partly | No | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

Built on main: bounded canonical PNG retrieval and the strict Mac smoke driver ([p1-05 acceptance](tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md), feature `91d6e37`, independent PASS `ade7814`, native owner demo accepted 2026-11-26); common MCP envelopes and **31 intent tools**, including health/configured-worker visibility ([p1-04 acceptance](tasks/p1-04-mcp-health-and-workers/acceptance.md), feature `72f4834`, independent PASS `3422ccd`), plus bounded wait/results ([p1-03 acceptance](tasks/p1-03-mcp-wait-and-result/acceptance.md), feature `77e3e3c`, independent PASS `d088c32`); the earlier 29-tool consolidation ([combined acceptance](tasks/p1-01-mcp-response-envelope/acceptance.md), integration `7ba2059f7e46920eaf860e19e61aa84bae8bf02c`); naming and per-run folders for LoRA, smoke tracking, revision context on generation, Gallery seed precision and routing fixes (integrated in `32b59fd`). Details per goal: [mcp](mcp.md), [prompt dashboard](prompt-dashboard.md), [Windows worker](windows-worker.md), [LoRA training](lora-training.md), [architecture limits](ARCHITECTURE.md#known-limitations-to-optimize).

## Tests

Windows, 2026-11-24: Backend 2018 passed, 6 skipped, no failures or hangs (about 5 minutes); MCP 314 passed, 4 skipped. Tests that failed or hung on Windows and did not test a feature (hardening, redaction, smoke reconciliation, legacy worker packaging, Argus) were removed. LoRA run files are now read as UTF-8, which fixed LoRA training start on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

macOS, 2026-11-24: [p1-00](tasks/p1-00-mcp-friction-run-mac/manifest.md) full Backend suite `1900 passed, 124 skipped, 77 warnings in 43.84s`; independent [QA rerun](tasks/p1-00-mcp-friction-run-mac/review.md) `1900 passed, 124 skipped, 77 warnings in 44.13s`. Both exited 0 with `--timeout=60`; QA confirmed every skip requires Windows. Tests/skips were unchanged. That baseline ran no full MCP, Frontend or Windows suite.

Accepted repair `b6d5846`, [QA round 2 AID-154](/AID/issues/AID-154): reused independent [round-1](tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md) full Backend `1900 passed, 124 skipped, 76 warnings in 42.40s` and MCP `314 passed, 4 skipped in 1.10s`, exit 0 with isolated roots and `--timeout=60`. Round 2 verified source/test/root-input/package/platform equivalence and repeated the read-only schema audit; no extra suite/generation. Backend skips require Windows; MCP skips require exported HTTP fixtures. No new Frontend/Windows result.

Historical first candidate `b1082a8` (before correction), [independent QA AID-158](/AID/issues/AID-158): Backend **1900 passed, 124 Windows-only skips, 76 warnings in 42.93s**; MCP **458 passed, 2 unchanged optional smoke-export skips**, final restored run 1.81s; LoRA parity **5 passed**; extra QA boundary cases **15 passed**. All full suites used isolated roots and `--timeout=60`. The false-admin-read mutant also passes 458/2, so these green results do not satisfy p1-02 D2. No new Frontend/Windows/live-service/generation result. That first-round gap is resolved in the accepted corrected candidate below.

Accepted corrected feature `616f67f`, [independent QA round 2 AID-160](/AID/issues/AID-160): fresh Backend **1900 passed, 124 Windows-only skips, 76 warnings in 41.60s**; restored full MCP **460 passed, 2 unchanged optional smoke-export skips in 1.95s**; parity **5 passed**, extra boundaries **15 passed**. Full suites used isolated roots/`--timeout=60` and fresh Backend exports. The false-admin-read fault now fails both guards/full MCP; source is restored before GREEN. No prior Backend result was reused. Producer verified exact integration/documentation/publication, with no extra suite on identical code/test inputs. No new Frontend/Windows/live-service/generation result.

Accepted p1-03 `77e3e3c`, [independent QA AID-164](/AID/issues/AID-164): fresh Backend **1900 passed, 124 Windows-only skips, 76 warnings in 44.39s**; restored full MCP **540 passed, 2 unchanged optional smoke-export skips in 2.80s**; targeted wait **77 passed**, additional registered QA **28 passed**. Fresh Backend exports/pinned imports and `--timeout=60` are recorded. Seven meaningful faults fail and restore before GREEN; 13 QA registry rows retain all nine prior rows. Actual client limit remains **unverified**, with approved **50-second overall fallback**; short mocked deadlines include SDK/setup overhead and are not live client-limit measurements. Producer verified source/document/package/integration/publication, with no extra suite or live product/generation/retrieval run.

Accepted p1-04 `72f4834`, [independent QA AID-168](/AID/issues/AID-168): fresh final restored Backend **1916 passed, 124 Windows-only skips, 76 warnings in 42.21s**; full MCP **606 passed, two unchanged optional smoke-export skips in 3.27s**. Fresh Backend exports, pinned imports and --timeout=60 are recorded. Ten meaningful faults fail and restore before full GREEN; independent 51-call/107-GET probe and 28 fresh wait cases pass. All 13 earlier registry rows survive; three additions yield **16 active** items. No new Frontend/native Windows/runtime/generation/retrieval result. Producer verified official packages/Git/publication and unchanged reviewed inputs, without repeating full suites. Two affected documentation/catalog guards pass after topic status edits.

Unaccepted p1-05 delivery `8736298`, [QA AID-172](/AID/issues/AID-172), report
`f510a0a`: fresh Backend **1916 passed/124 existing platform skips**; final restored
MCP plus six independent QA cases **669 passed/four existing optional skips**;
fresh Backend revision export **one passed**, current cross-layer consumers
**seven passed**, seven effective production faults RED/restored. Actual CLI
SIGINT probe demonstrates **R5-1 P1 D3 FAIL** despite those green suites.
D1 and recorded D2 pass independent checks; D4 stays unchecked. These results
are evidence for that rejected candidate, not accepted main or repaired software.

## Phase 0

Done 2026-11-24 (`1898378`).

Removed research data (`experiments/`, `research/`, `model_benchmarks/`); evidence will be rebuilt by testing after the code changes.

## Next work

**Phase 2 (active).** The [real First check is accepted](tasks/p2-00-civitai-first-check/acceptance.md)
after [AID-177 CLEAR](/AID/issues/AID-177), actual [Coding AID-178](/AID/issues/AID-178)
`0d571b7d571561ebdea34c959ed6f16e2db06953` and independent [QA AID-179](/AID/issues/AID-179)
`9caf92fefac6f30255bac528e3f4292f2c1bddf6` D1–D5 observation PASS. One safe
selected-version search → login-required free-key LoRA download → current
registration → Mac checkpoint+LoRA default_lora image completed. Resource 80
is the new 228,518,900-byte LoRA; 81 adopts the hash-matched existing Illustrious
checkpoint, without redownload/rename/overwrite. Job da6a825f, image 4463,
artifact **3878**; original [PNG](tasks/p2-00-civitai-first-check/evidence/original.png)
333,502 bytes, decoded MCP/Gallery proof and persisted/PNG/history graphs agree.
Actual triggers/manual parameters and nonzero LoRA loading are preserved.

This is **20 interventions**, not automated Phase 2 acceptance: 15 capability +
five recovery; separately 77 observation/work-block units with overlap explained.
14 provider requests, one submit, one wait, 42 same-ID status GETs; seven used
Civitai modules including a value type and 12 uncalled. Preserve all failed
operations. QA P2: five tokenizer before-run hashes were masked; other 787
Comfy and 137 Backend hashes/current-Git corroboration do not reconstruct them.
[Evidence decision](decisions/evidence.md) preserves ordinary source-path hashes
in future helpers. Baseline units differ from Phase 1's 23/eight incidents.

**Accepted: [p2-01 private key-file and credential-safe requests](tasks/p2-01-civitai-key-file/acceptance.md)**.
Coding AID-183 **2e3850307f767ec2be213781accde367f321dc1d**, corrected freeze
2491ceb7, after independent QA AID-184 **D1–D5 PASS**, report/evidence/registry
**155e2209a9910556dfa0255223a9b4a30f120d87**. Production source reads the private
file and enforces bounded stateless final-request credentials. Original R1/P1/D3
FAIL 301c5dee and first manifest/raw evidence remain unchanged; correction 1/
review 2 resolves it, with one delivery rejection retained. Kickoff 1 CLEAR and
task hash unchanged. All reviewed product/tests/evidence and QA's **22-row**
registry integrate exactly. Source publication is not runtime deployment.

QA freshly records Backend **1978 passed/124 existing skips**, MCP **666/four**,
exports 93/readers 73/wait 12/restored registry 412/restored feature 81; meaningful
faults fail then restore. Frozen Coding and independent source HEADs observe
anonymous 401 versus configured-file 307→200, no Cookie/Proxy-Authorization/key
outside permitted Authorization, closed responses and zero body-method calls.
Producer verifies 15 official uploads, 234/79 exact archive payloads, both bundles,
2436/2494 complete fingerprints and private-value exclusion; no new product suite,
live provider/service probe/restart/download/generation/live Gallery-byte read.
Failed attempts remain attributed in actual reports; no new skips or product fix
by QA/Producer. Preserve all runtime/private config/data and 13 memory edits.

**p2-02 review9 FAIL accepted:** [Coding AID-203](/AID/issues/AID-203) FINAL
**c01730db22cc91d64aa779550313c3125fd66355**, freeze5baa7cfa, received actual
[independent QA AID-204](/AID/issues/AID-204) [original R1 incomplete](tasks/p2-02-resource-record/review-round-9.md),
report/evidence **b58b6d2cd82a9b72b7c1d536c563e6052f38bef9**. Supplied QA8
unit/new-note/status cases now pass; R2-R4 and checked R5 bounds pass. The whole
public local ledger still exposes selected-provider AIR/filename assignments in
outer `air`/`local_path`, beside safe typed diagnostics. Eight complete traces
fail initially/confirmation; two useful controls pass,104 observations/16 exposed
phases. Exact old columns/metadata/notes remain. All synthetic, no actual key read.

Nine rejected deliveries/five distinct historical P1 findings/original R1 open.
[Correction9 reassessment](tasks/p2-02-resource-record/repair-round-9.md) retains
single-row/internal matching/path semantics, applies the shared complete-value
policy to the entire public ledger, and audits raw outer fields/actual consumers.
Real whole-response/fault/old-storage guards precede another delivery. Original
task/repairs1-8/CLEAR/bounds/current delegation stay unchanged; no routine owner
question or architecture/scope change. Separate Coding and exact QA10 follow;
Producer handles findings/acceptance, no product merge before independent PASS.

Rejected-source independent Backend6774/124 existing skips,MCP666/four,restored
4796,495 additional positives,fresh93/73/412/12/19/schema2 and25 progress cases/
180 observations pass.29 mutations/39 invocations/1577 feature assertions plus20
actual3s timeouts restore exactly. These are current-source observations, not
R1 acceptance or changed-source qualification. QA9's initial archive422/partial
saved uploads/verified original parts and corrected report packaging remain.
[Producer integrity](tasks/p2-02-resource-record/producer-correction9-integrity.json)
records28 official uploads and both exact declared-shallow restorations; current
14 shared memory bodies/statuses and distinct prior pins remain preserved.
Product/tests stay off main. No new Producer product suite/key/provider/service/
restart/download/register/generation/live Gallery bytes; remaining Phase2
jobs/budgets/hash/search/MCP/defaults/removals/automatic three different sentences/
fresh checkpoint+LoRA/CTY demo/exit remain pending. Source is not deployment.

## Team

Coding and independent QA completed their Phase 1 recipient-owned cards. Producer
owns reconciliation of AID-146 with CTY's published closeout and current start
direction, the real Phase 2 First check, and subsequent reviewed implementation.
No routine start/resource/phase-close confirmation is pending under that direction.
Other production specialists remain paused; retained runtime/worktrees/data and
concurrent shared-main edits are preserved. Actual execution and results belong
to the native task/run records, not an inference from the active roadmap label.
