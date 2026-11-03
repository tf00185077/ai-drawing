# Current state

## Product acceptance

Generation/Gallery/Prompt Library/style-preset interfaces exist. Use the [document map](INDEX.md) for setup and MCP tools; source/live schemas define implemented contracts. Backend health and mocked tests do not establish GPU readiness.

[Resource references](prompt-and-workflow-resources.md) identify graph inputs and recipe/replay differences. Digital Painting's preserved graph uses no LoRA; NihilMania uses the checkpoint VAE. Style/image effects remain **Needs re-verification (需要再驗證)** unless supported by accepted output. Static checks do not establish generation acceptance.

[LoRA training](training-status.md) is not accepted as a complete feature. Training to a valid new LoRA and successful smoke output remains unverified here. Output-integrity and smoke completion/artifact reconciliation have passed independent offline QA in isolated source candidates; canonical integration and real training/image delivery remain separate work.

## Windows work

CTY has deferred Windows Worker installation and installation-result reporting. Installation is not confirmed, and the Windows route is not permanently cancelled. The [reviewed first-installation guide](http://127.0.0.1:3100/AID/issues/AID-10#document-installation-guide), source ZIP and [independent static QA](http://127.0.0.1:3100/AID/issues/AID-11#document-qa-report) remain completed evidence. The installation-result question card was superseded by the [latest owner direction](http://127.0.0.1:3100/AID/issues/AID-4#comment-bf46ca77-46f4-4938-91c2-d4d6c4116f18); it no longer blocks agenda planning. Windows execution, cross-machine access, ComfyUI/GPU and generation remain unverified. Future host checks require applicable readiness and permission; deferral grants no alternate compute, installation or service authority.

Earlier failed Worker/updater attempts are historical evidence, not an installed-host baseline; an address change remains unproven. Source uses open PowerShell control after narrower API attempts, without an accepted long-term company interface.

The worktree fixes a discovered-URL cache defect: disabling discovery now uses the configured URL. Offline regression/core tests cover the fix; Windows deployment and acceptance remain unverified. [Windows worker](windows-worker.md) records the source behavior and required evidence.

Worker health identity validation has an isolated, independently QA-passed source candidate in completed AID-1/AID-2/AID-3; it is unmerged and undeployed, not proof of installed-host acceptance. Hostname normalization, installer/updater recovery, installed-host state and management security remain findings, not prescribed next assignments.

## Company preparation and next step

All [seven responsibilities](team/README.md), including [LoRA training](team/roles/lora-training.md), are approved. Paperclip company AI Drawing (`AID`) and the Art Production & Delivery and Platform Engineering projects exist. All seven hires are approved; the six specialist roles report to Producer. Both workstreams are bound to the [AI Drawing channel](team/channel-routing.md). CTY owns aesthetics; Engineering QA verifies technical behavior.

Documentation cleanup, responsibility reviews and role configurations are complete. [AID-4](http://127.0.0.1:3100/AID/issues/AID-4) is the continuing Producer coordinator under [CTY's latest native mandate](http://127.0.0.1:3100/AID/issues/AID-4#comment-71655f19-384a-4aa9-af39-d2ba7bdcd9d7); it does not stop when one work package finishes. The prior first-agenda/per-item-confirmation and single-package cutoff instructions are superseded. Ordinary priorities, dispatch, QA, defect handling and successor work proceed autonomously. [The supplementary delegation](http://127.0.0.1:3100/AID/issues/AID-4#comment-d8af5865-ed01-47cf-8e5f-37bef39e0e5f) gives Hermes ordinary follow-through and milestone assessment while retaining Producer judgment. The [latest completion mandate](GOAL.md#current-owner-completion-mandate) and [current native plan](http://127.0.0.1:3100/AID/issues/AID-4#document-plan) require real ComfyUI MCP submission/status/error/result retrieval, LoRA preparation-to-valid-model/selection/smoke retrieval, and the existing simple UI with real Backend progress/error/result integration and independent QA, alongside image/style delivery and native intake; the reusable-source milestone has now passed independent offline integration and dependency-reconstruction QA; runtime/delivery/aesthetic evidence remain separate.

The [LoRA frozen delivery](http://127.0.0.1:3100/AID/issues/AID-16#document-engineering-handoff) and Worker health repair are combined in [AID-20's frozen source](http://127.0.0.1:3100/AID/issues/AID-20#document-engineering-handoff), candidate `e7101d8692292c430664e9b09377a7ba78c6c39d`. [AID-21 independent QA](http://127.0.0.1:3100/AID/issues/AID-21#document-qa-report) passed the assigned offline reconstruction, Frontend typecheck/tests/build and combined compatibility scope. This meets the reusable-source milestone, without merge, deployment or runtime acceptance. Original candidates and FAIL/PASS evidence remain preserved; historical multi-LoRA contract debt and Windows-only gaps are not relabeled as passed.

LoRA smoke source has reached its bounded offline milestone: [AID-24 candidate](http://127.0.0.1:3100/AID/issues/AID-24#document-engineering-handoff) `7314a8c01ed2ef9e0dbb8a9ded37500422087494` passed [AID-25 independent QA](http://127.0.0.1:3100/AID/issues/AID-25#document-qa-report). This covers full image decoding, invalid-image isolation, deterministic same-job retrieval and recoverable status without new submission. Producer's [source acceptance](http://127.0.0.1:3100/AID/issues/AID-4#document-smoke-source-acceptance) preserves the original FAIL and all prior candidates. Canonical source still records submission only; no merge, deployment, runtime or real-image acceptance is implied.

[AID-26 multi-LoRA contract candidate](http://127.0.0.1:3100/AID/issues/AID-26#document-engineering-handoff), `3e95cb7481aaf30886426fb3aa5872bffb6c5e45`, passed [AID-27 independent offline QA](http://127.0.0.1:3100/AID/issues/AID-27#document-qa-report) and [Producer source acceptance](http://127.0.0.1:3100/AID/issues/AID-4#document-multi-lora-contract-acceptance). It reconciles the two historical test expectations with the complete-set contract through tests/docs only; product code is unchanged. Omission and an explicit empty list remain distinct, unused template LoRAs are bypassed and excess requests fail during queue compilation. A queued acknowledgement does not establish capacity acceptance or completed generation. Original failure evidence remains preserved.

The [ordinary image lineage candidate](http://127.0.0.1:3100/AID/issues/AID-32#document-engineering-handoff), `ba04a81a96b587f1486bdb8cc261164bffa4671e`, passed [AID-33 independent offline QA](http://127.0.0.1:3100/AID/issues/AID-33#document-qa-report) and [Producer's source acceptance](http://127.0.0.1:3100/AID/issues/AID-4#document-image-lineage-source-acceptance). Optional immutable brief/feedback/parent-artifact context, durable output retrieval, four actionable MCP errors and decoder-failure fallback have source-scoped evidence. Both earlier FAIL verdicts and candidate bytes remain preserved. The canonical ordinary contract still lacks these fields, so this does not establish integrated/running capability, actual image delivery or artwork acceptance.

[AID-36's `aid36-posix-v1` kit](http://127.0.0.1:3100/AID/issues/AID-36#document-engineering-handoff) passed [AID-37 independent offline review](http://127.0.0.1:3100/AID/issues/AID-37#document-qa-report) and [Producer's bounded acceptance](http://127.0.0.1:3100/AID/issues/AID-4#document-canonical-integration-kit-acceptance). Original numeric permissions now survive scratch reconstruction/apply/rollback, with Git source `92e96e9fa73dbfad28f0fa36108d60f4a1cacf40` unchanged; the [old kit FAIL](http://127.0.0.1:3100/AID/issues/AID-35#document-qa-report) remains. This meets the source-integration-kit milestone. Current authority/memory bytes have drifted from its fixed preimage and must be preserved.

[AID-40's isolated Backend
environment](http://127.0.0.1:3100/AID/issues/AID-40#document-prepared-environment) completed
dependency preparation and owner verification; [Producer accepted its bounded
scope](http://127.0.0.1:3100/AID/issues/AID-4#document-prepared-environment-acceptance). The new
durable target closes the Alembic/closure gap without changing existing environments or live
services. The [specific maintenance
request](http://127.0.0.1:3100/AID/issues/AID-4#document-maintenance-operation-request) was accepted
for its fixed version. [The actual maintenance
operation](http://127.0.0.1:3100/AID/issues/AID-41#document-operation-report) stopped before service
shutdown: the permitted read-only snapshot found 408 unique queued LoRA jobs while the in-memory
training queue was idle. Their origin and intended disposition were unresolved at that observation; the operation
preserved every ID/status and made no source, checkpoint, schema or service changes. The [LoRA
lifecycle candidate](http://127.0.0.1:3100/AID/issues/AID-43#document-engineering-handoff),
`bf3f1ee249be8719b42d67d69371534c5291a6fb`, passed [independent source/offline
QA](http://127.0.0.1:3100/AID/issues/AID-44#document-qa-report) and [Producer source
acceptance](http://127.0.0.1:3100/AID/issues/AID-4#document-lora-lifecycle-source-acceptance) for
pre-import test isolation, read-only durable uncertainty and post-commit canonical job identity. It
remains unadopted. The earlier accepted-fixture diagnosis is corrected: the parent already isolated
test DB sessions; direct-body execution bypassed that fixture, while the separate root pre-import
gap was real. Historical job origin remains unknown; the current administrative intent is now decided separately. The [Environment
assessment](http://127.0.0.1:3100/AID/issues/AID-45#document-job-disposition-assessment) is complete:
the bounded snapshot retained all original queued IDs, while path clues did not establish provenance
or intent. Producer accepted the diagnostic, preserved the records and prepared a concrete
[exact-ID intent/data request](http://127.0.0.1:3100/AID/issues/AID-4#document-lora-job-intent-request).
Hermes has answered B under the standing delegation: administratively terminate the exact
approved queued-ID set while retaining records/assets, with fresh guards, known ingress/writer/Bot
freeze and a private consistent checkpoint plus restore verification before any write. Producer has
[verified the decision](http://127.0.0.1:3100/AID/issues/AID-4#document-lora-job-terminal-decision-assessment)
and reviewed the [actual administrative operation](http://127.0.0.1:3100/AID/issues/AID-46#document-operation-report):
it ended partial before service stop, checkpoint or any UPDATE/COMMIT. Its bounded snapshot retained
all 408 queued IDs; known-caller/writer freeze and Bot submission/delivery in-flight state were not
established. The decision remains valid and is not proof of historical provenance or cancellation.
Producer resumes ordinary documentation/memory writes after this completed precondition stop;
no maintenance window or global freeze is claimed. [The completed source/synthetic assessment](http://127.0.0.1:3100/AID/issues/AID-47#document-quiescence-assessment)
confirmed that completed delivery ledgers and current shutdown helpers cannot establish that window.
The [maintenance source candidate](http://127.0.0.1:3100/AID/issues/AID-48#document-engineering-handoff),
`ae5f7383cba7d8011ecdd976ce8f2c32ac886125`, received an [independent FAIL](http://127.0.0.1:3100/AID/issues/AID-49#document-qa-report).
A close receipt can report clean closure while the persistence-aware status detects missing/corrupt
ledger history or an inconsistent checkpoint. The [repaired candidate](http://127.0.0.1:3100/AID/issues/AID-50#document-engineering-handoff),
`9b96655ea4994932854ea6028f25a58fe4a6302e`, passed [independent source/offline retest](http://127.0.0.1:3100/AID/issues/AID-51#document-qa-report).
The close receipt now validates persistent history and retains uncertainty after active work drains.
Source adoption is not yet executed. The [new source-preserving kit](http://127.0.0.1:3100/AID/issues/AID-52#document-engineering-handoff),
`aid52-source-kit-v1`, passed [independent scratch packaging QA](http://127.0.0.1:3100/AID/issues/AID-53#document-qa-report).
Its 110-path write projection preserves current authority and unrelated work; source adoption is
not yet executed. Environment has delivered the [complete conditional adoption proposal](http://127.0.0.1:3100/AID/issues/AID-54#document-adoption-operation-proposal),
and Producer accepted that proposal deliverable. The recommendation is one future window with a
verified private checkpoint/restore, the already-decided exact-ID administrative disposition, the
110-path source adoption and a closed Backend while the Bot stays stopped. This is a technical
recommendation, not an operation grant or normal service recovery. The old 75-path approval does
not cover the new source; current authority overlays remain preserved.

The limited read consent is accepted, and the authorized channel Hermes operator has now
[saved the two substantive decisions](http://127.0.0.1:3100/AID/issues/AID-4#document-proxy-decision-result)
through the supported Board surface. Legacy delivery uses a conservative no-resend hold while
remote outcomes remain unknown; every local closure, checkpoint/restore and remaining data guard
still applies. Both decisions received separate verified Discord reports. Earlier stopped CLI
attempts remain partial and are not relabeled as successful.

The [Hermes Board-proxy review](http://127.0.0.1:3100/AID/issues/AID-4#document-board-proxy-operation-review)
returned new110 v1 for five precise document corrections, without approving or executing it.
New scope needs an exact reviewed grant, which the authorized proxy may issue; it does not
automatically require CTY personally. Producer's revised
[new110 A+Bot-S request v2](http://127.0.0.1:3100/AID/issues/AID-4#document-new110-operation-request)
preserves the full110 appendix, fixed source/kit and exact408 B guards. It separates admission of
one Environment task from that task's bounded preflight, actual caller/window holds before any
service stop, and cold closure/checkpoint/restore before B/source changes. It proposes named
caller holds plus existing Backend/Bot ingress closure, explicitly retaining the unblocked direct
ComfyUI route and unavailable MCP lifecycle control as limits for Board review. Manual no-submit
acknowledgements are actual window coordination, not proxy votes or message receipts. Logical
copies must fit 120 GiB and each affected filesystem must have physical free space for its
remaining allocation estimate plus 20% margin. The exact v2 confirmation is accepted by local-board, substantively Hermes under delegation.
[AID-55](http://127.0.0.1:3100/AID/issues/AID-55#document-operation-report) and its approved
[finite supplement](http://127.0.0.1:3100/AID/issues/AID-55#document-operation-report-2) both ended
partial before any signal. The second run corrected the typed training observation and completed
more named-copy accounting, but full post-transaction/startup copies, reliable physical overhead
bounds and effective runtime/client/companion bindings remain unproved. The failed MCP locator
is unknown, not proof of an absent client; no error cause is established. There is no demonstrated
capacity shortage. Conditional window reads and all service/checkpoint/data/source/start stages
remained unused. The original administrative intent, approved scope and both actual partials remain
preserved; this grant supplies no third attempt or replenished observations.

Producer accepted [AID-58's frozen diagnostic repair](http://127.0.0.1:3100/AID/issues/AID-58#document-source-method-handoff)
after [AID-59's independent targeted PASS](http://127.0.0.1:3100/AID/issues/AID-59#document-qa-report).
The two original assertions reproduce RED on the parent and GREEN on the fixed source, preserving
unknown totals and denying runtime acceptance. Offline method utility remains conditional;
complete real capacity and old loaded roots/settings/client bindings remain unavailable. Original
conditional findings and both pre-signal operation partials stay preserved, without a third attempt
or replenished reads.

Producer reviewed [AID-60's fixed protection proposal](http://127.0.0.1:3100/AID/issues/AID-60#document-transition-protection-proposal)
and [AID-61's independent technical review](http://127.0.0.1:3100/AID/issues/AID-61#document-qa-report).
The document milestone is decision-ready and conditional; neither route is executable yet.
The [fixed policy brief](http://127.0.0.1:3100/AID/issues/AID-4#document-transition-protection-policy-brief)
separates named legacy protection scope, finite physical budgets and postcommit exposure,
the changed 20% denominator, and private storage versus restore metadata. The native
question card has four separate conditional-accept answers from Hermes under the supported
human/Board delegation. Producer verified the actual local-board resolution and exact scoped
answers; all four separate designated-channel reports have actual delivery receipts. The accepted
policy establishes a design baseline only. Actual owner/operator scope confirmations, caller/manual
holds, complete logical accounting, closure, dual cold copies and isolated restore remain required;
no historical bindings or successful operation are inferred.

[AID-64's fixed failure-contract repair](http://127.0.0.1:3100/AID/issues/AID-64#document-source-control-handoff)
passed [AID-65's independent targeted source retest](http://127.0.0.1:3100/AID/issues/AID-65#document-qa-report).
Producer accepted those two source repairs, preserving the original FAIL. The completed
[AID-66 control-binding package](http://127.0.0.1:3100/AID/issues/AID-66#document-operation-control-binding)
and [AID-67 independent review](http://127.0.0.1:3100/AID/issues/AID-67#document-qa-report) are conditional;
actual preflight and maintenance remain unavailable. The first demonstrated prerequisite is M1:
bind the real named hierarchy, metadata and finite observation/output to one aggregate writer.
The [M1 four-boundary source repair](http://127.0.0.1:3100/AID/issues/AID-70#document-engineering-handoff)
passed its [independent targeted retest](http://127.0.0.1:3100/AID/issues/AID-71#document-qa-report).
Receipt truthfulness, stopped/serial entries and bounded owned-resource cleanup are accepted only
for that source API; complete M1 operational acceptance and the original parent FAIL remain separate.
[AID-72's M2 source](http://127.0.0.1:3100/AID/issues/AID-72#document-engineering-handoff)
passed [independent source/refusal QA](http://127.0.0.1:3100/AID/issues/AID-73#document-qa-report).
Producer accepted the pre-access refusal and isolated derivation; the operational reader,
DB-setting profile and exact408 executor remain unavailable. A main-page cap and post-fetch
serializer do not close full native companion/temp/write bounds. This is a specific component/input
gap, not universal SQLite impossibility or permission to enable fixture SQL.
[AID-74's fixed M3 audit](http://127.0.0.1:3100/AID/issues/AID-74#document-engineering-handoff)
passed [independent source/receipt review](http://127.0.0.1:3100/AID/issues/AID-75#document-qa-report).
Producer accepted that source milestone; no new launcher or candidate was implemented. Original
closed-start and complete startup D_S/M/U remain unavailable. The audit separates bounded future
identity/actor inputs from missing native/output/lifetime controls and an unresolved OS-effect
accounting boundary. Repeating the same refusal or readiness work would not close those gaps.
[AID-80's finite-child component](http://127.0.0.1:3100/AID/issues/AID-80#document-engineering-handoff)
passed [independent component QA](http://127.0.0.1:3100/AID/issues/AID-81#document-qa-report).
Helper acquisitions, owned closure/unknown outcomes and the complete before-effects receipt now have
source/isolated-fixture acceptance; both earlier FAIL verdicts remain preserved. This component rejects
the original prepared Python/Uvicorn command. It does not complete the native/DB/metadata profile or
authorize actual startup. Producer has consolidated the remaining mechanisms, future inputs and actors;
there is no new demonstrated component defect to repair or generic readiness work to repeat.
The [W19 proposal](http://127.0.0.1:3100/AID/issues/AID-4#document-os-effect-boundary-proposal)
now has two conditional-accept answers. Hermes relayed CTY's fresh explicit agreement through the
supported Board surface; Producer [verified the actual local-board resolution and scope](http://127.0.0.1:3100/AID/issues/AID-4#document-w19-decision-producer-adoption).
Only indirect host-managed H satisfying every fixed predicate is outside the retained logical-copy
domain and finite modeled physical denominator. Its values remain unknown/excluded_by_policy,
not zero. Direct/protected/task-owned/native/DB/metadata/copy/output/temp effects remain fully
accounted; the 120 GiB logical cap and direct-demand/shared-pool/F-once/20% physical comparison
remain. Indirect OS allocation can still exhaust the margin or cause ENOSPC/IOERR; no guaranteed
reserve, full physical bound or execution success follows. The earlier stopped intake remains partial.

[AID-87](http://127.0.0.1:3100/AID/issues/AID-87) owns one operation-specific direct-write/control
profile and isolated source evidence for the existing B plus closed-start sequence.
[AID-88](http://127.0.0.1:3100/AID/issues/AID-88) independently reviews its frozen delivery through a
native blocker dependency. The Platform assigned run has started; QA awaits the frozen profile.
Producer waits on those two deliverables, rather than the answered W19 card. The work reuses accepted components, must provide concrete before-effects controls and a
complete direct-effect account or a demonstrated precise gap, and does not repeat generic readiness
or add a general sandbox/VFS/quota framework. Creation, actual specialist execution, source verdict,
future exact operation approval and real stage results remain separate evidence.
Actual endpoint/native utility bindings, the executable DB profile, full startup write sets,
genuine actor/window receipts and complete numerical inputs remain unpassed M1/M2/M3/A1/I1
requirements. A new exact grant and actual stage evidence are still needed; no third AID-55
attempt, read refill, private-state query, service/data/source adoption or real metadata change
follows from these source tasks or the accepted design decision.
Current role/channel guidance retires recovery patrols; preserve native events and the existing
source-triggered Hermes handoff rather than recreating watchdogs or periodic polling.
Prepared
dependencies and accepted source evidence remain reusable; runtime adoption, real image/style
delivery and LoRA effects remain unaccepted. Windows installation/reporting remains deferred.

Producer owns continuing execution and planning across the complete art-team goal. Applicable compute, aesthetic, data, spending and external-commitment boundaries follow current authority; they do not impose a permanent work-type whitelist or per-item waiting rule. See [Goal](GOAL.md) and the topic authorities above.
