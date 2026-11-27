# Phase 2 First check measurement delivery

The real safe search → key-required download → current resource registration →
local checkpoint + LoRA `default_lora` chain completed once. This is an
evidence-only observation with **20 counted intervention units**. Independent
exact-evidence QA and CTY's aesthetic judgment remain separate; no Phase 2 exit,
software acceptance or self-PASS is claimed.

## Fixed inputs and delivery

- Coding: [AID-178](/AID/issues/AID-178); dependent exact-evidence review: [AID-179](/AID/issues/AID-179).
- Actual [AID-177](/AID/issues/AID-177) full kickoff report read: **CLEAR**, commit `4702a662a88bf5611dcee9c5da1964a21a41aa74`.
- Fixed publication/base: `2d2a0b1b46cbfe196815e21bb4aede6e87228bf6`; owner handoff `1666ffb9d264946e2fb7bbffb583f6180f6d8722`.
- Task SHA-256: `dfb23f60ecbd18bd8f8e481dc725406f2bfa07653f2172b5efcadd44748e6777`.
- Persistent isolated worktree `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-178-first-check`, branch `aid-178-first-check`.
- This manifest is included in the exact evidence commit. Its full final commit/tree and official artifact hashes are pinned in AID-178's post-commit delivery receipt; no circular self-SHA is embedded here. The branch is not merged or pushed.

## Actual result

Safe search `query=watercolor`, type LORA, base Illustrious, `nsfw=false` selected
model **551903**, version **1843039**, file **1743033**,
`WatercolorMJ7Illustrious.safetensors`. The selected version is SFW (`nsfwLevel=1`),
published and has no paidAccess. Model permissions/license and real downloads/
thumbs-up counts are retained; a numerical star rating is absent, not invented.
The model's aggregate NSFW level is 23 while its `nsfw` flag is false; only the
SFW selected version and safe still-life prompt were used. No preview was fetched.

Anonymous HEAD **401** and a later bounded anonymous GET **401** on that exact
file route contrast with the credentialed GET **307** followed by a credential-free
CDN GET **200**. The GET refusal explicitly says login is required. Actual key-file
presence/readability/nonempty/0600, authenticated-route success and byte verification
are separate observations. This demonstrates access to this selected login-required
free-key file, not all restricted resources. No 429, Early Access refusal or paid
purchase occurred; rate-limit quota headers were absent. Normal-use rate-limit
capacity remains unmeasured.

Acquisition/resource **80** installed **228,518,900 bytes**, SHA-256
`77d71396e29a26225a6dce2544930e58983fc12a754f8fb602df11ee383ee34b`.
One download attempt, no retry/resume; exact published size independently agrees
with CDN Content-Length, and a separate post-download hash agrees. Free disk was
15,236,485,349,376 bytes at initial preflight and 15,236,246,274,048 after download,
well above the 20 GiB reserve; guards also ran while streaming. No existing final
or part file was overwritten.

Existing `Illustrious-XL-v2.0.safetensors` is **6,938,040,674 bytes**, SHA-256
`c2a1a3eaa13d4c107dc7e00c3fe830cab427aa026362740ea094745b3422a331`.
Real provider hash lookup identifies model **1489531**, version **1684912**, file
**1586063**, whose published filename includes `-stable`. Current inspect/select/
install, with the counted local-name mapping, rehashed/adopted the bytes into
existing Backend ledger resource **81**. It did not redownload the checkpoint.
This reuse does not satisfy the later fresh-checkpoint-plus-LoRA exit condition.

One Backend job **`da6a825f-5687-4b7e-94e2-f213ae33150c`** completed locally.
ComfyUI prompt **`82c8a922-706e-4727-8e9e-503de19e7444`**, image **4463**,
canonical artifact **3878**, Gallery path
`2026-11-26/ComfyUI_00268_da6a825f_0.png`. The exact final prompt is:

> a blue ceramic cup on a wooden table, soft daylight, simple still life, no people, ArsMJStyle, Watercolor

Seed **638386492**; batch one; **512×512**, **20 steps**, **CFG 7**, **Euler/normal**;
LoRA model/CLIP strengths **1.0/1.0**; empty negative prompt explicitly supplied.
Trigger words and all parameters were manually applied. Strength follows the
model-description starting point; version-specific sampling recommendations were
absent, so the brief's fallback settings were used. Actual LoRA tensor metadata
says `stable-diffusion-xl-v1-base/lora`, and current loader options contain both
files. The compiled graph links LoRA output to sampler and both text encoders.

The original PNG was retrieved through a new actual MCP
SDK session's canonical Gallery read, then base64-validated, hashed and fully
decoded: one frame, **333,502 bytes**, SHA-256
`8268b9571b8b9535b9500994a021919de317f84b1fbb36d9b74468d969ca3673`.
Submitted settings, persisted graph, PNG embedded graph and successful ComfyUI
history agree. Sampler/LoRA were uncached; cached nodes were checkpoint 4 and
latent 5. The log reports 20 real sampler steps and 18.49 seconds total prompt
execution, not an isolated GPU-inference-time measurement. No aesthetic verdict.

## Done when evidence

| Item | Check / level | Evidence | Actual boundary / result |
|---|---|---|---|
| D1 — actual baseline bound | manual / P1 | preflight, runtime supplement, selection, guard | Actual owner Mac key access, source/import/interpreter/packages/schema/process/jobs/roots/disk and real candidate metadata. No mock. |
| D2 — real provider/download observation | manual / P1 | search, version, access probes, anonymous GET, acquisition, bytes | Real Civitai/credential route/CDN/actual bytes/current acquisition ledger. One new LoRA; checkpoint reused by real provider hash. No mock. |
| D3 — registration/image observation | manual / P1 | registration, request, submit, records, graph check, retrieval, PNG | Actual current installer, Backend queue, local ComfyUI, persisted Gallery and original canonical MCP bytes. No mock or replacement image. |
| D4 — friction/service account | inspection / P1 | [friction ledger](friction-ledger.md), events, service inventory, preservation | 14 provider requests, one acquisition/submit, full same-ID status accounting, 20 interventions; seven called modules including one value type, 12 operationally untouched; no pending job. |
| D5 — independent reviewable delivery | delivery + independent review / P1 | This manifest, evidence index/offline verification, native full commit/tree and downloadable package/bundle/PNG delivery receipt on AID-178 | Coding freezes and uploads actual evidence; AID-179 pins and independently reviews that exact commit. QA verdict is pending and belongs to QA. |

## Verification and preservation

- **Offline:** `python docs/tasks/p2-00-civitai-first-check/evidence/verify-evidence.py` checks actual saved hashes/PNG/graph/IDs/budgets/source/task/accounting and credential exclusion. No speculative product suite, Windows run, dependency install or test edit. AID-177's prior suite results are not relabeled as this run's tests.
- **Running services:** prior Backend PID 99953 and ComfyUI PID 99952, creation/cmdline/cwd and effective nonsecret settings remain unchanged. All product fingerprints match fixed measurement source; equivalent existing Backend imports and live OpenAPI are retained. This is bounded source binding, not universal loaded-module attestation.
- **Real generation:** one successful local checkpoint+LoRA job, one bounded wait; no worker/training/fallback/retry/resubmit. Actual successful ComfyUI history and uncached sampler corroborate execution.
- **Artifact retrieval:** actual new-session canonical Gallery bytes fully decode, match hash/length and graph, and remain linked to image/artifact/job/resource records. Local service URLs are host locators; official uploads provide board access.

All prior SQLite schema and row values match the private before snapshot. Only
two resource rows, one image and one artifact were added. Existing AID-171 runtime/
private config/backups, AID-151 snapshots, venvs, shared-main edits, models,
datasets, outputs and Gallery records were preserved. No runtime restart,
product/service/schema/workflow repair, package installation or deletion.

## Deviations, failures and limits

The brief expressly permits counted hand bridges. They were used for absent
search/key-file support, bounded safe download, current checkpoint registration,
family/workflow choice and trigger/default application. Current records remain
the actual `DownloadedResource` ledger plus its existing local projection/aliases;
no parallel registry was introduced. Trigger words/recommendations were retained
as task evidence, not fabricated as automatically stored/applied product fields.

Five executor/platform friction incidents and all failed observations are kept in
the ledger and runtime supplement. The pre-admission wrong-import attempt and
detached launcher did not create an acquisition; the sole admitted ID was 80.
No product tests were run to establish a fresh failing baseline; no known test was
changed/removed/skipped. Later detailed product repairs require their own CLEAR
specification and exact-commit QA. One Mac, one selected file/checkpoint/workflow,
no commercial-use filtering, no paid access, no broad rate-limit conclusion,
no later three-run exit and no aesthetic acceptance are claimed.
