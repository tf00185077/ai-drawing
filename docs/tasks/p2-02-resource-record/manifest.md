# p2-02 Coding correction2 delivery

Coding [AID-190](/AID/issues/AID-190) delivers correction2 for independent
[QA AID-191](/AID/issues/AID-191) review3. [Producer AID-146](/AID/issues/AID-146)
owns findings and acceptance. This manifest records Coding observations; it is
not a self-PASS, merge, push, deployment or Phase 2 exit.

Fixed implementation base **5c6e9b4fcd9e1bf0adff89da8d93a5146e804953**,
tree **9c66e1c3b9fef0b61a5095641b1101b1b050be44**. Imported only the four
specified supplement bodies from **bd9d26d8004f741c2dc0e84053dbb2e196364c62**:
repair-round-2, resource decision, immutable manifest-correction-1 and review-round-2.
No Producer status wrapper or substitute resource topic was imported.

Task SHA256 `c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`;
repair1 `b3d649dcd8e60217b6581d1bdf8ca34db5f22ad0c71f5efd31c1449390b06977`;
repair2 `60cb4837543ebb729d9d256e725f0d9e4c7ba46e7cca3b8f933f9e84e9478b78`.
Original kickoff1 CLEAR remains; delivery1 and review2 FAIL are historical,
with two rejected deliveries and original R1 unresolved at dispatch. R2–R4
remain regression obligations. Old manifests/reports/raw directories are unchanged.

Final software/tests/replay-helper freeze:
**374c158b58332c9f49164a478961de5e9a7b871e**, tree
**a0067cd1cd498af3956bb1c06f90f106c687bc8c**. All current qualification below
follows exact restoration at this freeze. Initial fe1e07b and d4dedc8 attempts
remain in history. Subsequent commits contain reporting/evidence only.

The actual **FINAL full candidate SHA/tree** is in the official uploaded
`delivery-index.json` and this card's post-commit receipt. This avoids circular
self-hashing in the committed manifest. QA must pin that actual FINAL candidate,
not the freeze ancestor or a moving branch. The official manifest equals its
FINAL Git body; the final index fingerprints every ordinary FINAL blob.

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-190-resource-correction`;
branch `aid-190-p2-02-correction2`, with a dedicated ignored Python3.11.15 venv.
All commits carry the Paperclip co-author. Shared main, its13 memory edits,
retained worktrees/environments, private runtime/config/key/snapshots/backups and
model/dataset/output/Gallery data were not used as implementation inputs or changed.

## Change and limits

The shared `safe_text` normalizer now redacts the whole recognizable
credential-bearing string, rather than consuming one token and losing its label.
It handles Authorization/Proxy-Authorization schemes, later cookies, quoted and
unterminated multiword values, compound labels, embedded/multiple headers,
whitespace and delimiters. A bare Basic scheme is recognized when its decoded
value contains user:password, preserving ordinary “basic painting” text. Sensitive
keys are excluded before renaming, keeping repeated normalization idempotent.
URL userinfo/query/fragment exclusion remains; safe neighboring fields, typed
permissions/triggers/parameters/provenance and ordinary hashes remain useful.
The affected free-text string may lose benign content alongside credentials;
unlabelled arbitrary secret discovery is outside this contract.

Existing shared provider snapshot/publication/stored projection boundaries retain
this normalization. Retained inspect/select/install also normalize legacy descriptor
fields, and acquisition normalizes its generated license snapshot. Strict canonical
identity/locator validation runs on supplied input before descriptor normalization:
cleaning a forged locator must not convert refusal into acceptance. No new schema,
registry, dependency, job/budget/search/default/alias lifecycle or MCP intent.

Three application services change, one new product test adds117 cases, and the
[existing Backend topic](../../resource-records.md) is updated. Existing product
tests are untouched. All31 MCP names/risks,22 prior contracts, frozen recipe/AIR/
Anima behavior, identity omission/conflict checks and original-note preservation
remain. The original [legacy inventory](legacy-inventory.md) and AST caller inventory
remain source evidence, not a removal certificate. No large replacement is made.

## D1–D5, C1–C5 and S1–S5 evidence

Every item is test/P1; D5/C5/S5 also require delivery evidence and independent QA.
Paths below are in [correction-2-evidence/](correction-2-evidence/) unless specified.

| Item | Evidence and layer | Real boundary / substitutes |
|---|---|---|
| D1 | Original resource_records tests, new credential_values guards, current Backend; mapping/verification faults | Real ORM typed snapshots, exact four-label mapping, malformed/absent data and measured versus declared facts. Neighbor retention and repeated normalization. |
| D2 | Original writers/corrections plus new registered/provider guards; split-writer/identity/notes faults | Registered inspect/select/install/acquire/background, real Settings/resolver/provider machinery/strict schemas/ORM. Only external HTTP and scheduling substituted; synthetic paths/keys/bytes. |
| D3 | schema-audit-qualified.json/log/data, migration test and unchanged qa-evidence/test_baseline_schema.py | Whole16-table old-schema/value/sequence audit, eight resource rows and five alias/history tables; notes/files/IDs unchanged, startup/backfill repeat idempotently. Isolated fixture only. |
| D4 | Original reads/corrections plus48 new stored-read cases; bounds/write/filter/projection faults | Actual detail/list/local-ledger/SQL, canonical family counts and pagination, safe old storage with SQL writes/provider/body/backfill/publication denied and exact metadata/notes afterward. |
| D5 | freeze/source-inventory/fault-audit/preservation, current full/standing, official artifacts | Exact qualified source; complete ordinary fingerprints, all22 prior registry rows, restoration and independent review3 prerequisites. QA owns certification. |
| C1 | qualified-original-probes four pass; qualified-review2-probes14 pass;117 new product cases | Actual typed/shared/provider/wire/ORM/read paths, all nested fields/keys, safe ordinary data retained; historical REDs unchanged. |
| C2 | Existing nine mixed-validity HTTP cases and raw-json fault nine failures | Typed validity, version/nested/JSON/legacy cases, exact totals/pages/filter/detail truth and SQL bounds. |
| C3 | Existing16 registered writer combinations and clearing fault two failures | Omitted/same/augmenting/conflicting AIR, same resource ID/count/hash/measured evidence, no replacement row. |
| C4 | Existing12 retained-note outcome cases plus new-row/retry cases; overwrite/error faults12/eight failures | Success/refusal/credential-resolution exception, exact null/empty/malformed/whitespace/history notes and truthful same-ID status/error/recovery. |
| C5 | qualified-restored-feature222, full Backend/MCP and93/73/412/12/19 standing scopes | Fresh current evidence after restoration, no old suite substituted, no deleted/relaxed test/new skip/registry supersession. |
| S1 | credential_values direct/edited-install/provider guards,117 total; rejected review2 RED | Complete affected strings at actual provider inspect wire, select, install, admission/background and ORM commit/reload.20 forms with neighboring fields/hashes. |
| S2 |48 stored-read cases across12 nested fields/keys and four minimum forms | Detail/list/local-ledger, no entire-resource hiding, exact old metadata/notes, read-only SQL/provider/model-body denial; idempotence and canonical filtering. Direct publication compounds cover every nested area. |
| S3 | qualified-faults.json and fault-audit.json |18 effective invocations/17 distinct mutations/158 feature assertion failures: original13 retained, reviewed one-token production defect fails20 writer and36 stored-reader guards, descriptor and legacy-license faults fail20 each. Exact finally restoration before222 GREEN. |
| S4 | qualified full/standing/schema commands, registry-audit and preservation | Backend2200/124 existing skips; MCP666/four existing optional skips; fresh producers/readers/standing/wait/provider; all22 contracts and469 historical bodies exact. |
| S5 | FINAL index/manifest/delta bundle/full-index binary patch/evidence archive, prerequisite chunks and readback/restoration | Self-contained exact artifact access and ordinary fingerprints; complete current evidence/all attempts; independent QA pins FINAL and supplies actual review3. |

## Current qualification

[Replay guide](correction-2-evidence/verification-commands.md), individual command
JSONs/logs and [verification.json](correction-2-evidence/verification.json) record
exact argv/cwd/allowlisted environment/actual imports/roots/guard identities,
start/duration/exit and raw/saved hashes. Logs retain byte-exact deterministic
`.raw.log.gz`; readable `.log` only trims trailing whitespace.

The dedicated venv references three recorded dependency sites read-only; no
canonical installation. Guard activation preceded new tests and actually denied
private key/.env, non-scratch DB/model reads, remote DNS and repository writes.
Ordinary child receipts have zero blocked events and pinned source imports;
rejected replay pins archived old application source. Nested -I/-S children use
the established repository offline guard. Long suites use **--timeout=60**,
unique run-owned scratch, no cache/bytecode and pinned Backend/MCP interpreters.

| Current label | Actual result |
|---|---|
| qualified-restored-feature |222 passed after exact restoration |
| qualified-backend-full |**2200 passed,124 existing skips**,76 warnings,52.39s |
| qualified-mcp-full |**666 passed,four existing skips**,80.55s |
| qualified-original-probes |Four passed, original helper unchanged |
| qualified-review2-probes |14 passed, original helper unchanged |
| export-qualified / cross-layer-qualified |Fresh93 Backend producers /73 separate MCP readers |
| registry-mcp-qualified |412 standing MCP/PNG/stdio/smoke/content cases |
| fresh-wait-qualified / retained-provider-guards-qualified |12 /19 passed |
| schema-audit-qualified |Two passed, full synthetic audit payload retained |
| registry-audit |All22 prior rows exact; no additions/deletions/supersession |
| frozen source audit |All3271 ordinary frozen blobs fingerprinted;427 protected application/test/replay bodies exact, no ordinary path suppression |

The124 Backend skips require Windows; the four optional MCP exports are separately
exercised with fresh current producers/readers. No new skip or existing-test change.
Frontend unchanged/unrun; native Windows unrun. SQLite filtering retains its
existing scan/performance/portability limits; this is no database redesign.

## Attempts and preservation

- Rejected exact6fbcb246 replay first referenced a QA helper absent from that older
  candidate: pytest exit4/no tests. Preserved separately. The retry uses the
  unchanged later QA helper with actual archived app imports: **13 failed/one
  passed**, the expected historical feature REDs. No old probe/log was rewritten.
- New pre-product guards observed97 failed/20 passed. The first implementation
  observed115 passed/two failed: redacted-key second-pass removal and overbroad
  bare Basic recognition. Both corrected under the new assertions;117 pass.
- The initial optional descriptor fault passed20 because another normalizer still
  protected the tested select result. It is preserved and **not counted** as
  sensitivity. The stronger guard observes inspect wire before selection; a
  deliberate bypass of both inspect normalizers now fails20 assertions.
- The first full Backend at d4dedc8 observed2198 passed/two failed/124 skips: strict
  descriptor tests caught forged signed locators becoming accepted after early
  cleanup. Validation order is restored with all original assertions unchanged.
  Affected167 then pass. Current full/standing/fault/schema qualification is all
  repeated on final374c158; old green suites do not qualify it.
- Initial official package1546ecd restored the bundle and the final patch tree,
  but patch fsck failed because raw intermediate headers referenced absent trees.
  This packaging attempt and all its official uploads/index are preserved. The
  replacement adds every per-commit binary patch, rebuilding intermediate objects
  from the official base without importing the candidate bundle. This is a
  report/package correction; the qualified product/tests/replay helpers remain
  byte-exact at374c158. It adds no QA rejection or product-test skip.
- All18 current fault invocations fail on observable feature assertions, never
  setup/import/fingerprint/SQL errors. Original13 now yield42 failures; descriptor
  input normalization provides overlapping protection for one old bypass case.
  One-token writer/read faults yield56 and three additional publication bypasses60,
  total158. Exact source restores in finally and222 feature cases pass afterward.
- preservation.json compares469 historical evidence bodies, original mirrors,
  all four exact authorized imports, original task/repairs, unchanged existing
  tests/catalog/registry and13 shared-main memory bodies. No staging/stashing/reset
  or copying of shared edits. New evidence stays in correction-2-evidence.

## Official restoration and evidence levels

The official delivery index identifies FINAL commit/tree and every ordinary blob,
all payload hashes and exact attachment paths. Eight ordered official base-bundle
chunks reconstruct **66,109,399 bytes** and the exact published prerequisite
base5c6e9b4, including its declared **b4e71d18ba4600ad7e053274b90b45ffdfbce87b**
shallow boundary. All eight were downloaded, recombined, fetched in a new bare
store and checked with git fsck. This supplies the prerequisite bytes directly;
no external Git server or old workspace is needed. It is not a pre-boundary
history backup. Fetch uses --update-shallow and an explicit prerequisite ref.

The candidate delta bundle and full-index binary patch each restore FINAL from
that base in separate bare stores. The evidence archive includes every per-commit full-index binary patch and raw
commit body. Applying those patches in ancestry order reconstructs intermediate
trees/blobs as well as FINAL; raw headers then restore exact commit identities.
The single base-to-FINAL patch is independently checked against the same final
tree. Both trees/commits and fsck are checked. Official uploaded bytes/readback/restoration and final artifact
hashes are recorded in the native delivery/index/integrity receipt after FINAL
is known, avoiding circular committed hashes.

**Offline:** synthetic real Settings/resolver/provider request machinery, ORM,
registered HTTP/background, complete-value guards, faults/restoration, full suites,
migration and official artifact verification. **Running service:** none; no
production probe/start/restart/deployment/backfill. **Provider/generation:** no
actual owner key read, live provider request, model download/registration or
image generation. **Retrieval:** synthetic installed bytes and official Paperclip
attachments only; no live model/Gallery bytes. Historical live evidence stays
attributed to its original task, never presented as this correction's result.

Coding completes only this delivery card; QA independently pins FINAL and reviews
D1–D5/C1–C5/S1–S5, then Producer handles findings/acceptance. No self-delegation,
parent/owner status write, feature merge/push, routine owner gate, Phase2 automatic
flow/three zero-fix sentences/fresh checkpoint+LoRA/phase exit or artistic acceptance.
