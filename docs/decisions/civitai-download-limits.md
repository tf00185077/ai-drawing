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

## 2026-11-27 acceptance and next dependency

Actual review3 PASS accepts all
D/C/E at0508ac43/report1e69e9c6. R1/R2/R3 resolved in checked scope; prior two
rejections/three historical findings remain. [Acceptance](../tasks/p2-03-bounded-download/acceptance.md)
records exact-source limits. Next establish [persisted download operations/status/wait](civitai-download-jobs.md)
before aggregate budgets/reservations, using the existing Backend/resource authority.
This refines the earlier "next task" accounting statement into bounded dependencies;
no numeric total quota, generation-queue rewrite or owner-boundary change. Fresh
independent kickoff applies; source acceptance does not deploy or close Phase2.
