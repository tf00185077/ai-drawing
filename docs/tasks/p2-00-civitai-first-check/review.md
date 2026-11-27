# Phase 2 First check independent delivery review

Verdict: PASS
Review round: 1
Issue: [AID-179](/AID/issues/AID-179)
Coding: [AID-178](/AID/issues/AID-178)
Exact candidate: `0d571b7d571561ebdea34c959ed6f16e2db06953`
Exact tree: `f542e7692a3b529eaa2b55d4dea1ea1df127156f`
Base: `2d2a0b1b46cbfe196815e21bb4aede6e87228bf6`
Owner handoff: `1666ffb9d264946e2fb7bbffb583f6180f6d8722`
Task SHA-256: `dfb23f60ecbd18bd8f8e481dc725406f2bfa07653f2172b5efcadd44748e6777`

PASS applies to this **observation record** against D1–D5. The record also
supports one successful, manually bridged real search/download/registration/
checkpoint-plus-LoRA image chain. It does not establish an implemented automated
Phase 2 product flow, three consecutive zero-fix exit runs, a fresh checkpoint
download or CTY's aesthetic acceptance.

## Findings

No P0/P1 defect found in the delivered observation. No product repair was made.

**P2 — five supplemental ComfyUI source fingerprints were over-redacted.**
In runtime-supplement, five dictionary paths
containing `tokenizer` have `[REDACTED]` instead of a hash. The measurement helper's
`common.clean` treats the substring `token` in any dictionary key as sensitive.
An initial QA supplemental all-hashes assertion exposed the masking rather than
a demonstrated source change. QA independently matched the other **787** ComfyUI fingerprints
and all **137** retained Backend runtime fingerprints. The five current files
also equal their Git objects at the recorded ComfyUI commit
`7597a5a0d59ee251674e6c1270049909c63e7ede`. Their missing before-run fingerprints
cannot be reconstructed as original measurements. This is an evidence-usability
limit, not a demonstrated execution failure; the graph, original bytes, preserved
process identities and retained source binding support this bounded observation.
See source check. For future evidence
helpers, redact credential fields without masking ordinary source-path keys.
Keep this original record unchanged.

## Done when assessment

| Item / level | Independent result | Evidence and practical limit |
|---|---|---|
| D1 / P1 | PASS — baseline observation | Fixed task, actual copied kickoff report and all 147 publication/source fingerprints agree with Git. Executor's private readable/nonempty/0600 check is present. Interpreter/package/import paths, effective nonsecret roots, old jobs/queues and disk are recorded. QA corroborated prior process identities, runtime source files, actual selected model bytes and private before-snapshot row preservation. Key presence is separate from provider authentication; source binding is bounded as above. |
| D2 / P1 | PASS — provider/download observation | Real safe search and selected version/file identity, license/permission fields, downloads/thumbs-up metadata, exact size/SHA-256 and anonymous-versus-credentialed outcomes are retained. Actual async acquisition 80 installed the selected file through current acquisition/safe-download code with a disclosed injected transport. QA rehashed the real installed bytes. No mock provider or repeated provider measurement was used by QA. |
| D3 / P1 | PASS — registration/image observation | Current installer adopted the hash-matched existing checkpoint as 81, with disclosed local filename mapping. Sole local `default_lora` job completed with explicit nonempty LoRA, triggers and manual parameters. Persisted rows, submitted request, PNG embedded graph and ComfyUI history agree; sampler and LoRA nodes were uncached. QA independently decoded and retrieved the same Gallery bytes and read the same completed job/history. |
| D4 / P1 | PASS — friction/service account | Counts independently reconcile to 64 events, 14 provider HTTP requests, one admitted acquisition, one generation submit, one wait and 42 same-ID status reads. Fifteen capability plus five execution/recovery interventions are disclosed; seven preparation/audit and six delivery blocks account for the remaining work. Used/untouched services are distinguished, with value-type-only use labeled. Original failures remain; no pending measured job or hidden worker fallback is evidenced. |
| D5 / P1 | PASS — exact reviewable delivery | The native Coding done receipt names the actual full commit/tree, not a future self-SHA. All 89 candidate changes are confined to this task's evidence/docs. QA downloaded the four official payloads plus receipt; hashes agree, all 90 ZIP payloads equal frozen Git bodies, and the bundle verifies/names the exact commit. This independent report is delivered on QA's own card. |

Detailed QA assertions are in independent audit
and official artifact integrity.
The actual kickoff report equals the report at
`4702a662a88bf5611dcee9c5da1964a21a41aa74`; it clears the unchanged operating
brief, including counted manual bridges and truthful adverse outcomes.

## Actual chain and authentication classification

Safe search used `query=watercolor`, `types=LORA`, `baseModels=Illustrious`,
`nsfw=false`. Three first-version search candidates were considered; one LoRA
version and one checkpoint version were inspected in detail, within the brief's
three/two limit. Selected LoRA model **551903**, version **1843039**, file
**1743033** is `WatercolorMJ7Illustrious.safetensors`. Selected version NSFW level
is **1**; the model aggregate is **23** despite `nsfw=false`, both truthfully
retained. No preview bytes or explicit-content query were used. Model/versions
retain real download and thumbs-up counts; absent star ratings and version
sampling recommendations are not invented. No commercial-use license filter or
paid/Early Access purchase occurred.

The same selected file route returned anonymous HEAD **401** and bounded GET
**401**, whose body expressly requires login. Credentialed HEAD and actual GET
returned **307**, followed by credential-free CDN HEAD/GET **200**. Thus this
record demonstrates successful access to **this login-required file with the
owner's free key**, separately from its local presence check. It is not evidence
of anonymous/public-download success, every restricted resource, Early Access
refusal or sustained rate-limit capacity. No **429**, free-key refusal or Early
Access result occurred; quota headers were absent. QA made no new provider request.

New LoRA bytes: **228,518,900**, SHA-256
`77d71396e29a26225a6dce2544930e58983fc12a754f8fb602df11ee383ee34b`.
Existing checkpoint bytes: **6,938,040,674**, SHA-256
`c2a1a3eaa13d4c107dc7e00c3fe830cab427aa026362740ea094745b3422a331`.
QA recomputed both from the actual host files and matched provider metadata.
The checkpoint hash identifies model **1489531**, version **1684912**, file
**1586063**. Its published `-stable` filename differs from the local filename;
the counted mapping preserves and adopts the exact existing bytes, without a
checkpoint download, rename or overwrite. Registration uses the existing
`DownloadedResource` ledger, not an invented parallel registry.

Published exact size agrees with CDN Content-Length and actual bytes. One
transport attempt streamed the LoRA; zero internal retries/resume. The temporary
8 GiB/file, 10 GiB total and 20 GiB reserve limits were inspected in the actual
injected transport and independently checked against recorded totals/free space.
Initial free space was **15,236,485,349,376** bytes and post-download free space
**15,236,246,274,048** bytes. The LoRA is below the 512 MiB preference. Extension,
scan/hash/size, finite deadline, redirect/credential and existing-target guards
were present. These are measured hand-run safeguards, not stock product guarantees
or tested refusal behavior under every adverse condition.

Sole Backend job: **`da6a825f-5687-4b7e-94e2-f213ae33150c`**.
ComfyUI prompt: **`82c8a922-706e-4727-8e9e-503de19e7444`**.
Image **4463**, canonical artifact **3878**, Gallery path
`2026-11-26/ComfyUI_00268_da6a825f_0.png`.
Exact prompt:

> a blue ceramic cup on a wooden table, soft daylight, simple still life, no people, ArsMJStyle, Watercolor

Seed **638386492**, batch one, **512×512**, **20 steps**, **CFG 7**, **Euler/normal**,
LoRA model/CLIP **1.0/1.0**, explicit empty negative prompt. Triggers come from the
selected version; starting strength ~1 comes from the model description. Absent
version sampling recommendations use the brief's disclosed fallback. These values
were manually applied. Current acquisition family `illustrious`, registration
family `Illustrious` and manually selected workflow family `sdxl` remain distinct.
Actual LoRA tensor metadata identifies SDXL and the actual `LoraLoader` patches
both model and CLIP; both text encoders and sampler consume its outputs.

The original PNG and
QA's independently retrieved bytes are both
**333,502 bytes**, SHA-256
`8268b9571b8b9535b9500994a021919de317f84b1fbb36d9b74468d969ca3673`.
Both decode to one 512×512 frame. Visual inspection shows the prompted blue cup
on a wooden table without people; no artistic quality verdict is made. PNG graph,
persisted graph and successful ComfyUI history match. Nodes 3 (sampler) and 10
(LoRA) were uncached; the log records 20 sampler steps and **18.49 seconds total
prompt execution**, not isolated inference timing.

## Failures, recovery, accounting and bounded next gaps

The original failed observations remain part of the result: a quota interruption
after preflight; a premature hash-file read before the calculation completed;
a reaped detached launcher before any import/admission; two successful metadata
reads followed by the wrong import-root SQLite missing-table error **before**
acquisition admission; and an offline accounting helper integer-key TypeError.
Recovery reused the existing runtime import root and preserved private config.
No product/schema/workflow/dependency repair, restart, hidden generation retry or
worker fallback replaced that baseline. The two admitted resource rows and one
image/artifact are the only database additions. QA independently compared all
**9,218** pre-existing rows in **15** tables against the private before snapshot:
none changed or disappeared, and schema agrees. This does not claim an exhaustive
before/after byte inventory of every file on the model/output disks.

The [friction ledger](friction-ledger.md) counts **15 capability interventions**
(including seven credential-bearing process bridges) and **five execution/recovery
interventions**, totaling **20**. The **64** instrumented observations comprise
18 preparation, 32 flow, two recovery and 12 audit events. They are call/boundary/
verification observations rather than HTTP-request counts. Seven additional
preparation/audit blocks plus six delivery blocks yield **77** whole-round work
units. The receipt freezes at 75 with two pending delivery blocks; its subsequent
native done comment and official receipt readback complete those two. Interventions
overlap work units and must not be added again. Provider counts independently
reconcile to **14 requests: 10×200, 2×401, 2×307**. Backend log corroborates one
submit and **42** status GETs on the same job, including 40 inside the sole wait.
No timeout or uncertain admission was followed by a duplicate submission.

The inventory has **19** Civitai service modules: seven called modules including
one value type, and **12** with no operational invocation. QA traced the actual
current acquisition, safe-download, install, acquisition helpers, local-ledger,
resolution value type and source-alias read call paths. Importing a module is not
operational use of every service; historical alias provenance is not new provider
traffic. No dynamic profiler was attached, and this inventory alone does not
establish that deleting any module is safe.

Producer can turn observed gaps into separate bounded specifications: safe agent
search/version inspection; private file-key loading; stock asynchronous download
budgets/deadlines/credential-safe redirects and clear restricted/rate-limit errors;
consolidated Backend resource records/reuse and one SDXL mapping; and resource-
derived triggers/parameters/workflow selection. The record demonstrates why those
bridges are needed; it does not implement or independently CLEAR those changes.
Producer owns next work after reading this verdict. No repair was delegated or
performed by QA on this observation card.

## Commands and verification

Worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-179-qa`,
branch `aid-179-exact-review`, created at the exact candidate before substantive
review. Shared `main` and concurrent memory edits were untouched. Existing Python
3.11 QA and Backend dependency directories and frontend dependencies were reused;
no package installation or canonical environment edit. Test roots, build output
and Vite/Vitest cache are isolated in this run's Paperclip scratch directory.
Python suites have `--timeout=60`, explicit plugins and external-network/private-
`.env` guards; loopback fixture servers and SDK subprocesses are permitted.
No existing test was edited, removed or newly skipped.

Actual commands are captured in the per-case JSON receipts and complete raw logs:

| Check | Command / evidence | Fresh result |
|---|---|---|
| Backend full suite | `python3 .../review-evidence/run_review_checks.py backend`; command, log | **1,916 passed; 124 skipped** |
| MCP full suite | `python3 .../review-evidence/run_review_checks.py mcp`; command, log | **666 passed; four skipped** |
| Separate registered PNG guard | `python3 .../review-evidence/run_review_checks.py registry`; command, log | **Six passed** |
| Frontend full suite | `python3 .../review-evidence/run_review_checks.py frontend`; command, log | **226 passed; one skipped; 23 files passed** |
| Production build | `python3 .../review-evidence/run_review_checks.py build`; command, log | **Passed** |
| Coding saved-evidence replay | `verify-evidence.py`, without `--record`; receipt | **23 assertions passed** |
| Independent bytes/records/graph/accounting/live audit | `.../aid-175-qa/.venv/bin/python -B .../review-evidence/independent_audit.py`, with existing Backend site-packages; result | **37 checks passed** |
| Official payload readback | `python3 .../review-evidence/verify_official.py`; result | **Four payloads plus receipt verified; 90 exact Git ZIP payloads / 91 members; bundle verified** |

The registry's 18 active contracts are covered by the two full Python suites and
the separate PNG guard. Registry regeneration completed cleanly
with identical existing row bodies; no new automated product contract or
supersession is created. All new
D1–D5 checks here are manual/inspection/delivery evidence, so mutation testing a
production change would not test this task and was not performed. Existing
platform/optional skips and dependency/build warnings remain visible in logs.
Windows was not executed.

## Checked boundaries and untested outcomes

- **Offline:** all suites/build, recorded provider metadata and safe auth outcomes,
  source/task/packet fingerprints, full PNG decode/graph correlation and operation
  counts were independently checked. The key value is excluded from candidate
  changes; no key digest/header/signed query or private-settings dump is delivered.
- **Running services:** QA performed exactly four new local product-service GETs: same job status,
  artifact 3878 metadata, its Gallery PNG and the exact ComfyUI prompt history.
  All returned 200; raw metadata/history, bytes and request digests are retained
  separately in review evidence. QA also read selected host files and private
  SQLite before/current databases in read-only mode. No restart, deployment,
  private-config rewrite or universal loaded-module attestation was performed.
- **Real generation/provider:** this review corroborates Coding's one real chain.
  QA made **zero** new provider requests/downloads, registrations or generation
  submissions. Only this selected LoRA/checkpoint/default_lora pair is established.
- **Artifact retrieval:** Coding's fresh-session MCP canonical-byte response was
  decoded and compared independently; QA additionally retrieved the actual current
  PNG through the local Gallery HTTP route. Technical retrieval is established;
  no future caller/platform transport limit or aesthetic acceptance follows.
- **Unmeasured stages/branches:** live cancellation, timeout/resume recovery,
  duplicate-admission races, public-file anonymous success, free-key refusal,
  Early Access refusal and rate-limit capacity were not forced during the hand
  run. Existing fixture tests are not relabeled as those live outcomes. Fresh
  checkpoint download, automatic Phase 2 behavior and all three zero-fix exit runs
  remain untested/unmet. CTY alone judges aesthetics.

## Coverage

This task adds no `test` Done when items and supersedes none. Empty table is
intentional for registry parsing; D1–D5 are assessed above as operating evidence.

| item | level | guarding_test | status |
|------|-------|---------------|--------|
