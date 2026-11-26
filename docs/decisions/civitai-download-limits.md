# Decisions · Phase 2 stock download limits

## Context and decision

The [accepted First check](../tasks/p2-00-civitai-first-check/acceptance.md) needed a
custom guarded transport. After [p2-02 acceptance](../tasks/p2-02-resource-record/acceptance.md),
source inspection still finds the stock downloader writing the stream before
checking declared size/hash and publishing with replacement. Resource identity is
now established; enforce bounded stock execution before persistent attempt/job and
aggregate reservation accounting. One existing Backend remains responsible.

Adopt **8 GiB per file** and **20 GiB destination free-space floor** as configurable
positive integer byte defaults. These are Producer's in-boundary recommendations,
carried from the First check operating guards, not newly quoted owner numbers.
One GiB is 1,073,741,824 bytes. The First check's temporary 10 GiB new-download
measurement guard is not a persistent total-budget implementation. Total budget
and cross-process reservations belong to the next detailed task.

Limits apply to real stock acquisition and retained inspect/install execution,
not only a helper/test transport. Phase 2 checkpoint/LoRA selection accepts
safetensors only; frozen other resource-kind and Anima package-routing semantics
remain until their explicit replacement. No pickle-based checkpoint/LoRA fallback.
Cap checks use actual total partial bytes as well as exact declared bytes. The
space floor is observed on the destination filesystem before admission and every
write; it is not a guarantee against another process consuming disk or a substitute
for future reservations. The implementation must fail truthfully on unavailable
space information rather than claim compliance.

Verify exact size/hash before atomic no-overwrite publication; existing targets and
foreign/unsafe partials survive refusal and races. Resume must validate range offset
and total before appending and include retained prefix bytes in all limits. Existing
provider credential/origin/redirect/deadline/closure rules and typed verification
remain unchanged. Public sanitized copies never become internal executable paths.

## Why this scope

A byte/space cap and safe publication are testable prerequisites for download jobs.
Bundling a new scheduler, persistent budgets, search, alias removal and generation
would obscure which boundary was actually checked. The existing background-thread
acquisition ID is still a resource ID, not a generation job or durable attempt.
Do not present this task as implementing wait_for_job or Phase 2 download-job exit.

## Evidence and application

2026-11-27 Producer source review: `civitai_safe_download.safe_download`/
`_download_attempt` stream directly, compare size/hash after close, then call
`os.replace`; acquisition and retained install call that helper through
ProviderOperation. See [p2-03](../tasks/p2-03-bounded-download/task.md) and
[ranked intake](../tasks/p2-00-civitai-first-check/implementation-intake.md).
Fresh independent kickoff and exact delivery review apply. No owner boundary
change, live provider/key/model action, runtime deployment or new architecture is
needed. This records adopted scope, not implemented or accepted future behavior.

## 2026-11-27 application after independent CLEAR

Actual [kickoff1 CLEAR](../tasks/p2-03-bounded-download/kickoff-review.md) confirms
the unchanged bounded task. Apply the same ownership contract through retained
install's post-publication compensation as through download cleanup: an earlier
absence check does not prove a final is still this invocation's file. Likewise,
post-admission failure/current outcome applies to both callers on the existing
resource authority, not just background acquisition. The source's size rounding/
truncation disagreement needs one explicit selected-size interpretation, not an
unreported metadata change. See [handoff](../tasks/p2-03-bounded-download/implementation-handoff.md)
for source evidence and compatibility feature replacements. These are applications
of existing D1–D5, not a task/specification or project-boundary change. Actual
implementation and exact independent delivery QA remain required.

## 2026-11-27 application after delivery review1 FAIL

Actual [review1](../tasks/p2-03-bounded-download/review-round-1.md) demonstrates
that post-commit adoption failures and already-active acquisition ownership need
the same existing-ID contract as newly downloaded installations. Rollback cannot
undo an installed-state commit. An earlier target-absence or identity check cannot
authorize a competing submission after the resource is already admitted.

Within unchanged D3/D4, adopt same-ID current failure publication with the actual
sanitized reason after adoption, and respect existing active ownership through
retained admission before any extra model-body submission/state mutation. Preserve
old notes, genuine historical evidence, inactive safe reuse/retry and foreign bytes.
Use the existing resource authority; durable attempts/jobs/aggregate reservations
remain subsequent work. [Correction1](../tasks/p2-03-bounded-download/repair-round-1.md)
and new exact delivery QA2 apply the unchanged task/kickoffCLEAR. First rejection,
two P1 findings; no new boundary/spec ambiguity or routine owner gate. Report actual
results under CTY's existing delegation; no Phase2/artistic acceptance.

## 2026-11-27 application after delivery review2 FAIL

[Actual review2](../tasks/p2-03-bounded-download/review-round-2.md) passes original
R1/R2 in checked scope but demonstrates new R3: process-local admission contention
waits beyond an existing ProviderOperation deadline. A correct timeout reason after
lock release does not bound waiting. Admission coordination is part of the existing
operation's absolute budget, even before network/body work.

Adopt bounded acquisition or immediate safe refusal at the existing admission boundary,
using the applicable budget before contention and preserving active ownership,
reentrancy and useful retry/reuse. Audit both callers; do not reset the deadline
after entry, drop synchronization or create a scheduler/attempt architecture.
[Correction2](../tasks/p2-03-bounded-download/repair-round-2.md)/new exact review3
remain unchanged task/CLEAR/current delegation. Two delivery rejections/three P1s;
R3 unresolved, no scope/order/Not now or artistic-authority change. Report actual
results without a routine owner gate or Phase2 acceptance.

## 2026-11-27 acceptance and next dependency

Actual [review3 PASS](../tasks/p2-03-bounded-download/review-round-3.md) accepts all
D/C/E at4cd3c042/report3e440ef1. R1/R2/R3 resolved in checked scope; prior two
rejections/three historical findings remain. [Acceptance](../tasks/p2-03-bounded-download/acceptance.md)
records exact-source limits. Next establish [persisted download operations/status/wait](civitai-download-jobs.md)
before aggregate budgets/reservations, using the existing Backend/resource authority.
This refines the earlier "next task" accounting statement into bounded dependencies;
no numeric total quota, generation-queue rewrite or owner-boundary change. Fresh
independent kickoff applies; source acceptance does not deploy or close Phase2.
