# p2-02a implementation manifest

Correction 1 by Coding [AID-221](/AID/issues/AID-221), coordinated by
[Producer AID-217](/AID/issues/AID-217). Independent exact-candidate
[QA AID-222](/AID/issues/AID-222) follows this delivery. Rejection count remains **1**.
The actual [round 1 rejection](review-round-1.md) is preserved unchanged.

## Source and boundary

- Starting rewritten main: `39737296217ec1bb8f14df2744b85a0530d4b0c0`.
- Branch: `coding/aid221-p202a-correction1` in the retained `aid-221-correction1` worktree.
- Carried implementation: the single unmerged change from rejected candidate
  `8d5f29686555119b1cbcc934cbb38af9d6edaafc`, applied with `git cherry-pick --no-commit`.
  Its pre-rewrite history is not merged. Its starting source was
  `05da4bb981b4b8e44e991720093c9127509abc80`.
- Candidate identity: the commit containing this manifest (`git rev-parse HEAD`).
  Its full SHA is pinned in the native delivery comment and commit/branch work products.
  A commit cannot contain its own SHA; no placeholder is presented as a reviewed SHA.
- Reviewed SHA: pending the independent delivery review, which pins this exact candidate.
- One corrected implementation commit from the current rewritten main. No main merge, product
  acceptance, p2-04 resumption, task/ROADMAP edits, owner-library edits or rejection reset.

## Done-when matrix

| Item | Check / level | Tests / evidence | Layer and real boundary / substitutions |
|---|---|---|---|
| D1 | test / P1 | `backend/tests/test_resource_record_allowlist.py`; `test_resource_record_reads.py`; retained typed filter cases in `test_resource_record_corrections.py` | Registered FastAPI list/detail/OpenAPI routes, real SQLite fixture rows and SQL queries. Rich/hostile/invalid metadata, all recommendation bounds, source URL identity, useful public text, licenses, diagnostics, pagination, filters, 404/422 and denied read writes. No provider needed. |
| D2 | test / P1 | `backend/tests/test_resource_record_held_secrets.py::test_acquisition_held_key_signed_urls_transport_absent_every_phase`; `::test_shared_filter_only_urls_exact_transport_keys_and_held_secrets`; retained writer/provider suites | Real Settings and synthetic `CIVITAI_API_KEY_FILE`, provider caller, registered acquisition route, actual background target, SQLite persistence, resource list/detail/status and ledger, captured logging. Only HTTP I/O and thread scheduling are substituted. HTTPcore header traces are injected at mocked HTTP to exercise the production logging boundary. Checks all resource columns plus notes/metadata before and after successful install. No owner key. |
| D3 | test / P2 | `test_resource_record_migration.py`; `test_resource_record_reads.py`; legacy-note, retry and ledger cases in `test_resource_record_corrections.py`, `test_resource_record_acquisition_notes.py`, `test_resource_record_ledger_projection.py` | Real old-schema SQLite copy/startup/backfill, idempotent repeat, old columns/notes/aliases/files preserved, incomplete and old recognizer rows readable. Read routes prohibit SQL writes/provider/model-body access. No live database migration. |
| D4 | test / P2 | Inherited Backend/MCP qualification at rejected `8d5f2968`, new affected tests and REGISTRY counts below; code/test deletion list below | Inherited complete offline suites with per-test 60-second timeout, isolated data roots, real registered MCP/stdio fixture paths; correction checks are bounded as assigned. No source inventories or raw logs committed. |

## Resulting behavior

Public record fields use closed schemas, bounded names/triggers, seven range-checked
recommendation keys, four license fields with known values, and closed diagnostics.
`source_url` is reconstructed from valid IDs. `source_evidence` is absent from the
public record and OpenAPI while internal acquisition/resume state remains stored.
The legacy metadata DTO remains readable and read normalization never rewrites rows.

The shared filter strips HTTP(S) URL userinfo/query/fragment, drops only the eight
exact case-insensitive transport keys, replaces raw/URL-encoded held keys, and
maps non-finite floats to null. It does not recognize credential-looking prose.
Existing `redact_secrets` callers retain their query policy by default; the shared
filter requests exact replacement without the old query-label scan. Encoded held
keys are now protected by the same existing replacement mechanism. Acquisition
locator storage and HTTPX logs use bounded URL filtering; raw HTTPcore debug
payloads are suppressed because they contain arbitrary auth/cookie header tuples.
The ledger filters its embedded public diagnostic at construction so rebuilt source
URLs do not cause false unsafe-lock refusals. Recipe services are unchanged.

`resource_records.py` changes from 460 to 321 lines (139 fewer); the separate closed
public-shape helper is 78 lines. There is no replacement credential recognizer.
The matching [resource-record topic](../../resource-records.md) documents bounds,
license enums, public/internal state and logging behavior.

## Correction 1 verification

R1 / D2 / P1 is guarded by the real acquisition test's new `apostrophe-query`
parameter. It receives exactly
`https://civitai.com/api/download/models/21?filename=O'Reilly.safetensors&X-Amz-Signature=SIGNED_DOWNLOAD`.
Before the fix, this parameter failed on `SIGNED_DOWNLOAD` in persisted columns:
**1 failed**, exit 1. The embedded URL/public-text check separately failed on the
same apostrophe truncation: **1 failed**, exit 1. With the fix, the held-secret
module passed **3 tests**, exit 0. The final affected run below includes both.
Only synthetic secrets and mocked external HTTP/thread scheduling are used;
settings, registered routes, provider caller, SQLite and background target are real.

URL-only strings are parsed as complete locators before userinfo/query/fragment
removal. Embedded URLs include legal apostrophes, so no signed-query tail survives.
Public creator prose before/after a URL, exact transport keys, raw/encoded held-key
replacement, typed projection and internal state keep their existing boundaries.
No credential-label recognition or p2-04 product change is added.

The only new quarantine is
`docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases[-0.01-install]`.
Its task-linked skip names [p2-04](../p2-04-durable-download-jobs/task.md), which owns
the diagnostic fix and re-enabling it. All assertions and other parameters remain.
QA independently reproduced it on starting source in round 1; that baseline result
is reused. The prior candidate's separate Backend immediate-expiry skip is inherited.
REGISTRY rows and historical review/acceptance reports are unchanged; supersession
still belongs to a subsequent independent PASS review.

Current run uses isolated Python 3.11.15 with existing Backend package versions,
MCP 1.26.0 and pytest-timeout 2.4.0. No shared environment was changed.
`QUAL_PY="$PAPERCLIP_SCRATCH_DIR/qualification-venv/bin/python"`; both final commands
also set `MCP_TEST_PYTHON="$QUAL_PY"` and
`AI_DRAWING_TEST_SITES="$PAPERCLIP_SCRATCH_DIR/qualification-venv/lib/python3.11/site-packages"`.

- Affected check: `AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/affected-final" "$QUAL_PY" -m pytest -c pytest.ini -q --timeout=60 backend/tests/test_resource_record*.py backend/tests/test_civitai_acquisition.py backend/tests/test_civitai_provider.py backend/tests/test_civitai_resource_install_api.py backend/tests/test_civitai_easy.py backend/tests/test_civitai_admission_deadline.py backend/tests/test_civitai_safe_download.py` — **436 passed, 1 skipped, 7 warnings**, exit 0, 11.74 s. The skip is inherited; warnings are existing Pydantic/AnyIO deprecations. An initial selection named a nonexistent acquire-API module and exited before collection; the corrected selection above is the qualification result.
- REGISTRY: one invocation, **877 passed, 3 skipped, 7 warnings**, exit 0, 72.15 s. The three skips are the inherited Backend immediate-expiry case, the historical optional lifecycle-export case and the one newly assigned deadline parameter. Existing warnings are the same Pydantic/AnyIO deprecations. The invocation selects the same 27 modules as round 1: test-function-bearing Python paths in retained REGISTRY rows; the owner-approved recognizer-only S–Z rows are excluded pending QA supersession. Suite-directory rows reuse inherited qualification; historical non-test fault/artifact packagers are not executed. Reproduce the selection and command from the candidate root:

```python
import ast, os, re, subprocess
from pathlib import Path
files = set()
for row in Path('docs/tasks/REGISTRY.md').read_text().splitlines():
    if not row.startswith('| ') or re.match(r'\| p2-02-resource-record/[S-Z][1-5] \|', row):
        continue
    for name in re.findall(r'(?:backend|mcp-server|docs)/[\w./-]+\.py', row):
        p = Path(name)
        if p.is_file() and any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                              and n.name.startswith('test_')
                              for n in ast.walk(ast.parse(p.read_text()))):
            files.add(name)
os.environ['AI_DRAWING_TEST_ROOT'] = os.environ['PAPERCLIP_SCRATCH_DIR'] + '/registry'
subprocess.run([os.environ['QUAL_PY'], '-m', 'pytest', '-c', 'pytest.ini', '-q',
                '--timeout=60', *sorted(files)], check=True)
```

`QUAL_PY` and the two interpreter variables above are exported for that reproduction.
The historical deadline module remains registered and is included in these 27 modules.

- New full Backend/MCP/Frontend suites: not run, per the correction rule. Earlier full-suite counts below apply only to rejected candidate `8d5f29686555119b1cbcc934cbb38af9d6edaafc`, not this corrected commit.
- Offline checks only. Running service: not deployed or probed. Real generation: not run. Artifact retrieval: synthetic fixture files only; no live model/Gallery retrieval.

## Inherited verification at rejected candidate 8d5f2968

The following results are retained from [Coding AID-219](/AID/issues/AID-219).
They are not new qualification of this corrected candidate.

The first new behavior checks failed on the starting implementation: 3 failed.
After implementation, focused resource/provider coverage passed: 286 passed.
One further control-only trigger fixture is included in final full qualification.

P1 sensitivity checks (temporary changes restored before qualification):

- D1: changed the steps upper bound from 150 to 151. The registered HTTP bound test
  failed because the invalid recommendation was returned (1 failed).
- D2: removed URL-encoded exact-secret replacement. The real acquisition test failed
  on the synthetic encoded key in stored/public observations (1 failed).

Qualification uses a run-owned Python 3.11.15 environment containing the existing
Backend/MCP installed package versions plus `pytest-timeout` 2.4.0. No repository or
shared virtual-environment dependencies were changed. An initial environment attempt
used extra packages on PYTHONPATH; stdio/child interpreters intentionally omit that
path, so that attempt was not a qualification result. The isolated environment
makes subprocess imports self-contained. Commands from the candidate worktree:

```sh
QUAL_PY="$PAPERCLIP_SCRATCH_DIR/qualification-venv/bin/python"
AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/backend-final" \
  MCP_TEST_PYTHON="$QUAL_PY" "$QUAL_PY" -m pytest -c pytest.ini backend/tests -q --timeout=60
AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/mcp-qualified" \
  MCP_TEST_PYTHON="$QUAL_PY" "$QUAL_PY" -m pytest -c pytest.ini mcp-server/tests -q --timeout=60
```

- Backend: **2340 passed, 125 skipped, 82 warnings**, exit 0 in 63.38 seconds.
  Skips: 124 Windows-only cases and the one linked pre-existing deadline case.
- MCP: **672 passed, 4 skipped**, exit 0 in 64.76 seconds.
  Skips are existing optional smoke-export cases.
- `git diff --check`: passed before commit; staged check is recorded in delivery.
- Running service: not checked or deployed.
- Real generation: not run.
- Artifact retrieval: not run against a service; only synthetic fixture files were checked.
- Raw output stays in run-owned scratch, outside Git; it is disposable after the run.

## Baseline failures, test adaptations and limits

A starting-main read/migration run had 26 passed / 1 failed: the old schema test
forbade the three empty additive p2-04 tables now created by startup. Its assertion
now permits exactly those additions and retains the whole legacy schema/value,
no-write, file and idempotence checks.

Selected starting-main reproduction also confirmed the legacy progress/retry
mismatch (47 failed / 70 passed across overlapping parameter cases), and a broader
selection confirmed 20 failed / 1 passed. These are overlapping samples, not a
full baseline count. Test-only adaptations preserve useful feature coverage:

- Two old acquisition/install fixtures now create the complete current ORM schema,
  rather than only `downloaded_resources`; the 91 tests in those modules pass.
- Legacy untracked downloading rows report no inferred `.part` progress and refuse
  an implicit retry, matching existing main behavior. The retained-note tests still
  check exact storage preservation and current outcomes. A failed-row retry fixture
  supplies its already known local path and selected size for durable admission.
- The pre-existing immediately expired install-deadline diagnostic omits resource ID
  before lookup. That one feature case is explicitly skipped with a reason linking
  [p2-04](../p2-04-durable-download-jobs/task.md), as AGENTS requires for known blocked
  feature tests. Other deadline/lock guards run. No p2-04 product fix is included.
- Existing resource-record tests now expect omitted public evidence/file-license/
  LoRA-strength fields, bounded sampler values and control-free labels. Internal
  operation-state assertions read internal metadata instead of the public DTO.
- Partial acquisition-note/ledger modules retain every test function and their
  non-recognizer feature cases. Their retired synthetic spelling matrices are
  replaced by signed-URL or actual configured synthetic-key inputs (listed below).

Public metadata intentionally has less detail. Numeric recommendations reuse the
existing generation bounds (steps 1–150, CFG 1–30, dimensions 256–2048) and recipe
clip skip 1–24. License enums are `None`, `Image`, `Rent`, `Sell`, `RentCivit`.
Third-party creator text resembling credentials is retained. Existing legacy rows
and notes are never scrubbed or rewritten. When a configured key is unreadable,
read-only projection remains available; it does not recover historical rotated
keys. No real owner-key, network, Windows or deployed-service qualification is claimed.

No alternative design was abandoned: implementation follows the cleared allowlist.
Raw provider header logging was removed instead of trying to parse header tuples.

## Deleted recognizer code and tests

Removed from `resource_records.py`: `_IDENTIFIER_UNIT`, `_ASSIGNMENT_LABEL`,
`_LABEL_ESCAPE`, `_LABEL_ESCAPES`, `_BEARER_AUTH`, `_BASIC_AUTH`, `_SENSITIVE`,
`credential_label`, `_assignment_in_view`, `_credential_assignment`,
`_json_string_view`, the free-text recognition branches of `safe_text`, and the
unused base64 import. The URL and exact-secret portion remains.

The following eight files and all their parameterized recognizer cases are deleted.
Every deleted test function is named here (associated safe-neighbor/parser-bound
controls are superseded by the new bounded public-contract and shared-filter tests):

- `test_resource_record_credential_labels.py`:
  - `test_prefixed_direct_publication_commit_reload_idempotent`
  - `test_prefixed_registered_edited_install`
  - `test_prefixed_provider_inspect_select_acquire_background`
  - `test_prefixed_old_storage_all_fields_readonly`
  - `test_credential_dictionary_keys_share_assignment_policy`
  - `test_near_neighbor_metadata_and_keys_remain_useful`
  - `test_prefixed_label_keys_in_old_storage_readonly`
  - `test_credential_failure_keeps_actionable_hint_through_background_and_status`
  - `test_long_unassigned_description_publishes_and_reads_without_parser_retry`
- `test_resource_record_credential_values.py`:
  - `test_complete_value_direct_publication_commit_reload_and_idempotence`
  - `test_complete_value_old_storage_detail_list_ledger_readonly`
  - `test_complete_value_registered_edited_install_publication`
  - `test_complete_value_real_provider_inspect_select_acquire_background`
  - `test_safe_neighbors_retain_meaning`
- `test_resource_record_quoted_labels.py`:
  - `test_quoted_direct_publication_commit_reload_idempotent`
  - `test_quoted_registered_edited_install`
  - `test_quoted_provider_inspect_select_acquire_background`
  - `test_quoted_old_storage_all_fields_readonly`
  - `test_quoted_key_text_consistency`
  - `test_quoted_keys_real_publication_and_reads`
  - `test_quoted_safe_neighbors_retain_useful_metadata`
  - `test_quoted_long_descriptions_have_bounded_scanning`
  - `test_escaped_unmatched_long_description_consumes_tail_once`
  - `test_nested_opposite_quote_label_publication`
- `test_resource_record_quote_contexts.py`:
  - `test_quote_context_complete_value_recognition`
  - `test_quote_context_publication`
  - `test_quote_context_provider`
  - `test_quote_context_edited_install`
  - `test_quote_context_old_reads`
  - `test_quote_context_safe_original`
  - `test_dense_odd_quote_description_retains_content`
  - `test_json_unit_publication`
  - `test_json_unit_provider`
  - `test_json_unit_old_reads_finally`
- `test_resource_record_quote_prefix_escapes.py`:
  - `test_quote_prefix_complete_value`
  - `test_quote_prefix_publication`
  - `test_quote_prefix_provider`
  - `test_quote_prefix_old_reads`
  - `test_quote_prefix_safe_original`
- `test_resource_record_serialized_assignments.py`:
  - `test_serialized_assignment_publication`
  - `test_serialized_assignment_provider`
  - `test_serialized_assignment_edited_install_and_new_notes`
  - `test_serialized_assignment_old_reads_finally`
  - `test_serialized_assignment_key_text_consistency`
  - `test_serialized_safe_neighbors_keep_original_representation`
  - `test_serialized_ordinary_description_bound_and_content`
- `test_resource_record_terminal_escapes.py`:
  - `test_terminal_description_provider_publication_orm_detail`
  - `test_terminal_description_registered_provider_inspect`
  - `test_terminal_description_stored_reads_readonly`
  - `test_increasing_terminal_descriptions_retain_exact_content`
  - `test_terminal_neighbors_cannot_hide_complete_credentials`
  - `test_serialized_terminal_descriptions_remain_complete`
- `test_resource_record_representation_contexts.py`:
  - `test_representation_context_recognition`
  - `test_representation_context_publication`
  - `test_representation_context_provider`
  - `test_representation_context_edited_install`
  - `test_representation_context_old_reads_finally`
  - `test_representation_context_safe_original`

Retired recognizer parameter cases in retained modules (functions remain):

- `test_resource_record_acquisition_notes.py`: the old `TEXTS` representations in
  `test_new_notes_admission_background_and_all_public_phases`,
  `test_old_notes_public_summary_readonly_exact_storage`,
  `test_retained_adverse_notes_acquisition_reuse_and_retry_exact`,
  `test_acquisition_refusal_diagnostics_exclude_complete_source_values`,
  `test_source_derived_package_warnings_use_complete_policy`, and
  `test_selected_provider_legacy_license_snapshot_contract`. The independent long
  safe-content test remains, with the new metadata length bound.
- `test_resource_record_ledger_projection.py`: old `TEXTS` recognizer cases in
  `test_real_acquisition_outer_ledger_complete_trace`,
  `test_seeded_old_whole_ledger_readonly_exact_columns`,
  `test_raw_internal_resolution_public_refusal_and_failure`,
  `test_variant_raw_report_refused_before_build_or_queue`, and
  `test_easy_public_plan_copy_preserves_raw_internal_match`. Safe identity, mixed
  ledger order/filter/count and safe variant controls remain.

## Historical REGISTRY handoff

Delivery QA owns supersession and regeneration; this candidate does not edit
`REGISTRY.md` or historical review files. The affected p2-02 families are S1–S5,
T1–T5, U1–U5, V1–V5, W1–W5, X1–X5, Y1–Y5, and Z1–Z5: their recognizer-only
meanings and removed-file/spelling-matrix guards are superseded by this approved
behavior. S4/V4/W4/X4/Y4/Z4 include retained migration/preservation checks; keep
those feature meanings represented. C1–C5 and D1–D5 retain their non-recognizer
identity, publication, migration/read and actionable-error coverage with the test
adaptations above. QA should update affected old output-shape claims while retaining
those guards, then add this task's independent review outcome. Historical acceptance
and rejection counts remain unchanged.
