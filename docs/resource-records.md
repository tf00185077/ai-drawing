# Backend resource records

The existing `downloaded_resources` row is the authoritative model identity.
`resource_id` equals its existing integer primary key; provider IDs, path, SHA-256
and status stay in their original columns. A nullable `metadata_json` field adds
version 1 typed metadata and verification evidence. There is no second registry.
This Backend foundation is [accepted after exact delivery review10 PASS](tasks/p2-02-resource-record/acceptance.md).
Source publication does not identify a loaded service, implement search/download
jobs/defaults, or establish Phase 2 exit.

`GET /api/resources` returns `{items, total, limit, offset}` in ascending ID order.
`limit` is an integer 1–100 (default 25), `offset` a nonnegative integer (default 0).
Exact optional filters are `resource_type`, `provider`, raw `base_model`,
`model_family` (`sdxl` only), `status` and a case-insensitive 64-hex `sha256`.
Strings are trimmed, including outer Unicode whitespace. All filters combine;
total is counted before SQL pagination. Connection-local deterministic SQLite
scalars use the projection's complete typed metadata parser and the sole family
mapping, including legacy notes fallback and Unicode case folding. Invalid typed
JSON/version/nested fields have null base/family for both filtering and projection;
they do not fall back to notes. SQL counts and bounds the query before ORM row
materialization; there is no whole-table or already-paged Python post-filter.
Unsupported valid values return no items;
malformed selectors return 422. `GET /api/resources/{resource_id}` returns the same
projection, or 404 `resource_not_found` with a recovery hint. OpenAPI describes
both typed responses. Unknown query parameters are rejected.

The projection distinguishes provider-declared size from measured size. A declared
hash, installed status or historical file stat never proves verification.
`sha256_verified` is true only when an actual successful download/adoption supplied
measured hash/size and those facts still match the authoritative columns and file
stat. Otherwise it is null with `verification_unknown`. This is retained measured
evidence, not a new read-time hash: modification that preserves all stat fields
cannot be detected without a later explicit byte-verification operation.
`installed` reflects recorded status; `path_available` separately reports a regular
file at its current path (null without a path). Reads may stat paths, but never
read model bodies, call providers, backfill, repair, or write the database.

The sole Phase 2 mapping is in `resource_records.WORKFLOW_FAMILIES`: trimmed,
case-insensitive exact `SDXL 1.0`, `Illustrious`, `Pony`, `NoobAI` map to `sdxl`.
Other/missing/malformed labels have null family and `no_matching_workflow`.
The raw label is retained. This does not establish checkpoint/LoRA compatibility.

Both current publication paths share `provider_snapshot`, `publish_metadata` and
`project_resource`: acquisition admission/background completion and retained
inspect/select/install/adoption. Strict descriptors carry an optional typed
`resource_metadata` snapshot of the actually selected version/file. Historical
inputs without it retain unknown triggers/recommendations. Repeated identical
publication retains IDs and evidence; conflicting known immutable identities are
refused. Empty identity fields may be filled after the complete conflict check. An omitted
optional identity, including AIR, preserves the known column rather than clearing
it. Non-null conflicting identities are still refused before assignments.
A failed acquisition retry reuses its same row. All preexisting notes, including
null, empty, malformed and whitespace-bearing bodies, remain byte-for-byte through
success, failed-result and exception branches. Current operation status and
sanitized errors live under metadata `source_evidence.acquisition`; status responses
read that outcome instead of a stale legacy-note error. A retry clears the current
error on admission/success without changing the old note. This reserved field is
written only by internal operation publication and retained across ordinary provider
snapshot refreshes; a supplied snapshot cannot replace it. Newly created rows keep
the established generated notes/file-identity/error behavior. Legacy acquisition/status responses
keep their established IDs and enums; no MCP tool name or risk changes.

Public metadata follows the [typed allowlist](decisions/verification-scope.md#allowlist-for-the-resource-record).
Names (`resource_name`, `resource_type`, `provider`, `air`, `base_model`) retain public
creator text with C0/C1 controls removed and a 200-character limit. Trigger words
are trimmed, ordered, unique, control-free strings, limited to 32 entries of 200
characters each. Credential-looking creator prose remains public text. The exact
configured key and its URL-encoded form are replaced wherever the shared filter
publishes or stores metadata.

`source_url` is rebuilt from valid model/version IDs as
`https://civitai.com/models/<model_id>?modelVersionId=<version_id>`; it is null when
either ID is unavailable. Stored locators are never echoed. `source_evidence` is
absent from the public `ResourceRecord` and its OpenAPI schema. Internal version-1
snapshots retain this field, including acquisition state and resume evidence.
There is no database rewrite: old snapshots are normalized in memory during reads.

Only explicit recommendations from `version.meta` and `file.metadata` are used.
Supported keys are `sampler`, `scheduler`, `steps`, `cfg`, `width`, `height`, and
`clip_skip` (provider aliases `cfgScale` and `clipSkip` are supported). Steps are
integers 1–150, CFG is a finite number 1–30, dimensions are integers 256–2048,
and clip skip is an integer 1–24. These reuse generation/recipe input bounds;
they do not provide defaults. Sampler/scheduler names match
`^[A-Za-z0-9_+. -]+$` and have at most 64 characters. Conflicting or invalid
recommendations are omitted. Provenance is one of the supported source fields;
unknown legacy provenance becomes the recommendation's own key. LoRA-strength
and arbitrary metadata keys are absent from the public recommendations.

License values contain only `allowNoCredit`, `allowCommercialUse`,
`allowDerivatives`, and `allowDifferentLicense`. Values are booleans, known Civitai
permission strings (`None`, `Image`, `Rent`, `Sell`, `RentCivit`), or lists of those
strings. Rejected or absent values appear in `missing_fields`. Model/file license
blobs are omitted; there is no commercial-use restriction. Diagnostics have closed
codes and fields drawn from the record's own fields, never raw notes or provider
paths. Invalid version-1 snapshots remain readable as incomplete records without
repair writes; supplied verification never establishes measured evidence.

`safe_evidence(value)` retains its shared interface. HTTP(S) URLs lose userinfo,
query and fragment. Received URL-only values are parsed whole; apostrophes in
embedded URLs remain part of the URL so their query suffix is removed too.
Dictionaries drop case-insensitive exact transport keys
`authorization`, `proxy-authorization`, `cookie`, `set-cookie`, `token`, `api_key`,
`apikey`, and `x-api-key`; held-key values and their URL-encoded form are replaced;
non-finite floats become null. There is no credential-label, assignment, quote,
escape, Bearer or Basic recognizer. New acquisition locator storage and HTTPX
request logs use the same URL policy. Raw httpcore transport debug events are
suppressed because their payloads include header tuples and cookies. Existing
legacy rows/notes remain untouched. A missing or unreadable credential file does
not make resource reads fail or cause a fallback credential to be loaded.

Normal startup adds the nullable column only. Explicit backfill is a caller-owned
maintenance operation, separate from startup/read routes:

```python
from app.services.resource_record_backfill import backfill_metadata
# db is an explicitly selected SQLAlchemy Session; do not use a live DB to test.
report_by_resource_id = backfill_metadata(db)
```

It fills only absent metadata from recognized legacy notes, commits that selected
session, and preserves every old column, original notes, row, alias/history and
file. It reports malformed notes, conflicts, unsupported labels, duplicates and
unavailable paths. It neither hashes nor guesses model identities from filenames
or image aliases. Repeat backfill/startup preserves counts, IDs and projections.
The supplied migration test uses a synthetic copy of all pre-task tables/schema;
no production database was migrated by this task.

The local-ledger adapter includes the same typed record under diagnostics. Its
historical status-based availability and recipe family enums remain frozen.
`civitai_resource_legacy.normalize_model_family` exists only for those enums,
AIR ecosystems and Anima split-package routing. It is never Phase 2 mapping
or evidence that an unsupported workflow/loader is compatible. Retained install
still requires its old complete descriptor safety gates; acquisition keeps its
old scan, storage, package and allowed-extension behavior. Safetensors-only future
download-job policy, byte budgets, unknown-local adoption and alias replacement
remain separate tasks.

The ledger's raw internal snapshot retains AIR and filesystem locators for exact
filters, recipe matching, hashing and filename planning. `ledger_payload` applies
the bounded shared filter to the **whole** public entry and snapshot,
including outer AIR/path/hash/kind/status copies beside typed diagnostics. Safe
AIRs, paths, IDs, hashes, state and counts retain their meaning; old storage is
never repaired or hidden. Canonical status strings use the same normalization. The embedded record diagnostic
is filtered when the ledger is built so its canonical source URL does not create a
later false unsafe-lock refusal; raw matching fields remain authoritative.

Registered resolve/resolve-local project outgoing results only after raw matching
and verification. Their internal report/lock transfer format stays raw. A ready report requiring
projection is refused with `unsafe_resource_projection` and inspect/retry guidance
rather than returning a masked path as an executable verified lock. Unavailable
reports retain their existing 409 state and safely projected diagnostics. Variant
provenance likewise refuses an unsafe report before build or queue; it cannot
rewrite a locator without changing its bound hashes. Safe variants keep their original locks and
hashes. Retained source-info/generate-like responses project public plan copies;
internal filesystem matching and execution parameters remain raw. No new recipe,
alias or generation feature is introduced.
