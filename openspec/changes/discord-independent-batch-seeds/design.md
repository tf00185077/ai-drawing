## Context

Normal generation currently enqueues one in-memory job, builds one template
workflow, selects one sampler seed, and leaves the latent node at the requested
`batch_size`. ComfyUI can produce multiple outputs, but every recorded image has
the same seed. Discord submits that normal generation request and later queries
one job ID through the unchanged `/result` command.

The existing queue is intentionally process-local while completed image
artifacts are persisted. This change must preserve that execution model while
adding durable parent/member terminal accounting so a mixed result such as
three successes and one failure remains accurate after restart. Custom and
audited workflow execution is immutable and cannot safely be rewritten into
child workflows.

## Goals / Non-Goals

**Goals:**

- Give every image in an opted-in normal-template batch a distinct random seed.
- Preserve one public job ID and the current Discord commands and count controls.
- Keep shared batch behavior exactly backward compatible for all existing
  callers.
- Reserve independent child work atomically and expose one aggregate lifecycle.
- Continue later siblings after a member failure and return every successful
  `SaveImage` artifact with sanitized failure summaries.
- Persist parent/member terminal state, per-member seeds, and deterministic
  artifact identity and ordering.

**Non-Goals:**

- No graph cloning for custom, audited, Hires, or other arbitrary workflows.
- No durable recovery or resubmission of in-flight ComfyUI executions.
- No new Discord command, child-job lookup, or independent-seed MCP behavior.
- No live Backend restart, ComfyUI submission, GPU smoke, deployment, archive,
  merge, or push during the non-live implementation phase.

## Decisions

### 1. Independent mode is explicit and template-only

`GenerateRequest` gains
`batch_seed_mode: Literal["shared", "independent"] = "shared"`. Omission and
`shared` retain the current single queue job and single ComfyUI batch.
`independent` is valid only for normal template generation with implicit/random
seed selection. Explicit seeds, `fixed`, `workflow_default`, and immutable
custom/audited workflow paths are rejected at validation boundaries.

This avoids silently changing API and MCP callers and avoids unsafe graph-shape
assumptions. Cloning sampler/latent/decode/save nodes was rejected because it
would couple correctness to individual workflow topology.

### 2. One public parent owns distinct private executions

An independent submission allocates one public parent job ID and one private
execution ID per child. Each child records its zero-based ordinal, parent ID,
unique seed, and params with `batch_size=1`. Internal queue and running identity
uses the execution ID; API, gallery, image, artifact, and Discord identity uses
only the parent ID.

This prevents collisions in running slots, failures, and cancellation while
keeping external lookup stable.

### 3. Seeds and capacity are allocated atomically

Before enqueue, the queue lock covers total-capacity validation, bounded unique
seed allocation from the existing valid seed range, child construction, durable
parent/member creation, and insertion of all children. If capacity or
construction fails, no child becomes visible.

A small pure allocator tracks generated values in a set and retries collisions
within a bounded budget. This makes uniqueness directly testable and avoids
partial parent batches.

### 4. Parent lifecycle is monotonic and terminal accounting is centralized

An in-memory batch-progress record owns total, completed, failed, started,
current ordinal, and member seeds. The parent is `queued` until its first child
starts, then `running` until every member is terminal. It never returns to
`queued` between sequential children.

One terminal-accounting helper updates the durable member, derives aggregate
counts, and derives the parent terminal state. A parent with at least one
successful member is `completed` after all members terminate, including mixed
outcomes; a parent with zero successful members is `failed`. Member failure
never removes later siblings. All-failed public state is rebuilt from that
durable aggregate ledger; a final child's raw `node_errors` cannot replace the
parent counts and bounded member reasons.

### 5. Parent/member outcomes are durable but in-flight execution remains local

One generation-batch parent row stores public ID, mode, total, counts, status,
and timestamps. One member row per requested image stores ordinal, private
execution ID, seed, status, and sanitized structured failure fields. Raw
ComfyUI or collaborator payloads are never persisted.

At application startup, non-terminal persisted independent batches are
reconciled because their process-local executions were lost. Already terminal
members remain unchanged; unfinished members become failed with stable
`backend_restarted` code/message. The parent becomes `completed` if any member
succeeded and otherwise `failed`.

### 6. Artifact identity includes parent and ordinal

Every child is recorded under the public parent ID with its actual seed.
Artifact metadata contains `batch_index` and seed while preserving
`source_node_type`. Destination names incorporate parent ID and child ordinal,
so identical ComfyUI source filenames cannot overwrite siblings. Status results
sort artifacts by child ordinal and then their original artifact order. An
independent member succeeds only when terminal history contains a real
`SaveImage` image artifact; preview-only output fails that member without
stopping later siblings.

### 7. Aggregate cancellation and result presentation preserve existing APIs

Queue status lists each public parent once. Cancelling a fully queued parent
removes every child while holding the queue lock and marks durable unfinished
members cancelled/failed consistently. Once any child is running, cancellation
retains the current conflict behavior.

Discord adds independent mode only to the final normal generation payload.
`/result id:<parent>` continues downloading all successful parent `SaveImage`
artifacts and excluding previews. Mixed completion returns files first and a
concise successful/failed count plus sanitized member ordinals. Independent
jobs with no valid `SaveImage` artifact do not re-enter the legacy Gallery
filename fallback.

## Risks / Trade-offs

- **[Independent batches are slower than native Comfy batches]** → Execute
  sequentially by design to guarantee workflow-independent seed provenance.
- **[Parent/child state can diverge]** → Centralize all member terminal updates
  and derive parent counts/status from durable member rows.
- **[Process restart loses in-flight Comfy identity]** → Do not claim in-flight
  recovery; reconcile only the durable member ledger with `backend_restarted`.
- **[Seed RNG collisions]** → Enforce uniqueness with a set and bounded retry,
  failing atomically before enqueue if uniqueness cannot be allocated.
- **[Output overwrite from repeated source names]** → Include parent and ordinal
  in every destination name and test repeated-source recording.
- **[Secret-bearing failures reach persistence or Discord]** → Persist and
  expose only stable codes plus bounded sanitized messages.
- **[Queue slots leak on malformed submission, status polling, or recording
  failure]** → Use terminal accounting for submission/recording failures. For
  malformed queue polling, query history by the known prompt ID, retain the
  running slot while status is uncertain, and release only after a bounded
  persistent inability to determine status.

## Migration Plan

1. Apply one Alembic migration creating generation batch parent/member tables
   and indexes/uniqueness constraints for parent ID and member ordinal.
2. Deploy backend code with shared mode as the default; existing records and
   callers require no data migration.
3. On startup, reconcile only non-terminal persisted independent batches.
4. Deploy Discord payload/result handling after backend compatibility exists.
5. Roll back application code by returning Discord to shared payloads; the new
   additive tables can remain unused. Schema removal, if ever required, is a
   separate reviewed migration.

Live deployment and GPU E2E require separate CTY approval and remain unchecked.

## Open Questions

None. CTY approved the parent/child, durability, mixed-outcome, compatibility,
and non-live boundaries in the implementation plan.
