# p2-04 source handoff

Historical discovery for the withdrawn original handoff. The
[revised task](task.md) and [verification scope](../../decisions/verification-scope.md)
supersede its implementation and review obligations. In particular, current main
already contains the unfinished download-job checkpoint, a per-process boot
identifier is sufficient for the revised restart contract, and source identity is
the Git SHA without inventories. A fresh kickoff follows p2-02a acceptance. Do not
resume the old native Coding assignment from this discovery note.

## Current starting inputs — after p2-02a acceptance

[p2-02a acceptance](../p2-02a-allowlist-projection/acceptance.md) integrates corrected
candidate `3e70e04c5bb8fb104bcf0324d19d99629741cd4c`, independently PASS at
`28df4bcf165f2cfd2136a00b0e1b46fd77267175`. Use its shared public projection and
held-value/locator filtering; no credential recognizer or new filter framework.

Two pre-existing immediate-expiry install cases are quarantined with this task as
their fix/re-enable owner. Preserve their same-ID diagnostic and bounded contention
requirements while completing the revised lifecycle integration; fix the missing
`resource_id` diagnostic and remove both skips before delivery:

- `backend/tests/test_civitai_admission_deadline.py::test_registered_contender_times_out_before_original_owner_releases[-0.01-install]`
- `docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases[-0.01-install]`

The baseline finding and exact quarantine approval are preserved in p2-02a's
[first review](../p2-02a-allowlist-projection/review-round-1.md) and
[correction handoff](../p2-02a-allowlist-projection/implementation-handoff.md).
All other deadline parameters and p2-03 feature/REGISTRY rows stay active. These
are retained compatibility obligations, not a new p2-04 Done-when item or a p2-02a
rejection. Fresh kickoff checks this input against the revised task and current WIP.

## Historical discovery

Fixed accepted product inputs: p2-03 Coding0508ac43, independent PASS1e69e9c6;
full hashes, freeze, evidence and limits are in [acceptance](../p2-03-bounded-download/acceptance.md).
Fresh kickoff pins the actual published full source/tree and task hash from its
native initial plan. This file is source discovery, not independent CLEAR.

- `backend/app/services/civitai_resource_acquire.py` creates integer resource IDs
  and daemon-thread callbacks. `acquisition_status` currently projects the row and
  observed part progress; a resource is not a durable job. `civitai_resource_install.py`
  has synchronous verified adoption/download with current-row failure. `resource_records.py`
  is the model authority/public projection and deadline-aware process-local admission.
- `backend/app/api/civitai_easy.py` owns current `/resources/acquire` and
  `/resources/status`; AcquireRequest currently has locator only. Existing MCP
  `mcp_server/tools/civitai.py` acquire(source)/status wraps those routes.
- `backend/app/db/models.py` has DownloadedResource, generation-batch/member and
  training-specific persistence. It has no generic persistent download Job table.
  `db/database.py` create_all plus explicit additive nullable columns initializes
  old SQLite; read the schema memory and complete production model set.
- `backend/app/core/queue.py` is generation's in-memory execution queue, with
  separate persisted generation-batch metadata. `/api/generate/job/{job_id}` reads
  generation queue/batches/Gallery; it is not a download domain or generic job table.
  Do not route a download through ComfyUI or reinterpret GenerationBatch as a model
  download. Phase3 generation-queue durability remains outside this increment.
- `mcp_server/tools/wait_for_job.py` currently probes generation then training on
  actual404, with one50s max/default total deadline, same-ID timeout semantics and
  generation Gallery enrichment. Add authoritative download reads without fake
  Gallery output or submission; preserve old domains/transport failures/validation.
- `backend/app/main.py` owns Backend lifespan/init. New download interruption
  reconciliation must prove prior worker death and preserve live/foreign ownership;
  startup is not permission for blind model replay or production migration by tests.

Chosen bounded sequence: persist operation identity/ownership and shared status/wait
before aggregate quota/reservation accounting. An execution row links existing
resources; it does not compete with model metadata or prescribe a new queue engine.
No numeric total quota is silently introduced. Single Backend/lifecycle and explicit
no-auto-replay keep the restart contract reviewable; ambiguous live ownership fails
safely. All selected components participate in one logical public job while existing
resource IDs/package semantics remain. Independent kickoff must test this against
actual callers, additive schema/legacy data, p2-03 ownership/deadline and accepted
wait contracts; complete an adverse verdict rather than hand back routine choices.

Planning source discovery first named nonexistent generic jobs/Civitai files; rg
located the actual paths above. No API/product mutation, live probe or test ran for
that exploration. Producer's reviewed merge had three documentation conflicts
(INDEX/current manifest/current review); exact QA artifacts and reconciled topic/
status resolve them. Source tests remain exactly the reviewed candidate.
