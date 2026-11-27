Verdict: CLEAR
Review round: 2 (specification and implementability only)

Reviewed source: **`4fc3ff25eb95e191ec45432c11f82055b914dae5`**.
Task SHA-256: **`c8bbbe8215f440e8859a5bc0bedf3febf4686f42ea0178fc82da871b041b8698`**.
Clarification 1 SHA-256: **`f172d2098b69308b62a7cff7dc9c9cba7ed6bc71b3161a08b86ed9e9aa20e859`**.
Full MCP decision SHA-256: **`bf94f8b4277e7a264770b4788d2facfa2fbcdd7ec216538c429865b6c693e395`**.
Date: 2026-11-24 UTC. Independent QA: [AID-170](/AID/issues/AID-170).
Producer: [AID-146](/AID/issues/AID-146).

**K5-1 and K5-2 are resolved at specification level.** The refreshed task and
normative clarification supply implementable means and observable acceptance
criteria for all four items. No remaining blocking ambiguity or owner-boundary
change is demonstrated. No additional owner question or specification change is
needed before Coding. This CLEAR permits the clarified implementation handoff;
it certifies no unimplemented behavior, deployed service, qualifying run or phase
exit. There is no p1-05 `manifest.md` at this source.

## Independent owner reading and comparison

My reading: an agent must use the real SDK stdio MCP flow on the local Mac to
obtain and decode both an actually sampled original and a fresh, persistently
traceable revision, three consecutive times without manual fixes or client
retries. Metadata and paths alone cannot establish retrieval. Every unsuccessful
attempt, preparation, recovery and audit remains visible under the original
23-unit/eight-incident baseline. Routine technical choices inside Phase 1 are
delegated. CTY explicitly replies to the reviewed demo and alone judges
aesthetics; a later roadmap review precedes Phase 2.

The owner reading was recorded from
the actual owner request, roadmap, team rules and prior adverse report before
opening the repository task. The authenticated wake already supplied the task
and clarification; this is not a blind-reading claim. I read the complete task,
clarification and MCP decision, and the accepted prerequisite manifests,
independent reports and acceptances. The difference from the original proposal
is now an explicit bounded content feature and strict attempt/accounting policy,
which implement the existing owner goal without changing it.

[CTY's delegated instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md)
permits routine technical choices inside current boundaries. Static PNG delivery
on the existing Gallery read, four-step 512×512 smoke parameters and fresh seeds
are such choices. They do not add a phase, compute target, workflow engine or
resource acquisition, excuse an outside-MCP read/retry, promise performance, or
transfer aesthetic/phase-close authority to QA.

I reviewed my own run-scratch worktree on `aid-170-p1-05-kickoff-round-2`, pinned
to the full source above. Shared main and AID-151's runtime/private configuration
were untouched. The source audit
pins the relevant Git blobs and byte hashes. It verifies the 25-file publication
commit is documents only; the 26-file delta from round-1 source also includes
the earlier kickoff handoff. All tracked non-document inputs are unchanged.

## Resolution of the actual prior findings

### K5-1 — resolved by a bounded canonical-artifact PNG read

The actual round-1 report, also read back from its
[official AID-169 upload](/api/attachments/69962b71-71e0-4605-a241-b78410dc0390/content),
found a missing means of actual MCP retrieval. The refreshed task now explicitly
includes that missing feature. Current `tools/intents.py::gallery_get` still has
only image/artifact selectors; `tools/gallery.py` still projects metadata. That
is the expected starting point, not a new defect or proof of byte delivery.

Clarification 1 specifies each boundary needed to implement and test the change:

| Boundary | Independent assessment and later proof |
|---|---|
| Selection and compatibility | `include_content` defaults to false. True requires one positive canonical artifact ID and rejects image, absent/multiple or invalid selectors in the common envelope before access. Existing metadata/video/legacy behavior remains. Registered validation must assert zero Backend/file calls on rejection; schema/SDK discovery must retain 31 intents and the literal Gallery read risk. Invalid types include boolean/coercible selectors that do not represent the required canonical ID. |
| Backend identity and authority | The existing artifact route supplies ID, kind, MIME, Gallery mapping, job and revision context. Verify returned canonical identity; never fall back to an image ID or accept caller path/URL/root. No Backend redesign is required. Tests must make a mismatched ID fail, even if a readable PNG exists. |
| Actual opened file | Resolve configured `MCP_GALLERY_DIR` to its actual host root and establish the supported Gallery relationship. Preserve nested/Unicode identity. Reject nonregular files, traversal, symlink escape, outside/container-only or contradictory mappings. A lexical prefix or earlier resolve alone cannot prove containment of the file actually opened; the implementation must preserve the specified boundary through opening. Existing locator construction is useful metadata logic, not sufficient byte-read proof. No basename substitution, copying, migration or arbitrary URL request is allowed. |
| Byte/decode limits | A bounded read of at most 2,097,153 bytes detects the 2,097,152-byte maximum. Nonempty static PNG only, declared image/png, dimensions 1–2048 and at most 4,194,304 pixels; check format/dimensions before full decode and require successful full decoding/one frame. Signature or extension alone cannot pass. Test exact byte boundary, oversized streams, dimension rejection before expensive decode, corruption, empty/non-PNG/animated input, MIME conflict and unreadability. A minimal declared decoder dependency is allowed and its setup belongs in preparation. |
| Successful payload | Preserve ordinary metadata under data; add exactly content.encoding/mime_type/byte_length/sha256/width/height/base64 as specified. Decode standard unwrapped base64 and independently recompute exact bytes, lower-case digest, length and dimensions. Text/structured envelopes must agree. No conversion, thumbnail or rewritten bytes. Pure validation of the received MCP payload is permitted; another filesystem/HTTP artifact fetch is not. |
| Errors and state | Existing Backend lookup codes/hints remain. Other failures use artifact_content_unavailable, artifact_content_too_large or artifact_content_invalid according to the normative categories, with no partial success/content. Keep the requested canonical ID and safe available metadata; unsafe locators/contents must not leak through error details. Hints inspect the same artifact/configuration or use metadata-only reads. No completed-job failure, cancellation, regeneration or resubmission. |

These are bounded extensions of an existing read capability. The scope expressly
excludes general file transfer, arbitrary remote retrieval and video/legacy
content. No residual K5-1 clarification is needed. Later QA must inspect the
actual implementation and prove the opening/decoding/error boundaries; this
kickoff does not presume them implemented.

### K5-2 — resolved by literal qualification and complete accounting

The prior report found that repeated waits and omitted preparation could falsely
appear to meet zero retries. The clarification now gives an explicit state and
accounting policy, preserving the accepted read-only wait behavior:

- Freeze driver/product source and declare all invocation inputs, request
  references and fresh seed allocations before qualification. Identify loaded
  Backend/MCP/ComfyUI source, interpreters/imports and effective non-secret data,
  model and authored-data roots during disclosed preparation. Health, HEAD and
  cwd alone are insufficient. Any necessary controlled replacement first checks
  active work, preserves private snapshots/paths/data and audits complete startup
  schema plus old-value preservation. Never relaunch for a documentation SHA.
- An attempt starts immediately before health and uses the exact eight-call
  flow: health, list_resources, original generate/wait/content, revision
  generate/wait/content. Each image has one submit and one bounded wait; internal
  tool polling is distinct from another client call. End at successful revision
  content/lineage validation or the first disqualifying event. The invocation
  permits at most six attempts and stops on three consecutive successes.
- Timeout/error/failure/cancellation/nonterminal response, uncertain admission,
  extra client call to salvage a result, outside-MCP product operation, manual
  change, invalid bytes, wrong lineage or interruption ends qualification and
  resets the streak. It never reclassifies an unknown/running/completed Backend
  job as failed. Retain all events, existing IDs and earlier outputs.
- Recovery is a separately recorded, same-ID read-only status/wait sequence,
  at most six calls per possibly outstanding known job, each within existing
  tool policy and waits at most 50 seconds. Establish all prior jobs terminal
  before another declared attempt. Unknown admission without a recovered ID,
  or exhausted recovery with unresolved state, stops the invocation. No cancel,
  blind resubmission or target fallback; recovery cannot rehabilitate a failed
  attempt. This is duplicate avoidance, not a new idempotency guarantee.
- A qualifying streak has six distinct new jobs/artifacts and six correlated
  ComfyUI prompts with actual sampling. New IDs/seeds alone are insufficient;
  retain graph and sampling/cache evidence. Original and revision share a
  per-pair request_ref, use changed brief_revision and a new generate with the
  original canonical parent. Gallery reads must contain fresh persisted context
  without context errors. A new SDK session independently corroborates persistence
  after results. All post-result Backend/ComfyUI/file reads are audit work,
  disclosed separately and included in totals; failed audit invalidates exit
  evidence. A product repair requires renewed applicable review and a fresh
  qualifying streak under the fixed source, retaining the earlier record.

The actual client call limit is still unverified. Fifty seconds remains the
unchanged overall wait fallback, including lookup/enrichment/preparation. The
four-step workload guarantees neither completion within one wait nor acceptable
art. The implementation may honestly exhaust its budget or stop unresolved;
that is a non-exit result, not a reason to increase the limit, hide a retry or
waive a gate. There is no remaining K5-2 policy gap requiring Producer/CTY input.

## Every refreshed Done when item and later evidence

No Coding manifest supplies levels yet. Proposed P1 levels below reflect false
retrieval, lineage, exit or owner-acceptance consequences; there is no demonstrated
P0 issue. These classify future proof, not current feature certification.

| Item | Check / proposed level | Kickoff result | Required later evidence |
|---|---|---|---|
| D1 — optional canonical static PNG bytes | test / P1, with manual source/security inspection | CLEAR, unimplemented | Meaningful tests through actual registered validation/wrappers/client, transport/storage fixtures only, plus real SDK stdio to a test Backend with synthetic PNG. Prove exact received bytes/identity, default metadata/video/legacy compatibility, selector-before-access rejection, limits and full decode, safe actual opening, nested/Unicode paths, missing/unreadable/invalid/animated/MIME cases, conflicting identity/locators, error privacy and no write/submit. Exact implementation/declared dependencies, applicable affected suites/16 standing guards and deliberate fault/restoration evidence in the manifest. |
| D2 — three consecutive real original/revision pairs | manual / P1, supported by tests | CLEAR, unexecuted | Frozen driver and real source-bound SDK stdio command; declared Illustrious/default, local, loras=[], 512×512/batch 1/four steps/CFG 7/Euler/normal, prompts and fresh seeds. Complete timestamped SDK messages/commands/stderr for all attempts, resets and IDs; six distinct jobs/artifacts/prompts with actual sampling and correct compiled inputs. Both MCP payloads per pair decode with matching length/digest/dimensions. Persisted canonical parent/job/request/brief fields and new-session corroboration, plus independent Backend/ComfyUI audit. No fixture/cache-only substitution. |
| D3 — strict no-fix/no-retry qualification and full friction | test + manual / P1 | CLEAR, unimplemented/unexecuted | Tests of the actual driver boundary reject missing/invalid bytes, digest/length mismatch, wrong stored parent, nonterminal/failed/cancelled/timeout and uncertain-submit states. Assert one submit/wait, no hidden status salvage/resubmit/fallback, reset/retained failures, six-attempt stop, finite same-ID recovery and stop on unknown admission/unresolved jobs. Inspect full source/logs/ledgers independently; reconcile preparation, attempts, recovery, audit and total with every original F1–F8 unit rule. Honest non-exit remains possible. Offline state-machine checks cannot replace D2. |
| D4 — CTY explicitly replies to reviewed demo | owner-demo / P1 | CLEAR, UNCHECKED/pending later owner-demo | Producer presents the exact technically reviewed candidate's images/revision/Gallery records in the existing project channel and records CTY's actual explicit reply/message/source identity. A bot send receipt, silence, Coding assertion or QA technical PASS cannot satisfy it. CTY alone judges aesthetics. |

For D1/D3, later mutation checks must reach the meaningful boundary: for example,
wrong bytes/digest, bypassed root/size checks, accepted invalid lineage or a
second client wait must make the corresponding tests fail. A duplicate state
machine or patched tool callable is not proof of the actual driver. There is no
appropriate product fault injection now: neither requested feature exists yet.

## Baseline, prerequisites and preservation

The audit rechecks all 12 accepted manifest/report byte comparisons against their
actual delivery/QA commits and all six acceptance documents against round-1
source. Their limits remain unchanged:

| Input | Accepted evidence and retained limit |
|---|---|
| p1-00 | 23 units/eight incidents; original completed, metadata only, relative-URL client fetch failed before HTTP; revision not submitted and live context null. No-repair baseline stays immutable. |
| p1-00a | Corrected b6d5846 / QA 3d5d890: identified launch, original/revision lineage and decoded colocated host paths. Original used deterministic cache; byte reads were outside MCP. One prior rejection/correction 1/review 2 stays separate. |
| p1-01/02 | 616f67f / QA 28cd451: common envelopes, literal risks, intent/mode/capability/namespace preservation. One p1-02 delivery rejection and separate kickoff history stay intact. |
| p1-03 | 77e3e3c / QA d088c32: bounded read-only wait, truthful terminal/timeout/identity/locators; client limit unverified, 50-second fallback. No real wait/byte proof. |
| p1-04 | 72f4834 / QA 3422ccd: 31 intents, configured/expected/current worker identity distinct and unknown reads not empty. Health is reachability with sequential five-second reads, not loaded-source/readiness proof. No live Windows worker is required for this local task. |

The F1–F8 comparison remains explicit, with original units **1,1,1,6,1,11,1,1 =
23**. F1 test/dependency setup and F2 client/source/root binding are preparation;
F3 uses the delivered common envelope; F4/F5 require actual loaded-source and
persisted revision proof; F6 applies the strict single-wait rule and counts
recovery visibly; F7 sampling/cache corroboration belongs in the disclosed audit;
F8 requires MCP-returned bytes. Setup/relaunch/diagnostic work does not disappear
from the complete total. Only the request-to-result qualifying-attempt count can
be zero while preparation/audit totals are nonzero. No whole-round zero claim
follows. Original records and all failed attempts remain inspectable.

All 13 round-1 report/evidence files and the original task are byte-identical at
their preserved paths; the official prior report also matches byte-for-byte.
All 16 registry rows remain unchanged. This kickoff does not run the registry
builder or certify p1-05. History remains **one kickoff ambiguity event/two P1
findings, clarification 1, kickoff round 2 CLEAR; zero implementation delivery
rejections**. Earlier tasks' histories remain separate.

## Checks actually performed and limits

The new verification command
and full output record UTC,
argv, cwd, duration and exit **0** for `python -B .../verify-inputs.py.txt`.
The audit checks pinned hashes, fixed Git/AST/source contracts, input equality,
prior official report readback, preserved history and baseline/registry counts.
An exploratory rg command named the nonexistent tools/generation.py before the
actual tools/generate.py was read; this was source navigation, with no product
change. The audit's field name was aligned to the existing receipt schema before
its first execution. Both actual audit invocations passed; the final invocation
has the retained command/output receipt. No product or dependency fix was made.

Applicable historical evidence is reused with attribution, as the assignment
requires for this documents-only kickoff. Backend, MCP, Frontend, worker, bot,
scripts, prompt library and style-preset trees, all tests, dependency declarations
and root non-document inputs match the earlier fixed source. This establishes
source-check applicability; it does not assert installed-package/process equality
or manufacture a current test result.

- **Offline tests:** no new pytest/full-suite/build run. Actual AID-169 receipts
  retain 32 selected MCP cases passed in 2.10s (real registration/SDK stdio with
  test-only HTTP and mocked transport), one Backend persisted-route/SQLite case
  passed with one warning in 0.50s (synthetic execution), and the metadata-only
  registered source probe. These remain earlier results. Actual AID-168 full
  Backend 1916 passed/124 Windows-only skips/76 warnings and MCP 606 passed/two
  optional skips, ten restored faults and all standing guards remain prior
  independent source evidence, not p1-05 acceptance or a fresh run here.
- **Running product service:** no probe, restart, deployment, reconfiguration or
  source-identity assertion. No product dependency installation or venv change.
- **Real generation/training/download/worker dispatch:** none. No cancellation,
  live recovery, cache/parameter manipulation or duplicate submission.
- **Generated-artifact retrieval:** none. Only the prior review-document
  attachment was downloaded; that is not a live Gallery/image read.

Frontend/native Windows/runtime/decode/performance/aesthetic checks are not
performed. Current metadata source is not relabeled as a content feature.
Models, datasets, outputs, Gallery records and private configuration remain
preserved. QA writes only this current kickoff report and round-2 evidence;
no task/clarification/decision/manifest/registry edit, merge/push, parent write,
cross-agent issue write or CTY message is part of this review.

## Handoff and acceptance order

Producer can now hand the clarified task to Coding, then arrange independent
exact-final-commit delivery QA through native prerequisites. Coding supplies its
manifest/source/tests and complete real evidence on its own card; a completed
adverse QA verdict is still that review card's done deliverable. Later software
changes require a new exact-commit review; execution-input changes require
renewed applicable qualification. No implementation acceptance is implied here.

Delivery QA evaluates D1–D3 and explicitly leaves D4 unchecked/pending owner-demo.
Producer reads the actual technical verdict, obtains CTY's explicit reply for
that reviewed candidate and records D4 before whole-task acceptance and feature
merge/push. Owner aesthetic judgment is not inferred from technical PASS. The
later roadmap phase-close review is a separate owner gate before Phase 2.

The external integrity/readback receipt and AID-170 completion pin this report's
exact byte hash and report/evidence commit, indexed source packet, exact
binary/full-index patch and verified prerequisite Git bundle. A commit cannot
embed its own SHA. Producer reads the actual CLEAR deliverable on this
recipient-owned card; no parent mutation is needed to complete this review.
