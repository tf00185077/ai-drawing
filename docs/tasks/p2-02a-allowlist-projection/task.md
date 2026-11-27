# Task specification

## Task

Replace the free-text credential recognizer in the Backend resource record with a
typed allowlist for public fields and one bounded secret check, and delete the
recognizer's code and tests.

## Purpose

p2-02 spent nine correction rounds teaching `safe_text` / `safe_evidence` to find
credential-looking text inside arbitrary metadata strings (quotes, escapes,
serialized assignments, prose). That approach cannot be finished, and no real
leak was ever shown. The owner-directed [verification scope](../../decisions/verification-scope.md)
replaces it: public fields have fixed shapes, and the secrets to protect are the
values the system actually holds. This must land before p2-04, whose job status
uses the same output filter.

## Outcome

`GET /api/resources` and `GET /api/resources/{id}` (and the
acquisition/install/status responses that reuse the same filter) return only
allowlisted fields. The configured Civitai key, signed download URLs and auth
headers never appear in stored metadata, responses or logs. The resource-record
code is about 200 lines shorter and has no regex recognizer to maintain.

## Scope

Included:
- **Record projection** (`project_resource` and `provider_snapshot` in
  `backend/app/services/resource_records.py`, schema in `backend/app/schemas/resources.py`):
  apply the allowlist table in [verification scope](../../decisions/verification-scope.md#allowlist-for-the-resource-record).
  Values outside it are dropped; a dropped license field goes to `missing_fields`.
  `source_evidence` leaves the public `ResourceRecord` (it stays stored internally,
  where it holds acquisition state). `source_url` is rebuilt from IDs.
- **Shared output filter.** Keep the `safe_evidence(value)` interface so its
  callers (`civitai_easy.py`, `civitai_resource_acquire.py`, `civitai_resource_install.py`,
  `civitai_acquisition.py`, `civitai_safe_download.py`, `civitai_provider.py`,
  `download_jobs.py`) need no change, and reduce its behavior to:
  1. HTTP(S) URLs lose userinfo, query and fragment;
  2. dict keys equal (case-insensitive) to a short fixed list of transport fields
     are dropped: `authorization`, `proxy-authorization`, `cookie`, `set-cookie`,
     `token`, `api_key`, `apikey`, `x-api-key`;
  3. exact occurrences of the configured key value and its URL-encoded form are
     replaced (the existing `redact_secrets(value, secrets=...)` mechanism);
  4. non-finite floats become null.
  No other text inspection.
- **Delete** `_IDENTIFIER_UNIT`, `_ASSIGNMENT_LABEL`, `_LABEL_ESCAPE(S)`, `_BEARER_AUTH`,
  `_BASIC_AUTH`, `_SENSITIVE`, `credential_label`, `_assignment_in_view`,
  `_credential_assignment`, `_json_string_view` and the free-text part of `safe_text`.
- **Delete tests** that only guard the recognizer: `backend/tests/test_resource_record_credential_labels.py`,
  `..._credential_values.py`, `..._quoted_labels.py`, `..._quote_contexts.py`,
  `..._quote_prefix_escapes.py`, `..._serialized_assignments.py`, `..._terminal_escapes.py`,
  `..._representation_contexts.py`, and the recognizer cases inside
  `..._acquisition_notes.py` and `..._ledger_projection.py`. Keep their non-recognizer
  feature cases. List every deleted test in the manifest.
- **Registry.** The delivery review marks the affected p2-02 REGISTRY items superseded
  by this task (owner-approved behavior change), and regenerates `REGISTRY.md`.

Excluded: recipe import/variants/variation-set services (they are removed later in
Phase 2; leave their use of the filter as is), MCP tools, p2-04 job behavior, any
database rewrite of stored rows, UI.

Open questions: none.

Read first: [verification scope](../../decisions/verification-scope.md),
[resource-record decision](../../decisions/civitai-resource-record.md),
[resource-records topic](../../resource-records.md), [credential guidance](../../civitai-credentials.md),
[p2-02 acceptance](../p2-02-resource-record/acceptance.md).

## Done when

- [ ] **D1 / P1:** List and detail responses for rows with rich, malformed and
  hostile metadata contain only allowlisted fields and values; out-of-range or
  unknown values are absent or reported in `missing_fields`/`diagnostics`; filters,
  pagination, 404 and 422 behavior from p2-02 are unchanged. Check: test. Evidence:
  HTTP tests over the registered routes with fixture rows.
- [ ] **D2 / P1:** With a synthetic key loaded through `CIVITAI_API_KEY_FILE`, the key
  value (raw and URL-encoded) and signed query strings do not appear in stored
  metadata, acquisition notes, list/detail/status responses or captured logs after a
  mocked acquisition that receives them from the provider. Check: test. Evidence:
  one end-to-end test through the real acquisition caller with mocked HTTP.
- [ ] **D3 / P2:** Rows written by the old recognizer, legacy notes and incomplete
  snapshots stay readable; reads perform no DB writes; startup and backfill remain
  idempotent. Check: test. Evidence: existing p2-02 migration/read tests still pass.
- [ ] **D4 / P2:** The recognizer code and its tests are gone, and the full Backend
  and MCP suites pass on the final commit. Check: test. Evidence: manifest list of
  deleted code/tests, suite counts.

## Delivery

- Artifact: one commit on a branch from current `main`; `manifest.md` with the
  Done-when matrix, reviewed SHA and suite counts. Evidence follows
  [verification scope](../../decisions/verification-scope.md#evidence-that-is-committed)
  (at most 2 MB; no inventories or raw logs).
- Review: kickoff, then one delivery review of the exact commit. Fault injection is
  one smallest violating change per `test` item. Correction rounds rerun affected
  tests and the REGISTRY guards only.
- Known limitations: public metadata becomes less detailed (no `source_evidence`,
  bounded license values); that is intended.
