# Decisions · Phase2 persisted download operations

## Context

Accepted p2-03 proves bounded stock file execution, same-ID current outcome and
bounded admission contention. It still launches daemon threads keyed by a resource
ID; current common wait reads generation/training only. The existing ORM has
DownloadedResource plus domain-specific generation/training persistence, no generic
persistent download-job table. Generation execution is a different in-memory queue.

## Adopted in-boundary sequence

[p2-04](../tasks/p2-04-durable-download-jobs/task.md) adds durable operation identity,
component/resource linkage, atomic current ownership/idempotency, truthful progress/
terminal/interrupted status and common wait reads inside the same Backend/SQLite.
One resource row remains model authority; an operation record is execution history,
not a second registry. Retained synchronous install participates in ownership while
keeping its current behavior. No new stack, scheduler, workflow engine, worker or
change to generation-queue durability is authorized by this refinement.

First establish durable identity/recovery evidence, then specify aggregate quota/
reservations against that operation authority. Existing per-file8GiB/observed20GiB
floor are retained; no persistent total or cross-process reservation is yet claimed.
The First check's temporary10GiB measurement guard remains historical, not a quota.
This is an in-phase dependency split under current delegation, not a Phase2 scope/
order/exit/Not now change. Fresh CLEAR then exact delivery QA apply to p2-04.

Adopt optional bounded caller idempotency, one namespaced job per logical selected
operation, existing resource IDs unchanged, and failure/interruption without automatic
replay. A known dead process cannot leave a phantom forever-running job; a possibly
live owner cannot be stolen. Preserve genuine completed components/history/files and
fail safely when concurrent Backend ownership is unsupported. Implementation chooses
the smallest additive lifecycle/claim mechanism after independent kickoff; no new
cluster lease/queue service. Source presence or a matching filename alone is not
proof that an interrupted operation completed.

Read-only download status and existing wait_for_job return authoritative resource
outcomes, preserving one50s total read budget and same-job timeout guidance. A model
file is not a Gallery image; never fabricate media locators or resubmit during reads.
New search/hash/MCP replacement/defaults/removals and full three-sentence real flow/
CTY image demo remain later work. Owner artistic judgment and all data/runtime/
private configuration/environment preservation remain.

## Evidence

Actual p2-03 [acceptance](../tasks/p2-03-bounded-download/acceptance.md),
[source handoff](../tasks/p2-04-durable-download-jobs/source-handoff.md), accepted
Firstcheck intake, current owner request/ROADMAP and actual current acquire/install/
models/lifespan/wait sources. This decision records adopted scope, not implemented
p2-04 behavior, runtime deployment or Phase2 acceptance.

## Kickoff application

Kickoff 1 CLEAR (report `c1d5ffc0`) applied to the original spec. p2-04 is being respecified under [verification scope](verification-scope.md) and needs a fresh kickoff.
