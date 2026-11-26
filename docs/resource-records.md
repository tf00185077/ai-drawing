# Backend resource records

The existing `downloaded_resources` row is the authoritative model identity.
`resource_id` equals its existing integer primary key; provider IDs, path, SHA-256
and status stay in their original columns. A nullable `metadata_json` field adds
version 1 typed metadata and verification evidence. There is no second registry.
This source increment needs independent delivery QA; it does not identify a loaded
service, implement search/download jobs/defaults, or establish Phase 2 exit.

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

Snapshots keep ordered unique trimmed trainedWords, diagnose invalid entries,
and retain only explicit typed finite sampler/scheduler/steps/CFG/width/height/
LoRA-strength recommendations with source field names. Integers are required for
steps and dimensions; sampler/scheduler are nonblank strings; CFG/strength are
finite numbers. Conflicting recommendations are excluded. Current recognized
sources are `version.meta` and `file.metadata`, with keys `sampler`, `scheduler`,
`steps`, `cfgScale`/`cfg`, `width`, `height`, `strength`/`loraStrength`. Missing
parameters stay absent; sample-image prompts provide no defaults. Safe source
metadata remains opaque evidence. License permissions and optional explicit model/
file license evidence are stored without a commercial-use filter; missing and
invalid permission fields are explicit. Provider credentials and URL queries are
excluded. Every typed nested field passes shared safe normalization at provider
snapshot construction, publication and public projection: license values and keys,
missing-field strings, diagnostics, trigger words, recommendation values/source
fields, raw labels and opaque evidence. HTTP locators lose userinfo, queries and
fragments. A recognizable credential-bearing free-text string is redacted in
full, including Basic/Proxy-Authorization schemes, later cookies, quoted multiword
values, compound labels, whitespace and delimiters. Token-by-token removal cannot
safely locate their ends. The same normalization covers retained descriptor
license/usage fields and newly generated acquisition license snapshots. Credential
keys are excluded before renaming so repeated normalization is idempotent.

Keys and parsed assignment/header labels use one identifier policy. Labels may
be unquoted or enclosed in matching single/double quotes; colon/equal delimiters
and Unicode whitespace are accepted. Matching quoted labels are consumed as complete
lexical units before recognition, including leading/trailing inner spaces, tabs
and serialized escapes such as `\t` or `\u2003`. Escaped quotes/backslashes retain
their lexical meaning. Ordinary quoted values do not hide inner assignments;
each quote kind scans independently, including opposite-quote labels inside
ordinary quoted values. Each quote kind traverses forward with one cursor. An escape consumes its next
character, or end of input when the backslash is terminal; an unmatched tail ends
that pass. Closed labels alone reach one-time escape decoding and the common key
policy when followed by an explicit delimiter. No failed suffix is retried at its
inner quotes. Together with maximal ordinary runs, this bounds traversal work by
the complete input length, including odd/even terminal escapes, while retaining
full ordinary values without truncation or a new format/size restriction.
Recognition checks the original text and one relevant serialization view before
associating quoted labels with delimiters. A complete JSON string is decoded once
without its outer envelope; escaped content without that envelope receives one
lexical escape pass. The decoded view is used only to recognize assignments.
Any recognized assignment redacts the complete original value; safe public text
keeps its original representation. Views are not recursively decoded, and the
same monotonic scanner runs at most twice. JSON parsing, lexical substitution and
both scans each make bounded progress over the input; terminal escapes keep the
explicit EOF behavior and unchanged three-second feature bounds.
Identifier components use whitespace,
underscore, dot or hyphen separators, plus camelCase/acronym transitions. A
component ending in `token`, `secret`, `authorization`, `password`, `credential`,
`signature`, `cookie` or `api key` (including joined `apikey`) is sensitive,
case-insensitively; prefixes need no word boundary. Thus `CIVITAI_API_KEY`,
`HTTP_AUTHORIZATION`, `providerApiKey`, `provider.api.key` and Unicode-prefixed
identifiers have the same meaning as keys and as assignment labels. Extra
separator-delimited components do not undo recognition. The complete affected
string is redacted regardless of its value, including opaque labelled Basic.
Trailing letters are significant: `tokenizer`, `api_keyboard`, `secretariat` and
`passwordless` remain useful keys/values. Unassigned prose such as “API_KEY
documentation” is retained. This is recognizable labelled metadata treatment,
not arbitrary unlabelled secret discovery or a list of app environment settings.
Bare Basic text is recognized only with a decodable user:password value;
ordinary text such as “basic painting” remains useful. Credential-resolution
recovery guidance uses sentence syntax so the setting and file requirements stay
actionable through the same metadata normalization. Bare Bearer treatment and
URL exclusion keep their established behavior. Sensitive evidence keys are removed.
Legitimate typed values and ordinary hashes are retained. Unsafe stored snapshots
are normalized for reads without repair writes. Invalid typed snapshots remain
readable as incomplete; supplied verification never establishes measured evidence.
Original notes are never returned as diagnostics.

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
