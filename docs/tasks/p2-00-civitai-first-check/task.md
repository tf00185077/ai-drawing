# Phase 2 First check operating brief

## Task

Measure one real Civitai search → credentialed safe download → resource registration
→ checkpoint + LoRA `default_lora` image on the Mac, using current software.
This is the owner-required First check before detailed Phase 2 implementation
specifications. It is an operational measurement brief, not a design or a product
feature specification. Independent kickoff and exact evidence review remain.

## Purpose and outcome

Phase 1 is closed by CTY's published review; revised Phase 2 is active. Settle its
riskiest unknowns with actual API/download/loader evidence and a complete list of
services touched. An honest measured failure is a useful First check result;
never claim a successful chain from metadata, a mocked service or a copied image.
Producer then ranks observed gaps and writes bounded software specifications.

## Scope and inputs

Read [current roadmap](../../roadmap/ROADMAP.md), [owner review](../../requests/2026-11-26-phase-1-close-and-phase-2-review.md),
[later execution direction](../../requests/2026-11-26-phase-2-start-and-key-file.md),
[credentials](../../civitai-credentials.md), [operating policy](../../OPERATING-POLICY.md),
[runtime memory](../../memory/runtime-source-contract-verification.md),
[loader compatibility](../../memory/model-family-loader-compatibility.md),
[LoRA list semantics](../../memory/explicit-lora-list-semantics.md),
[resource/target scope](../../memory/compute-target-and-resource-scope.md), and
[prior runtime preservation/real evidence](../p1-05-mcp-e2e-smoke-mac/acceptance.md).
Current source input is `5608e1443978d04c3a2d67aff4a86adb747ce793` plus this
brief's fixed publication. Pin actual source, imports, graph/meta, interpreter,
package versions, existing runtime identity/jobs and data roots before action.
Health or checkout HEAD does not identify loaded service behavior. Preserve
AID-171 runtime/private configuration/backups, AID-151 snapshots, canonical venvs
and all existing models/datasets/outputs/Gallery records. No routine restart.

Producer adopts these in-boundary reference choices:

- Safe still life: "a blue ceramic cup on a wooden table, soft daylight, simple
  still life, no people". Record the exact final prompt including actual trigger
  words. CTY judges aesthetics; technical decoding/graph evidence is separate.
- Explicit `local`, `default_lora`, batch one, a fresh recorded seed. Prefer the
  existing `Illustrious-XL-v2.0.safetensors` only if actual local bytes and real
  Civitai identity/version/hash corroborate it. Search for a safe, compatible
  small style LoRA; no invented model ID, compatibility or license. Prefer one
  new free-key download; checkpoint reuse in this First check does not satisfy
  the later exit's fresh-checkpoint-plus-LoRA requirement.
- One mapping only: SDXL 1.0 / Illustrious / Pony / NoobAI → `sdxl`; reject other
  bases as no matching workflow. Group mapping alone does not prove a LoRA is
  compatible with a particular checkpoint: inspect actual version/graph/loader.
- Safe results by default; no explicit-content search. Store actual source,
  IDs, base/family, downloads/rating/file size/NSFW/license, trigger words and
  recommended parameters, with unknown fields truthful. Personal non-commercial
  use; no commercial-use permission filter and no paid/early-access purchase.
- Measurement download guards: `.safetensors` only; choose published SHA-256 and
  exact byte size, inspect current free space, cap a file at 8 GiB, new downloads
  at 10 GiB total and retain at least 20 GiB free. These are Producer's temporary
  First check limits, not implemented Phase 2 product guarantees. Prefer a LoRA
  at most 512 MiB when compatible. Verify actual post-download bytes/hash before
  registration/use; reuse a matching existing resource rather than overwriting.
- Use actual version-recommended LoRA strength, trigger words and parameters
  when available; record manual application and explicit overrides. Do not
  fabricate the future automatic defaults. For absent recommendations choose
  512×512, 20 steps, CFG 7, Euler/normal as disclosed technical reference settings.

The authorized key is `/Users/tf00185088/Desktop/civitai.txt`; executor checks
local readability/nonempty/0600 itself. Read/trim inside the needing process;
never emit value, key hash, Authorization headers, signed query strings, env
contents or private settings in commands, evidence, artifacts, URLs or Git.
Approved future `CIVITAI_API_KEY_FILE` support is not implemented merely by docs;
trace current `CIVITAI_AUTHORIZATION` path. A temporary in-process bridge is
allowed for this measurement, counted and removed from the process afterward;
preserve private on-disk configuration. Keep credential-bearing requests in a
redacting client and prevent forwarding authorization to an untrusted redirect.
A public download with a header does not prove login-required access. Record
actual auth-required/free-key refusal, Early Access and rate-limit outcomes.

Use existing MCP/Backend capabilities first, then record any necessary manual
API/search/credential/registration bridge as an intervention. Backend remains
the owner of jobs/artifacts/provenance. Do not introduce a parallel resource
record: inspect and use the current ledger/aliases as they are, reporting the
single-record gap instead of implementing the planned replacement. Capture
actual async acquisition/job IDs/status, resource records, selected workflow,
applied prompt/parameters, compiled graph/LoRA loading and Gallery output bytes.
If capabilities are missing or incompatible, record the exact failing stage
before any bounded manual workaround. No product repair, new service, schema,
workflow, dependency install, tool registration or service deletion in this run.

Bound the measurement: at most three candidate LoRA versions and two checkpoint
versions inspected, one selected acquisition per role (reuse where identity
matches), at most one generation submission. Record alternate choices/retries,
resume and existing downloader internal retries. Timeout is not job failure:
check the same acquisition/job before retrying; never resubmit while admission
or completion is uncertain. Poll/read the existing job as needed with a finite
recorded deadline; on deadline, preserve job ID and stop further submissions,
return terminal measured-blocker evidence or a native tracked completion path.
No hidden fallback to a worker. First check permits counted manual operations;
it is not any of the later three zero-fix exit runs.

Excluded: detailed Phase 2 software design/implementation, deleting Civitai
services/tests before the used-service inventory, Phase 3 registry/auth/concurrency,
video/training, paid cloud, new architecture, non-Windows workers or remote admin.

## Done when

- [ ] **D1 — actual baseline bound.** Check: executor verifies key-file access
  privately and records actual source/runtime/jobs/roots plus safe candidate and
  budget selection, with no secret values. Evidence: sanitized preflight and
  source fingerprints; presence is separate from authentication success.
- [ ] **D2 — real provider/download observation.** Check: real safe Civitai search,
  actual version metadata and credentialed download attempt with async IDs,
  HTTP/auth/rate-limit outcomes, size/disk/hash evidence. Evidence states whether
  a login-required download succeeded, failed or was unavailable; no mock proof.
- [ ] **D3 — actual registration/image observation.** Check: attempt current
  registration and `default_lora` local generation with explicit nonempty LoRA
  selection/trigger words/parameters; on success retrieve/decode actual Gallery
  bytes and corroborate the submitted/compiled graph and persisted IDs. A failed
  prior stage prevents fabricated later success: record exact stage/error and
  what was untested. Evidence: records, graph, job/Gallery and original image.
- [ ] **D4 — complete friction/service account.** Check: record every failure,
  manual bridge/retry/workaround, preparation/recovery/audit operation and used
  Civitai module/service with call evidence; distinguish available but untouched
  services. Reconcile counts and unresolved jobs. Evidence: chronological ledger,
  used-service inventory and risks for next bounded implementation tasks.
- [ ] **D5 — independent reviewable delivery.** Check: freeze exact evidence-only
  commit, manifest, source mapping and sanitized durable artifacts on Coding's
  card, then independent QA verdict on its own card. Adverse measured results or
  an adverse review are completed reports for Producer to handle, not self-PASS.
  No software change or Phase 2 exit/aesthetic acceptance is implied.

## Delivery

`manifest.md`, sanitized raw evidence, friction ledger, used-service inventory,
original image if produced, limitations and actual full final commit. Keep all
failed observations; no replacement of the baseline with a repaired happy path.
Producer reads the actual result/verdict before detailed Phase 2 task specs.
Any product repair follows its own CLEAR kickoff and exact-commit delivery QA.
