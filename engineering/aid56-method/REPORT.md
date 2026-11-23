# Offline partial-budget diagnostic repair — aid58-partial-overflow-v1

Engineering deliverable complete; independent verdict belongs to [AID-59](/AID/issues/AID-59). This repairs the two original assertions for QA57-01 in [AID-57](/AID/issues/AID-57#document-qa-report). Offline utility remains conditional; actual full capacity and legacy runtime/client binding remain unavailable. `runtime_acceptance` is always false. No operation, deployment, rollback or third preflight is authorized or executed.

## Fixed source, custody and dirty inputs

- New branch/worktree: `aid-58-partial-overflow`, `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-58-partial-overflow`. Exact parent commit `200345773e20e60cd0fc455bb09f0f4a45708b32`, tree `19a4f967323e2e2c319b27692abe6f076d1f1d1f`; product ancestor `9b96655ea4994932854ea6028f25a58fe4a6302e`, tree `c85ed83a1ca941b964f3ecc04a81de41f8ff4cbc`. Final candidate commit/tree and complete changed-path bytes/SHA/numeric modes are bound in the archive-only `freeze.json` and native receipt, avoiding self-hash cycles.
- Actual [engineering input ZIP](/api/attachments/390e453d-308f-447c-85e9-7872cb45c450/content?download=1): 480239 bytes / SHA256 `4b6490ce395b1e468afa0f34940f7346a3b7c65e2b05883d7ad9a95895764c3b`. Actual [independent QA input ZIP](/api/attachments/f93d06d8-c250-432b-b1c6-628c77adc85b/content?download=1): 509987 bytes / SHA256 `ad3c10b3b194a003557038aaae1ae02873025924e31910212ffa2d1297a244ca`.
- Verified both downloads: CRC; 45/18 safe unique regular members; every 44/17 manifested payload's bytes, SHA and numeric archive mode; exact nested candidate equality. All 41 committed method files equal the fixed parent Git objects. Parent `method.py` SHA256 `db58e415f2b367ea75dbfb09273464a63ef162eff6c3b63c183e683cd6d6228c`. Original QA harness SHA256 `e6948cef4ad1e2aadf1adb0bc7719b443546c833d5444da8fa5da2cc11f76c0d`; copied unchanged to `controls/aid57_independent_checks.py`.
- Both exact original ZIPs are retained as `inputs/aid58-engineering.zip` and `inputs/aid58-qa.zip`; they preserve the original reports, controls, earlier logs and FAIL/conditional history. Source issue attachment lists verified their company/issue bindings. Direct attachment metadata GET was unavailable (404); this was a control-plane route limitation, not product HTTP or a failed payload verification. Input locators/native records are in `inputs/aid58-inputs.json`.
- Creation-time plan document `516a8a94-1291-4f8e-beb9-b9636605ff7f`, revision `f491910d-fcb1-402b-b4ae-0b07ee932d40`, was read back and retained in `inputs/aid58-plan.json`. Physically read all 12 required current authorities/memory files; read-only copies and original numeric fingerprints are separate from the frozen historical overlays. No missing/conflicting ref was identified. Producer alone curates shared memory; none was edited.
- Canonical dirty code was not copied, reset, normalized or adopted. Canonical HEAD at start was `da78a449d0aca575f8707f834774b9d1ec8a95f1`. Administrative Git worktree/ref creation is separate from product adoption. `evidence/aid58/preservation.json` records the bounded end comparison: HEAD and tracked porcelain matched, 11 authority fingerprints matched, while `docs/PROGRESS.md` changed during this run. Its new text records this repair and independent successor without expanding authority; it was read and retained as the later read-only overlay, not restored. The writer/cause was not independently established. A first comparison assertion detected this drift and stopped manifest assembly; assembly resumed only after documenting the distinct fingerprints. No preservation claim covers all 12 start fingerprints, and even matching fingerprints would not establish whole dirty-tree byte invariance. The previously reported public diff drift remains unexplained and is not relabeled as preserved or repaired.

## Diagnosed loss and minimal correction

The parent discards the logical sum whenever any logical term is missing. In a pool, a missing B/H/U poisons the allocation accumulator, so subsequent justified contributions are also discarded. Comparing only complete sums loses the promised partial-budget diagnostic. This is a low-severity diagnostic/document-contract defect, not false fit or demonstrated disk shortage.

`capacity()` now accumulates justified selected-budget contributions independently from completeness. No other function changes; no collector, framework, overhead constant or broader capability is added.

| Output | Meaning |
|---|---|
| `logical_known_budget_bytes` | Sum of justified selected logical terms, with P weighted twice, irrespective of other missing terms. |
| `pools[id].known_budget_bytes` | Sum of justified selected B/H/U contributions across every row of that pool, including terms before and after unknowns. |
| `pools[id].known_budget_threshold` | Exact integer `ceil(6 * known_budget_bytes / 5)` for that selected subtotal. |
| Existing `logical_bytes` | Complete logical budget; remains null if any logical term is missing. |
| Existing pool `allocation`, `threshold`, `fits` | Complete pool budget/comparison; allocation and threshold remain null if any row component is missing; fits also remains null if F is missing. |
| `missing` | All previous incompleteness obligations are retained and deduplicated; they are never removed because a subtotal exceeds. |

A known selected logical subtotal greater than cap, or a pool's known selected threshold greater than its supplied F, returns `exceeds` even when another term is unknown. Equality alone does not exceed. Otherwise missing inputs return `unknown`; `conditional_fit` still requires all existing completeness/proof preconditions, supplied physical scope and F. Shared-pool F is compared once per pool, distinct pools cannot borrow, and no release credit is invented. Exact integer comparisons are retained beyond 2^53 and 2^64.

These subtotals are lower bounds on the **selected budget expressions**, conditional on the supplied proof obligations. When B/H/U or other supplied terms are upper bounds, a subtotal is **not a lower bound on actual physical demand**. `exceeds` says this selected budget cannot satisfy the stated comparison; it does not prove actual disk shortage or impossibility under another justified plan. A zero selected subtotal can mean no justified term exists; it does not assign zero to unknown terms or certify an empty scope. Evidence strings do not authenticate their producer or establish truth/completeness/custody.

The unchanged Bound contract accepts only nonnegative integer bytes, an eligible basis (`complete_manifest`, `enforced_limit`, `derived`) and a nonempty evidence locator. Named-only, estimates, page-rounded inputs, missing proof and null remain unknown. Negative/bool/float/string byte values remain rejected. The full original P/link, full post-DB and companions, closed-startup, aggregate M, physical-pool/H/U, discovery and loaded-binding proof conditions remain as documented in the retained original engineering report; this repair supplies none of those real inputs.

## Original counterexamples, preserved unknowns

1. P=100, D_B unknown, D_S=7, M=5, cap=199, physical zero/F=0: selected logical subtotal **212**, state `exceeds`; complete `logical_bytes=null`, `missing=[D_B]`, `runtime_acceptance=false`.
2. B=100, H unknown, U=0, F=119; complete logical69/cap69: selected pool subtotal **100**, selected threshold **120**, state `exceeds`; complete allocation/threshold/fit all null, `missing=[one:H]`, `runtime_acceptance=false`.

`evidence/aid58/counterexamples.json` records actual guarded evaluation of these exact fixtures. At selected-subtotal equality with an unknown term, state remains unknown. Existing retained real-value projection remains unknown, with complete logical/physical totals null; its new known-budget fields are zero because those retained estimates/named-only terms do not qualify. No real P, D_B, D_S, M, H/U, fresh F or legacy binding gap is filled.

## Actual verification, without overlapping PASS totals

Existing macOS Python 3.9.6, `python3 -I -S`, stdlib only. No repository pytest, conftest, product imports or dependency install. The original independent harness and new regression harness each installed the guard and passed seven synthetic denial probes **before** evaluating candidate code. The original method runner is unchanged; its four denial checks occur after method loading and are reported with that limitation. These audit hooks constrain these harnesses, not arbitrary hostile Python at OS level.

| Suite/evidence | Exact parent | Repaired candidate |
|---|---|---|
| Unchanged original independent suite | exit1; 28 tests, 26 PASS / 2 assertion FAIL / 0 errors | exit0; 28 tests / 0 failures / 0 errors |
| Six direct subtotal/order/pool regressions | exit1; 6 assertion failures / 0 errors | exit0; 6 tests / 0 failures / 0 errors |
| Existing method controls | Reused fixed original identity; no extra baseline rerun | exit0; 24 controls; three interpretation mutations killed; four guard denials; 14 retained payload hashes verified |

The two original QA assertions are the actual diagnosed parent reproductions, unchanged RED→GREEN. Of the six new parent failures, five expose missing partial classification and one exposes the newly specified subtotal output field; they are not six independent live defects. Historical stub errors and mutation kills are not counted as defect reproductions. Suite scopes overlap; there is no summed PASS count. The original independent suite includes its unchanged Fraction oracle and existing full-total boundaries; they are replay evidence, not new independent engineering tests.

New regressions exercise a missing first/middle/last logical term, every missing B/H/U position, all six permutations of three repeated shared-pool rows, distinct partial pools and missing F, ineligible huge terms, equality/one-byte boundaries and large partial integers. Literal expected values are independent of method helpers. Rejected estimates cannot enter selected subtotals; unknowns cannot produce fit. Raw RED/GREEN logs and commands are retained under `evidence/aid58/`. The exact source was reviewed with `git diff --check`; no whitespace errors were found.

Portable replay from the extracted method directory:

```sh
python3 -I -S run_controls.py
python3 -I -S controls/aid57_independent_checks.py .
python3 -I -S run_regressions.py
```

The native freeze receipt records replay from the actual completed ZIP, manifest/CRC/mode checks, archive-to-Git comparison and clean branch state. `freeze.json` lists every changed Git path with bytes/SHA256/numeric mode and exact parent/commit/tree. `artifact-manifest.json` binds every committed method payload except itself. The archive-only `delivery-manifest.json` binds every archive payload except itself, including `freeze.json` and the source manifest; neither commit nor report claims its own archive hash. Later source changes require a new candidate and verification.

## Limits, handoff and next owner

Effective roots/companions/callers, actual full post-DB bounds/schema/writer caps, exact startup write-set, enforced aggregate M, reliable physical metadata/transient bounds, fresh F/pool mapping and old loaded source/settings/client bindings remain unavailable. Producer routes any future narrowly authorized evidence work to Environment; unsupported old exports remain unavailable and may require a separately reviewed transition/protection decision. The locator's original exit2 cause remains unknown. Both [AID-55](/AID/issues/AID-55) partials and the original reports retain their actual outcome. Fixed source kit `aid52-source-kit-v1` / controls `143e04fcd1c53a28ed9807cd1c512dd00f59a36634c96e3713a8750fdd1ba049` and prior source/kit QA are reused by identity, not rerun for additional PASS claims.

No private config/DB/assets, product process/env query, product HTTP/MCP/CLI, service/backup/schema/startup/source adoption, generation/training, resource download/install/spend, remote or Windows operation occurred. Control-plane evidence GET/document/comment/artifact upload and isolated Git/file work are the separately authorized task work. Shared memory, canonical product, dirty work and prior frozen candidates are preserved without a whole-tree invariance claim.

Engineering disposition: **done / frozen source-only repair, conditional offline utility; runtime proof unavailable**. The already-created [AID-59](/AID/issues/AID-59) has a first-class dependency on this delivery and owns independent retest/verdict on its own ticket. Producer continues from [AID-4](/AID/issues/AID-4); engineering does not self-approve technical acceptance. No new dispatcher, poller, liaison, monitor or owner start confirmation is needed. Deployment/rollback execution remains a separate authorized Environment operation; this unadopted offline method has no product data to roll back.

**Memory candidates:** A justified selected-plan subtotal can diagnose budget exceed despite missing terms without completing the total; when supplied terms are upper bounds, that subtotal is not an actual physical-demand lower bound. Evidence: the unchanged two QA57-01 assertions RED→GREEN, new order/shared-pool regressions, and frozen `method.py`/report. Reuse when describing partial capacity diagnostics; no shortage/runtime-acceptance inference. Producer alone decides memory curation.
