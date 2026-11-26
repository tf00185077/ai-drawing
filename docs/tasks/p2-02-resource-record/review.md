# p2-02 independent delivery review

Verdict: FAIL
Review round: 2
Issue: [QA AID-189](/AID/issues/AID-189)
Coding: [AID-188](/AID/issues/AID-188)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed FINAL candidate: **6fbcb24602e23d72363834cc9437a4a14f216386**.
Reviewed tree: **5a909f28dbd046b684b4528a4350ed5e5d943981**.
Software/tests/replay freeze: **42e6812e846754ea31f32573d4ef66a8af3f2d47**.
Fixed correction base: **4b95c7a74c032d092ac86b53b657bd107bdfcb3e**.
Task SHA256: `c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`.
Repair SHA256: `b3d649dcd8e60217b6581d1bdf8ca34db5f22ad0c71f5efd31c1449390b06977`.
The actual final SHA/tree was pinned on this card before substantive review
([receipt](review-round-2-evidence/pin-receipt.json)). This report's own commit/tree
is recorded in the official post-commit delivery to avoid a circular hash.

**One P1 remains: R1 complete snapshot secrecy is incomplete.** R2, R3 and R4
pass independent current checks. All four original probes fail on the exact
rejected software and pass on this correction, but additional independent
credential cases fail through real publication and public reads. Ordinary full
suites passing does not override those observations. Producer owns corrections
and acceptance; QA has made no product or product-test repair.

## Finding

### R1 remains / P1 / D1,D2,D4,C1: normalization leaves credential values behind

All line references identify the reviewed candidate. In
`backend/app/services/resource_records.py:40`, the new credential-text expression
consumes only one whitespace/comma/semicolon-delimited token after a credential
label (with an optional Bearer prefix). Consequently:

| Synthetic supplied text | Persisted/public remainder |
|---|---|
| `Authorization: Basic UUEyX1NZTlRIRVRJQ19PTkxZ` | `[redacted credential] UUEyX1NZTlRIRVRJQ19PTkxZ` |
| `Proxy-Authorization: Basic UUEyX1BST1hZX09OTFk=` | `[redacted credential] UUEyX1BST1hZX09OTFk=` |
| `Cookie: theme=light; session=QA2_SESSION_ONLY` | `[redacted credential]; session=QA2_SESSION_ONLY` |
| `api_key="QA2 TWO WORD SECRET"` | `[redacted credential] TWO WORD SECRET"` |

These are complete recognizable credential-bearing values, not arbitrary
unlabelled text. Repeated normalization cannot recover the removed label and
therefore retains the remainder. `normalize_metadata` at :55–62 applies this
partial transformation recursively. Registered install accepts it at
`civitai_resource_install.py:253`, shared publication at
`resource_records.py:148,167` persists it, and stored projection at :199 returns
it. The fix reaches the intended boundaries but does not enforce their full
secrecy contract.

Reproducer: [independent_probes_final.py](review-round-2-evidence/independent_probes_final.py).
Actual output: [independent-secrecy-final.log](review-round-2-evidence/independent-secrecy-final.log),
pytest exit1, **13 failed / one passed**. The initial nine-case observation and
its original helper/log remain separately preserved. The final probes:

- Obtain a real registered inspect/select descriptor, insert each synthetic value
  into `resource_metadata.license.values.file_license.description`, and call
  registered install. Install returns200. The actual ORM body and GET detail,
  list and retained local ledger all retain the respective marker. Legitimate
  ordinary hashes remain available; no whole-resource hiding explains the result.
- Persist unsafe old snapshots and request actual detail/list with SQL write
  denial. Basic credential values remain in license, diagnostic field, trigger,
  recommendation value, recommendation source_field, opaque evidence and raw
  base_model. Original metadata_json remains byte-exact; this is a disclosure
  through projection, not a read-time repair or provider request. A sensitive
  evidence dictionary key is successfully removed (the one passing case).
- Publish a validated typed snapshot through the actual shared writer and real
  ORM commit/reload: its nested Basic value persists. A synthetic external-HTTP
  provider metadata response also carries Basic text through real provider
  snapshot/registered inspect/select into the returned descriptor.

Expected: exclude complete credential values at publication and public projection,
while retaining safe metadata and ordinary hashes; safe rejection with a stable
failure and no publication would also satisfy the input boundary. Observed:
successful publication/reads retain the values above. This is an unresolved
application of original R1/C1, not a new owner requirement or four separate
findings. No real owner key was read/disclosed, and no live provider leakage is
asserted. These tests use only explicit synthetic strings and offline fixtures.

## Original findings and acceptance items

| Finding | Current independent result |
|---|---|
| R1 secrecy | Original signed/token URL probe now passes; complete normalization/storage bypass faults fail current guards. Broader credential probes above still FAIL, so R1 is unresolved. |
| R2 filter/projection | PASS in tested boundary: real HTTP mixed valid/invalid/legacy rows, bad version/nested/JSON cases, Unicode trim, exact base/family selection, filtered pre-pagination totals and SQL bounds agree with typed detail. Restoring raw-JSON selection fails nine guards. |
| R3 optional identity | PASS:16 real registered acquire/install combinations cover omitted/same/previously absent/conflicting AIR, preserved same ID/hash/measured facts, augmentation and rollback/no replacement row. Clearing assignment fails two cases. |
| R4 retry preservation | PASS:12 retained-note success/refusal/exception cases preserve null/empty/malformed/whitespace/unknown-history bodies exactly. Status and current code/message/hint remain truthful; three new-row/retry cases retain generated notes, same ID and error recovery. Notes-overwrite and error-loss faults fail12/eight cases. |

| Item | Level | Verdict | Independent evidence |
|---|---|---|---|
| D1 | P1 | FAIL | Real ORM mapping for all four labels and negative/malformed/absent inputs, typed metadata, selected provenance and declared/measured distinctions pass; remaining R1 violates complete secrecy. |
| D2 | P1 | FAIL | Both retained registered writers, real Settings/resolver/provider machinery/background/ORM, non-first version/file, duplicate/retry/status/ledger and R3/R4 pass. R1 persists/exposes credentials through those actual paths. |
| D3 | P1 | PASS within isolated migration boundary | Whole old-schema/value/alias-history/sequence/notes/file audit and independent exact-base schema authority pass; startup/backfill/repeat preserve old evidence and IDs. No production migration or new registry certification. |
| D4 | P1 | FAIL | Actual HTTP/OpenAPI/bounds/filters/counts/errors/read-only guards pass, including R2 correction. Unsafe stored snapshots still expose credential values through list/detail. |
| D5 | P1 | FAIL as delivery acceptance gate | Exact current source,13 effective faults/restoration,105 feature cases, full suites/standing contracts and both package restorations reproduced; independent RED cases demonstrate the remaining feature gap. |
| C1 | P1 | FAIL | Original URL cases pass, but the additional complete credential cases above fail at publication and old-storage public projection. |
| C2 | P1 | PASS | Mixed malformed-version/nested/JSON/legacy validity, unfiltered/detail truth, exact filtered totals/pages and SQL read/bounds guards pass; raw-JSON fault fails. |
| C3 | P1 | PASS | Omitted/same/conflicting/augmenting optional identity through real registered writers preserves known evidence; deliberate clearing fails. |
| C4 | P1 | PASS | Exact original notes, same-ID success/failure/exception, current errors and subsequent recovery pass; destructive/error-loss faults fail. |
| C5 | P1 | FAIL as delivery acceptance gate | Complete current qualification and historical preservation succeed, but C1 remains violated. No green-suite substitution or registry addition. |

No ambiguity or owner decision is needed to establish these results. Producer
handles the actual defect and another exact-final-commit review after any change.

## Independent commands and evidence

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-189-qa`;
branch `aid-189-exact-review`. All new evidence is in
[review-round-2-evidence/](review-round-2-evidence/).
[Replay guide](review-round-2-evidence/verification-commands.md) describes exact
setup, expected RED interpretation and restoration prerequisites. Each command
JSON records exact argv/cwd/allowlisted environment/start/duration/exit, actual
imports/roots/guard receipts and raw/saved log hashes. General invocation:

```bash
python3.11 -B docs/tasks/p2-02-resource-record/review-round-2-evidence/run_checks.py LABEL PATHS...
python3.11 -B docs/tasks/p2-02-resource-record/review-round-2-evidence/check_faults.py
python3.11 -B docs/tasks/p2-02-resource-record/review-round-2-evidence/run_standing.py
```

Independent RED invocations call run(...,expect=1), preserving pytest exit1;
the orchestration succeeding is not a passing feature. Every failed feature
observation remains outside ordinary product suites and is not a new skip or
certified passing guard.

| Label / scope | Actual result |
|---|---|
| rejected-r1-r4 | Four expected-feature failures on archived exact9abe3d1 source; old Backend import paths and source hashes recorded. |
| corrected-original-probes | Four passed on pinned corrected source; original probe/history untouched. |
| feature-before-faults |105 passed. |
| independent-secrecy-probes | Nine expected-feature failures; initial observation retained. |
| independent-secrecy-final |13 expected-feature failures / one passed; actual storage/public/read-only/direct/provider observations above. |
| faults |13 meaningful production mutants,43 intended assertion failures; every file restored exactly. |
| restored-feature |105 passed after fault restoration. |
| backend-full |**2,083 passed /124 existing skips**,76 warnings,45.99s. |
| mcp-full |**666 passed /four existing optional-export skips**,72.34s. |
| export / cross-layer | Fresh Backend producers93 passed; separate MCP readers73 passed. |
| registry-mcp |412 passed; standing MCP/PNG/stdio/smoke/independent-content guards. |
| fresh-wait |12 passed, fresh current Backend child and registered reader. |
| retained-provider-guards |19 passed, current credential/cookie/header/deadline/closure guards. |
| schema-audit | Two passed: full synthetic old-schema/value audit plus exact pre-task ORM schema authority. |
| source/restoration | All2,941 candidate blob fingerprints;420 protected product/test/replay bodies exact. No ordinary source-path suppression. |
| registry rebuild | All22 prior active rows exact; no additions, deletions or supersession. |

All long suites use per-test **--timeout=60** and independent scratch roots.
A fresh ignored Python3.11.15 environment uses existing dependency sites read-only;
no canonical dependency installation. Guard activation **preceded all new tests**
and actually denied private key/.env, non-scratch database/model reads,
repository writes and remote DNS. Ordinary child receipts contain zero blocked
events and pin imports to this worktree (the rejected replay pins archived old
source). Only the deliberate activation receipt has the six denied probes.
Isolated -I/-S children use the established repository offline guard. Current
fresh exports and nested receipts are retained, not old exports relabelled.
The source guard permits file stat; read/startup/backfill feature guards deny
model-body access. No unsafe private input was opened to prove these denials.

### Fault sensitivity

QA inspected and independently reran these production mutations sequentially,
with no suite/registry/source user overlapping a mutant. Each failure is an
observable feature assertion rather than setup, import, fingerprint or SQL error.
[faults.json](review-round-2-evidence/faults.json) records original/mutant/restored
hashes; [fault audit](review-round-2-evidence/fault-audit.json) checks exact recovery.

| Deliberate fault | Relevant failures |
|---|---:|
| NoobAI mapped to null |1|
| Fabricated verification without measured evidence |2|
| Acquire bypasses publication |1|
| Install bypasses publication |1|
| Backfill destroys notes |1|
| Remove SQL pagination |2|
| Write UPDATE during list |1|
| Bypass complete normalization |2|
| Bypass stored projection normalization |1|
| Raw-JSON family filter |9|
| Clear omitted identity |2|
| Overwrite retained notes |12|
| Lose current error dictionary |8|

Exact bytes restore in finally before105-case GREEN and full current suites.
These faults prove sensitivity of their guards; they do not certify complete
secrecy against the additional RED cases. No product/test repair, test deletion,
assertion relaxation, new skip or registry supersession was made by QA.

## Fixtures, preservation and delivery integrity

Real boundaries: Settings/environment-selected synthetic key-file resolver,
provider operation/request machinery, version/file selection, strict schemas,
SQLAlchemy/SQLite, shared publication/projection, registered HTTP/OpenAPI,
actual background targets and measured synthetic bytes. Substitutes: external
HTTPX wire responses and deterministic thread scheduling. Per-test DBs, tiny
model files, keys and paths live under scratch. Existing old unit-test fixtures
retain their documented limits. Current new adverse inputs are edited typed
snapshots, stored unsafe snapshots and synthetic provider metadata; they do not
manufacture production configuration success through a settings/key/domain
transport injection.

The full migration audit compares all16 tables including sqlite_sequence,
eight resource rows, five populated alias/history tables and their old columns,
values, notes, constraints, duplicates/conflicts/malformed/unsupported/offline
cases and synthetic file bytes. Normal startup adds only nullable metadata_json;
explicit backfill changes that field only and repeats idempotently. The schema
authority test loads exact pre-task models without application Settings and
normalizes only SQL line-ending whitespace. R4's distinct writer path is also
freshly tested; migration GREEN is not used as its substitute.

[preservation.json](review-round-2-evidence/preservation.json) confirms195 old
evidence/qa-evidence bodies, both first-round mirrors and all four authorized
supplement imports remain exact. All correction evidence remains untouched.
Only four application files and one added feature test differ from the fixed
correction base; no existing test is edited/deleted/skipped in correction1.
The original delivery's documented Illustrious fixture-source alignment and
its unchanged lock assertions remain attributed in the historical manifest.
All22 previous registry contracts pass through fresh producers/readers/full
suites; the registry builder's structural result is not treated as runtime proof.
This failed review certifies no new item. All31 MCP names/risks and frozen
recipe/AIR/Anima/alias behavior are unchanged. Legacy caller/removal inventories
remain source evidence, not proof of removability or new alias lifecycle work.

QA independently fetched **all five official Coding uploads** and checked exact
sizes/SHA256. [coding-integrity.json](review-round-2-evidence/coding-integrity.json)
records the independent manifest/Git comparison, **2,941** complete fingerprints,
**159 indexed payloads /160 archive members /157 exact Git bodies**, separate
restoration from the downloaded bundle and downloaded full-index patch, exact
commit/tree and both `git fsck --full` exit0. Restore requires published
base4b95c7a as an explicit prerequisite ref, --update-shallow and the declared
b4e71d18 shallow boundary. Prior official prerequisite handles are in Coding's
index; this is a delta, not a standalone pre-boundary history backup.

QA's report/evidence delta, exact report commit/tree, official artifact hashes,
sizes/readback and usable prerequisites are published in this card's post-commit
delivery. No feature source is pushed or merged. The shared-main13 memory-body
hashes remain unchanged; no staging/stashing/reset/copy of those edits occurred.
Private settings/key/runtime/snapshots/backups, canonical environments, retained
worktrees and all model/dataset/output/Gallery data remain preserved.

## Limits and disposition

**Offline:** exact source, real ORM/registered HTTP/provider machinery with
synthetic data, independent adverse/fault/restored/full tests, migration and
package verification. **Running service:** no production probe/start/restart,
deployment or backfill. **Provider/generation:** no real owner key read, live
provider request, model download/registration or generation. **Retrieval:**
synthetic installed bytes and official Paperclip attachments only; no live
model/Gallery bytes. Frontend unchanged/unrun; native Windows unrun. Existing
124 Backend skips are platform-specific; four MCP optional exports are separately
exercised by fresh producers/readers. No cancellation/job API is added here;
existing wait/interruption/PNG/stdio/smoke contracts pass, while live cancellation
and persistent download accounting remain later work.

History remains original kickoff1 CLEAR; delivery1 FAIL with four P1 findings
and one accepted rejection; correction1; **this independent delivery review2
FAIL with R1 incomplete**. R2–R4 resolution does not rewrite the earlier FAIL.
p2-01's separate R1 FAIL/correction1/review2 PASS and the First check's one bridged
chain/20 interventions/77 overlapping units/five missing historical hashes are
unchanged. No completed Phase2 automation, three zero-fix sentences, fresh
checkpoint+LoRA qualification, phase exit or CTY aesthetic acceptance is claimed.

QA completes its own card with this actual FAIL. Producer reads the actual report
and handles correction/acceptance; changed software needs another independent
exact-final-commit review. No parent/owner status write, external owner question,
routine gate, product repair, self-delegation or feature merge is performed.
