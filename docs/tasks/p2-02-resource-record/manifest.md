# p2-02 Coding delivery

Coding [AID-186](/AID/issues/AID-186) delivers the cleared Backend resource-record
foundation for independent [QA AID-187](/AID/issues/AID-187).
[Producer AID-146](/AID/issues/AID-146) owns acceptance. This is Coding evidence,
not a self-PASS, integration, deployment or Phase 2 exit.

Base: **a8e57d90e4678565baec8cd4638c350c8dd11deb**, tree
**a0115c2286b76bbd07676bdc45cba6e0686fb97c**. Actual kickoff
[AID-185](/AID/issues/AID-185) round1 CLEAR/report14b4c98 remains unchanged.
Task SHA-256: `c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`.

Final software/tests/replay-helper freeze:
**17e90a65b0b227900956e20b36d6ae8d3a8e4048**, tree
**2e46b02baf41f4d6e53addef888214298a865492**. Initial implementation commit
63044d5e6ae3f4c4cccbd62b6a17d11d9568feff precedes fixture/adapter whitespace
normalization and the source/registry replay helpers. The final full suites use
the final freeze. No later product/test/helper change is part of delivery.

The **final delivery candidate full SHA/tree** is pinned in the official uploaded
`delivery-index.json` and this card's post-commit delivery receipt. This manifest
is itself in that candidate, so it references the post-commit receipt to avoid a
circular self-hash. QA must review that final SHA, not the freeze ancestor or a
moving branch. The official delta bundle and full-index patch declare the fixed
published base above as their restoration prerequisite and are verified by actual
readback/reconstruction. Source publication does not identify a loaded service.

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-186-resource-record`;
branch `aid-186-p2-02-resource-record`. All commits carry the required Paperclip
co-author. Shared main and its 13 concurrent memory edits were never staged,
stashed, reset or copied. No canonical/private environment or data was mutated.

## Implementation

One nullable versioned metadata field augments DownloadedResource. Existing
integer IDs, identity/path/hash/status columns remain authoritative. Typed
provider snapshots preserve the selected version/file's raw label, ordered
triggers, finite recommendations and their origin fields, safe opaque metadata,
license permissions/gaps and explicit diagnostics. Actual measured hash/size/stat
evidence remains separate from provider declaration and historical status.

Both actual acquisition/background and retained inspect/select/install/adoption
paths publish through the same service. Strict schemas carry the selected
snapshot; legacy descriptors without it keep unknown triggers/recommendations.
Identity conflicts are refused before reuse/rebinding; identical publication,
retry and reuse retain IDs. Background completion rechecks admitted immutable
identity. Original notes remain source evidence; recipe enum/AIR/Anima behavior
stays behind a frozen legacy adapter. The local ledger derives its typed record
from the shared projection. No new model registry, lifecycle schema or MCP intent.

Normal startup is additive only. Explicit idempotent backfill preserves old
columns/values/notes/aliases/history/files, diagnoses incomplete/conflicting/
duplicate rows, and never hashes models or guesses image-alias model identities.
Registered read routes use SQL filters/count/pagination and the same projection.
They expose stable errors/OpenAPI and perform no writes, repairs, provider calls
or model-body reads. [Backend topic contract](../../resource-records.md) and
[legacy inventory](legacy-inventory.md) document choices and retained limits.

## D1–D5 evidence matrix

| Item | Check / level | Evidence / layer | Real boundary and fixtures |
|---|---|---|---|
| D1 | test / P1 | backend/tests/test_resource_records.py; schemas/resources.py; service resource_records.py; current full Backend; wrong-map and fabricated-verification faults | Real ORM round trips, all four exact labels/case/outer whitespace and unsupported/malformed/absent cases, raw label retention, invalid/conflicting recommendations, missing/invalid licenses/IDs, declared versus measured evidence, stat staleness, same-row publication/conflicts. Synthetic rows/files only. |
| D2 | test / P1 | backend/tests/test_resource_record_writers.py; current retained acquire/install/ledger/provider files; split-acquire and split-install faults | Actual registered HTTP, Settings/file resolver, version resolver, strict inspect/select/install, SQLAlchemy and actual background target. Non-first version/file, measured synthetic bytes, failed/same-ID retry/reuse/conflicts/AIR/publication-time and local-ledger projection. Only external HTTP and thread scheduling substitute operations; DB/path/key inputs are synthetic. |
| D3 | test / P1 | backend/tests/test_resource_record_migration.py; fixtures/resources/previous-schema.sql; evidence/schema-audit-data.json; legacy-inventory.md / legacy-callers.json; destructive-backfill fault | Real previous-schema SQLite copy, normal init_db and explicit backfill. Whole old schema/values, all alias/history sentinels, duplicates/conflicts/malformed/unsupported/offline rows, repeat startup/backfill and denied model-body/network/write boundaries. No production DB/snapshot. |
| D4 | test / P1 | backend/tests/test_resource_record_reads.py; real main/router/OpenAPI; unbounded-list and writing-list faults | Actual HTTP/ORM list/detail, all exact filters, filtered totals/order/bounds/errors/old+new rows, whitespace agreement, invalid selectors, secrecy and SQL/body/provider/repair denial. Offline service fixtures; no production service claim. |
| D5 | test + delivery / P1 | evidence/freeze.json, source-inventory.json, faults.json, verification.json, command JSON/logs, child-guards.json; manifest and official exact candidate/index/bundle/patch | Seven meaningful faults, exact restoration, final full Backend/MCP, fresh standing-contract producers/readers, 22 exact retained registry rows and complete ordinary source hashes. Independent QA owns any verdict/certification. |

Every feature file exists in the candidate, with **61 new feature cases**. Initial
REDs, intervening failed attempts and final GREENs are retained. The
[reproduction guide](evidence/verification-commands.md) enumerates fixtures,
commands, actual import/root/guard identities and restoration rules. The
[source inventory](evidence/source-inventory.json) fingerprints **2,603** frozen
tracked blobs, including every ordinary token-named path; none is suppressed.
The official final candidate index additionally fingerprints every final blob.
All four faulted source files restore byte-for-byte and match both source commits.

## Current verification

All long suites use isolated roots and per-test **--timeout=60**. A dedicated
Python 3.11 environment references existing dependency sites read-only. The
explicit .pth audit hook denies private-file access, remote/live-service network
and writes outside run scratch; activation is tested before probing. Test child
receipts have zero blocked events and pin actual imported component paths.
Nested child receipts and fresh exported shapes are retained separately.

| Command label / scope | Result |
|---|---|
| baseline-corrected / retained acquire/install/ledger | 93 passed |
| prefreeze-feature / new and affected retained features | 216 passed |
| restored-feature / all new D1–D4 cases after faults | 61 passed |
| backend-full / backend/tests at final freeze | **2,039 passed, 124 existing Windows skips**, 76 existing deprecation warnings, 45.88 s |
| mcp-full / mcp-server/tests at final freeze | **666 passed, four existing optional-export skips**, 72.66 s |
| export / current Backend revision/multi-LoRA/lifecycle/health producers | 93 passed |
| cross-layer / separate MCP consumers of current exports | 73 passed |
| registry-mcp / standing MCP/PNG/stdio/smoke/independent-content consumers | 412 passed |
| fresh-wait / separate current Backend child and registered wait | 12 passed |
| retained-provider-guards / unchanged prior independent positive credential tests | 19 passed, run here as Coding regressions |
| schema-audit / full synthetic old-schema preservation | one passed |
| scratch registry rebuild | all **22** prior rows exact; canonical registry unchanged |
| source inventory/restoration; final diff whitespace check | exact protected source, no suppressed ordinary hashes; clean after documented normalization |

The 124 Backend skips remain Windows-only; four full MCP skips require explicitly
exported fixtures, exercised by the current export/reader commands above. No new
skip, deleted feature test, assertion relaxation or registry supersession.
Frontend is unchanged and not rerun. Windows is not exercised. Prior p2-01 test
results are historical, not used to qualify changed source.

| Deliberate product fault | Observed relevant failures |
|---|---|
| NoobAI mapped to null | one mapping case fails |
| Missing evidence fabricated as verified | two honesty guards fail |
| Acquire bypasses canonical publication | registered acquire snapshot guard fails |
| Install bypasses canonical publication | registered non-first install snapshot guard fails |
| Backfill destroys original notes | whole old-value guard fails |
| List loses SQL bounds | pagination and read-query guards fail |
| List issues UPDATE | actual SQL write-denial guard fails |

Each mutant exits 1 at an observable feature assertion. Exact bytes restore in
finally before the 61-case GREEN; complete final suites follow restored freeze.
The seven mutants produce nine relevant failures, not an independent QA verdict.

## Failed attempts, deviations and limits

- First environment setup used system python3 (3.9) and stopped when the expected
  Python3.11 site path did not exist. Its following runner invocation found no
  driver file. Explicit python3.11 fixed setup. The first baseline then failed
  before collection because the timeout dependency path used an incorrect old
  worktree name; using the existing aid-175-qa site resolved it without install.
  Guessed nonexistent source/test filenames were resolved with rg --files.
- D1 initial RED: 24 missing-feature failures. D2 initial RED: four. D3 initial
  RED: missing backfill. D4 initial RED: 25 absent-route cases. These expected
  failures precede their implementations and remain in evidence.
- First combined D2 GREEN attempt: **two failed, 181 passed**. Planned rows must
  allow a stale path/absent identity to be filled while refusing conflicting
  known identity. The legacy Illustrious lock fixture now sets baseModel before
  inspection, keeping its snapshot consistent. Both original lock assertions are
  unchanged; this fixture-only compatibility change is the only existing-test
  edit. No existing test function is removed or skipped.
- First D3 GREEN attempt failed on a synthetic alias-history CHECK constraint.
  Correct table names and valid operation/hash sentinels fixed the fixture; no
  product relaxation. First D4 GREEN attempt: **one failed, 24 passed** because
  validator ordering hid OpenAPI maximum/minimum keywords. Reordering annotations
  preserves validation and publishes the actual bounds.
- Three edge REDs exposed recommendation conflict reapplication, missing-ID
  augmentation and conflicting legacy family diagnostics. Two later edge REDs
  exposed invalid IDs/licenses and repeated installation time/AIR preservation.
  A registered Unicode-whitespace RED exposed SQL/Python trimming disagreement;
  a background identity RED exposed possible completion-time hash rebinding.
  Minimal fixes precede current GREENs/full suites; none is an abandoned feature.
- Initial staged whitespace check reported generated SQL trailing spaces and a
  legacy adapter EOF blank line. The shell command lacked fail-fast and still
  created initial source commit63044d5. A separate, retained commit normalizes
  only that whitespace and adds replay helpers; its check is clean and the final
  full suites use freeze17e90a6. History is not amended or hidden.
- Internal representation choices stay within the cleared contract. No broad
  replacement, specification change, routine owner question, new architecture,
  lifecycle/MCP feature or new alias feature. Metadata recommendation sources
  are deliberately limited to explicit version.meta/file.metadata; unfamiliar
  safe fields are opaque evidence. Legacy install safety/enum/package behavior
  and stat-evidence limits are documented in the Backend topic.

**Offline:** the tests above, synthetic byte verification and restoration/package
checks only. **Running service:** no probe, startup, restart or deployment of a
production service. **Provider/generation:** no real key read, live provider
traffic, model download, registration or generation. **Retrieval:** synthetic
fixture bytes and official attachment readback only; no live model/Gallery bytes.
No completed record/search/download-job/default flow, fresh checkpoint+LoRA
qualification, phase exit or CTY aesthetic acceptance is claimed. First check and
p2-01 histories remain attributed unchanged. Independent AID-187 pins the final
candidate and supplies its own actual verdict; Producer handles acceptance or
correction. No feature push, merge, parent status/owner write or owner gate.
