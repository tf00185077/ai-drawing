# p2-01 Coding correction 1 delivery

Coding [AID-183](/AID/issues/AID-183), coordinated by [Producer AID-146](/AID/issues/AID-146).
This is a delivery for independent review round 2, not a self-PASS, integration,
deployment or Phase 2 exit. The actual first [FAIL R1/P1/D3](review-round-1.md),
[old manifest](manifest-round-1.md), original evidence/ and review-evidence/ remain
exact. The historical adverse cookie tests still describe a defect; their green
results are not security certification.

Fixed base: **301c5dee6f35d5bad9fa0fe51799b24c56f35a5e**. Imported only the four
named repair/decision/mirror files from supplement
**e2e6ee52022de188c003c0dcd056c649297d090c**. Unchanged task hash:
`bd291da2897099b84fd743dcd384ea7812105ec96e74ad7501d76c9d28784850`.
Persistent worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-183-cookie-boundary`,
branch `aid-183-p2-01-cookie-boundary`; its ignored test environment is retained.

Corrected software is frozen at **2491ceb7555fe49e3f6a1261113a3e6398185743**,
tree **7bcadfb7b75568c7e5c7a2d12ad397f6040b422d**. Final candidate SHA/tree appear
in the native delivery receipt and uploaded artifact index, avoiding a circular
self-hash. Subsequent changes are this manifest and correction evidence, including
a test-guard supplement; Backend/MCP product/tests and live probe are unchanged.

## Change and scope

`civitai_provider.py` adds a rejecting CookieJar policy and enforces credential
channels after HTTPX build_request on every initial request and redirect. It
removes implicit/caller Cookie, Proxy-Authorization and Authorization, then adds
only the Backend snapshot's permitted Authorization. Cookies are neither accepted
from provider responses nor retained for replay. Canonical Authorization remains
available for same-origin requests and stays stripped through cross-origin return
hops. The correction adds no dependency, endpoint, registry or scheduler.

Seven positive feature cases observe final HTTPX wire requests: domain/path/secure
and host-only cookies, canonical same-origin → www → b2 → canonical return hops,
repeated requests in one operation, implicit client headers/cookies, and registered
MCP → Backend → ORM admission → actual background download → status/installed bytes
for both b2 and www. Only external HTTP is replaced; Settings, file resolver,
request/cookie preparation, registered routes, records and byte verification are
real. Scheduling is deferred for deterministic background execution as before.
All original feature functions/fixtures remain exact; no test deletion/new skip.

Only the shared provider boundary changed in product code. Existing URL validation,
five redirects, snapshot/rotation, deadlines/retries, closures, sanitized failures,
acquisition/resource IDs, scanning/hash/size/adoption/dedupe and partial-file behavior
are exercised by current original tests. The 31-intent catalog and all 18 existing
registry rows are unchanged. The credential guide documents the stateless policy;
the imported Producer decision remains verbatim.

## D1–D5 evidence for independent review

| Item | Check / level | Current evidence and layer | Real boundary / substitute |
|---|---|---|---|
| D1 | test / P1 | Original configuration cases in backend/tests/test_civitai_provider.py; guarded restored-feature and final Backend full; precedence fault | Real environment/Settings and synthetic local files; only OS denial fixture is simulated. No settings/key injection. |
| D2 | test / P1 | Original registered/inspect/install cases plus new registered cookie cases; final Backend full and guarded MCP | Real MCP/HTTP Backend/ORM/resolver/factories/background/status and synthetic file publication. Only external HTTP and thread scheduling are fixtures; DB/storage isolated. |
| D3 | test / P1 | guarded/old-boundary-red.log, guarded/restored-feature.log, guarded/faults.json and final Backend full | Exact old provider fails seven current wire guards; cookie replay fails six, implicit headers/header/precedence/total faults each fail one. Exact source restored in finally before GREEN. |
| D4 | manual / P1 | live.json, live_probe.py, freeze.json, source-inventory.json | Fresh bounded actual anonymous/configured-file HEAD on version 1843039/file 1743033 after product freeze. No transport/key injection. Loaded unwrapped request and policy code match compiled exact source. |
| D5 | test + delivery / P1 | This manifest; guarded current suites/exports/readers/registry; verification.json; uploaded full Git bundle/evidence/index/readback | Exact candidate and source fingerprints, preserved histories and existing contracts. Producer's dependent independent QA owns the verdict. |

Evidence links are relative to [correction-1-evidence/](correction-1-evidence/).
The [command guide](correction-1-evidence/verification-commands.md) explains
reproduction, harness provenance and failed attempts. The runner and observer
reuse prior QA tooling; their inherited descriptions do not make these Coding
checks an independent QA review.

## Current verification

All pytest commands use --timeout=60, unique PAPERCLIP_RUN_SCRATCH_DIR roots,
pinned worktree Backend/MCP imports, no cache and a dedicated venv referencing
existing dependency sites read-only. Explicit .pth loading installs the child
private-file/remote-DNS/network/write audit hook. Its active-denial probes and
per-child receipts are retained. The final Backend guard handles macOS dir_fd
cleanup correctly and records zero blocked events. Canonical environments were
not installed into or modified.

| Current guarded command label | Result |
|---|---|
| old-boundary-red | **7 failed**, expected final-wire cookie/implicit-header failures against exact rejected provider; 55 deselected |
| five actual production faults | Cookie replay **6 failed**; implicit prepared headers, Authorization leakage, file precedence and total bound **1 failed each**, expected |
| restored-feature | **62 passed** after all faults, source restored exactly |
| backend-full-dirfd backend/tests | **1,978 passed, 124 existing skips**, 76 deprecation warnings, 44.47 s |
| mcp-full mcp-server/tests | **666 passed, four existing optional export skips**, 73.61 s |
| export | **93 passed**, fresh Backend revision/multi-LoRA/lifecycle/health exports |
| cross-layer | **73 passed**, separate MCP reader process, current exports bound |
| registry-mcp | **412 passed**, separate MCP registry/PNG guards, current lifecycle export bound |
| fresh-wait | **12 passed**, fresh Backend exporter child and registered MCP consumers |
| scratch registry rebuild; audit_source.py; git diff --check | All 18 rows exact; histories/task/mirrors/source/secrecy verified; whitespace clean |

These are current changed-source results; old round-1 totals are not substituted.
Full suites were repeated because the existing registry includes them. Backend
health guards also run in full/93-case producers. Guard v2 changes only resolution
of relative dir_fd filesystem paths; prior guarded feature/fault/MCP/export results
remain applicable to unchanged product and unchanged credential/network policies.
No further full-suite repetition adds coverage after evidence-only edits.
Frontend is unchanged and was not retested. Windows was not exercised.

## Fresh bounded live source result

Anonymous HEAD returned **401**. Configured-file HEAD returned **307 → 200**,
canonical civitai.com → b2.civitai.com. Authorization was present only on the
canonical keyed request. Every final request had no Cookie/Proxy-Authorization,
no configured key in another header or URL; all responses closed. The profiler
observed no response body-method call; **zero model-body bytes read/saved**, no
GET fallback, registration, generation or target change. The probe shortened the
900-second production total to 20 seconds and retained finite phase limits.

The private regular file was read locally; in-memory content/permission comparison
confirmed preservation. No private value/digest/length was emitted or hashed.
Loaded resolver, deadline runner, unwrapped request generator and cookie policy
code objects equal compiled exact frozen source. Complete ordinary source
fingerprints cover **2,436 frozen tracked files**. The uploaded candidate inventory
also covers every final blob. This does not reconstruct p2-00's five missing
historical tokenizer hashes and does not identify a deployed Backend.

## Failed attempts, deviations and limits

- Initial cookie-red failed before collection because pytest-timeout was absent.
  Adding the existing AID-175 read-only dependency site resolved it.
- Top-level offline logs record real observations but lack this run's audit-hook
  receipts: Homebrew's sitecustomize shadowed the environment file. They are
  superseded for isolation claims by guarded/. The explicit .pth hook was tested
  with actual denied private-file and remote-DNS operations before rerunning exact
  old RED, all faults, restored feature, full suites and fresh exports/readers.
- First explicitly guarded Backend full: **4 failed, 1,974 passed, 124 skips**.
  The original guard treated shutil.rmtree relative dir_fd paths as repository
  paths. Correcting only that test harness permits scratch cleanup while denying
  non-scratch dir_fd writes/private reads; final full Backend is green above.
  No product/test change or skip masks the four harness failures.
- The first wait-export retention command found both pytest's current symlink and
  numbered path. Resolving them identifies one payload; the retry succeeded.
- New runner logs normalize trailing whitespace, retaining raw/saved hashes and
  diagnostic text. New pre-normalization byte copies are not separately retained.
  Original Coding/QA raw logs and worktrees remain untouched. Failed attempts and
  adverse historical assertions remain attributed, never rebranded as acceptance.
- No specification/interface deviation, broad refactor or abandoned product
  alternative. The two existing test edits already disclosed in round 1 remain
  historical; this correction changes none of those functions.

**Running service:** no probe, restart, deployment or reconfiguration.
**Generation:** none. **Retrieval:** synthetic fixture bytes and official delivery
attachment readback only; no live Gallery/model-body bytes. Broader provider
rate-limit/Early Access/cancellation behavior and Windows are unverified.
Shared main and concurrent memory edits, prior private snapshots/runtime/backups/
venvs and every model/dataset/output/Gallery record are preserved. No parent
owner/status write, merge or push. Producer reads independent exact review 2 and
owns acceptance/integration. Changed product source requires new exact review.
