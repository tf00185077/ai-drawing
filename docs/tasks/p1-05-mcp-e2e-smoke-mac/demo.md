# p1-05 reviewed Mac demo — awaiting CTY

**Decision pending.** Independent [QA AID-175](/AID/issues/AID-175) passes D1–D3
for candidate **91d6e3790ecbb258b1a079395a1156912d090b62** (software freeze **e7819bcc02ceadc0dafad6d77a634618b5bfc02f**).
[Actual independent report](/api/attachments/acdf3498-3dc7-427d-9327-f591bca9cbfe/content),
report/evidence **ade78141f693a6ff1259d8b61d883e77434b2ccd**; [actual Coding manifest](/api/attachments/505ea4b5-d718-4792-a384-053de085f25d/content).
D4 stays **unchecked, awaiting CTY's explicit project-channel reply to this demo**.
The feature is not merged/pushed; Phase 1 is not closed and Phase 2 is inactive.

## What this shows

One frozen real SDK stdio invocation completes three consecutive original/revision
pairs. Each pair makes exactly eight MCP calls: health, resources, original
submit/wait/content, revision submit/wait/content. Six distinct jobs actually
sample on Mac ComfyUI; the caller receives and decodes the exact PNG bytes from
MCP, with persisted canonical parent/job/request/brief records. No manual fix,
retry, recovery or outside-MCP product operation occurs inside those flows.
All six images below are the unchanged recorded MCP payloads, verified against
official uploads and the candidate; none is regenerated, retouched or selected
as an aesthetic winner. Revision is a new generation with a changed prompt and
persisted parent; it makes no composition-preservation promise.

Parameters: Illustrious-XL-v2.0.safetensors / default / local / loras=[], 512×512,
batch 1, four steps, CFG 7, Euler/normal, fixed fresh seeds. Original prompt:
"a red ceramic cup on a wooden table, simple still life, soft daylight".
Revision changes red to blue. These are technical smoke parameters; CTY alone
judges whether the demo is acceptable. This is not a speed or quality benchmark.

| Attempt | Recorded UTC interval (2026-11-24) | Result | Original → revision |
|---|---|---|---|
| 1 | 16:57:28.571–16:57:45.531 | eight calls, streak 1 | 3872 → 3873 |
| 2 | 16:57:45.531–16:57:58.330 | eight calls, streak 2 | 3874 → 3875 |
| 3 | 16:57:58.330–16:58:15.132 | eight calls, streak 3; then stops | 3876 → 3877 |

## Images and Gallery records

Canonical artifact IDs and separate image IDs are distinct namespaces. These
are the original qualified Gallery record fields, corroborated by later SDK
sessions and QA's read-only persistence audit. Full values/digests are retained
in [the machine-readable projection](demo-evidence/bundle-and-real-evidence.json).
Each pair shares the exact request_ref shown below. All static PNGs are 512×512.

### Pair 1 — 3872 → 3873

Original **3872**, image 4457:

![Original artifact 3872](/api/attachments/4a73189b-e524-4608-a4f5-0da6a00770fc/content)

Revision **3873**, image 4458:

![Revision artifact 3873](/api/attachments/235cc19f-df0e-421a-8f82-b89239b9dc7a/content)

| Gallery field | Original | Revision |
|---|---|---|
| artifact_id | 3872 | 3873 |
| job_id | `0125d67b-25c5-42f5-b946-637eb56b1d6b` | `b4db9cd7-967c-4b33-a0db-f5612f203f07` |
| brief_revision | red-cup-v1 | blue-cup-v2 |
| parent_artifact_id | null | 3872 |
| parent_job_id | null | `0125d67b-25c5-42f5-b946-637eb56b1d6b` |
| parent_brief_revision | null | red-cup-v1 |
| PNG byte length | 351235 | 249637 |
| Gallery path | `2026-11-24/ComfyUI_00262_0125d67b_0.png` | `2026-11-24/ComfyUI_00263_b4db9cd7_0.png` |

request_ref for both: `p1-05/ab9b336d-e285-4821-9570-49f2c03a64fa/attempt-1`.
Revision parent_request_ref equals that same value. Both revision_context_error
values are null; parent_context_status is root/available respectively.

### Pair 2 — 3874 → 3875

Original **3874**, image 4459:

![Original artifact 3874](/api/attachments/bcf0f4d5-0433-48f5-acfd-146cf285cfd6/content)

Revision **3875**, image 4460:

![Revision artifact 3875](/api/attachments/fa6e1652-04d4-4360-b14a-637c2b4855d2/content)

| Gallery field | Original | Revision |
|---|---|---|
| artifact_id | 3874 | 3875 |
| job_id | `90bfbceb-e900-4dcc-9089-7bd4f8b5f316` | `3618799b-c3a9-4986-bb98-c59b102a5e17` |
| brief_revision | red-cup-v1 | blue-cup-v2 |
| parent_artifact_id | null | 3874 |
| parent_job_id | null | `90bfbceb-e900-4dcc-9089-7bd4f8b5f316` |
| parent_brief_revision | null | red-cup-v1 |
| PNG byte length | 218504 | 245252 |
| Gallery path | `2026-11-24/ComfyUI_00264_90bfbceb_0.png` | `2026-11-24/ComfyUI_00265_3618799b_0.png` |

request_ref for both: `p1-05/ab9b336d-e285-4821-9570-49f2c03a64fa/attempt-2`.
Revision parent_request_ref equals that same value. Both revision_context_error
values are null; parent_context_status is root/available respectively.

### Pair 3 — 3876 → 3877

Original **3876**, image 4461:

![Original artifact 3876](/api/attachments/de2d17fc-d306-4447-ab4f-0e1eceb61391/content)

Revision **3877**, image 4462:

![Revision artifact 3877](/api/attachments/84fbd5f7-4837-441c-8d41-2cc2fae59b6a/content)

| Gallery field | Original | Revision |
|---|---|---|
| artifact_id | 3876 | 3877 |
| job_id | `668610f6-1883-470d-8b86-cd02811bd18e` | `7c35d993-d091-44c5-8b13-25f9a92dc271` |
| brief_revision | red-cup-v1 | blue-cup-v2 |
| parent_artifact_id | null | 3876 |
| parent_job_id | null | `668610f6-1883-470d-8b86-cd02811bd18e` |
| parent_brief_revision | null | red-cup-v1 |
| PNG byte length | 238933 | 267709 |
| Gallery path | `2026-11-24/ComfyUI_00266_668610f6_0.png` | `2026-11-24/ComfyUI_00267_7c35d993_0.png` |

request_ref for both: `p1-05/ab9b336d-e285-4821-9570-49f2c03a64fa/attempt-3`.
Revision parent_request_ref equals that same value. Both revision_context_error
values are null; parent_context_status is root/available respectively.

## What was verified

- **Offline:** independent current Backend 1916 passed/124 existing platform skips; restored MCP plus six QA cases 672 passed/four existing optional skips; fresh revision export one passed and current cross-layer consumers seven passed. Three actual CLI signal cases fail on old source and pass on this source; five independent faults fail and restore. R5-1 is resolved. QA retains the original 16 registry rows and certifies D1/D3, 18 in its reviewed tree; main's registry remains unchanged pending feature merge.
- **Running services:** Coding and QA corroborate existing recorded process/source/import/settings/OpenAPI/schema and all old values read-only. No restart for this correction, no worker/training/resource change. This is not general in-process attestation. Preserve AID-171's runtime/private settings/backups, AID-151 snapshots, canonical venvs and all data.
- **Real generation:** six new distinct uncached KSampler histories and compiled graphs match the fresh declared seeds, parameters and recorded jobs. Attempts 1–3 qualify on corrected source. QA produces no replacement work; Producer generates nothing.
- **Artifact retrieval:** six original MCP-returned PNGs pass digest/length/static-frame/dimension/full-decoding and persisted-lineage checks. New driver/Coding/QA SDK sessions corroborate identical metadata/bytes. Producer views verified official copies and reads recorded evidence, with no new live Gallery-byte fetch or product probe.

## Baseline comparison and decision

Original baseline remains **23 units/eight incidents**, F1–F8 =
**1,1,1,6,1,11,1,1**. The old rejected delivery's **81** units remain historical.
The corrected Coding round records **22 preparation + 0 attempt interventions +
0 recovery + 14 audit = 36**. QA separately records **2 + 0 + 0 + 13 = 15**.
Only qualifying request-to-result flows have zero interventions. The complete
round is nonzero and exceeds baseline; no whole-round-zero or lower-total claim.
Source reading, packaging/control-plane work and this owner presentation remain
separate coordination overhead, not hidden generation calls.

Producer verifies all 22 official uploads, 1,897 Coding/680 QA indexed payloads
(1,898/681 members), exact reconstructed patches/trees, independent bundle fetches,
291 frozen source fingerprints, the 24 flow calls and six original payloads/
lineages. [Integrity evidence](demo-evidence/integrity-verification.json).
One kickoff ambiguity event/two P1 findings, clarification 1/kickoff 2 CLEAR,
first delivery FAIL/one implementation rejection/R5-1, correction 1/review 2
technical PASS remain distinct and unchanged.

**Recommendation:** accept this reviewed Phase 1 technical demo, then allow
Producer to integrate the exact reviewed feature/evidence after recording CTY's
actual explicit project-channel reply. If it needs changes, CTY specifies them;
changed code needs another exact-commit review and applicable real qualification.
This decision does not close Phase 1 or activate Phase 2. Producer will separately
present actual phase-exit evidence and ask CTY to review roadmap order/scope/next
phase at phase close. Actual calling-application limit remains unverified;
50 seconds is the wait fallback and 65 seconds the disclosed SDK guard.
