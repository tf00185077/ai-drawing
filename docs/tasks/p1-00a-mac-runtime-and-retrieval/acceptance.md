# Producer acceptance — p1-00a Mac runtime/retrieval repair

Date: 2026-11-24. Coordinator: [AID-142](/AID/issues/AID-142).

## Decision and fixed identity

Accept corrected candidate **`b6d58468147e11a21b3d7a26ea25ed4353a28a28`** after
[QA AID-154](/AID/issues/AID-154#comment-cc15f186-5fc7-49f8-8db7-81c81b65894c)'s
independent [round-2 PASS](review.md) on original D1-D5. QA report/evidence/registry
commit: `3d5d8902a89a8c3c8994ed89e944fcaee0260577`. Original specification remains
`4ac3d5653d7bffee2698809d32d0f5ea0f506cbc` with [CLEAR kickoff](kickoff-review.md).

The [first FAIL](review-round-1.md) at `00ebb4d73edf3efe54943f3e2d784200e3023cab`
and its official [AID-152](/AID/issues/AID-152) artifacts remain preserved.
Accounting stays one delivery rejection, correction round 1, delivery review
round 2. The corrected inventory resolves F-QA1; it adds no product behavior.
Integrate the complete corrected candidate and QA metadata, then publish before
completing this coordinator and releasing [AID-143](/AID/issues/AID-143) for
baseline-informed p1-01/02 kickoff. No routine owner confirmation is pending.

## Accepted evidence and limits

| Boundary | Accepted evidence |
|---|---|
| Offline tests | Independent QA full Backend `1900 passed, 124 skipped, 76 warnings in 42.40s`; MCP `314 passed, 4 skipped in 1.10s`; both exit 0 with `--timeout=60` and isolated roots. Round 2 reuses those results after renewed source/test/root-input/package/platform equality checks. Coding's separate full runs agree. No new Frontend/Windows result or correction-round suite execution. |
| Running service | Identified controlled launch from `eaf11b8`, retained launch/active-job receipts, and independent process/import/configuration/DB/source-fingerprint checks. Round-2 read-only checks confirm the revision schema and applicability. Old PID's loaded source remains unknown. A current checkout/cwd/health alone does not identify loaded code. |
| Real generation | Coding's completed fresh current-tool original/revision requests and independent QA ComfyUI-history/persistence reconciliation remain applicable. Original job `8b826d11-5f52-4972-bbe2-1d0909fc20f9`, image 4448, artifact 3863; revision `08955297-4723-477c-875e-7f234a71a4da`, image 4449, artifact 3864, parent **3863**. Derived parent job/request/brief agree. The deterministic original used cache; no new generation in correction or QA. |
| Retrieved artifacts | Independent QA consumed both Gallery tools' unmodified returned host paths and decoded baseline/original/revision PNG bytes. Round 2 reverified archived payloads; it did not repeat a live retrieval journey. Baseline/original: 241339 bytes, SHA-256 `3205fe71ff38759cea79116947af7342275be3b778c034f415e2462e32fd96bc`; revision: 221328 bytes, `f86f0daf4aa9b36041189ab742d098f08034578b79018564bbaab2d105f8e644`. RGB PNG, 512×512. Byte reads outside MCP are disclosed; proof is limited to the colocated Mac client. |
| Complete runtime inventory | Image revision column, all eight nullable training fields, empty reservation table/five indexes and existing startup cause are enumerated. QA repeated the complete read-only schema/value audit: all old values across 14 tables preserved, added training fields NULL, reservation table empty, only two expected image/two artifact additions. No later delta from the correction snapshot. Private DB/configuration are not published. |

## Producer verification and publication scope

- Read the actual corrected manifest, complete round-2 review, schema audit and
  original/repair accounting. Downloaded and hash-checked all seven Coding and
  five QA uploads. Official manifest/review match Git; correction, cumulative and
  QA patches match Git output. All 90 Coding archive repository files and 26 QA
  archive repository files match their named commits; three fixed references and
  all three PNG payload hashes match.
- Compared Backend/MCP and the other production/test trees with current main;
  they are identical. The original task, baseline records and raw generation
  evidence remain unchanged. Reused verification covers those inputs; another
  full suite or generation is not required for these documentation-only merges.
- Integrate the exact reviewed files unchanged, with a byte-identical historical
  round-1 review mirror, this acceptance and current-state/progress documents.
  Publication records/remote readback belong on AID-142. No private runtime file,
  database, model, dataset or output is committed or deleted.
- Producer performed document/archive/Git checks only in this acceptance round.
  No software suite, live product probe, restart, generation or live generated
  image-byte read. The archive hash checks are separate from QA's prior live
  locator/decoding proof. Standing registry guards total two items.

## Continuation and retained boundaries

The original [no-repair baseline](../p1-00-mcp-friction-run-mac/manifest.md) remains
**23 intervention units across eight incidents**, with its original failed
byte-retrieval/revision outcome and legacy/null context. Repair evidence does not
rewrite that measurement. F4/F5/F8 are resolved for this identified launch and
colocated filesystem client. F1/F2 environment binding, F3 response parsing, F6
polling and F7 visibility retain their later-task mappings.

Keep the active AID-151 worktree, private configuration, canonical Backend venv
and all data until reviewed deployment replaces that runtime. Its loaded source
remains the explicitly recorded launch source; publishing newer documentation
does not relabel the loaded commit. No restart is needed just to change a docs
SHA.

AID-143 next coordinates p1-01/02 together, requiring its own independent kickoff
CLEAR before Coding and exact-commit delivery QA. Later wait, health and smoke
tasks retain their order. Relative URL/remote-client support, live timeout/
cancellation/recovery and idempotency are not certified here; check an existing
job ID before any timeout resubmission. Three consecutive zero-intervention runs,
CTY's aesthetics/demo and phase-close decision remain unmet Phase 1 requirements.
