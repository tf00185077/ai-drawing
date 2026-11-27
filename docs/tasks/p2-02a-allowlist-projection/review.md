# p2-02a independent delivery review

Verdict: FAIL
Review round: 1

Reviewed 2026-11-27 for [QA AID-220](/AID/issues/AID-220), coordinated by
[Producer AID-217](/AID/issues/AID-217). Actual [Coding delivery](/AID/issues/AID-219#comment-40414ef8-c5f1-47b1-ad3c-6e4eecf13c04)
was read before review. Reviewed full candidate: **`8d5f29686555119b1cbcc934cbb38af9d6edaafc`**,
branch `coding/aid219-p202a-allowlist`; independent worktree `aid-220-qa`,
review branch `qa/aid220-p202a-review`. Starting source:
`05da4bb981b4b8e44e991720093c9127509abc80`. No moving checkout was reviewed.

## Findings

**R1 / D2 / P1 — a valid apostrophe in a provider download query leaves the signature in storage.**
The new assignment at `backend/app/services/civitai_resource_acquire.py:501` calls
`safe_evidence` for the provider's `downloadUrl`. Its URL match at
`backend/app/services/resource_records.py:86` ends at an apostrophe, sanitizes only
that prefix, then leaves the suffix unchanged with `redact_query=False`.
Through the registered acquisition route, the provider URL
`https://civitai.com/api/download/models/21?filename=O'Reilly.safetensors&X-Amz-Signature=SIGNED_DOWNLOAD`
is accepted (202), and the committed resource row's `resolved_download_url` is
`https://civitai.com/api/download/models/21'Reilly.safetensors&X-Amz-Signature=SIGNED_DOWNLOAD`.
The entire synthetic signature value reaches storage. This is a received download
locator, within the held-secret boundary; no credential-looking prose is involved.
The same reproduction **passes on the starting source and fails on the candidate**.

Minimal reproduction, saved only in run scratch (the fixture mocks HTTP and thread
scheduling; settings, provider caller, route, admission and SQLite commit are real):

```python
import json
from tests.conftest import client, isolated_database, isolated_worker_admission
from tests.test_resource_record_writers import boundary, acquire_http
from app.db import database
from app.db.models import DownloadedResource

def test_provider_signed_query_with_apostrophe_is_absent_from_storage(boundary):
    b = boundary
    b.file['downloadUrl'] = "https://civitai.com/api/download/models/21?filename=O'Reilly.safetensors&X-Amz-Signature=SIGNED_DOWNLOAD"
    response = acquire_http(b)
    assert response.status_code == 202, response.text
    rid = response.json()['resource']['acquisition_id']
    with database.SessionLocal() as db:
        row = db.get(DownloadedResource, rid)
        stored = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        assert 'SIGNED_DOWNLOAD' not in json.dumps(stored, default=str)
```

Command: `AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/url-query-final" "$QUAL_PY" -m pytest -c pytest.ini -q --timeout=60 "$PAPERCLIP_SCRATCH_DIR/test_url_query.py"`.
Result: **1 failed** on the signature assertion. Same command from an archived
starting-source checkout, with a separate test root: **1 passed**.
Correction should strip the whole received URL query before storage and add this
case to the real-caller D2 test in `test_resource_record_held_secrets.py`; retain the
bounded URL policy, without introducing credential-label recognition. That guard
is currently absent. QA made no product repair.

## Done-when assessment

| Item | Level | Observed boundary and result |
|---|---|---|
| D1 | P1 | Registered list/detail/OpenAPI tests, rich/malformed metadata, recommendation/license/diagnostic bounds, filters, pagination, 404/422: pass. Public evidence removed, canonical URL rebuilt. |
| D2 | P1 | Delivered real-caller raw/encoded configured-key, signed-URL and transport tests pass; R1 independently demonstrates a signed-query storage regression. **FAIL.** |
| D3 | P2 | Real old-schema startup/backfill, exact legacy columns/notes/files, repeated idempotence and denied-write reads: pass. Internal acquisition state remains readable. |
| D4 | P2 | Named recognizer code and eight specified test files absent; every deleted function is listed in manifest. Retained partial-module feature cases remain. Final Backend/MCP suites pass with the skips below. |

## Commands and results

`QUAL_PY="$PAPERCLIP_SCRATCH_DIR/qualification-venv/bin/python"` is Python 3.11.15,
with existing Backend packages, MCP 1.26.0 and pytest-timeout 2.4.0. Shared environments
were not changed. `AI_DRAWING_TEST_SITES` points to the Backend's existing Python
3.11 site-packages for guarded `-I -S` fixture children. All state is below run scratch.

- Backend: `AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/backend-qualified" MCP_TEST_PYTHON="$QUAL_PY" "$QUAL_PY" -m pytest -c pytest.ini backend/tests -q --timeout=60` — **2340 passed, 125 skipped**, exit 0, 61.94 s.
- MCP: `AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/mcp-full" MCP_TEST_PYTHON="$QUAL_PY" "$QUAL_PY" -m pytest -c pytest.ini mcp-server/tests -q --timeout=60` — **672 passed, 4 skipped**, exit 0, 66.34 s.
- Frontend: with `AI_DRAWING_TEST_ROOT`, `AI_DRAWING_TEST_SITES`, `BACKEND_TEST_PYTHON="$QUAL_PY"`, worktree-local `AI_DRAWING_VITE_CACHE`, `cd frontend && npm test` — **226 passed, 1 skipped**; `npm run build` — exit 0.
- Setup attempts are not product failures: initial Backend run had 2338 pass / 125 skip and two child-import failures (`sqlalchemy` absent under `-S`); explicit sites fixed them (2 passed), then final qualification above passed. Initial frontend attempts lacked its interpreter/test-root settings; the configured run above passed. No source was changed to resolve these.
- Backend skips: 124 Windows-only and one documented pre-existing immediate-install-deadline diagnostic case linked to p2-04. MCP's four and frontend's one are existing optional skips. Windows was not run.

One smallest production fault per test item was applied sequentially, followed by
byte restoration. Related tests only, never a full suite per fault:

| Item | Temporary production fault | Test selector | Result |
|---|---|---|---|
| D1 | Steps maximum 150 → 151 in `resource_public_metadata.py` | `backend/tests/test_resource_record_allowlist.py::test_registered_recommendation_bounds[steps-151-150]` | 1 failed |
| D2 | Remove encoded variants from exact-secret replacements in `civitai_acquisition.py` | `backend/tests/test_resource_record_held_secrets.py::test_acquisition_held_key_signed_urls_transport_absent_every_phase` | 1 failed |
| D3 | Clear retained notes during backfill | `backend/tests/test_resource_record_migration.py` | 1 failed |
| D4 | Reintroduce a Bearer free-text recognizer in `safe_evidence` | `backend/tests/test_resource_record_held_secrets.py::test_shared_filter_only_urls_exact_transport_keys_and_held_secrets` | 1 failed |

Each command was `AI_DRAWING_TEST_ROOT=<separate scratch root> "$QUAL_PY" -m pytest -c pytest.ini -q --timeout=60 <selector>`.
Restored selectors in one invocation: **4 passed**. `git diff --exit-code HEAD -- backend mcp-server`
passed after restoration. Deletion-manifest inspection found eight deleted files and
zero omitted test-function names. No new recognizer class, recipe, MCP, UI or p2-04
product change is made by QA.

## Standing guards and supersession

One REGISTRY pytest invocation ran 27 unique test modules: existing modules
referenced by retained items and the behavioral deadline module referenced by
historical fault runners: **877 passed, 1 failed, 2 skipped**, 76.59 s. Suite-directory rows are
covered by the full qualifications above; historical non-test fault/artifact
packagers were inspected, not executed. No evidence inventories/bundles were made.
The module selection was the REGISTRY's `backend/`, `mcp-server/` and `docs/` Python
paths containing test functions, excluding the approved obsolete S–Z families;
`docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py` was added
because the historical fault runner references its behavioral tests.

The failing guard is
`docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases[-0.01-install]`:
`KeyError: resource_id`. One independent run on starting source reproduces **1 failed**
with the same error; the install production file is unchanged. The caller returns
within budget and preserves files/owner; its immediate-expiry diagnostic lacks the
resource ID. This is the manifest's known p2-04 limitation, not a new p2-02a finding.
It remains active and was not hidden, superseded or weakened by QA. Producer owns
its handling with the separate p2-04 work.

Owner-approved recognizer-only supersession scope: `p2-02-resource-record/S1–S5`,
`T1–T5`, `U1–U5`, `V1–V5`, `W1–W5`, `X1–X5`, `Y1–Y5`, `Z1–Z5` (40 items).
Their retained preservation/identity/error behavior is still exercised by C1–C5,
D1–D5 and this task's D3 tests. No other guard is approved for supersession.
`build_registry.py` was rerun: exit 0, 87 active, no structural problems. It derives
certifications/supersessions only from PASS reports, so this rejected candidate
cannot retire those 40 standing rows yet; apply them in the corrected PASS review.
Historical review files and acceptance/rejection counts are untouched.

## Disposition and limits

This is p2-02a's **first rejected delivery** (one P1 finding). Producer owns the
correction/acceptance decision. Counts carry across cards/runs; after a second
rejection a further same-class finding is AMBIGUITY; three total rejections stop
for CTY before another correction. No gate, ROADMAP threshold or owner-library edit.

Offline tests: as above. Running service: not deployed or probed. Real generation:
not run. Artifact retrieval: synthetic fixture files only; no live model/Gallery
retrieval. No owner key, live database, models, outputs or Gallery records were used.
No product PASS, acceptance, main merge or Phase 2 exit is implied.
