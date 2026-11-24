# p1-05 Coding delivery 1

Technical candidate for independent [QA AID-172](/AID/issues/AID-172), delivered
on [Coding AID-171](/AID/issues/AID-171). **D4 is unchecked/pending Producer/CTY
owner-demo.** No QA verdict, whole-task acceptance, aesthetic judgment, feature
merge/push or Phase 2 activation is claimed.

Base: **`e540829376cc397b3dc509192643874fabad3459`**. Persistent branch/worktree:
`aid-171-mcp-png` at
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-171-mcp-png`.
Software frozen before qualification at
**`6bcb402ff8be2bea59c2dc3dbcd0de01c78ecab9`**. Subsequent changes are evidence and
status documents only. The final full candidate SHA is pinned by the external
integrity receipt/completion comment; a commit cannot embed its own SHA.

## Done when evidence

| Item | Check / level | Candidate evidence | Real boundary / fixtures |
|---|---|---|---|
| D1 — canonical bounded static PNG content | test + source inspection / P1 | [42 content cases](../../../mcp-server/tests/test_gallery_content.py), [actual SDK driver/stdio tests](../../../mcp-server/tests/test_smoke_driver.py), [final MCP suite](delivery-evidence/mcp-suite-final-software.txt), [fault/restoration](delivery-evidence/fault-restoration.json) | Real registered validation/wrappers, actual HTTP client and actual regular file/PNG decoder. Mock only HTTP transport or explicit storage/OS faults. SDK subprocess fixture uses actual product server and a test HTTP Backend; wire corruption wraps its real messages, never patches the driver or tool callable. |
| D2 — three real consecutive original/revision pairs | manual + independent evidence computation / P1 | [One invocation](delivery-evidence/real-invocation-1/summary.json), [full SDK messages](delivery-evidence/real-invocation-1/sdk-messages.jsonl), [full calls](delivery-evidence/real-invocation-1/calls.jsonl), [six PNGs](delivery-evidence/real-invocation-1/payloads/), [sampling/graph audit](delivery-evidence/post-result-audit.json), [canonical lineage/byte audit](delivery-evidence/lineage-payload-source-audit.json) | Actual source-bound Mac Backend/ComfyUI, real SDK stdio and actual MCP-returned bytes. Attempts 2–4 qualify; first timed-out attempt remains failed qualification with completed Backend job. New SDK process/session metadata reads and independent SQLite/ComfyUI graph/cache audit corroborate persistence/sampling. Initial audit probe limitation below is disclosed for QA. |
| D3 — no hidden retry/fix and complete accounting | test + manual / P1 | [17 actual CLI boundary cases](../../../mcp-server/tests/test_smoke_driver.py), [events](delivery-evidence/real-invocation-1/events.jsonl), [friction ledger](delivery-evidence/friction-ledger.json), [operator commands](delivery-evidence/operator-commands.jsonl) | Actual CLI + SDK + product MCP + HTTP/storage fixtures, with wire faults for metadata-only, invalid bytes/digest/length, wrong persisted parent/job/context, timeout/nonterminal/failure/cancellation, unknown admission, six-call unresolved stop, six-attempt exhaustion, reset and new-session audit failure. Real run: 28 attempt calls, one separate recovery, six SDK audit reads. |
| D4 — owner explicitly replies to reviewed demo | owner-demo / P1 | **Unchecked / pending Producer and CTY** | QA reviews D1–D3 at the exact final commit. Producer reads the actual verdict and presents that candidate's images/Gallery records. Only CTY's actual explicit reply can fill D4; a technical PASS/send receipt cannot. Separate roadmap phase-close review follows. |

## Delivered software and dependency contract

Only existing `gallery_get` gains `include_content: bool = false`; 31 intents and
literal Gallery `read` risk remain. Strict selector/boolean types reject coercion,
boolean IDs, missing/multiple selectors, image selectors for content, nonpositive
canonical IDs and unknown fields in the common envelope before access. Metadata
reads retain prior image/artifact/video/legacy projections and open no file.

Content fetches only the existing Backend canonical artifact route, verifies its
returned identity, requires image/image/png, and uses the configured actual host
Gallery root. Existing relative/URL/contained absolute mappings preserve nested
Unicode identity. A second host local locator must agree; the documented
`/data/gallery/<canonical-relative-path>` container locator is supported only
alongside the canonical relative mapping. No basename migration, arbitrary path,
URL fetch, new endpoint or record mutation is added.

The actual opened descriptor must identify the expected regular file under the
resolved root. Nonblocking open prevents FIFO hangs. OS handle paths use Darwin
F_GETPATH, Linux /proc/self/fd or Windows GetFinalPathNameByHandleW; unsupported
inspection fails closed. Tests swap an intermediate directory after locator
resolution, proving that a lexical/earlier resolve alone cannot pass.

One bounded read requests 2,097,153 bytes, enforcing 2,097,152 maximum. Pillow
checks PNG format/dimensions before full decode, one static frame, dimensions
1–2048 and at most 4,194,304 pixels, structural/CRC verification and full decoding.
Bytes are returned unchanged with exactly encoding/mime_type/byte_length/sha256/
width/height/base64. Backend errors keep their existing contract; other errors
use the three specified content codes, safe identity details and same-artifact
metadata/configuration guidance, with no partial content or job-state change.

Pillow is declared (`>=10,<13`), lock selects **12.2.0**, and MCP is bounded to
`>=1,<2`: the initially unconstrained requirement now resolved incompatible SDK
2.x. The isolated task environment uses **MCP 1.26.0**, matching the canonical SDK
version, and Pillow 12.2.0. Prior lock package versions are unchanged. Canonical
Backend/MCP venvs were not installed into or replaced. Full package versions and
import origins: [task environment](delivery-evidence/task-environment.json).

The driver under `scripts/` uses actual SDK stdio, complete JSON-RPC stream taps,
an exclusive output directory and append-only call/event capture. It validates
fixed parameters, source fingerprints, all received bytes and persisted lineage;
there is no filesystem/HTTP artifact fetch by the calling client. One generate
and one 50-second total-policy wait per image; at most six declared attempts and
six same-ID recovery waits per unresolved known job. Unknown admission stops.
A separate SDK session corroborates persistence. Exit zero means streak complete
**pending independent sampling audit**, not owner/phase acceptance. The disclosed
SDK response guard is 65 seconds; the calling application's limit remains
unverified and the tool's unchanged fallback stays 50 seconds.

## Verification commands and limits

All pytest commands use `--timeout=60` and isolated AI_DRAWING_TEST_ROOT below
run-owned TMPDIR. Exact argv/cwd/environment/UTC/durations/exits/output are in
paired `.json`/`.txt` receipts; early commands are additionally captured from the
actual [Paperclip command stream](delivery-evidence/operator-command-provenance.json).

| Check | Result / receipt |
|---|---|
| Baseline MCP registered/catalog subset after SDK environment correction | 161 passed; baseline-mcp-pinned.txt |
| Final restored full MCP: `.venv/bin/python -m pytest -c pytest.ini mcp-server/tests -q --timeout=60` | **663 passed, 4 existing optional export skips, one warning, 48.03s**, exit 0; mcp-suite-final-software.json/.txt |
| Full Backend using unchanged canonical Backend interpreter, explicit worktree PYTHONPATH and scratch timeout plugin | **1916 passed, 124 existing platform skips, 76 warnings, 42.30s**, exit 0; backend-suite-1.json/.txt |
| Focused final content/driver checks | **59 passed**, exit 0; affected-green-2.json/.txt |
| Fresh actual Backend revision HTTP/persistence export | **1 passed**, exit 0; backend-fresh-revision-export.json/.txt, revision-fresh-export.json |
| Revision and retained LoRA admission cross-layer consumers | **7 passed**, exit 0; retained-cross-layer-guards.json/.txt |
| Deliberate wrong canonical identity, removed opened-file checks, ignored driver digest | Each produces expected RED, exact source restored; final full MCP GREEN afterwards |
| Locked dependency consistency | `uv lock --check --project mcp-server`, exit 0; final-lock-check.txt |

Two of the full suite's four optional export skips subsequently execute in the
seven-case cross-layer check: fresh revision export, and the unchanged accepted
p1-04 lifecycle fixture. That is reused **test input**, not a reused test result;
LoRA Backend/source/test inputs are unchanged and the current real consumer runs
again in the recorded environment. The two smoke-export checks remain optional
skips as in the prior accepted delivery. No new skip, removed/changed existing
test, final failing/hanging feature test or registry certification is introduced.
All 16 standing registry rows are unchanged; only independent QA adds rows.
Existing warnings (HTTP status/Pydantic deprecations, SDK/Pydantic forward-reference
and pytest fixture-loop configuration warnings) are retained. No Frontend/build,
Windows execution, Discord send, training, download or worker dispatch is claimed.

## Runtime preparation and preservation

AID-151's original PID/config/source receipts were corroborated, not inferred
from current HEAD or health. Its private worktree/config remain unchanged.
ComfyUI's old process lacked an exact launch hash receipt. The controlled
replacement binds the actual current contracts and ComfyUI source, not a docs SHA.

Before stop, generation/Comfy queues were empty, trainer idle/current null/queue
empty, and no owner trainer subprocess. [Preservation receipt](delivery-evidence/runtime-preservation-before.json)
pins all old effective Settings, roots, private snapshots and complete database
schema/counts. Every old setting equals the candidate setting under the actual
process environment. Private environment/config/database and four prior ComfyUI
history entries are retained in canonical `data/backups/aid-171` (0700/0600), never
committed/uploaded. Models, datasets, outputs and Gallery records were not deleted.

[Controlled launch](delivery-evidence/runtime-relaunch.json): Backend PID **99953**,
canonical Backend Python, cwd this persistent worktree's `backend`, explicit
PYTHONPATH/PYTHONNOUSERSITE; ComfyUI PID **99952**, unchanged source
**`7597a5a0d59ee251674e6c1270049909c63e7ede`**, original executable/environment,
cwd `/Users/tf00185088/comfyui`. Both bind loopback as before. No long-lived
process depends on run scratch. Keep this worktree/private .env and canonical
venvs until a later controlled replacement; original AID-151 snapshots remain.

[Deployed audit](delivery-evidence/runtime-deployed-audit.json) records actual
processes, live schemas/status and equivalent-interpreter import origins. Complete
schema and every old value matched before qualification. [Post-result audit](delivery-evidence/post-result-audit.json)
confirms unchanged schema/all preexisting values afterwards; only seven new image
and seven canonical-artifact rows were added. No additive migration was required.
Effective DB/Gallery/output/model/training/authored roots remain those in the
preservation receipt, including canonical auto_draw.db and external-volume Gallery.

## The one real invocation

[Inputs](delivery-evidence/qualification-inputs.json) were declared before first
health, with all six request refs/twelve unique 48-bit seeds and their
`secrets.randbits(48)` origin. Hash:
`492d401602262101c8b560b1b34815e91ef141de58ca6607a698f3b559767595`.
Frozen source/packages/command: [frozen.json](delivery-evidence/real-invocation-1/frozen.json).
Illustrious/default, explicit local, loras=[], 512×512, batch 1, four steps, CFG 7,
Euler/normal, fixed seeds, empty negative prompt; original red-cup and revision
blue-cup prompts are retained verbatim. Four steps promise no speed or aesthetic
acceptance. No source/parameters/configuration changed during the invocation.

| Attempt | UTC start → end | Result / streak | Jobs / canonical artifacts |
|---|---|---|---|
| 1 | 16:05:34.293 → 16:06:29.734 | Nonqualifying timeout / 0; no revision submitted | Original a7f08f25-19a4-451d-a338-348ab23667e1; later completed, artifact 3865 retained |
| recovery | 16:06:29.76 → 16:06:59.220 | One same-ID read-only wait, 29.46s; terminal established | Same original only; no resubmit/cancel/target fallback |
| 2 | 16:06:59.245 → 16:07:16.106 | Qualifying / 1; exactly eight calls | 4c4dc74b… → 3d28d43f…; **3866 → 3867** |
| 3 | 16:07:16.106 → 16:07:28.856 | Qualifying / 2; exactly eight calls | 20149801… → dd44393c…; **3868 → 3869** |
| 4 | 16:07:28.857 → 16:07:46.162 | Qualifying / 3; exactly eight calls, then stop | c63f5036… → 75d34fd6…; **3870 → 3871** |

All dates above are **2026-11-24 UTC**. Attempts 5–6 were unused. The failed
attempt's wait returned timeout after 50.01s measured SDK duration with status
running; timeout did not prove job failure. All seven actual jobs are terminal.
[Complete stdout/command](delivery-evidence/real-qualification.json), its `.txt`,
SDK messages/calls/events and both session stderr files retain all results.

All six payload files are the decoded **MCP-returned** bytes, not an external
Gallery fetch. Each is static PNG 512×512, with exact byte lengths/digests:

| Pair | Original artifact / bytes / SHA-256 | Revision artifact / bytes / SHA-256 |
|---|---|---|
| 2 | 3866 / 209082 / 41dbf538f1dac67d25370114a44af81375301777d834d9e34caf4c47a9723b7e | 3867 / 324741 / 3b6c6cdcc7256ad2669383032318c998bd73f0ff6eb7bff3627aa8aab536778e |
| 3 | 3868 / 311390 / e36be93349ad608b282cac23b31167a80ccb3c272eac697bff2c553bffe425cc | 3869 / 264982 / 0794ec15662a294425d3770ed58400a92f85b3d03dcceb75ca38ca1321f94c2a |
| 4 | 3870 / 283312 / 570c398cd4ebeeadd3b380a01d0fb3a0210647172f554f2b72a610111eadb4cb | 3871 / 248206 / 9e14446bdc690b30300b95be749787b8236b74b6e753eec3e9205055d9a41971 |

The new SDK session agrees with all six persisted records. Independent image and
artifact DB rows agree on job/request/brief and canonical parent/job/request/brief
snapshots. Full IDs, image IDs (4451–4456, separate namespace), prompt IDs and
contexts are in lineage-payload-source-audit.json. Each canonical stored compiled
graph equals exactly one actual ComfyUI history graph; all seven samplers match
fresh declared seeds/four steps/CFG 7/Euler/normal, no active LoRA and 512×512 batch
1. KSampler nodes are absent from cached sets; successful execution messages and
4/4 runtime progress corroborate actual sampling. Raw histories, source graphs,
SQLite requested rows and HTTP audit responses are retained. No cache-only replay
is counted as a qualifying image.

## Failures, audit boundary and complete friction

All early failures are retained: incompatible initial SDK/collection; expected
feature REDs; wire-injector reset bug; malformed metadata/local conflict REDs;
the first insufficient mutation probe (independent second guard still protected
containment); wrong trainer URL 404; protected system-PID inspection failure; and
the real first-attempt timeout. None is an implementation delivery rejection.

The first **post-result** direct audit probe aborted because it expected absent
Backend INFO correlation lines. Seven status reads, three queue/trainer reads and
one log read had already occurred. Its outer command, UTC/error and exact
performed operations remain; intermediate response bodies were not saved.
One additional log inspection followed. This is a disclosed evidence limit, not
an omitted call or a repaired/requalified attempt. The completed independent audit
uses full canonical-graph equality with ComfyUI history, retains every raw HTTP
response and requested DB rows, and validates all sampling/persistence/source
checks. No product repair/input change or second qualification invocation occurred.
QA must assess this disclosure at the exact candidate; no self-certified QA PASS.

Original baseline stays **23 units/eight incidents**, F1–F8 =
**1,1,1,6,1,11,1,1**. Historical p1-00a remains one cached-original pair whose
client fetched bytes outside MCP. Earlier accepted feature/review histories and
limits stay separate. This task remains one kickoff ambiguity event/two P1
findings, clarification 1, round-2 CLEAR, **zero implementation delivery rejections**.

This round's conservative [ledger](delivery-evidence/friction-ledger.json) counts
**53 preparation + 0 attempt interventions + 1 recovery + 27 post-result audit =
81 total units**. All normal calls are still enumerated: 28 attempt calls,
one recovery wait, six new-session Gallery audit reads (zero intervention units
under the original rule), plus every outside-MCP audit operation. Preparation
includes diagnostics, failures, snapshots, Settings binding, runtime replacements
and source/import/schema checks; recovery does not rehabilitate attempt 1.
Only the three qualifying request-to-result pairs have zero fixes/retries.
**The whole round is not zero interventions, and its total is not below baseline.**

F1 dependency setup and F2 host/client binding remain explicit. F3 mixed parsing
is removed by the common envelope. F4/F5 source/schema preparation is evidenced,
not claimed to disappear through health. F6 repeated waits disappear inside the
three qualifying pairs but one failed attempt needs a separately counted repeat.
F7 execution diagnostics remain separate audit work. F8 actual bytes now arrive
through MCP; outside-MCP audits never substitute for their retrieval.

## Delivery and remaining authority

Official uploads on AID-171: this manifest; indexed source/evidence/all-six-payload
packet; exact binary/full-index patch (gzip, decompressed hash supplied); verified
prerequisite Git bundle; external integrity/readback receipt. The packet index
pins every member's bytes/hash/Git blob. Patch application and independent bundle
fetch reconstruct the exact final candidate tree. The external completion pins
full final SHA/base; the feature is not merged or pushed.

Verification boundaries: **offline** suites/faults above; **running services**
controlled source/import/config/schema binding; **real generation** seven actual
sampled jobs with a three-pair streak; **artifact retrieval** six actual decoded
MCP payloads and canonical persisted lineage. Independent QA and owner-demo remain
pending. Producer owns later acceptance, reviewed-image presentation and CTY reply.

No existing feature test was changed. Abandoned approaches: signature/header-only
PNG checks (insufficient full decode); path-only resolution (insufficient actual
open); scratch-launched services (nonpersistent); INFO-log-only prompt join
(unavailable logging). The implemented handle/decoder/SDK boundaries and complete
stored-graph join supply the required proof without a Backend redesign or new intent.
