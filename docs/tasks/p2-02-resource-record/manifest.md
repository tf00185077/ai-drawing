# p2-02 Coding correction1 delivery

Coding [AID-188](/AID/issues/AID-188) delivers the bounded R1–R4 corrections for
independent [QA AID-189](/AID/issues/AID-189) delivery review2.
[Producer AID-146](/AID/issues/AID-146) owns acceptance. This is Coding evidence,
not a self-PASS, product merge/push, deployment or Phase2 exit.

Fixed implementation base: **4b95c7a74c032d092ac86b53b657bd107bdfcb3e**, tree
**ea786f4650fd47b78cfaeabb6eddb68cbf66dd1c**. Its product/tests are byte-identical
to rejected **9abe3d1c3237791b684e3b9f5a692879df747361**. Imported only repair,
resource decision and the two original exact mirrors from fixed supplement
**2471ef8157e009aca70596abc27774f34c028a96**. Original kickoff1 CLEAR is unchanged.
Task SHA256: `c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`.
Repair SHA256: `b3d649dcd8e60217b6581d1bdf8ca34db5f22ad0c71f5efd31c1449390b06977`.

Final software/tests/test-replay-helper freeze:
**42e6812e846754ea31f32573d4ef66a8af3f2d47**, tree
**b8770633de2b9be61296bea4c1cf66bdf420e8ff**. Initial implementation47eac3a is
retained; the freeze adds an explicit error assertion and complete evidence.
All current complete suites run on this final freeze after exact restoration.
Later commits contain reporting/evidence only, with product/tests/helpers exact.

The **final full candidate SHA/tree** is pinned in the official uploaded
`delivery-index.json` and native post-commit delivery receipt, avoiding a circular
self-hash in this committed manifest. Review that exact final candidate, not a
moving branch or the freeze ancestor. The official manifest bytes equal this
candidate's Git body. The final index fingerprints every ordinary final blob.

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-188-resource-correction`,
branch `aid-188-p2-02-correction1`; its dedicated ignored Python3.11 environment
and history remain. All commits have the required Paperclip co-author.
Shared main, its13 memory edits, canonical environments, runtime/private settings,
key/snapshots/backups, retained worktrees and model/dataset/output/Gallery data
were not staged, stashed, reset, copied as implementation, or changed.

## Corrections

**R1:** complete shared normalization applies to provider snapshots, typed client
publication and stored-snapshot projection. Every nested key/string is covered,
including license, diagnostics, triggers, recommendations/origins, raw labels and
opaque evidence. URLs lose userinfo/query/fragment, recognizable credential text
is removed, and sensitive evidence keys are excluded. Typed safe values and
ordinary hashes remain. Revalidation fails closed if safety cannot retain the
schema. Supplied verification never becomes measured evidence. Unsafe old storage
projects safely without writes; no whole-resource hiding or serializer-only fix.

**R2:** deterministic connection-local SQLite scalars call the projection's actual
complete typed parser and sole exact workflow mapping inside SQL. Filtered count
and ordered LIMIT/OFFSET use that validity before ORM materialization. Invalid
versions/nested types/JSON do not borrow a valid label or fall back to notes;
legacy incomplete rows retain their canonical meaning. Unicode trim/case folding
and raw-label behavior agree. No whole-table loading or limited-page post-filter,
second registry/schema, new dependency or generalized database framework.

**R3:** install still checks all known immutable identities before assigning.
Unknown incoming identity is omitted from assignment; known AIR survives omission,
missing fields can be augmented, and real non-null conflicts remain refused on
the same ID. Registered acquire/install combinations retain hash/measured evidence.

**R4:** retained rows preserve every original note body exactly through success,
provider refusal/failed result and credential-resolution exception. Current
sanitized operation/error state augments existing metadata under reserved
`source_evidence.acquisition`; status responses read it instead of stale note
errors. Admission/success clears current errors while old notes stay evidence.
Ordinary provider publication preserves that field; supplied snapshots cannot
replace it. Newly created-row generated notes/file identity/error behavior remains.
No cloned row, job/lifecycle/budget table or lost status/recovery reporting.

The [Backend topic](../../resource-records.md) explains these boundaries. Frozen
recipe/AIR/Anima and source-alias adapters and all31 MCP names/risks are unchanged.
The original legacy inventory remains source/caller evidence, not removal proof.

## D1–D5 and C1–C5 matrix

All entries are test/P1, with D5/C5 additionally delivery evidence. Paths below
refer to [correction-1-evidence/](correction-1-evidence/) unless stated otherwise.

| Item | Evidence/layer | Real boundary and substitutes |
|---|---|---|
| D1 | Original test_resource_records.py plus new test_resource_record_corrections.py; full Backend; wrong-map/fabricated-verification and snapshot/filter/identity faults | Real ORM typed round trips, all four exact labels, unsupported/malformed/absent cases, finite values, license gaps and measured/declaration distinction. Synthetic rows/files only. |
| D2 | Original test_resource_record_writers.py plus44 new correction cases; full Backend/MCP; split-writer and preservation faults | Real registered inspect/select/install/acquire, Settings/file resolver/provider machinery, strict resolution, SQLAlchemy, actual background targets/status/local ledger. Only external HTTP and deterministic scheduling substitute domain execution; paths/keys/bytes/DBs synthetic. |
| D3 | schema-audit.json/log/data, test_resource_record_migration.py and unchanged qa-evidence/test_baseline_schema.py; destructive-backfill fault | Exact pre-task ORM schema authority and full16-table old-schema/value/sequence/resource/alias-history/file audit. Normal startup adds only nullable metadata_json; explicit backfill changes that field only and repeats idempotently. No private DB/backfill. |
| D4 | Original test_resource_record_reads.py plus complete unsafe-storage and mixed-validity HTTP tests; raw-JSON/pagination/write faults | Registered HTTP/OpenAPI/ORM exact filters, pre-page totals, ascending SQL bounds, stable422/404/hints, list/detail agreement, unsafe stored metadata, no SQL writes/provider/body/repair. Offline service fixtures only. |
| D5 | Exact freeze/source-inventory, faults.json, error-fault-assertion.json, verification.json, current full suites/standing exports/readers, preservation and official final index/bundle/patch/readback | Current code qualifies against all original guards plus corrections; exact fault restoration, all22 standing contracts byte-exact, full ordinary fingerprints and usable restoration prerequisites. Independent QA alone supplies verdict/certification. |
| C1 | rejected-source-r1-r4.log four REDs; c1-green, expanded/restored-feature and complete/stored snapshot bypass faults | Edited actual inspect/select/install typed input, direct typed publication, real provider fixture and ORM, unsafe old stored metadata through list/detail/local ledger. Valid permissions/trigger/hash retention and no repair writes. |
| C2 | Nine mixed malformed/valid/legacy HTTP/ORM parameter cases, retained read cases, raw-json-filter fault | Typed version999, license/triggers/recommendations/verification/evidence types, bad JSON/list/null, mixed valid/unsupported legacy rows, exact filtered totals/pages/raw filters/unfiltered/detail truth and SQL bounds. |
| C3 |16 registered acquire/install combinations plus retained conflict/background guards; clear-omitted-identity fault | Acquire→install and repeated acquire/install, omitted/same/conflicting/previously absent AIR, same row/count/hash/measured facts and conflict rollback. |
| C4 |12 retained-note outcome cases, three new-row/retry cases and supplied-operation guard; overwrite/error faults | Exact whitespace/unknown fields/malformed/empty/null notes across success, real403 refusal and real empty synthetic key exception. Same-ID current status/error/code/message/hint and retry recovery. |
| C5 |105 restored feature cases; original four probes GREEN on corrected source under new labels; full current Backend/MCP; fresh93/73/412/12/19 standing checks; schema2; final package | All original histories and exact mirrors retained, no old green substituted, no test deletion/edit/relaxation/new skip, no registry addition/supersession. Exact-final independent review2 is next. |

## Current verification

[Command guide](correction-1-evidence/verification-commands.md), individual command
JSONs and [verification summary](correction-1-evidence/verification.json) record
actual argv/cwd/imports/roots/allowlisted environment/guard identities, fixtures,
failed attempts and results. Python3.11.15 venv references three existing dependency
sites read-only; no install into canonical environments. Every long pytest run
uses **--timeout=60**, unique run-owned scratch, no cache/bytecode and pinned
Backend/MCP child interpreters. .pth guard activation precedes all new tests and
denies private key/.env/non-scratch DB/model reads, remote DNS/network/live ports
and non-scratch writes. No private bytes, values/digests/length were read/emitted.
140 nested/top-level guard receipts include two separate deliberate activation
receipts; all ordinary test receipts have zero blocked events and pinned imports.
The repository's existing offline guard covers isolated -I/-S child fixtures.

| Current command label/scope | Result |
|---|---|
| rejected-source-r1-r4 / unchanged original QA probes | **4 failed**, expected-feature RED at exact rejected software; retained raw history |
| corrections-red-collected / new regressions before product changes | **23 failed,17 passed**, expected boundary failures |
| corrected-original-adverse / original probes on corrected source | **4 passed**, separate new evidence, no old file rewritten |
| restored-feature-assertion / final original+correction feature files | **105 passed**, after exact fault restoration |
| backend-full / backend/tests at final freeze | **2,083 passed,124 existing skips**,76 warnings,47.25s |
| mcp-full / mcp-server/tests at final freeze | **666 passed,four existing skips**,71.34s |
| export / fresh Backend producers | **93 passed** |
| cross-layer / separate MCP readers of fresh exports | **73 passed** |
| registry-mcp / standing MCP/PNG/stdio/smoke guards | **412 passed** |
| fresh-wait / fresh current Backend child and registered reader | **12 passed** |
| retained-provider-guards / unchanged prior credential guards | **19 passed**, Coding regressions rather than a new QA verdict |
| schema-audit / full migration plus exact pre-task schema authority | **2 passed**; full synthetic audit payload retained |
| scratch registry rebuild | All **22** prior rows byte-identical; no additions/deletions/supersession |
| source/restoration audit | All **2,889** frozen ordinary blob fingerprints; **420** protected source/test/helper bodies exact; final index covers every final blob |

The124 Backend skips require Windows; four MCP skips require optional explicit
exports, exercised separately above with20 current payloads retained. No new skip
or changed existing test;44 new cases add feature coverage. Existing deprecation
warnings remain. Frontend unchanged/unrun; native Windows unrun.

## Fault sensitivity

Faults ran sequentially in this isolated worktree, with no overlapping suite or
registry against mutant source. Every file restores exact bytes in finally.
Seven original faults give nine relevant failures; six correction faults give34
more, total43. The missing-error fault's focused explicit-assertion replacement
also gives eight failures and restores105 GREEN. No import/setup/fingerprint/SQL
error is counted as a feature-assertion sensitivity result.

| Fault | Relevant failures |
|---|---:|
| Wrong NoobAI map; fabricated verification |1;2|
| Bypass acquire; bypass install publication |1;1|
| Destructive backfill; unbounded list; writing list |1;2;1|
| Bypass complete normalization; bypass stored projection |2;1|
| Raw JSON family filter; clearing omitted identity |9;2|
| Overwrite retained notes |12|
| Drop current errors / focused explicit-assertion replacement |8 /8|

## Attempts, preservation and limits

- Initial correction test collection failed because a new fixture import omitted
  the tests package under pytest importlib mode. The preserved replacement reaches
  23 actual expected-feature failures. No product code preceded that collected RED.
- Initial c4-green was1 failed/13 passed: an existing idempotence test caught the
  new operation evidence being discarded by provider refresh. Shared publication
  now preserves that reserved state; all existing assertions remain unchanged.
- The first missing-error mutant observed None and raised TypeError at the intended
  error check. A post-fault checker required literal AssertionError and failed;
  its non-fail-fast shell still committed initial47eac3a. No mutant survived and
  history is not amended. An explicit dict assertion now produces eight observable
  assertion failures on that fault; restored105 and full suites use final42e6812.
  This failed checker and focused replacement are documented, not silently omitted.
- A few guessed source/reference names were absent; tracked rg inventory resolved
  the actual files. Those read errors are not test or product results. Logs retain
  normalized readable bodies and byte-exact deterministic-gzip raw bodies/hashes.
- Both old raw directories and mirrors match fixed source exactly; imported
  supplement bodies match2471ef8. No Producer status/placeholder topic is imported
  as product. Current source publication identifies no loaded Backend service.
- SQLite scalar validation is intentionally tied to the existing SQLite stack;
  filtered counts may scan matching rows, but ORM materialization is SQL-bounded.
  No new DB portability/performance certification or mutable read repair is claimed.
- The delta bundle/full-index patch requires exact published report base4b95c7a
  as an explicit seed ref and the existing shallow boundary
  b4e71d18ba4600ad7e053274b90b45ffdfbce87b. Use --update-shallow; it is not a
  standalone pre-boundary history backup. Uploaded-byte/readback/restoration/fsck
  and complete final source/payload identity are recorded in the native delivery
  receipt and official index/integrity artifact after the final commit is known.

**Offline:** current real source/ORM/registered HTTP/provider machinery with
synthetic wire/key/model/DB fixtures, faults/restoration, full suites and schema
checks. **Running service:** no production probe/start/restart/deploy/backfill.
**Provider/generation:** no actual owner key read, live provider, real model
acquisition/registration or generation. **Retrieval:** synthetic installed bytes
and official Paperclip attachments only; no live model/Gallery bytes.

History remains p2-02 kickoff1 CLEAR/delivery1 FAIL/fourP1s/one rejection/
correction1/next independent review2; p2-01 R1 FAIL/correction1/review2 PASS stays
separate. First check remains one bridged chain/20 interventions/77 overlapping
units/five missing earlier hashes. No complete Phase2 automation, three different
zero-fix sentences, fresh checkpoint+LoRA qualification, phase exit or CTY artistic
acceptance is inferred. Coding completes only its delivery card; QA independently
pins the exact final candidate and Producer owns findings/acceptance. Any later
product change requires another exact review. No self-delegation or parent/owner
status write.
