Verdict: PASS
Review round: 2

Independent QA [AID-175](/AID/issues/AID-175), 2026-11-24 UTC. **Technical PASS for original D1–D3 and correction 1 only. D4 is UNCHECKED / pending Producer and CTY owner-demo.** This is not whole-task acceptance, aesthetic approval, Phase 1 closure or Phase 2 activation.

Reviewed full immutable candidate **91d6e3790ecbb258b1a079395a1156912d090b62**, tree **967e24606eb257b51c859fe1fd3c42a6597bdc4d**, against repair base **f510a0afde938671f43b590c66d9885507dd7046**, tree **5518a4351e056150a67ba42c26b7c8b56add0b5c**. Software frozen before renewed qualification: **e7819bcc02ceadc0dafad6d77a634618b5bfc02f**. All 291 frozen source fingerprints equal the final candidate. Candidate and cleared hashes were pinned on the card before substantive review: pin receipt. QA used its own persistent `aid-175-exact-review` worktree at `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-175-qa`.

## Findings

No blocking defect demonstrated in the reviewed candidate. **R5-1 / P1 / D3 is resolved at this SHA.** The prior FAIL remains valid for its old candidate; review-round-1.md and manifest-delivery-1.md are byte-identical historical mirrors. QA made no product repair.

## Done when assessment

| Item | Actual independent verdict | Evidence and limits |
|---|---|---|
| D1 — bounded canonical static PNG read / P1 | **PASS** | Current complete MCP and registered/SDK content checks, six additional independent content cases, deliberate full-decode and opened-file-containment faults, exact restored source. Metadata defaults, namespaces, errors, read risk and 31 intents preserved. |
| D2 — three consecutive real pairs / P1 | **PASS for this corrected frozen source and recorded invocation** | Independently reconciled attempts 1–3, full SDK traffic, six exact PNG payloads, fresh seeds, persisted lineages, new sessions and six distinct uncached real sampling graphs. Fresh QA SDK retrieves identical bytes. No replacement generation. |
| D3 — strict reset/no-retry/complete accounting / P1 | **PASS** | Actual CLI/SDK/product SIGINT RED on old source and GREEN on corrected source at health, admitted wait and uncertain submit. Complete call/attempt endings, retained state, finite recovery/budget guards, no subsequent submit/fallback/resume; complete separate ledgers. |
| D4 — explicit reply to reviewed demo | **UNCHECKED / pending Producer and CTY owner-demo** | Producer presents this reviewed candidate's images/Gallery records and records CTY's actual explicit project-channel reply. QA does not supply that reply or judge aesthetics. |

Correction C1–C3 pass the actual-boundary, regression, compatibility, renewed qualification and accounting checks below. C4 is satisfied by this exact-commit independent review and its immutable report/packet/patch/bundle/integrity handoff. External completion pins the report commit, which cannot contain its own SHA.

## Interruption and sensitivity

QA temporarily substituted **only the exact old 8736298 driver bytes** in its isolated tree and ran the three signal cases with the actual production MCP server and SDK. All three produced expected feature failures. After one qualifying fixture pair, SIGINT at attempt-2 health, an admitted original's wait, or an uncertain submit left streak 1, omitted the interrupted call, and left the active attempt without its end/count/streak. A safe nonzero exit was never mistaken for a compliant reset.

After exact corrected bytes were restored, all three cases pass. The actual CLI subprocess receives SIGINT while actual SDK/product MCP awaits a lower HTTP fixture response. No driver/tool/SDK callable or signal handler is patched. Health has nine sent calls/nine call records and two submits; admitted-wait has twelve/twelve and three submits; uncertain-submit has eleven/eleven and three submits. Each retains arguments/start/end/duration/interruption, no received result for the final sent request, zero streak, a reason and exactly one nonqualifying attempt-ending event. Independent computation matches every call's arguments and timestamp interval to sent SDK traffic.

The admitted job retains its known ID and last observed **queued** state; it is never called failed. The withheld submit response remains unknown admission, and its lower-fixture job ID is not invented as client knowledge. Earlier jobs remain completed. No recovery/audit/next attempt follows SIGINT, no extra submit or target fallback occurs, and reusing the output directory fails before another request. These lower HTTP/storage fixtures do not qualify as real-image evidence.

Old RED receipt, corrected GREEN, independent traffic/state analysis. Complete fixture configs, payloads, lower exchanges, stdout/stderr, SDK/call/event/summary evidence are in adjacent `old-signals-red/` and `signals-green/` directories.

Five independent production mutations each fail the targeted feature check: remove cancellation call capture; write stale attempt streak despite a zero summary; discard observed queued/running state; skip full pixel loading; remove both actual-open containment/identity guards. Each is restored byte-for-byte. Edits/results/restoration hashes. This detects incomplete attempt accounting hidden by a summary-only reset. Final complete MCP checks run after all restoration. Raw pytest RED tracebacks retain original trailing whitespace; the full diff whitespace check reports those evidence-only lines. Source/report/JSON checks pass without rewriting raw output.

## Independent offline checks

Own Python 3.11 venv, pinned MCP 1.26.0/Pillow 12.2.0 and all task package versions, explicit candidate imports, no editable install. Canonical environments were unchanged. Backend uses its canonical interpreter, candidate imports and a separate timeout-plugin copy. QA environment, Backend environment. All pytest runs use isolated roots below run-owned TMPDIR and `--timeout=60`; receipts retain exact argv/cwd/environment/UTC/duration/exit/full output.

| Check | Actual result |
|---|---|
| Old driver, actual three SIGINT boundaries | **3 expected failures**, 14.21s, exit 1 |
| Corrected driver, same boundaries | **3 passed**, 12.53s, exit 0 |
| Five independent deliberate faults | **Each expected RED**, exact restoration |
| Final restored complete MCP + six independent content cases | **672 passed, 4 existing optional skips**, 60.49s, exit 0; receipt, output |
| Fresh complete Backend | **1916 passed, 124 existing platform skips**, 42.34s, exit 0; receipt, output |
| Fresh actual Backend HTTP/persistence revision export | **1 passed**, 0.49s, exit 0; receipt |
| Fresh revision export + retained accepted LoRA cross-layer consumers | **7 passed**, 0.17s, exit 0; receipt |

No prior full-suite result is reused as QA's result. The unchanged accepted LoRA export is an explicit reused input; its current consumers run freshly. Two optional export cases execute separately; two old smoke exports remain skipped. Existing warnings/platform skips remain; the new POSIX signal test's Windows skip links this Mac task. No new macOS skip or changed existing test. All 16 standing guards run in these suites; no unrelated Frontend/build/Windows result is claimed.

D1 source inspection confirms one read bounded to 2,097,153 bytes, 2 MiB content maximum, pre-decode dimension/pixel bounds, static PNG/MIME/frame checks and full successful pixel decoding. Bytes are unchanged. Configured actual root, regular opened-file identity/containment, Unicode paths and contradictory/unsafe/container locators retain their guards. Selector errors precede Backend/file access. Same-artifact errors preserve job truth and direct metadata/configuration inspection. No arbitrary path/URL reader, Backend schema change, worker control or new risk/intent is introduced. The correction changes only the driver, new signal tests and matching guide; D1's unchanged production implementation is freshly checked here.

## Running services, real generation and retrieval

Independent audit, read-only audit source, fresh QA SDK results, current canonical rows.

**Running services:** live Backend PID 99953 and ComfyUI PID 99952 match recorded creation times, executable/cwd/full commands; unchanged deployed source, all 840 ComfyUI fingerprints/private configuration, equivalent-interpreter imports/settings/roots and live OpenAPI are corroborated. This is recorded-source corroboration, not general in-process attestation. Current Backend/ComfyUI queues are empty and trainer idle. No restart/deployment/configuration/resource/worker/training action occurred. Complete current SQLite schema and every pre-existing value equal the private pre-qualification snapshot; exactly six image and six artifact rows were added. The snapshot remains private and its digest matches. AID-171 runtime/private configuration/backups and AID-151 snapshots were retained; QA removed no data/outputs.

**Real generation:** one exclusive corrected-source invocation, attempts 1–3, 16:57:28.571–16:58:15.132 UTC. All 30 SDK calls (24 attempt + 6 new-session audit) match actual sent/received JSON-RPC identity, arguments, complete results, structured/text envelopes and timing. Each pair follows precisely the eight-call flow, one explicit local submit and one 50-second-bounded wait per image. Fixed parameters/red-blue prompts match declaration. Twelve distinct seeds/six request refs were declared before invocation and are new relative to the private snapshot. Attempts 4–6 were unused. No qualification timeout/retry/recovery/manual fix.

All six recorded waits and recorded Backend audit responses say completed. Current canonical rows and current ComfyUI histories match recorded identities/full compiled graphs. Six distinct new prompts show successful execution and uncached KSampler nodes with the declared fresh seed/four steps/CFG 7/Euler/normal, 512×512/batch 1, Illustrious checkpoint and no LoRA loader. Retained four-step logs corroborate sampling; repeated tqdm lines are not counted as jobs. QA ran no replacement generation or qualification invocation.

**Artifact retrieval:** all six original MCP payloads pass independent base64/digest/length/static-frame/dimension/full-decode checks, agree with official PNG uploads and embedded graphs, and are retrieved byte-identically by fresh QA SDK. Canonical **3872→3873, 3874→3875, 3876→3877** correspond to separate image IDs **4457–4462**. Original/revision parent/job/request/brief and parent snapshot fields agree across qualifying responses, driver's new session, Coding's audit session, current canonical rows and QA's new session, without context errors. QA image bytes came through MCP, with no host-path/HTTP artifact fetch. All QA retrievals remain separate audits.

## Integrity, history and accounting

Independent official integrity: all **16 uploads**, **1,897 indexed payloads / 1,898 archive members**, lengths/digests/Git blob/body equivalence, split reconstruction, exact binary/full-index patch and reconstructed candidate tree verified. The downloaded prerequisite bundle independently verifies/fetches in a separate bare repository to the same SHA/tree. Manifest equals committed bytes. The 909 protected historical task bodies checked against the repair base are unchanged, including old evidence directories; current manifest/report have byte-identical first-delivery mirrors. Original protected-input list: 727 exact bodies plus the original 16 registry rows (earlier generated date alone differs). All accepted p1-00/00a/p1-01–04 histories and prior official-readback evidence remain.

Cleared SHA-256 identities remain:

- Task: `c8bbbe8215f440e8859a5bc0bedf3febf4686f42ea0178fc82da871b041b8698`.
- Clarification: `f172d2098b69308b62a7cff7dc9c9cba7ed6bc71b3161a08b86ed9e9aa20e859`.
- Full MCP decision: `bf94f8b4277e7a264770b4788d2facfa2fbcdd7ec216538c429865b6c693e395`.
- Repair supplement: `6a5081548cddcf1575e8e400d282dc49b428cfd605512de7af1f781ba6ed6726`.

Original baseline remains **23 units/eight incidents**, F1–F8 **1,1,1,6,1,11,1,1**. Old seven jobs/six PNGs/**81 units** remain historical and never qualify corrected source. New Coding ledger reconciles to **22 preparation + 0 attempt interventions + 0 recovery + 14 audit = 36**. All 71 pre-packaging operator outcomes, failed file/environment reads, RED tests, earlier registry/bundle assumptions and progress-count correction remain disclosed. Two DB connections in the audit's single bundled receipt are expanded to two baseline units. Only qualifying request-to-result flows are zero; the whole round is nonzero and exceeds baseline.

History/accounting checks, QA separate ledger. QA's own environment/client preparation and 13 audit units are separate, including the stopped config inspection and resumed inspection. The QA tool initially treated a stored digest string as an object; failed receipt/source are retained. Resume reused completed process/import evidence, fixed only the audit tool and completed all checks. Offline fixtures never count as real qualification. Source reading, packaging and control-plane work remain separate overhead. No clean-first-try or whole-round-zero claim.

History: **one kickoff ambiguity event/two P1 findings; clarification 1/kickoff 2 CLEAR; delivery review 1 FAIL/first implementation rejection/one P1 R5-1; correction 1/delivery review 2 technical PASS**. Earlier histories remain separate. Registry regeneration preserves all 16 standing rows; the two automated original items below are newly certified after actual feature/sensitivity evidence. D2 remains manual; D4 remains pending.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | mcp-server/tests/test_gallery_content.py; mcp-server/tests/test_smoke_driver.py::test_three_pairs_exact_eight_calls_and_new_session_content_roundtrip; docs/tasks/p1-05-mcp-e2e-smoke-mac/review-evidence/test_independent_content.py | active |
| D3 | P1 | mcp-server/tests/test_smoke_interruption.py::test_sigint_finishes_active_attempt_and_retains_sent_call; mcp-server/tests/test_smoke_driver.py | active |

## Limits and disposition

One Mac/checkpoint/template/static-PNG qualification, requiring host Gallery access. Actual calling-application limit remains unverified; 50-second tool fallback and 65-second SDK guard are not performance guarantees. No Windows generation, broader runtime attestation, worker/resource/training work, Frontend build, aesthetics, CTY reply, whole-task acceptance or phase close is verified. QA generated/restarted nothing and neither merged nor pushed the feature. Later product changes need another exact-commit review.

Complete recipient-owned AID-175 with this D1–D3 technical PASS and immutable evidence. Native continuation returns the actual verdict to Producer AID-146, who owns demo/CTY reply/acceptance. Technical PASS and CTY's explicit reply to this reviewed demo precede feature merge/push; a separate phase-close roadmap review precedes Phase 2.
