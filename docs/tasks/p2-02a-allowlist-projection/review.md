# p2-02a independent correction review

Verdict: PASS
Review round: 2

Reviewed 2026-11-27 for [QA AID-222](/AID/issues/AID-222), coordinated by
[Producer AID-217](/AID/issues/AID-217). Read actual [Coding delivery](/AID/issues/AID-221#comment-4c311459-80eb-409e-b16b-13fdd47eec7c)
and its complete manifest before review. Exact candidate: **`3e70e04c5bb8fb104bcf0324d19d99629741cd4c`**,
branch `coding/aid221-p202a-correction1`, based on `39737296217ec1bb8f14df2744b85a0530d4b0c0`.
Independent worktree `aid-222-qa`, report branch `qa/aid222-p202a-review`.
The rejected candidate and rewritten main were not substituted for this correction.

## Findings

**R1 / D2 / P1 resolved.** The received provider locator containing
`?filename=O'Reilly.safetensors&X-Amz-Signature=SIGNED_DOWNLOAD` is stripped before
commit. An independent registered-acquisition reproduction checks every stored column
and exact `resolved_download_url == 'https://civitai.com/api/download/models/21'`: pass.
The permanent real-caller `apostrophe-query` guard also passes through admission,
background install, stored notes/metadata, list/detail/status/ledger and captured logs.
Only external HTTP and scheduling are mocked; settings, key-file loading, provider
caller, registered routes, SQLite commit and background target are real.

Sensitivity: temporarily restored only the rejected URL-string branch, adapting its
callback to the candidate interface. Command: `AI_DRAWING_TEST_ROOT="$PAPERCLIP_SCRATCH_DIR/r1-sensitivity" "$QUAL_PY" -m pytest -c pytest.ini -q --timeout=60 'backend/tests/test_resource_record_held_secrets.py::test_acquisition_held_key_signed_urls_transport_absent_every_phase[apostrophe-query]'`.
Result: **1 failed**, exit 1, on `SIGNED_DOWNLOAD` in committed columns. Candidate
bytes were restored in `finally`; `git diff --exit-code HEAD -- backend mcp-server`
passed before the final combined run. Prior D1/D3/D4 sensitivity results remain
attributed to round 1; no repeated fault catalog or full suite was run.

No new blocking finding in the correction. Whole locator parsing and embedded URL
handling remove userinfo/query/fragment while retaining surrounding creator text.
Raw/URL-encoded configured-key replacement, exact transport keys, non-finite values,
public credential-looking prose, typed projection and internal state checks pass.

## Commands and results

Run-owned Python 3.11.15 uses the existing Backend package versions plus MCP 1.26.0
and pytest-timeout 2.4.0; shared environments are unchanged. `QUAL_PY` is
`$PAPERCLIP_SCRATCH_DIR/qualification-venv/bin/python`; export `MCP_TEST_PYTHON="$QUAL_PY"`
and `AI_DRAWING_TEST_SITES="$PAPERCLIP_SCRATCH_DIR/qualification-venv/lib/python3.11/site-packages"`.
One pytest invocation selects the manifest's 27 retained REGISTRY modules, unioned
with its 15 affected modules and the independent reproduction (35 unique modules):

```python
import ast, os, re, subprocess
from pathlib import Path
files = set()
for row in Path('docs/tasks/REGISTRY.md').read_text().splitlines():
    if not row.startswith('| ') or re.match(r'\| p2-02-resource-record/[S-Z][1-5] \|', row):
        continue
    for name in re.findall(r'(?:backend|mcp-server|docs)/[\w./-]+\.py', row):
        p = Path(name)
        if p.is_file() and any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_') for n in ast.walk(ast.parse(p.read_text()))):
            files.add(name)
files.update(str(p) for p in Path('backend/tests').glob('test_resource_record*.py'))
files.update('backend/tests/'+n+'.py' for n in ('test_civitai_acquisition','test_civitai_provider','test_civitai_resource_install_api','test_civitai_easy','test_civitai_admission_deadline','test_civitai_safe_download'))
os.environ['AI_DRAWING_TEST_ROOT'] = os.environ['PAPERCLIP_SCRATCH_DIR']+'/combined-review2'
subprocess.run([os.environ['QUAL_PY'], '-m', 'pytest', '-c', 'pytest.ini', '-q', '-ra', '--timeout=60', '--junitxml='+os.environ['PAPERCLIP_SCRATCH_DIR']+'/review2.xml', *sorted(files), os.environ['PAPERCLIP_SCRATCH_DIR']+'/test_review2_query.py'], check=True)
```

Result: **1071 passed, 3 skipped, 7 existing warnings**, exit 0, 77.39 s.
JUnit subsets: affected **436 passed / 1 skipped**; REGISTRY **877 passed / 3 skipped**;
independent R1 **1 passed**. Subsets overlap; they are not additive.
Scratch reproduction uses the unchanged round-1 reproduction with the exact-locator
assertion above. Raw logs, JUnit and helpers remain disposable run scratch only.
Suite-directory rows reuse earlier qualification; historical non-test fault/artifact
packagers were inspected, not executed. No new full Backend/MCP/Frontend run.

The sole new quarantine is `review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases[-0.01-install]`
under p2-03. Its reason names `docs/tasks/p2-04-durable-download-jobs/task.md` for fix
and re-enable. Independent baseline reproduction is in unchanged round 1. Assertions
are unchanged; **all five other parameters pass**. Its p2-03 D4/E1/E2/E3 feature rows
remain active. Other skips: inherited Backend immediate-deadline case (same task)
and existing optional MCP lifecycle-export case. No new p2-04 product change.

Earlier complete independent qualifications belong **only to rejected `8d5f29686555119b1cbcc934cbb38af9d6edaafc`**,
reported by [QA AID-220](/AID/issues/AID-220) at `35976f6f183336e67a923df55c15ad2883435928`:
Backend **2340 passed / 125 skipped**, MCP **672 / 4**, Frontend **226 / 1**, build exit 0.
This bounded correction PASS reuses that attributed evidence under the settled rule;
it does not relabel those full-suite runs as qualification of the corrected SHA.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | backend/tests/test_resource_record_allowlist.py; backend/tests/test_resource_record_reads.py | active |
| D2 | P1 | backend/tests/test_resource_record_held_secrets.py; backend/tests/test_resource_record_writers.py | active |
| D3 | P2 | backend/tests/test_resource_record_migration.py; backend/tests/test_resource_record_reads.py; backend/tests/test_resource_record_acquisition_notes.py; backend/tests/test_resource_record_ledger_projection.py | active |
| D4 | P2 | backend/tests/test_resource_record_held_secrets.py; backend/tests/test_resource_records.py (bounded correction; inherited full suites attributed above) | active |
| p2-02-resource-record/S1 | P1 | — | superseded |
| p2-02-resource-record/S2 | P1 | — | superseded |
| p2-02-resource-record/S3 | P1 | — | superseded |
| p2-02-resource-record/S4 | P1 | — | superseded |
| p2-02-resource-record/S5 | P1 | — | superseded |
| p2-02-resource-record/T1 | P1 | — | superseded |
| p2-02-resource-record/T2 | P1 | — | superseded |
| p2-02-resource-record/T3 | P1 | — | superseded |
| p2-02-resource-record/T4 | P1 | — | superseded |
| p2-02-resource-record/T5 | P1 | — | superseded |
| p2-02-resource-record/U1 | P1 | — | superseded |
| p2-02-resource-record/U2 | P1 | — | superseded |
| p2-02-resource-record/U3 | P1 | — | superseded |
| p2-02-resource-record/U4 | P1 | — | superseded |
| p2-02-resource-record/U5 | P1 | — | superseded |
| p2-02-resource-record/V1 | P1 | — | superseded |
| p2-02-resource-record/V2 | P1 | — | superseded |
| p2-02-resource-record/V3 | P1 | — | superseded |
| p2-02-resource-record/V4 | P1 | — | superseded |
| p2-02-resource-record/V5 | P1 | — | superseded |
| p2-02-resource-record/W1 | P1 | — | superseded |
| p2-02-resource-record/W2 | P1 | — | superseded |
| p2-02-resource-record/W3 | P1 | — | superseded |
| p2-02-resource-record/W4 | P1 | — | superseded |
| p2-02-resource-record/W5 | P1 | — | superseded |
| p2-02-resource-record/X1 | P1 | — | superseded |
| p2-02-resource-record/X2 | P1 | — | superseded |
| p2-02-resource-record/X3 | P1 | — | superseded |
| p2-02-resource-record/X4 | P1 | — | superseded |
| p2-02-resource-record/X5 | P1 | — | superseded |
| p2-02-resource-record/Y1 | P1 | — | superseded |
| p2-02-resource-record/Y2 | P1 | — | superseded |
| p2-02-resource-record/Y3 | P1 | — | superseded |
| p2-02-resource-record/Y4 | P1 | — | superseded |
| p2-02-resource-record/Y5 | P1 | — | superseded |
| p2-02-resource-record/Z1 | P1 | — | superseded |
| p2-02-resource-record/Z2 | P1 | — | superseded |
| p2-02-resource-record/Z3 | P1 | — | superseded |
| p2-02-resource-record/Z4 | P1 | — | superseded |
| p2-02-resource-record/Z5 | P1 | — | superseded |

## Notes and disposition

Only the 40 approved recognizer meanings are superseded. Retained p2-02 C1–C5 and
D1–D5 remain active; D3 above also guards old-note/column/file preservation, read-only
projection and idempotent migration, including retained meanings of S4/V4/W4/X4/Y4/Z4.
Eight deleted modules and all **58** deleted test-function names match the manifest;
named recognizer identifiers are absent. No owner-library edit or product repair.
Registry command: `python3 <reviewspec-review>/scripts/build_registry.py` — exit 0,
**51 active, 40 superseded**, no structural problems (87 - 40 + 4).
Unchanged round-1 report, cleared task/kickoff/handoff, historical p2-02/p2-03 acceptance
and ROADMAP were checked byte-for-byte against the assigned rewritten main.
Rejections remain **1** across all cards/runs; this PASS adds none. Thresholds remain
verbatim: after rejection 2 another same-class finding is AMBIGUITY; at 3 stop for
CTY before another correction. Producer owns acceptance, integration and continuation.
Offline tests: above. Running service: not deployed/probed. Real generation: not run.
Artifact retrieval: synthetic fixtures only; no live model/Gallery retrieval. Windows
was not run. No main merge, deployment, artistic verdict or phase exit is implied.
