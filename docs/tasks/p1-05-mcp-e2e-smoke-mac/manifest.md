# p1-05 correction 1 — Coding delivery 2

Technical candidate from [Coding AID-174](/AID/issues/AID-174) for native dependent
[QA AID-175](/AID/issues/AID-175). Independent delivery review 2 is pending.
**D4 is unchecked/pending Producer/CTY's explicit reply to the reviewed demo.**
No independent PASS, owner aesthetic decision, feature merge/push, whole-task
acceptance, phase closure or Phase 2 activation is claimed.

Implementation base: **75b7570e708fec5df0f99f507bf9b5d1d92ee327**. This report-only
QA descendant has identical product bytes to reviewed
**c22f2311c88c049fd66ddf60e913c4c0139d5d67**. Persistent branch/worktree:
`aid-174-interruption`,
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-174-interruption`.
Software freeze before qualification:
**76452a6134c8d1ec16aabcb51ccc88da49b754a8**. Later changes contain only reports,
audit helpers and evidence. The external integrity receipt and completion pin
the exact full final SHA/tree; a commit cannot contain its own SHA.

## Done when evidence

Original cleared task and clarification retain their exact hashes and authority.
Rows below describe Coding evidence, not independent certification.

| Original item | Check / level | Evidence | Boundary and fixtures |
|---|---|---|---|
| D1 — bounded canonical static PNG read | test + inspection / P1 | Complete restored MCP checks, output, unchanged content/security source and tests | Actual registration, SDK stdio, HTTP client, file containment/open and full PNG decoding. Lower HTTP/storage fixtures only for offline tests. Includes six retained independent QA content cases. Gallery implementation, Backend, risk labels and 31-intent catalog unchanged. |
| D2 — three consecutive real pairs | manual + independent evidence computation / P1 | Fresh invocation, calls, SDK messages, corroboration | Six actual Mac Backend/ComfyUI jobs; six MCP-returned static PNGs, persisted lineage, new-session reads and new distinct uncached KSampler histories. No synthetic generation substitutes. |
| D3 — strict interruption/reset/no-retry/accounting | test + manual / P1 | [Signal tests](../../../mcp-server/tests/test_smoke_interruption.py), RED, GREEN, fault/restoration, friction | Actual CLI subprocess receives SIGINT while actual SDK/product MCP awaits lower HTTP fixture response. Health, admitted wait and uncertain submit covered; no patched driver/tool/SDK callable. All earlier error/finite-budget/byte/lineage/recovery tests rerun. |
| D4 — explicit reviewed-demo reply | owner-demo / P1 | **Unchecked / pending Producer/CTY** | Producer presents the independently reviewed candidate's images and Gallery records. Only CTY's actual explicit reply satisfies this gate; later roadmap phase-close review is separate. |

| Correction item | Check / level | Candidate evidence / state |
|---|---|---|
| C1 — actual interruption RED, fix, restored GREEN | test / P1 | Three actual SIGINT cases fail on untouched base, then pass. Three deliberate production mutations each RED; final restored complete MCP GREEN. Full lower exchanges, sent/received SDK messages, calls/events/config/summary/stdout/stderr retained in `signals-red/`, `signals-green/`, `signals-restored/` and `fault-*/`. |
| C2 — compatibility and standing guards | test / P1 | Complete current Backend and MCP checks, fresh HTTP/persistence export and seven cross-layer checks pass. All 16 standing registry rows preserved. No reused Backend test result needs equivalence certification; full Backend rerun is fresh. |
| C3 — frozen fresh real evidence and accounting | manual / P1 | One invocation, attempts 1–3 qualifying, 24 attempt calls, zero recovery, six driver persistence audit reads. Separate fresh SDK six-content audit and Backend/ComfyUI/SQLite checks corroborate results. Preparation 22 + attempts 0 + recovery 0 + audits 14 = **36** units. |
| C4 — immutable technical handoff and review 2 | delivery + independent review / P1 | Coding delivers full source/evidence/PNG packet, binary/full-index patch, prerequisite bundle and full-readback integrity receipt. AID-175 is the existing recipient-owned native dependent review; it pins the actual final SHA after AID-174 completes. QA verdict is pending and belongs to QA. |

## Repair and reproduced failure

Before any product edit, the new regression sent SIGINT after one qualifying
fixture pair at attempt-2 health; it also interrupted an admitted original's
wait and a submit whose lower HTTP response was withheld. All three exited
nonzero without another submit, but retained streak 1, omitted the interrupted
call and omitted the active attempt's reason/end/count/streak/ending event.
The original 17 driver tests passed. This directly reproduces R5-1.

`Run.call` now catches cancellation at the actual await boundary, retains
arguments/start/end/duration/interruption, and re-raises it. It invents no result
or admission: SDK sent traffic is the evidence of transmission. Attempt
finalization is idempotent, records an ended event once, marks nonqualification,
resets streak and preserves explicit admission uncertainty. Cancellation is
re-raised past recovery/audits/next attempt. The outer interruption handler also
resets the invocation and completes any still-open attempt. Last actually
observed queued/running/terminal job status is retained instead of discarding
known admission as `unknown`; no timeout/interruption manufactures job failure.
The exclusive output directory cannot be resumed.

Only `scripts/mcp_smoke_mac.py`, its new signal test and `docs/mcp.md` change
behavior/documentation in this correction. No Gallery/Backend/interface/resource
change or large replacement. Existing tests are unchanged. Windows is not run;
the new POSIX SIGINT tests have a linked, explicit Windows-only skip because this
is the Mac signal boundary. No new macOS skip or weakened existing test.

## Offline verification

Every pytest receipt records actual argv, cwd, UTC, duration, exit and isolated
`AI_DRAWING_TEST_ROOT` below run-owned `TMPDIR`; all use `--timeout=60`.
Actual operator commands and full output
retain early failures and diagnostic work as well as successful commands.

| Check | Actual result |
|---|---|
| Unmodified-base driver checks | **17 passed**, 46.75s; `baseline-driver.json/.txt` |
| Before-fix actual CLI signals | **3 expected failures**, 12.47s; `signals-red.json/.txt` |
| After-fix actual CLI signals | **3 passed**, 12.33s; `signals-green.json/.txt` |
| Removed cancellation call capture; stale streak; discarded known queued state | Each targeted signal test **RED**; exact repaired source restored, `fault-restoration.json` |
| Complete restored MCP suite plus six retained independent content cases | **672 passed, 4 existing optional export skips**, 1 warning, 62.50s, exit 0; `mcp-restored-full.json/.txt` |
| Complete current Backend suite | **1916 passed, 124 existing platform skips**, 76 warnings, 42.64s, exit 0; `backend-full.json/.txt` |
| Fresh actual Backend revision HTTP/persistence export | **1 passed**, 0.50s; `fresh-revision-export.json/.txt`, `revision-fresh-export.json` |
| Revision and retained LoRA cross-layer consumers | **7 passed**, 0.18s; `cross-layer.json/.txt` |
| Dependency lock | `uv lock --check --project mcp-server`, exit 0; actual command/output in provenance |

The task-owned Python 3.11 venv pins MCP 1.26.0/Pillow 12.2.0 and prior QA package
versions; candidate imports use explicit PYTHONPATH, with no editable install.
Task environment and
requirements pin all packages.
The full Backend suite uses the unchanged canonical Backend interpreter, candidate
source imports and a run-owned copy of the timeout plugin, recorded in
Backend test environment.
Canonical environments are unchanged. The cross-layer tests consume a fresh
revision export and the retained accepted p1-04 LoRA lifecycle fixture; this is
reused unchanged test input, not a reused result. Two optional export checks are
therefore exercised separately; two old smoke exports remain optional skips.
Existing pytest/Pydantic/HTTP deprecation and forward-reference warnings remain.
No Frontend/build/Windows/worker/training result is claimed.

## Live runtime and preservation

Initial current-job/process check,
preflight,
Comfy supplement
and immediate idle/seed check
corroborate actual Backend PID **99953** and ComfyUI PID **99952**, their creation
times/executables/commands/cwd against the deployed launch receipts. Equivalent
interpreter probes under their actual environments corroborate import origins
and non-secret settings; this is not general in-process attestation. Source
fingerprints agree with the reviewed deployment, excluding the deliberately new
client driver. All 840 tracked ComfyUI fingerprints, source
`7597a5a0d59ee251674e6c1270049909c63e7ede`, private configuration and effective
roots agree. Live OpenAPI is unchanged; queues are empty and trainer idle.
No Backend/ComfyUI restart, config mutation, model/resource change or migration.

A private pre-qualification SQLite snapshot is retained at canonical
`data/backups/aid-174/before-qualification.sqlite3` (directory 0700, file 0600),
never uploaded. The audit compares complete schema and all pre-existing values:
unchanged, with exactly six new image and six canonical-artifact rows. AID-171
persistent runtime/private config/backups and AID-151 snapshots remain intact.
No models/datasets/outputs/Gallery records were removed.

## Fresh real invocation and retrieval

The twelve unique 48-bit seeds/six request references were declared once with
`secrets.randbits(48)`, checked against stored image seeds before qualification.
Input file SHA-256:
**5298bdb0cd115b04511a2ea85737b522ceb45e50dd84845743119a5396af1873**.
Frozen source/config/packages
identifies the freeze above. Fixed Illustrious/default/local/empty LoRA list,
512×512/batch 1/four steps/CFG 7/Euler/normal, original red and changed blue prompts
are unchanged. Actual client application limit is unverified; 50 seconds is the
tool fallback and 65 seconds the SDK guard, neither a performance guarantee.

| Attempt (2026-11-24 UTC) | Start → end | Result / streak | Original → revision |
|---|---|---|---|
| 1 | 16:57:28.571 → 16:57:45.531 | Qualifying / 1 | **3872 → 3873** |
| 2 | 16:57:45.531 → 16:57:58.330 | Qualifying / 2 | **3874 → 3875** |
| 3 | 16:57:58.330 → 16:58:15.132 | Qualifying / 3, then stop | **3876 → 3877** |

Attempts 4–6 are unused. Each pair has exactly eight calls, one submit and one
bounded wait per image; no timeout, retry, recovery, manual fix or external
product operation occurred during qualification. All six jobs are completed.
Full stdout/command,
its `.txt`, SDK messages, calls, events and session stderr retain the full run.
The post-result audit reconciles every SDK tools/call ID, arguments, result and
structured/text envelope, then reads the canonical rows/compiled graphs and
ComfyUI histories. Six new distinct prompt IDs, successful executions, fresh
seeds and uncached KSampler nodes establish new diffusion sampling; the retained
runtime log also contains four-step progress. Repeated progress lines are not
counted as independent jobs; the six distinct uncached histories establish that count.

All payload files contain actual decoded MCP-returned bytes, without host/HTTP
artifact fetches. Static PNG/full decode/dimensions/digests/lengths and parent/
job/request/brief fields agree with current canonical DB rows, the driver's new
session and a separate fresh audit SDK session. Image IDs are 4457–4462, a
separate namespace from canonical artifacts 3872–3877. Full job/prompt IDs,
canonical contexts and raw query/HTTP/SDK responses are retained in
post-result audit and
audit rows.

| Artifact | Bytes | Exact MCP byte SHA-256 |
|---|---:|---|
| 3872 | 351235 | 4003f62598dc963d18eb43888e524d10e9e10dcfca95be38e64034f77c4e0975 |
| 3873 | 249637 | 166edc70aea104468c7d256b3c954964ef5f86d7b181c4aba206050cfc2c28b2 |
| 3874 | 218504 | 83fee9ebb306b757529d04ac6fbe726c118dd205dcb72c8e3f839b358176e7b8 |
| 3875 | 245252 | 70c9e7c274d865db6aa5a471146fa4def2dac7d9cef97917036dcf6198ca1fe3 |
| 3876 | 238933 | 22ad62b2f81f3cdd616564865bb3b81261926fa70b7cea3cd6f59d9d3cde7ef1 |
| 3877 | 267709 | ab89a3b194702eeef4e8601e9eebba91035555b50c59f2f46df50b7c88fae907 |

## Accounting, history and delivery

Original baseline remains **23 units/eight incidents**, F1–F8 =
**1,1,1,6,1,11,1,1**. The old seven sampled jobs, three pairs/six PNGs and
**53 preparation + 0 attempts + 1 recovery + 27 audit = 81** units are historical
and never qualify this corrected software. New
ledger:
**22 preparation + 0 attempt interventions + 0 recovery + 14 audit = 36 units**.
Only qualifying request-to-result flows have zero interventions. The complete
round is nonzero and exceeds the original baseline; no whole-round improvement
is claimed. There are 24 normal attempt calls, six driver new-session metadata
reads and six separate new-session content audit reads. All are disclosed.
The audit receipt groups current DB and private-snapshot reads as one bundle;
the baseline ledger conservatively expands those two read-only connections to
two units (receipt bundles 13, baseline units 14). No call is omitted.

All preparation/failures/repair tests remain visible. Initial psutil use in the
old task venv failed before product access and is included in environment setup.
An initial protected-hash check overlooked QA's existing registry generated-date
change; corrected check proves 727 original bodies plus all original registry
rows unchanged, and registry bytes equal the required QA base. A separate bundle
verifier first imported the earlier e540 base; reading the actual QA bundle
header identified required c22f231, then successful independent import/fetch
proved f510's exact tree. A final report check also rejected an assumed exact log-line count: tqdm repeats
completion lines (26 matches). The report now uses distinct prompt histories as
the job count and treats log progress only as corroboration. These are retained
tool errors, with no new product read, fix, resubmission or qualification invocation. No abandoned repair design
or unresolved feature failure remains in the candidate; QA still decides.

History stays **one kickoff ambiguity event/two P1 findings; clarification 1 /
kickoff 2 CLEAR; delivery review 1 FAIL / first implementation rejection /
one P1 R5-1; correction 1 / delivery review 2 next**. Earlier task histories stay
separate. First manifest and FAIL
are byte-identical mirrors; old `delivery-evidence/` and `review-evidence/` remain
unchanged. `review.md` remains QA's earlier report until QA replaces its own
current report. Only the pinned Producer repair document was imported, with its
verified SHA-256. Original task/clarification/MCP-decision hashes and all 16
registry rows retain integrity; receipt.
The official first manifest/report and all 206 QA indexed payloads were fully
downloaded/read back against Git; receipt.

Official AID-174 delivery includes this manifest; full candidate source/evidence/
PNG indexed packet; exact base-to-final binary/full-index patch; prerequisite Git
bundle; six individual fresh PNGs; external hash/size/full-readback integrity
receipt. Patch application and independent bundle fetch reconstruct the exact
candidate tree. No feature push/merge. Native AID-175 performs exact-final-commit
review after Coding delivery, then Producer handles its actual verdict and CTY
reviewed-demo gate. No self-certified technical PASS or D4 substitution.

Verification boundaries: **offline** full suites/signals/faults/cross-layer checks;
**running service** unchanged actual process/source/import/settings/schema binding;
**real generation** six fresh uncached sampled jobs and three consecutive pairs;
**artifact retrieval** six actual MCP byte payloads and separate session/persistence
corroboration. This remains one Mac/checkpoint/template/static-PNG technical
candidate. Host Gallery access is required. Owner aesthetics, Windows execution,
review 2 verdict, whole-task/Phase-1 acceptance and phase close remain outside
Coding's delivered claims.
