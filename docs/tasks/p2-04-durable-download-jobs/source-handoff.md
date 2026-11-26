# p2-04 source handoff

Fixed accepted product inputs: p2-03 Coding4cd3c042, independent PASS3e440ef1;
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
