# Phase 1 execution plan — 2026-11-24

Status: **p1-00/p1-00a, combined p1-01/02 and bounded wait/results p1-03 accepted/published after actual independent exact-commit PASS; health/configured-worker p1-04 accepted after exact-commit PASS; p1-05 fresh kickoff and real Mac smoke/demo next**.
Planning/coordinating issue: [AID-141](/AID/issues/AID-141).
[Initial request](../../requests/2026-11-24-fresh-producer-planning.md) ·
[later owner instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md).

## Authority and adopted choices

The authenticated board relayed CTY's later instruction to proceed directly with
executable work and use routine reference options inside the project boundaries.
This supersedes the earlier planning-only framing and ordinary-choice wait. It
does not change the destination, phase order/scope, architecture, Not now list,
operating policy, three-real-run exit or independent review requirements.

Producer adopts `Illustrious-XL-v2.0.safetensors` + `default`, no LoRA and explicit
`execution_target=local` for p1-00 and p1-05. This is a delegated technical choice,
not an individual owner model selection or aesthetic approval. There is no
outstanding CTY question on the current supported path. Escalate a demonstrated
project-boundary change through native interaction plus project-channel delivery.

## Baseline and evidence

Fetched published `main` matched the clean local checkout at
`6be499f62629e6478bdb290951dbd0e6eb23c6a1`. Phase 0 remains done; Phase 1 now
proceeds under the later direction. This planning commit changes docs/specs only.

| Area | Observed source / read-only evidence | Work consequence |
|---|---|---|
| MCP surface | `tool_catalog.py`: 40 tools; 3 plain-text, 19 dict and 18 JSON-string categories; existing tool modules registered by `server.py` | Run the baseline on today's tools; envelope and consolidation still needed |
| Error boundary | Existing `tools/responses.py` helpers; `ContractFastMCP.call_tool` handles LoRA start validation only | Extend existing boundaries; test validation through the MCP call path |
| Generation/revision | Existing template/custom-workflow functions, Backend revision schema and Gallery artifact readers | Reuse them; revisions use a new generate request with `parent_artifact_id`, not `gallery_rerun` |
| Completion | Generation job endpoint returns durable artifacts; MCP has no wait tool | Read existing state; never resubmit on a wait timeout |
| Health/worker | `/api/system/status` and `/api/workers/status` already exist | Reuse these; registry/scheduler remain Phase 3 |
| Mac services | Backend healthy, system status connected; ComfyUI reports `darwin`/`mps` | Reachable now; no generation or deployed Git-revision proof implied |
| Adopted pair | Backend and ComfyUI both list the selected checkpoint; catalog marks `default` valid/SDXL; graph uses `CheckpointLoaderSimple` | No new download dependency; runtime compatibility remains p1-00 evidence |

The default graph saves an older, unlisted checkpoint filename. Pass the adopted
checkpoint explicitly through the existing generation argument; do not edit the
graph or download a replacement as a hidden baseline repair. Backend resource
listing describes Backend model directories, not worker readiness.

Read: README, AGENTS, INDEX, MEMORY and compute/model/revision topics; operating
policy; team guide, Producer role, skill bindings and channel routing; ROADMAP,
CURRENT, PROGRESS; decision files and all existing Phase 1 specs. Run-installed
Producer skills were loaded. The administrative live skill-selection GET returned
403; no configuration was changed or inferred from it. Native roster showed
Coding/QA available and other production specialists paused.

## Ordered native backlog

The existing task folders remain the implementation specifications. New native
cards give Producer coordination ownership and actual prerequisite edges; parent
links only group work. QA is the first released recipient. Coding/delivery-review
cards follow CLEAR kickoff without another routine start confirmation.

| Native card / order | Work and execution owner | Native prerequisite | Observable delivery |
|---|---|---|---|
| [AID-147](/AID/issues/AID-147), completed | QA kickoff for [p1-00](../p1-00-mcp-friction-run-mac/task.md) | Published fixed planning/spec commit `e443f2e` | [CLEAR](../p1-00-mcp-friction-run-mac/kickoff-review.md); independent reading and comparison; no execution acceptance |
| [AID-148](/AID/issues/AID-148), completed | Coding ran p1-00 without repairs | AID-147 CLEAR read by Producer before dispatch | [Evidence](../p1-00-mcp-friction-run-mac/manifest.md) `3081952`: passing Mac suite, completed original, byte retrieval/revision blocked; 23 intervention units/eight incidents |
| [AID-149](/AID/issues/AID-149), completed | QA independently reviewed p1-00 evidence | AID-148 exact delivery | [PASS](../p1-00-mcp-friction-run-mac/review.md) at `3081952` for D1-D4 including the documented-blocker route; report/registry `c377a02` |
| [AID-150](/AID/issues/AID-150), completed | QA independently reviewed [bounded Mac runtime/retrieval repair](../p1-00a-mac-runtime-and-retrieval/task.md) | Published fixed specification `4ac3d56` and accepted baseline evidence | [CLEAR](../p1-00a-mac-runtime-and-retrieval/kickoff-review.md); official report/archive/patch match `9bd0029`; no specification change |
| [AID-151](/AID/issues/AID-151), completed | Coding delivered original p1-00a candidate `00ebb4d` | AID-150 actual CLEAR read; isolated branch from published `eaf11b8`; fixed task unchanged | Runtime/client-configuration/docs-only repair; fresh pair and decoded bytes/lineage; original raw evidence retained in corrected delivery |
| [AID-152](/AID/issues/AID-152), completed | QA independently reviewed exact candidate `00ebb4d` | AID-151 actual delivery | Historical [FAIL](../p1-00a-mac-runtime-and-retrieval/review-round-1.md): D1-D4 PASS, D5 incomplete runtime inventory; report `537d47f`; old values preserved |
| [AID-153](/AID/issues/AID-153), completed | Coding corrected inventory/schema evidence under original D5 | Actual QA finding and [bounded correction](../p1-00a-mac-runtime-and-retrieval/repair-round-1.md) at `c41815c`; original CLEAR/task unchanged | [Corrected manifest](../p1-00a-mac-runtime-and-retrieval/manifest.md), exact candidate `b6d5846`; complete schema/preservation receipts; no product change/restart/new generation |
| [AID-154](/AID/issues/AID-154), completed | QA independently reviewed exact corrected candidate `b6d5846`, round 2 | AID-153 actual delivery | [D1-D5 PASS](../p1-00a-mac-runtime-and-retrieval/review.md), report/evidence/registry `3d5d890`; applicable D1-D4 evidence reused with equivalence checks; one prior rejection retained |
| [AID-142](/AID/issues/AID-142), 1 | Producer accepted baseline and corrected repair | Actual AID-154 PASS read and official packets checked | [Acceptance](../p1-00a-mac-runtime-and-retrieval/acceptance.md), unchanged reviewed delivery integrated; publication/completion releases AID-143 |
| [AID-155](/AID/issues/AID-155), completed | QA independently reviewed both p1-01/02 fixed specifications at `d1ffb8d` | AID-143 complete baseline/friction handoff | [p1-01 CLEAR](../p1-01-mcp-response-envelope/kickoff-review-round-1.md); [p1-02 AMBIGUITY K2-1](../p1-02-mcp-tool-consolidation/kickoff-review-round-1.md), report `b32ac4f`; Producer's compose/save clarification needs fresh round-2 kickoff |
| [AID-156](/AID/issues/AID-156), completed | QA independently reviewed clarified fixed specs at `496cee2` | Actual first-round reports and Producer clarification 1 | [p1-01 CLEAR](../p1-01-mcp-response-envelope/kickoff-review.md) and [p1-02 CLEAR](../p1-02-mcp-tool-consolidation/kickoff-review.md), exact report `9d79d20`; K2-1 resolved at specification level, first-round history preserved |
| [AID-143](/AID/issues/AID-143), 2 | Producer coordinates [p1-01](../p1-01-mcp-response-envelope/task.md) + [p1-02](../p1-02-mcp-tool-consolidation/task.md); Coding; QA | AID-142 accepted usable baseline, plus newly CLEAR specs informed by its log | Uniform success/failure envelopes; catalog/intent/risk/mode coverage; docs and MCP suite; both changes published together at one reviewed final commit |
| [AID-144](/AID/issues/AID-144), 3 | Producer coordinates [p1-03](../p1-03-mcp-wait-and-result/task.md); Coding; QA | AID-143 accepted/published result; CLEAR kickoff | Complete/failed/timed-out generation/training jobs; truthful artifact/output locators; bounded calls, no timeout resubmission; sourced limit or explicit fallback |
| [AID-145](/AID/issues/AID-145), 4 | Producer coordinates [p1-04](../p1-04-mcp-health-and-workers/task.md); Coding; QA | AID-144 accepted/published result; CLEAR kickoff | Up/down/unconfigured health; empty or one configured worker; read-only risk; existing status endpoints reused |
| [AID-146](/AID/issues/AID-146), 5 | Producer coordinates [p1-05](../p1-05-mcp-e2e-smoke-mac/task.md); Coding; QA; CTY sees demo | AID-145 and all earlier accepted results; same adopted pair; CLEAR kickoff | Stdio smoke script; 3 consecutive original/revision real runs, zero manual fixes; retrieved artifacts and lineage; CTY demo reply and phase-close review request |

Keep the existing serial order. One Coding agent and one combined breaking change
make serial delivery clearer than parallel health/wait work. Phase 2 stays
inactive until Phase 1 exits and CTY reviews the roadmap at phase close.

## Specification reconciliation applied before kickoff

- The map contradicted the existing owner-confirmed LoRA exclusion. Keep
  `lora_train_job_status` and `lora_train_cancel` unchanged in Phase 1; their
  envelopes/risk labels change with the other tools. Renamed generation
  `job_status`/`cancel_job` do not absorb LoRA intents. This preserves scope.
- p1-02/p1-03 previously had six Done when items. Their existing checks are
  regrouped into at most five without dropping coverage; p1-01/02 still integrate
  together. A stale roadmap LoRA phase number is aligned to Phase 5.
- p1-03 reports training output/status honestly. No media artifact means an empty
  media list, not a fabricated image; preserve existing smoke-generation links.
- p1-03 inspects the actual client timeout. If no limit is established, use the
  existing 50-second fallback and label the client limit unverified. Include
  Backend request durations in the overall wait budget; do not certify an
  unknown limit as measured.
- p1-00's adopted resource pair is explicit in its specification and decision
  record. p1-05 reuses it. p1-00 does not fix failures: a non-passing full suite or
  blocked generation needs a bounded repair task and independent review before
  dependent work is released. A documented stop is evidence, not a phase pass.

QA independently reviews these points. A demonstrated spec defect is repaired or
escalated according to its actual effect on boundaries, not automatically sent
back to CTY as a routine technical option.

AID-143's [baseline-informed kickoff context](../p1-01-mcp-response-envelope/kickoff-context.md)
maps all eight original incidents without changing the 23-unit baseline or
overstating the accepted Mac repair. It clarifies MCP-path validation/error
coverage, all 40 old-tool dispositions and the staged `mcp_ping` → `health`
transition. QA must give a fresh explicit verdict for each fixed specification;
no earlier baseline/repair clearance releases Coding for p1-01/02. The recipient
card and current gate are linked in AID-143's native plan.

AID-155 returned p1-01 CLEAR and p1-02 AMBIGUITY at `d1ffb8d`. Its actual
reports/package were checked and preserved. [Clarification 1](../p1-02-mcp-tool-consolidation/kickoff-clarification-1.md)
settles K2-1 under the approved read/write map: composition rejects legacy
`save_as`; returned fragments are saved through `prompt_write(save)` with
existing concurrency/provenance semantics. Backend APIs and p1-01 task bytes
stay unchanged. Fresh independent round-2 verdicts for both fixed specs precede
Coding. This is one kickoff ambiguity/clarification round 1, not an
implementation delivery rejection; p1-00a accounting remains separate.

AID-156 returned explicit CLEAR for both at fixed `496cee2`. Producer read both
full reports and verified official reports/archive/patch/bundle and fixed
references against report commit `9d79d20`. This satisfies the kickoff gate;
Coding and a separate natively dependent delivery-QA card can proceed from the
published handoff base in AID-143's native plan. Task digests, decisions and
historical reports remain unchanged. Future software is not accepted by this
kickoff; exact-final-commit PASS still precedes combined feature publication.

## First p1-01/02 delivery result and correction

[Coding AID-157](/AID/issues/AID-157) delivered combined candidate
`b1082a855a66eedba6a4f11fbd4fcec0e9e867ab`, based on `cee1013`.
[QA AID-158](/AID/issues/AID-158) independently returned p1-01 PASS / p1-02
FAIL F2-1 (P1, D2), report/evidence/registry `1001586`. Producer read both actual
manifests/verdicts and the exact mutant/discovery/request evidence. All official
uploads, raw Git diffs, bundles and indexed archive contents match immutable Git.
Correct catalog labels are delivered, but the automated test uses the same
catalog as its oracle; a ComfyUI admin-to-read mutation remains fully green.

[Correction round 1](../p1-02-mcp-tool-consolidation/repair-round-1.md) repairs
this already cleared test-checked D2 without changing specifications or product
behavior. Coding must independently assert all 29 policy risks against catalog
and discovery, show false-admin-read fails, restore source and pass the full
MCP suite. Both manifests and a new exact combined candidate go to separate
independent delivery QA round 2. The live card identities and native prerequisite
chain are in [AID-143's plan](/AID/issues/AID-143#document-plan).

One p1-02 delivery rejection/correction round 1/next review round 2 is retained;
one kickoff ambiguity/clarification round 1/kickoff round 2 CLEAR and p1-00a
history remain separate. Candidate source stays unmerged and p1-03 remains gated
until both tasks independently PASS a new exact SHA, followed by publication.
No ordinary CTY confirmation or boundary/threshold escalation is needed.

## Accepted combined correction and next release

[Coding AID-159](/AID/issues/AID-159) delivered exact corrected combined
`616f67ff68fc27070e85861e94d70de1baf5082a`. [QA AID-160](/AID/issues/AID-160)
independently returned PASS for both original tasks at that SHA, report/evidence/
registry `28cd4512b8ec7d6594ec972ab81161b8c2d09d03`. Producer read both actual
manifests and reports plus exact false-label fault/restore/GREEN evidence.
All thirteen official uploads, exact patches/bundles and 147/123 archive entries
match their inventories and named immutable Git references.

[Combined acceptance](../p1-01-mcp-response-envelope/acceptance.md) integrates
reviewed source/manifests/reports/history/registry unchanged at
`7ba2059f7e46920eaf860e19e61aa84bae8bf02c`. Fresh independent QA Backend 1900/124 Windows skips,
restored MCP 460/two unchanged optional skips, parity five and additional
boundaries 15 pass. The risk downgrade now fails both guards/full suite before
restoration. Original task/decision bytes, 40-row mapping, all merged
capabilities, F1–F8 and prior baseline/repair evidence stay intact.

The final published main SHA/equality receipt is recorded in
[AID-143's plan](/AID/issues/AID-143#document-plan); subsequent acceptance/status
changes contain no new product code. One p1-02 rejection/correction round 1/
review round 2 PASS and prior kickoff/p1-00a counts remain recorded. No new live
service, generation, Gallery-byte, aesthetic or phase-exit proof is claimed.

AID-143's accepted publication/completion releases [AID-144](/AID/issues/AID-144)
for the existing p1-03 task's independent CLEAR kickoff. Its handoff must read
the new envelope/intent contracts and accepted manifests, preserve truthful
training outputs/locators and source the client limit or explicitly use the
unverified-limit/50-second fallback, including request time in the budget.
No routine start/resource/plan confirmation is pending.

## p1-03 kickoff result and clarification

[QA AID-161](/AID/issues/AID-161) independently returned **AMBIGUITY K3-1**
at fixed published `7a46cb7`, exact report/evidence `b3276dc`. Producer read
and verified the actual report, official uploads, archive/Git identity and
existing Backend source shapes. The [original task](../p1-03-mcp-wait-and-result/task-kickoff-round-1.md),
[round-1 report](../p1-03-mcp-wait-and-result/kickoff-review-round-1.md) and evidence
remain unchanged. One kickoff ambiguity is separate from delivery rejections.

[Clarification 1](../p1-03-mcp-wait-and-result/kickoff-clarification-1.md) resolves
the locator disposition under the delegated technical-choice rule: return real
canonical artifact identities and supported Gallery locators, preserve legacy
image-only results separately, and return a recoverable locator error with the
completed Backend state when required generation locators are unavailable/unsafe.
Training output and independent nullable smoke references stay truthful. No new
Backend storage/migration, file copying or phase boundary is introduced. The task
still has five Done when items and requires a total budget including request and
enrichment durations, sourced client limit or explicit unverified-limit/50-second
fallback, and no timeout cancellation/resubmission.

The next gate is fresh independent kickoff round 2 at the published clarified
source; [AID-144's native plan](/AID/issues/AID-144#document-plan) names the fixed
commit and recipient. No Coding dispatch before actual CLEAR and no p1-04 release
before exact-commit delivery PASS/publication. Producer performed document/source/
identity checks only; selected fixture tests remain QA's prior results, not a
new live deployment, generation or Gallery-byte retrieval.

## p1-03 kickoff round 2 CLEAR and execution gate

[QA AID-162](/AID/issues/AID-162) returned independent **CLEAR** for all five
clarified requirements at `522c2f10b550d90f7b88ab1a3c9d1f6352439c8e`, exact
[report/evidence](../p1-03-mcp-wait-and-result/kickoff-review.md)
`3bbcb9cdd30397c497c71da50ce83482642302e7`. Producer read the actual report
and verified five official uploads, binary patch/bundle and all 90 indexed
payloads/92 archive members against immutable hashes/Git. Original task/report/
evidence, cleared task/decision and nine registry items remain unchanged.

K3-1 is resolved at specification level; one kickoff ambiguity/clarification 1/
round-2 CLEAR is retained separately from delivery rejections. Coding may now
implement the cleared task. [AID-144's native plan](/AID/issues/AID-144#document-plan)
names separate Coding and exact-commit delivery-QA recipients, with native
Coding → Review → Producer prerequisites. Actual delivery evidence/PASS still
precedes feature merge/push and p1-04 release; later code needs fresh review.
No ordinary owner confirmation remains. Client limit is unverified unless sourced;
50 seconds is the approved total fallback including lookup/status/enrichment.

QA's fresh selected Backend 3/one warning, MCP 19 and extended isolated fixture
checks establish existing source shapes only. Producer's handoff adds no software
suite, runtime probe/deployment/restart, real generation/training or live Gallery
retrieval. Historical full suites/live proof and all retained-data boundaries stay.

## Accepted p1-03 delivery and p1-04 release

[Coding AID-163](/AID/issues/AID-163) delivered exact candidate
`77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce`; [QA AID-164](/AID/issues/AID-164)
returned independent all-D1-D5 PASS, report/evidence/registry
`d088c3258ab782623631d60daaaccc8ce6fcb6dc`. Producer read both actual
manifest/report, verified ten official uploads, exact patches/bundles and all
203/262 indexed payloads against Git/hashes. Reviewed source/tests/manifests/
evidence and QA registry are integrated unchanged; [acceptance](../p1-03-mcp-wait-and-result/acceptance.md)
records behavior, tests, client-limit uncertainty and live proof limits.

Fresh QA Backend 1900/124 Windows skips, restored MCP 540/two unchanged optional
skips, wait 77 and independent extra cases 28 pass. Seven faults fail and restore
before final GREEN; 13 registry rows preserve the prior nine. Actual client limit
remains unverified, with explicit approved 50-second total fallback; short
mocked elapsed checks disclose SDK/setup overhead and are not live measurement.
No extra Producer suite, runtime deployment, real generation/training or live
Gallery-byte retrieval is claimed. Preserve all runtime/private config/venvs/data.

One p1-03 kickoff ambiguity/clarification 1/kickoff 2 CLEAR and delivery review 1
PASS, zero delivery rejections, remains separate from p1-02/p1-00a history.
Completion/publication of [AID-144](/AID/issues/AID-144) releases [AID-145](/AID/issues/AID-145)
for its existing health/configured-worker specification's own fresh CLEAR before
Coding and exact-commit PASS before publication. Read current 30-intent envelopes;
use existing endpoints and empty/one configured worker, not Phase 3 registry/
heartbeat/scheduling. Real Mac smoke/demo/three-run/phase-close gates remain later.
No routine owner/start/resource confirmation remains.

## p1-04 kickoff ambiguity and identity clarification

[QA AID-165](/AID/issues/AID-165) returned **AMBIGUITY K4-1** for fixed
`c70162d`, exact report/evidence `3a980ec`. Producer read the actual report and
worker route/client/settings, and verified five official uploads, exact binary
patch/bundle and 59 indexed payloads/61 members against pinned Git/hashes.
D1/D3/D4 are CLEAR at specification level; D2 needs configured-versus-observed
identity semantics for failed and URL-only probes.

[Clarification 1](../p1-04-mcp-health-and-workers/kickoff-clarification-1.md)
adopts a minimal additive extension of existing worker status. Configured URL
and expected identity remain distinct from nullable current observed identity
and validated resolved endpoint; failed probes retain one entry and safe current
error. Backend-read failure returns an error, never an inferred empty list.
The [normative contract](../../decisions/mcp.md#configured-worker-health-and-identity)
preserves single-worker/read-only scope, existing LAN discovery/cache and all
unrelated intents/risks. No registry/heartbeat/scheduling or persistent history.
Original task/report/evidence stay intact; one kickoff ambiguity/clarification 1/
next kickoff round 2 is not an implementation delivery rejection (zero).

Fresh independent round-2 CLEAR at the published clarified SHA precedes Coding;
[AID-145's native plan](/AID/issues/AID-145#document-plan) pins the recipient and
source. Later exact-commit PASS/publication still precedes p1-05. No ordinary
owner confirmation is needed. QA's selected existing Backend 9/one warning,
catalog 14 and shape checks remain offline source-contract evidence. Producer
adds no suite, live probe/restart, generation or Gallery-byte retrieval.

## p1-04 kickoff round 2 CLEAR and implementation handoff

[QA AID-166](/AID/issues/AID-166) returned independent **CLEAR** for fixed
`5cf158b65d924a9508a3b5bfb7b47adb92eff7a1`, exact report/evidence
`e75a94ec63a507bac194b702a87eb369ea1ccb20`. Producer read the actual report
and verified all five official uploads, exact binary patch/bundle and 78 indexed
payloads/80 archive members against sizes, hashes, blob IDs and pinned Git.
The [cleared task](../p1-04-mcp-health-and-workers/task.md) retains SHA-256
`28077043ebe82e1371657219e6bab0685a8ec1918ec8130b122dad097dbc88e8`;
full MCP decision and clarification hashes remain unchanged. K4-1 is resolved at
specification level. One kickoff ambiguity/clarification 1/round-2 CLEAR and zero
implementation delivery rejections remain separate from earlier task histories.

This actual CLEAR permits Coding dispatch from the published handoff base,
followed by a separate exact-final-commit delivery-QA card. [AID-145's native
plan](/AID/issues/AID-145#document-plan) records recipients, fixed source and
Coding → Review → Producer prerequisites. Implement the four cleared requirements,
including authoritative configured/observed identity and failed-read recovery;
replace ping, add health/list_workers=read and preserve other 29 names/risks.
Existing status endpoints and empty/one worker remain the boundary; no registry,
heartbeat, scheduling or runtime deployment is pulled forward. Exact-candidate
PASS/publication still precedes p1-05. No ordinary owner confirmation is pending.

Fresh QA selected Backend **10 passed/one warning**, MCP catalog **14 passed**
and the **11-case/12-GET** existing-route/client probe are source-contract
checks. No feature implementation is certified. Producer verifies documents,
official evidence/Git and publication only, with no new software suite, live
product probe/restart, generation/training/worker dispatch or Gallery-byte read.
Runtime/private configuration, canonical venvs and all retained data stay intact.

## Accepted p1-04 delivery and p1-05 release

[Coding AID-167](/AID/issues/AID-167) delivered exact
`72f483418524a613fb104b92ab483e39f7432bfc`; [QA AID-168](/AID/issues/AID-168)
returned independent all-D1-D4 PASS, report/evidence/registry
`3422ccda7a66514fe7dadf7d3c8785a5718ba472`. Producer read actual manifest/
report and verified ten official uploads, exact binary patches/bundles and all
159 Coding/296 QA indexed payloads against sizes, hashes, blob IDs and Git.
Reviewed product/tests/manifest/evidence and QA registry are integrated unchanged;
[acceptance](../p1-04-mcp-health-and-workers/acceptance.md) records the result.
Cleared task/decision/clarification, original history and prior guards remain.

Current software exposes 31 intents: health replaces ping, list_workers is read,
other 29 names/risks and bounded wait are preserved. Existing worker status is
extended additively; configured/expected identity stays separate from nullable
accepted observations, including cached discovery followed by failed validation.
Three-component health retains truthful unknowns on failed reads. No registry,
heartbeat, scheduling, persistent history or new control path is added.

Fresh independent final Backend **1916 passed/124 Windows-only skips/76 warnings**,
MCP **606 passed/two unchanged optional smoke-export skips**, registered probe
**51 calls/107 GETs** and fresh wait consumer **28 passed** are recorded. Ten
production faults fail and restore before full GREEN. All 13 earlier registry
rows remain; three additions yield **16 active**, no supersession. Producer checks
documents/source/official package/Git/publication identity, without another full
suite on unchanged reviewed product/test/dependency inputs. No service probe/
restart/deployment, real generation/training/worker dispatch or live Gallery
bytes. Preserve active runtime/private configuration, canonical venvs and data.

p1-04 accounting is one kickoff ambiguity/clarification 1/round-2 CLEAR and
implementation delivery review 1 PASS, zero delivery rejections. Earlier task
histories remain separate. Health uses sequential five-second status reads,
not an atomic snapshot/overall deadline; client limit stays unverified with
50-second total wait fallback. Reachability/locators prove neither readiness
nor bytes/access. Source publication does not deploy the running product.

Publication/completion of [AID-145](/AID/issues/AID-145) releases [AID-146](/AID/issues/AID-146)
for p1-05's own fresh kickoff using the accepted 31-intent surface and actual
prior results. Retain the adopted Illustrious/default/no-LoRA/local pair and
verify loaded contracts/client setup for real execution. Three zero-intervention
real original/revision runs, retrieval/lineage, CTY demo and phase-close review
remain later gates. No ordinary start/resource confirmation is pending.

## Handoff, delivery and continuation

After CLEAR, Producer creates a Coding card and a separate QA delivery-review
card whose native prerequisite is Coding. The coordination card waits on the QA
card. QA reviews the exact delivered commit and posts its verdict on its own
issue, marking the review done even for FAIL or AMBIGUITY. Producer reads the
actual deliverable: completed prerequisites alone are not acceptance. Later code
changes need a new exact-commit review. Engineering uses isolated worktrees.

For p1-01/02, deliver a manifest in each task folder and review their combined
final commit. Merge/push together only after PASS; every later software delivery
also needs PASS. Update CURRENT/PROGRESS and continue without per-item starts.

AID-147 returned CLEAR for `e443f2e`. AID-148 delivered `3081952` without repairs;
AID-149 returned evidence-only PASS, and Producer inspected the actual manifest,
review, full bounded suite receipts, raw transcript and friction accounting. The
official attachments and exact patches match Git. The original evidence and QA
report/registry `c377a02` are integrated without changing their bytes.

The full Mac Backend suite passed twice independently: 1900 passed, 124 existing
Windows-only skips, 77 warnings; Coding 43.84s, QA 44.13s, both exit 0 with
`--timeout=60`. One original completed, with Gallery metadata only. The relative
URL failed locally before an HTTP image request; no bytes or revision were
retrieved. The live Backend omits revision context and its loaded commit is
unknown. This is an accepted baseline record, not a usable end-to-end journey.

Producer sent p1-00a to independent fixed-commit kickoff on AID-150 at `4ac3d56`.
QA returned CLEAR; Producer read the complete comparison and verified the official
report/archive/patch against QA report commit `9bd0029`. Its bounded scope
aligns the existing Backend runtime and resolves the locator/client boundary,
then proves a fresh original/revision pair with actual bytes and persisted
lineage. No envelope/consolidation/wait/health redesign is pulled forward. The
original 23-unit/eight-incident no-repair baseline remains unchanged; repair
interventions are recorded separately. Coding AID-151 delivered `00ebb4d` from
published `eaf11b8`, with unchanged product/test source. QA AID-152 returned FAIL:
D1-D4 pass, but D5 omits eight nullable training columns and a new empty reservation
table from the existing startup footprint. Its read-only audit found old values
preserved. Producer checked the official report/audit and startup source; the
first candidate was rejected and held from merge pending correction.

[Correction 1](../p1-00a-mac-runtime-and-retrieval/repair-round-1.md) fixes the
inventory and schema receipts within original cleared D5. No specification change,
product fix, restart or extra generation was needed. Coding AID-153 delivered
`b6d5846`, a direct child of `00ebb4d`, with the complete additive schema inventory,
reproducible read-only preservation audit and refreshed integrity packet. QA
AID-154 independently returned D1-D5 PASS at that exact candidate; report/evidence/
registry commit `3d5d890`. Its new schema/value audit and process/source/configuration
checks support reuse of the independently passing full suites, actual returned-path
byte reads and generation/lineage checks. One prior delivery rejection remains
recorded; correction round 1 and review round 2 are not reset.

Producer read the full manifest and verdict, verified the official attachments,
archives and exact patches against Git, and accepts the bounded repair. The
unchanged reviewed evidence, topic docs and QA registry are integrated with
[acceptance](../p1-00a-mac-runtime-and-retrieval/acceptance.md), CURRENT and PROGRESS.
Publication and completion of AID-142 release AID-143 for its own independent
p1-01/02 kickoff. No implementation CLEAR for those tasks is implied. The proof
is a Mac colocated filesystem client consuming both Gallery tools' returned paths;
the fresh original used deterministic cache. Remote URL access, aesthetics and
the three zero-intervention Phase 1 exit runs remain unaccepted. Keep the active
AID-151 runtime worktree and canonical Backend venv. No ordinary owner confirmation
or escalation threshold is pending.

Later coordination cards depend on their predecessor. This is an event-driven
continuation, not polling or a prose-only promise to resume. A completed review
with FAIL or AMBIGUITY is triaged before dependent release. Any later kickoff
returning ASK OWNER/BLOCK is likewise triaged before implementation starts.

## Verification and reporting

The planning and initial dispatch rounds verified source/docs, native handoffs,
read-only health/resources and publication. The acceptance round verified the
actual completed deliveries, official attachments/archives/patches and raw call
accounting. It integrated reviewed task evidence and QA metadata and wrote the
bounded repair specification/status documents. Producer did not rerun software
suites, probe services, generate or retrieve image bytes in this acceptance
round. Accepted Coding/QA results remain attributed to those runs; prior Windows
counts remain prior evidence. The repair-dispatch follow-through verified CLEAR,
official report/archive/patch integrity and native plans/dependencies, then
published the unchanged kickoff mirror and dispatch state. It performed no
software suite, live product probe, generation or image-byte retrieval. These
earlier rounds did not accept the repair or imply a phase exit.

Report the adopted pair, first work, native task links and actual next actor in
Traditional Chinese in Discord `1562710701280202813`. No owner response is
requested for these ordinary choices. Later delivery reports must distinguish
offline tests, running services, real generation and artifact retrieval.

The delivery-triage round inspected actual manifest/review/schema evidence and
published the bounded correction/status records only. QA's full Backend/MCP,
runtime, decoded-byte and lineage checks remain attributed to QA. D5 accounting
failed despite the verified journey; that round did not accept, merge or release.

The final acceptance round verified all seven corrected Coding attachments and
five QA attachments by hash/size, matching official manifest/report and exact
patches to their pinned commits. All 90 Coding archive repository members and 26
QA archive repository members match Git; retained references and three archived
PNG payloads match their published hashes. Product/test trees, fixed specifications
and original baseline evidence are unchanged. Producer checked document links,
whitespace and publication, with no new software suite, live product probe,
generation or live image-byte read. Backend 1900 passed/124 skipped and MCP 314
passed/4 skipped remain independently observed AID-152 results, reused by AID-154
under verified source/environment equivalence. No new Frontend/Windows result or
Phase 1 exit is claimed. AID-143 owns the next kickoff and delivery cycle.

Knowledge capture: the delegated-choice rule remains in roadmap/MCP decisions;
the new [runtime source-contract topic](../../memory/runtime-source-contract-verification.md)
explains why a current checkout and healthy process cannot certify loaded
revision behavior. The [startup-schema topic](../../memory/backend-startup-additive-schema.md)
explains whole-schema inventory versus old-column value preservation. Compute/model/lineage topics remain in place. Receipts and
incident accounting stay in task evidence.

## p1-05 fresh kickoff after accepted prerequisites

[Producer AID-146](/AID/issues/AID-146) read the actual accepted baseline/repair
and p1-01–04 manifests, independent PASS reports and acceptances after native
[AID-145](/AID/issues/AID-145) completed. [QA AID-169](/AID/issues/AID-169) now owns
the independent kickoff at fixed published `d95f1a3607709285d45ac25f6d87a3be53a7ba41`.
The existing task remains unchanged at SHA-256
`5ff74c8794101ed1dc1c1346096444d184ca0b6f999271e820ae6829fcc8ea8b`.
Its complete self-contained assignment/verbatim task was saved in the recipient
card's native plan at creation and read back exactly. AID-146 depends on that
actual verdict; no earlier CLEAR transfers to p1-05 and no Coding or delivery-QA
card is dispatched before its own CLEAR.

The [handoff](../p1-05-mcp-e2e-smoke-mac/kickoff-handoff.md) records accepted
identities and the independent review's concrete boundaries: retrieved bytes
versus locators/outside-MCP file reads, bounded same-ID wait/counting, runtime
preparation/source identity, real versus cached generation, three-run resets,
and technical delivery versus CTY demo/phase-close decisions. These are review
questions, not adopted exceptions to owner rules. Producer handles findings
and any real owner-boundary decision after reading the actual report. QA owns
its report on its own card and completes even an adverse review.

Retain the adopted Illustrious/default/no-LoRA/local pair, immutable original
23-unit/eight-incident baseline, prior colocated cached-original/revision proof,
and all separate clarification/rejection histories. No routine start/resource
confirmation remains. Source publication does not deploy services. This round
does document/source/Git/native-handoff checks only; no new software suite,
product probe/restart, generation or live Gallery bytes. Preserve active runtime,
private configuration, canonical venvs and all retained data. Three real
zero-intervention runs, CTY's explicit demo reply and phase-close roadmap review
remain unaccepted; Phase 2 stays inactive. No new memory topic is needed.

## p1-05 kickoff result and clarification 1

[QA AID-169](/AID/issues/AID-169) completed **AMBIGUITY**, exact report/evidence
`039c0aee181b2a78588f7b02cb89b575157c581f`. Producer read its actual report and
verified all five official uploads, exact patch/bundle and 83 indexed payloads/
84 members against immutable Git/hashes. K5-1 is missing actual MCP bytes;
K5-2 is wait/preparation/no-retry accounting. Original task/report/evidence and
all 16 registry rows remain unchanged in historical mirrors. Preserve one kickoff
ambiguity event/two P1 findings, clarification 1/next round 2, zero delivery
rejections; earlier histories stay separate.

Adopt [clarification 1](../p1-05-mcp-e2e-smoke-mac/kickoff-clarification-1.md) under
delegated in-boundary technical authority. The [refreshed task](../p1-05-mcp-e2e-smoke-mac/task.md)
includes the bounded canonical PNG content option on existing Gallery read
(2 MiB, dimensions up to 2048, common envelope/digest, authoritative safe Gallery
root), plus the repeatable driver. Retain strict one submit/one bounded wait per
image and reset on timeout/retry. Six-attempt and per-job six-call recovery
budgets are finite; all preparation, attempts, recovery and post-result audit
operations stay visible with original F1–F8 accounting. No external artifact
fetch exemption or relaxed owner gate. Retain Illustrious/default/no-LoRA/local;
predeclared four-step 512×512 parameters imply no aesthetics/performance promise.

Fresh independent round-2 CLEAR at the published clarified source precedes
Coding/exact-commit delivery-QA cards. [AID-146's native plan](/AID/issues/AID-146#document-plan)
pins the actual source/recipient and prerequisite. Later exact-commit technical
QA reviews D1–D3, D4 stays pending CTY's explicit demo reply for Producer to
record; technical PASS alone is not whole-task/phase acceptance. Feature merge/
push follows required PASS and owner-demo acceptance. Phase-close roadmap review
remains a separate later gate before Phase 2. No routine owner confirmation.

QA's 32 selected MCP and one Backend lineage fixture pass are offline source
checks, not content implementation or real generation. Producer integrates
report/spec/status only, with document/source/evidence/Git verification and no
new suite/product probe/restart/generation/live Gallery bytes. Runtime/private
configuration, canonical venvs and all data stay. New durable choices are in MCP
decisions; no duplicate memory topic.

## p1-05 round-2 CLEAR and implementation handoff

[QA AID-170](/AID/issues/AID-170) independently cleared fixed `4fc3ff2`, exact
report/evidence `a745998382a17e818f8588e2cdfb421f77c3f124`. Producer read the actual
report and verified five official uploads, all 93 indexed payloads/94 members,
exact patch/tree and independently fetched bundle. [Kickoff acceptance](../p1-05-mcp-e2e-smoke-mac/kickoff-acceptance.md)
records unchanged cleared task/clarification/decision hashes and limits. K5-1/K5-2
are resolved at specification level; one ambiguity event/two findings,
clarification 1/round-2 CLEAR and zero implementation rejections are preserved.
Original history/evidence and 16 registry rows stay unchanged.

Coding implements the cleared bounded PNG Gallery read/SDK driver and supplies
meaningful tests plus all real attempts/bytes/lineage/sampling and complete
preparation/recovery/audit/F1–F8 evidence. Use persistent isolated worktrees,
preserve runtime/private paths/venvs/data and stop honestly on unresolved jobs.
Native recipients, fixed published base and Coding → exact-final-commit delivery
QA → Producer prerequisites are in [AID-146's plan](/AID/issues/AID-146#document-plan).
QA reviews actual D1–D3 and explicitly leaves D4 pending CTY's demo reply for
Producer; technical PASS alone does not close/publish the feature. Changed code
needs renewed exact review; owner-demo acceptance and later roadmap phase-close
review retain separate authority. Phase 2 is inactive and no routine owner
confirmation remains. This handoff publishes reports/status, not implementation,
runtime or generation/retrieval evidence; prior tests retain their attribution.
