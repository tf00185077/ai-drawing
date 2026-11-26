# Private key-file and credential-safe requests: independent kickoff

Verdict: CLEAR
Review round: 1
Issue: [AID-180](/AID/issues/AID-180)
Producer: [AID-146](/AID/issues/AID-146)
Fixed source: `316327d0992f4f6ebe5d912c3b5ef8d215deba81`
Fixed tree: `1b53d0cfe696e71d3f1ed1ca04a2b40559579b36`
Task SHA-256: `bd291da2897099b84fd743dcd384ea7812105ec96e74ad7501d76c9d28784850`
Date: 2026-11-26

This clears this specification for Coding. It is not delivery PASS, implementation,
provider access, runtime deployment or Phase 2 exit acceptance. There is no
p2-01 `manifest.md` at the fixed source. The report's exact commit/tree and official
artifact identities are supplied in AID-180's post-commit receipt, avoiding a
circular self-SHA in this file.

## My reading

CTY expects Phase 2 to use the already-supplied private host file for Backend
authentication, without credentials in MCP, Git or evidence. The first bounded
software increment should replace counted in-process key bridges on retained
current paths, preserve data and public contracts, and give truthful refusal and
recovery outcomes. The selected real access comparison must identify the loaded
source component separately from the long-running Backend. Search, generic
download jobs/budgets, the unified resource record and generation defaults remain
later Phase 2 work. Routine technical choices inside that boundary are delegated;
another routine owner start gate is not required.

This reading was recorded before opening the repository `task.md`, from the owner
request and active roadmap. The wake itself already included the entire task;
there was no blind or withheld-spec experiment. Original owner words, inherited
project requirements and Hermes's application remain distinct in the
[request](../../requests/2026-11-26-phase-2-start-and-key-file.md).

Difference: none requiring a specification change. No P0/P1 kickoff defect or
demonstrated ambiguity. No ASK OWNER/BLOCK finding and no owner question pending.
The concrete limits and security defaults are Producer's delegated technical
choices, not invented direct quotations from CTY.

## Owner and First check comparison

The task advances the active roadmap's private `CIVITAI_API_KEY_FILE` requirement
using `/Users/tf00185088/Desktop/civitai.txt`, outside the repository. The credential
guide explicitly says the existing product has only legacy authorization; a
documented locator is not an implemented reader. This review did not inspect the
owner file or assert its current readability. A known missing/unreadable file is
a concrete loading failure, not an unknown location requiring CTY to repeat it.

The accepted First check's F2 ledger records seven credential-bearing process
bridges; F3 supplied a bounded injected transport. Its actual observation was one
selected login-required free-key LoRA, anonymous 401, credentialed 307 and a
credential-free CDN 200, with bytes and one manually assembled checkpoint+LoRA
image verified. The accepted observation is not evidence that this new file
reader or a general authenticated flow already exists. Its 20 interventions,
77 overlapping work units and five missing historical tokenizer fingerprints
remain historical limits. The original evidence/helper is not changed here.

The bounded task neither replaces the accepted phase/order/exit nor revives
recipe/generate-like functionality. The pending intake still owns the resource
migration, SDXL mapping, safe search, budget/job integration, removal and automatic
defaults. The three different-sentence zero-fix exit and CTY's image judgment
remain separate.

## Trace against the fixed production source

The [static audit](kickoff-evidence/static-audit.json) records symbol line spans,
the catalog and registry rows. These observations describe the baseline that
Coding must change, not newly passing feature tests.

| Boundary | Actual retained code | Specification assessment |
|---|---|---|
| Private configuration | `backend/app/config.py` has `civitai_authorization`, dotenv loading and cached Settings; no key-file setting. | D1 adds an optional private setting and rereads file content per operation. Cached Settings must not become cached file content. No private setting rewrite is needed. |
| Ordinary acquisition | MCP `civitai_resource_acquire` posts to `/api/civitai/resources/acquire`; the Backend router calls `start_acquisition`. `resolve_version_metadata` performs nested version/model reads through `_fetch_json`/`_maybe_fetch_model`. | D2 reaches registered MCP and actual Backend routes, rather than proving an isolated resolver. One metadata snapshot and total deadline must span nested reads. |
| Acquisition execution | Admission records `DownloadedResource` IDs, dedupes active/installed resources, then captures authorization for background `_run_one`/`safe_download`. Anima can queue multiple files. | One download snapshot/deadline per file execution includes retries/backoff. Rotation between operations must work; active/installed dedupe and same acquisition IDs remain. No new generic job schema is implied. |
| Inspect/install adapters | `/api/civitai-recipes/resource-inspect` calls `httpx.get` directly with raw legacy authorization. `/resource-install` independently builds `_CivitaiDownloadTransport` and supplies legacy authorization to `install_civitai_resource`. | These adapters are explicitly retained and included in D2/D3. Their location in a recipes router does not justify skipping them or expanding recipe features. |
| Request/stream lifetime | Acquisition metadata follows automatic redirects; both download adapters use automatic redirects and `read=None`. Stream release currently depends on consuming/closing the body iterator. | Explicit initial-URL and redirect validation, five-hop maximum, finite phase timeouts, operation-wide deadlines and stream closure are necessary changes, already specified. |
| Retry/error persistence | `safe_download` permits three attempts on 429/5xx/network failures and optional backoff. It stringifies initial transport exceptions; streaming errors become a class name. `_run_one` can reduce exceptions to their class name. | Stable credential/redirect/timeout outcomes must survive these layers, status records and HTTP/MCP projection. Catch-all handling must not erase them or leak a raw URL. 401/403 remain refusals, without retrying another target. |
| Resource/byte evidence | Acquisition stores the provider `download_url` in `resolved_download_url`. Installer canonicalizes a public URL identity, validates descriptors and adopts exact existing bytes. Safe download verifies size/hash and handles `.part` files. | D2/D3 secrecy extends to stored provider values; merely hiding a returned header is insufficient. Preserve existing safety/adoption/dedupe contracts, ordinary hashes and partial-file truth. Do not claim broad pre-existing no-overwrite safety from the transport helper alone. |
| MCP contract | Catalog contains 31 unique intents; acquisition is `mutate`, source-info/status are `read`. Registration invokes adapters through the common envelope. Structured Backend errors preserve `code` and `hint`. | Existing names, risk labels and envelope shape stay. New errors must be observed through that public boundary with useful hints; no key/path parameter is added to tools. |

## D1–D5 review and delivery focus

| Item | Kickoff assessment | Required evidence at delivery |
|---|---|---|
| D1 | CLEAR: precedence and operation boundaries are specified. | Configured nonblank file wins over legacy; all specified unusable files fail before traffic without fallback. Test UTF-8/trim/header controls/64 KiB boundary, absence/blank setting, legacy raw/Bearer compatibility, anonymous mode, rotation and a stable snapshot across nested calls/retries. Nonregular files must fail without a blocking special-file read. |
| D2 | CLEAR: all actual retained adapters and identities are named. | Use private environment configuration and real resolver/client factories with isolated HTTP/DB fixtures. Do not inject a key or substitute the domain transport to make the configured-file case pass. Check public success/error envelopes, background status, duplicate admission/reuse and absence of credentials in persisted values. Existing roots/config/bytes remain preserved. |
| D3 | CLEAR: host, credential, redirect, deadline and closure policies are concrete. | Observe request headers at the HTTP boundary: Authorization only to canonical HTTPS `civitai.com`; none to `www`, `b2` or any changed origin. Reject disallowed initial URLs and redirect destinations, userinfo, ports, schemes and deceptive suffixes. Cover loops/hop limit, allowed CDN streaming, 401/403/429/network failures and deadline exhaustion across nested reads, retry/backoff and chunk streaming. Check success, rejection and interruption close streams, including an unconsumed response. Independently demonstrate that header leakage, file-precedence bypass and loss of the total bound make meaningful guards fail, then restore green. |
| D4 | CLEAR: bounded live source comparison has an existing selected route and honest adverse outcomes. | After code freeze, exercise the actual configured-file resolver and request machinery on version 1843039/file 1743033. Anonymous comparison can use separate ephemeral process configuration; it must not rewrite canonical settings or reintroduce manual key injection. Credentialed redirect/CDN HEAD or bounded equivalent is enough; do not fetch a whole file. Record actual status and loaded component identity even if provider behavior changes. This source-component probe does not establish Backend redeployment. Exclude private values/digests and signed query values while retaining complete declared ordinary source hashes. |
| D5 | CLEAR: ownership, exact-source delivery and regression gates are defined. | Coding supplies its own manifest, current topic docs, final full SHA and sanitized evidence. Independent delivery QA reviews that exact commit and actual boundary/fault evidence, runs affected meaningful checks plus the existing registry guards with isolated roots and `--timeout=60`, and reports skips/platform limits. Any subsequent software change requires another exact review. |

The metadata total of 20 seconds includes nested HTTP reads; the download
transport total of 900 seconds includes all retained retries/backoff and redirect
hops. Per-request connect/read settings alone cannot prove either total. The
download bound is not a generic MCP caller-wait guarantee, local hashing benchmark,
new cancellation API or scheduler requirement. An interrupted caller must not be
reported as a failed transport or trigger a duplicate submission.

Security scope includes logs, signed redirect URLs, provider exception strings,
metadata, records and MCP errors. The current shared redactor recognizes exact
credential keys, preserving `tokenizer` keys, but its query pattern does not cover
all signed query forms. Delivery tests need realistic signed-query cases and
actual secret-value exclusion at the scoped request boundary. Do not delete
ordinary file hashes or rewrite p2-00 raw evidence to make a scan pass.

One existing implementation assertion needs explicit handling:
`backend/tests/test_civitai_resource_install_api.py::test_civitai_download_transport_follows_redirects_and_streams`
asserts `follow_redirects is True`. D3 intentionally changes automatic redirects
to explicit bounded handling. Coding should list the changed assertion under
manifest deviations and retain meaningful redirect, byte-stream and closure
coverage. This does not justify deleting the feature test, broad test churn,
changing existing skips or superseding any registry behavior. The spec excludes
test deletion, not necessary documented updates to an obsolete implementation
assertion, so this is not a kickoff ambiguity.

## Commands, results and verification limits

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-180-kickoff-review`,
branch `aid-180-p2-01-kickoff-review`, created at the fixed source. The shared
checkout stays on `main`; its 13 concurrent memory edits were not staged, reset,
stashed or copied into this report branch. No product, tests, registry, private
settings, environments or p2-00 evidence were edited.

- `git rev-parse`, `git ls-tree`, `git show` and targeted `rg`/`sed` reads established
  the fixed task/source, retained call paths, adapters, errors and test boundaries.
- `python3 -B docs/tasks/p2-01-civitai-key-file/kickoff-evidence/check_source.py`:
  **36 static source/identity assertions passed**; all **202** tracked files in
  the declared inventory match their fixed Git blobs. See the complete
  [source inventory](kickoff-evidence/source-inventory.json). The declared scopes
  are Backend application/workflows, MCP implementation and listed review inputs;
  this is not a whole-disk or loaded-runtime inventory.
- Git object comparison confirms Backend application/tests/workflows, MCP
  implementation/tests, frontend and the registry are identical to accepted
  First check QA `9caf92fefac6f30255bac528e3f4292f2c1bddf6`. Its recorded Backend
  1,916 passed/124 skipped, MCP 666/four skipped, separate PNG six passed and
  frontend 226/one skipped/build results are historical context on unchanged
  product trees. They are not fresh p2-01 tests or proof of a new file reader.
- `git diff --check`: passed for the authored report/evidence. The 18 existing
  active registry rows are unchanged; kickoff adds no certified product behavior
  and no `review.md` coverage rows, so the registry was not regenerated.

**Offline:** independent static review and source identity audit only. No new
product suite or mutation test was run: this assignment is specification kickoff,
not contract certification, and explicitly requests the smallest relevant static
checks rather than rerunning unchanged suites.

**Running service:** not probed, restarted or redeployed. **Provider/generation:**
no new provider request, key read, download, registration or generation.
**Retrieval:** no live Gallery/model/artifact retrieval; official review uploads
and their byte readback are recorded separately in AID-180's delivery receipt.
Windows and real cancellation/rate-limit/Early Access behavior were not exercised.
No artifact contains new private/provider observations: evidence inputs are fixed
tracked source and QA-authored observations, with no private-key digest computed.

## Handoff

Producer should read this actual CLEAR and dispatch separate Coding and
exact-final-commit delivery QA cards with native prerequisites. This QA kickoff
card completes with its own verdict and official artifacts; it does not modify
the parent's owner/status, implement the task or self-authorize delivery PASS.
