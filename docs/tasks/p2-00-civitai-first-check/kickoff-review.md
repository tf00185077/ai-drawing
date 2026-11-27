# Phase 2 First check independent kickoff review

Verdict: CLEAR
Review round: 1
Issue: [AID-177](/AID/issues/AID-177)
Reviewed publication: `2d2a0b1b46cbfe196815e21bb4aede6e87228bf6`
Owner handoff: `1666ffb9d264946e2fb7bbffb583f6180f6d8722`
Task SHA-256: `dfb23f60ecbd18bd8f8e481dc725406f2bfa07653f2172b5efcadd44748e6777`

## Independent reading and comparison

My reading: CTY closed Phase 1, activated revised Phase 2, supplied the private
key-file locator and delegated ordinary choices within the accepted boundary.
Before detailed implementation specifications, measure one real safe Civitai
search, credentialed download attempt, resource registration and local
checkpoint-plus-LoRA `default_lora` image attempt using current software. Keep
Backend ownership, preserve runtime/private configuration/jobs/data, record all
failures and manual operations, and retain independent evidence review. A failed
stage can yield a complete measurement report; it cannot yield invented later
success. The later three-run exit and CTY's artistic judgment remain separate.

This reading comes from the [published owner review](../../requests/2026-11-26-phase-1-close-and-phase-2-review.md),
[later owner direction](../../requests/2026-11-26-phase-2-start-and-key-file.md)
and [active roadmap](../../roadmap/ROADMAP.md). Owner words, inherited rules and
Hermes's application remain separately attributed in those sources. The earlier
native Phase 1 proposal does not override the later direction.
The initial reading was written before
opening the checked-out task; the assignment had already supplied the brief inline.

Difference: none material. The [fixed task](task.md) expressly describes an
operating measurement, including bounded manual bridges and truthful failure,
before product implementation. Its reference prompt, checkpoint preference,
resource budgets and candidate limits are delegated ordinary choices. No routine
owner/start/resource/phase-close question is pending. No owner question or blocking
finding is raised by this review.

## Done when review

These are prospective operating-evidence checks. CLEAR certifies their suitability
for this First check, not their completion or any deployed feature.

| Item | Required evidence and review conclusion |
|---|---|
| D1 | Task lines 29–34 and 65–75 require actual source/import/interpreter/package/graph/runtime/jobs/roots and private key access checks. Presence, authentication and loaded behavior are distinct. Preservation and no routine restart are explicit. CLEAR. |
| D2 | Lines 41–59, 65–75 and 109–112 require real safe metadata/search, credentialed download observation, actual auth/free-key/Early Access/rate-limit outcomes, IDs and size/disk/hash evidence. A public file with an Authorization header proves no login-required success. Unavailable or refused access stays an observed outcome. CLEAR. |
| D3 | Lines 41–49, 60–63, 77–86 and 113–118 require explicit local target, batch one, recorded seed, compatible selected checkpoint and nonempty LoRA selection, actual trigger words/parameters, compiled loading graph, persisted IDs and original decoded Gallery bytes on success. An earlier failure makes downstream stages explicitly untested. CLEAR. |
| D4 | Lines 77–97 and 119–123 require chronological accounting of every preparation, manual API/credential/registration bridge, retry/resume/internal retry, recovery and audit operation, plus call-evidenced used services distinguished from untouched services and unresolved jobs. There is no whole-round zero-fix claim. CLEAR. |
| D5 | Lines 124–136 require a fixed evidence-only commit, manifest/source mapping, sanitized durable originals, recipient-owned delivery QA and Producer reading the actual result before implementation specs. An adverse observation or review is still a completed report. No self-PASS, phase exit or aesthetic acceptance follows. CLEAR. |

## Current-source risks for the executor

These observations do not block a measurement that can stop honestly at a failed
stage. They do not authorize a product repair or weaken the existing brief.

1. **Authentication is still a manual boundary.**
   [Settings](../../../backend/app/config.py#L85) defines
   `civitai_authorization`; [acquisition authentication](../../../backend/app/services/civitai_resource_acquire.py#L130)
   reads it and normalizes a Bearer header. This publication adds no file reader.
   The credential guide and task require a counted temporary in-process bridge,
   redacted results, no secret/key digest/header/signed query disclosure, no
   private on-disk changes, and no authorization forwarding to an untrusted
   redirect. The executor must check its own access and real provider result;
   Producer's saved presence/readability observation is only attributed evidence.

2. **Family grouping is not loader compatibility.**
   [The current normalizer](../../../backend/app/services/civitai_resource_acquire.py#L99)
   can return `illustrious`, accepts Anima and does not implement the brief's
   complete SDXL-group table. Record actual current values separately from the
   allowed manual grouping; do not repair or relabel the product to hide the gap.
   [The graph](../../../backend/workflows/default_lora.json) uses
   `CheckpointLoaderSimple` and one `LoraLoader` connected to model and CLIP.
   [Its metadata](../../../backend/workflows/default_lora.meta.json) explicitly
   requires actual compatibility and output re-verification. Provider version
   information, real target files and actual compiled loader execution remain
   necessary. The template's embedded checkpoint/LoRA names are not selections.

3. **Download policy must be enforced for the hand run.**
   [File selection](../../../backend/app/services/civitai_resource_acquire.py#L220)
   permits formats beyond `.safetensors` and can prefer a primary file;
   its `sizeKB` conversion is not independent proof of exact byte size.
   [The downloader](../../../backend/app/services/civitai_safe_download.py#L102)
   verifies post-download size/hash and clean scan status, retries up to three
   requests and publishes with `os.replace`; it does not enforce this brief's
   8 GiB/10 GiB/20 GiB limits while streaming. The stock transport follows
   redirects and has no read timeout. Inspect the actual selected file and
   target, establish trustworthy size/hash/budget evidence, protect existing
   final/partial files and keep the run bounded before using this path. If the
   requirements cannot be upheld through an allowed counted bridge, stop and
   report that stage. A small advertised file alone does not establish all guards.

4. **Existing records and deduplication need corroboration.**
   [Acquisition](../../../backend/app/services/civitai_resource_acquire.py#L351)
   uses `DownloadedResource`, returns acquisition IDs and reuses matching active
   or installed version/name rows. Its installed check establishes file presence,
   not a fresh content hash. Verify actual reused bytes/identity and do not
   overwrite or create a parallel registry. The
   [local identity ledger](../../../backend/app/services/civitai_local_identity_ledger.py)
   and [source aliases](../../../backend/app/services/civitai_source_alias_registry.py)
   remain existing separate structures. The active
   [MCP catalog](../../../mcp-server/mcp_server/tool_catalog.py) exposes source-info,
   acquire and status, without a model-search intent. Missing search/registration
   conveniences and manual calls belong in the measured friction/service account.

5. **Submission, recovery and image proof stay separate.**
   [Explicit LoRA compilation](../../../backend/app/core/workflow.py#L288)
   treats an explicit list as the complete active set; an empty list removes the
   loader and an omitted list can retain template defaults. Use the required
   nonempty selection and corroborate actual strengths, trigger words and
   model/CLIP links in the [queued graph](../../../backend/app/core/queue.py#L1119).
   At most one generation submission is allowed. Observe cancellation/failure
   on the same ID; a timeout or uncertain admission permits no duplicate submit.
   Set finite recorded observation deadlines, preserve IDs at the deadline and
   use the brief's terminal blocker report or real tracked completion path.
   Do not claim cancellation from a timeout or silently fall back to a worker.
   Original Gallery bytes must be retrieved and decoded; status, paths, metadata
   and an unrelated copied image cannot substitute for them.

## Verification

The fixed review worktree is
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-177-kickoff-review`.
Source evidence records the exact Git
tree, matching task hash, 42 source/document fingerprints and ten resolved task
link targets. The publication changes only four documentation/evidence files
from the owner handoff; no product code changes are present.

Registry regeneration has no warnings:
all 18 prior row bodies remain identical, with no new certification or
supersession. The checked-in registry and historical reviews remain unchanged.

Fresh suite commands and raw outputs are in
Backend, MCP,
frontend and build.
The separately registered independent PNG content guard
also passes all six cases.
Python suites use `pytest -c pytest.ini`, separate scratch roots, explicit
`pytest_asyncio`/`pytest_timeout`, `--timeout=60`, and no result cache. Frontend
uses `npm test -- --no-cache --testTimeout=60000 --hookTimeout=60000`; Vite cache
and build output are in run scratch. An existing Python 3.11 QA environment and
existing Backend dependency directory are used without installation or edits.

| Check | Fresh result |
|---|---|
| Backend full suite | 1,916 passed; 124 skipped. |
| MCP full suite | 666 passed; four skipped. |
| Separate registered PNG guard | Six passed. |
| Frontend full suite | 226 passed; one skipped; all 23 test files passed. |
| Frontend production build | Passed. |

Initial runner attempts are retained under `*-attempt-*` in the evidence folder.
They exposed review setup mistakes: an incomplete interpreter dependency set,
the deny-all runner rejecting fixture loopback/Git/SDK subprocesses, a missing
frontend interpreter setting, an audit-hook import error and a missing scratch
parent directory. The corrected suite setup uses existing dependencies, explicit
interpreter paths and separate pre-created scratch roots. Its Python network
guard denies external connections while permitting test loopback fixtures.
No tests were edited, removed or newly skipped; no product repair followed these
setup failures. The final complete command results are reported separately from
those attempts. Build warnings and dependency deprecations are retained in logs.

## Boundaries and handoff

- **Offline:** only the listed local test/build/source/document checks were
  performed. Existing platform/optional skips remain limitations; Windows was
  not run. This kickoff adds no new runtime/product certification.
- **Running services:** no live Backend/ComfyUI/worker probe, restart, deployment
  or private-settings read/change. No canonical environment mutation or package
  installation. Existing runtime identity and data are not inferred from Git.
- **Real provider/generation:** no provider search, authenticated request,
  download, model registration, key-file read or generation by this QA run.
- **Artifact retrieval:** no live Gallery bytes were requested. Test fixture
  PNGs/HTTP servers and this report's official uploads are separate evidence.

Producer and Coding must read this actual CLEAR on AID-177 before real provider
operations. It clears only the unchanged fixed operating brief, with its existing
guardrails and truthful failed-stage acceptance. Delivery remains a new fixed
evidence-only manifest/commit and independent QA on its own card. Later product
changes require their own CLEAR specification and exact-commit review. CTY's
artistic judgment and Phase 2 exit remain outstanding and are not inferred here.
