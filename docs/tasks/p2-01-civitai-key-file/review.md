# p2-01 independent delivery review

Verdict: PASS
Review round: 2
Issue: [QA AID-184](/AID/issues/AID-184)
Coding correction: [AID-183](/AID/issues/AID-183)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed final candidate: **2e3850307f767ec2be213781accde367f321dc1d**
Reviewed tree: **7b082793fb75a45dfedb5f211ab54f46511775db**
Corrected software freeze: **2491ceb7555fe49e3f6a1261113a3e6398185743**,
tree **7bcadfb7b75568c7e5c7a2d12ad397f6040b422d**.
Correction base: **301c5dee6f35d5bad9fa0fe51799b24c56f35a5e**;
fixed specification supplement: **e2e6ee52022de188c003c0dcd056c649297d090c**.
The final report/evidence commit and tree are recorded in the native post-commit
receipt, avoiding a circular self-hash.

The corrected candidate satisfies D1–D5 within the checked scope. The accepted
round-1 R1/P1 cookie-channel defect is corrected: provider cookies are rejected,
and prepared requests strip Cookie/Proxy-Authorization and permit only the
Backend credential snapshot's canonical-origin Authorization. Independent faults
demonstrate that both outgoing isolation and cookie nonretention are guarded.
This is independent software review, not deployment or Phase 2 acceptance.

## Findings

No remaining demonstrated P0/P1 defect. **R1 is resolved at this exact candidate.**
The original [round-1 FAIL](review-round-1.md), manifest-round-1.md, evidence/,
review-evidence/ and all Coding correction-1-evidence/ bodies remain exact. The
two historical adverse tests still pass against the rejected provider while
reproducing the defect. They are never counted as current security guards.

## D1–D5 assessment

| Item | Level | Verdict | Independent evidence and limits |
|---|---|---|---|
| D1 | P1 | PASS | Actual Settings/environment/file resolver covers precedence, trim, rotation, immutable operation snapshots, legacy raw/Bearer, anonymous behavior and bad files including FIFO, unreadable, invalid UTF-8/control/header/JSON, empty and 64 KiB boundaries. Configured failures precede traffic without fallback. Precedence fault fails its guard. |
| D2 | P1 | PASS | Registered MCP → HTTP Backend → ORM admission → actual background execution → status/installed fixture bytes, duplicate admission and installed reuse pass. Retained inspect/select/install use the same real resolver/factories. File rotation and bad-file recovery retain existing IDs. No settings/credential/transport object is injected to make loading work. Only external HTTP and deterministic thread scheduling are fixtures; storage/DB are isolated. Registered cookie guards fail with the rejected boundary and replay fault. |
| D3 | P1 | PASS | Final outgoing requests exclude Cookie/Proxy-Authorization and keys outside permitted Authorization across canonical/same-origin/www/b2/return hops, domain/path/secure/host cookies, repeated metadata/download requests and implicit client headers. Clients retain no response cookies. Allowed fixture bytes, status and stream/client closure are observed. Existing URL denial, five-hop limit, finite phase/total deadlines, retry/backoff snapshots, slow drip/interruption, 401/403/429/network, redaction, scanning/hash/size/adoption/partial-file behavior pass. Six deliberate faults fail and restore. |
| D4 | P1 | PASS | Fresh post-correction Coding record audited; independent same-route bounded HEAD confirmation repeated on the final candidate. Anonymous 401 versus configured-file 307→200; no Cookie/Proxy-Authorization/key outside canonical Authorization, all responses closed, zero body-method calls. Complete 2,436 frozen and 2,494 candidate ordinary fingerprints verified, including actual loaded unwrapped request/policy identities. Private equality scans and static data-flow review passed. Source component only. |
| D5 | P1 | PASS | Exact manifest/topic docs, independent full current Backend/MCP and fresh producers/readers/wait/registry checks pass. All old tests/functions/skips and 18 registry contracts preserved; four additions below follow demonstrated fault sensitivity. Official artifacts and bundle reconstructed independently. No product repair, self-review by Coding, merge or parent acceptance claim. |

## Commands and results

Persistent worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-184-qa`,
branch `aid-184-exact-review`, created directly at the final candidate before
substantive review and pinned on this card. Shared main was never the test target.

The [runner](review-round-2-evidence/run_checks.py) records exact argv, cwd,
allowlisted environment, timestamps, raw/saved log hashes and inherited child
audit receipts. Invocation: `python3 -B docs/tasks/p2-01-civitai-key-file/review-round-2-evidence/run_checks.py <label> <paths>`.
Every pytest run has `--timeout=60`, no cache, unique scratch roots below
PAPERCLIP_RUN_SCRATCH_DIR and pinned QA Backend/MCP imports. A new ignored venv
references existing dependency sites read-only. Its explicit .pth hook blocks
private files, remote DNS/traffic, live service ports and non-scratch writes/DBs;
actual denial/dir_fd-cleanup probes are in guard-activation.json. Test receipts
record no blocked operations. Canonical environments were not modified.

| Label / command | Result |
|---|---|
| backend-full backend/tests | **1,978 passed, 124 existing platform skips**, 76 deprecation warnings, 47.53 s |
| mcp-full mcp-server/tests | **666 passed, four existing optional-export skips**, 74.87 s |
| independent-corrected | **19 passed**: two positive versions of the old adverse scenarios, nine retained safe checks, eight new metadata/download cookie nonretention cases |
| export | **93 passed**; fresh revision/multi-LoRA/lifecycle/health Backend exports |
| cross-layer | **73 passed**, separate MCP process consuming these fresh exports; no Backend modules imported |
| registry-mcp-restored | **412 passed**, named registry/independent PNG guards; fresh lifecycle export bound |
| fresh-wait | **12 passed**, fresh current-source Backend child export consumed by registered MCP wait in a separate interpreter |
| check_faults.py: old-adverse | **2 passed**, against exact rejected provider only; preserved adverse observations |
| check_faults.py: old-current-red | **17 failed**, expected: seven current Coding and ten independent positive cookie/header guards reject the old provider |
| fault-cookie-acceptance | **8 failed**, expected; disabling rejection alone retains cookies despite final stripping |
| fault-cookie-replay | **6 failed**, expected final outgoing Cookie failures, including both registered CDN variants |
| fault-prepared-headers / fault-header / fault-precedence / fault-total | **1 failed each**, expected implicit-header / Authorization / file-precedence / total-bound violations |
| restored-feature | **81 passed**: all 62 current feature cases plus 19 independent checks after exact restoration |
| audit_source.py, audit_artifacts.py, registry rebuild, git diff --check | Complete source/history/secrecy/artifact checks and registry structure pass |

Fault changes are confined to the isolated QA provider file and restored in
`finally`. Exact bytes match the candidate. Full suites preceded mutation; the
81-case affected run and final registry run follow restoration. Code, tests,
dependencies and environment inputs match the full-suite inputs, so those current
full results remain applicable. Evidence/report edits do not justify another
full suite. No old candidate's suite result substitutes for this candidate.

## Independent boundary and source evidence

[Positive guards](review-round-2-evidence/test_independent_boundary.py) observe
actual HTTPX-prepared requests and real response cookie handling below the
production resolver/factories. Both metadata and download modes retain permitted
Authorization on same-origin requests, strip it after changing origin, and do
not restore it on return hops. Separate new requests in an operation may send
their own permitted canonical Authorization. Every request has positive absence
assertions for Cookie/Proxy-Authorization. Cookie jars remain empty after real
Set-Cookie responses; replay stripping alone cannot satisfy that separate check.
Successful fixture streams and actual registered status/bytes are verified.

[Faults](review-round-2-evidence/faults.json) retain the exact rejected-provider
reproduction and six independent sensitivity results. The old provider yields
17 current failed guards. Current product code was never repaired by QA, and no
test/skip was deleted or changed in the product. Historical adverse assertions
were copied into a new QA area and converted to positive assertions there only.

[Source audit](review-round-2-evidence/source-audit.json) verifies the frozen
inventory against Git, every blob/SHA-256/byte count, complete final inventory,
task hash, original functions, catalog, fixed supplement mirrors, old evidence,
p2-00 and memory. Backend/MCP product and tests are identical from freeze to
candidate and after restoration. The cookie boundary is the only corrected
product module; no dependency, endpoint, job schema, identity or scheduler changed.

Coding's fresh D4 observer compares loaded resolver, deadline runner, **unwrapped**
request generator and rejecting policy code to compiled exact frozen source.
I audited that data flow and independently repeated the bounded manual check
using the actual configured-file resolver and request machinery on version
**1843039/file 1743033**. [QA live record](review-round-2-evidence/live.json):
anonymous HEAD **401**, keyed HEAD **307 → 200** to b2. No transport/key injection,
GET fallback or target change. The production download total stays 900 s; this
probe shortens it to 20 s with finite phase limits. No body method was called,
and every observed response closed. Private content/permissions were compared
in memory and stayed unchanged. No private value, digest or length was recorded.
This demonstrates the source component, not a deployed Backend or provider
cookie safety in general; adversarial cookie fixtures provide that guard.

Actual value and URL-encoded equality scans cover all candidate blobs, expanded
Coding payloads and new QA evidence. Static data-flow inspection confirms private
input is not hashed by the probes/verifiers. This does not claim detection of
arbitrary unknown derived encodings. Ordinary source/tokenizer hashes remain;
the First check's five missing historical hashes remain a historical limitation.

[Artifact audit](review-round-2-evidence/coding-artifact-audit.json) independently
downloads all **11** official Coding uploads, verifies advertised hashes/sizes,
and checks **237 ZIP members / 234 exact Git payloads**. Eight numbered bundle
parts reconstruct the declared complete source package. A new empty bare store
lacked the candidate, received the explicitly declared original shallow cutoff,
then verified/fetched the reconstructed bundle without external Git access.
Candidate SHA/tree, every one of its **2,494** blobs and the archive inventory
agree with the reviewed Git objects. Pre-cutoff history is not claimed.

## Notes and failed attempts

- The first new independent run had **1 failed / 18 passed**: its positive copy
  of a historical helper created an unused Stream for a JSON response and then
  asserted that unused object was closed. I moved allocation into the response
  branch that uses it. Cookie absence already passed; the corrected run gives
  19 passed. Only the new QA helper changed; old evidence remains exact.
- I incorrectly overlapped the first registry run with provider fault mutations.
  Its source-integrity smoke guards truthfully disqualified three cases as
  source changed (**409 passed / three failed**). The retained diagnosis records
  all three reasons and zero blocked guard events. Exact restoration followed by
  the same sequential registry run gives 412 passed. No product/test workaround.
- The first QA artifact audit stopped before bundle restoration with a Path
  subscript typo. Correcting path composition gives the recorded complete audit.
  [Attempt record](review-round-2-evidence/attempts.json) retains these outcomes.
- Coding's prior failed attempts remain in its unchanged correction evidence;
  its top-level unguarded results are not substituted for guarded verification.
  New QA raw logs remain in the persistent ignored venv; committed logs strip
  trailing whitespace, with both hashes in the command records.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | backend/tests/test_civitai_provider.py::test_file_precedence_trim_and_rotation_without_settings_patch; backend/tests/test_civitai_provider.py::test_configured_bad_file_fails_before_provider_traffic; backend/tests/test_civitai_provider.py::test_nested_metadata_snapshot_and_absolute_deadline | active |
| D2 | P1 | backend/tests/test_civitai_provider.py::test_registered_cookie_responses_install_without_replaying_credentials; backend/tests/test_civitai_provider.py::test_registered_mcp_admission_background_rotation_status_and_reuse; backend/tests/test_civitai_provider.py::test_retained_inspect_install_routes_use_private_file_and_preserve_identity | active |
| D3 | P1 | backend/tests/test_civitai_provider.py; docs/tasks/p2-01-civitai-key-file/review-round-2-evidence/test_independent_boundary.py | active |
| D5 | P1 | backend/tests and mcp-server/tests (full suites with --timeout=60 and isolated roots); backend/tests/test_civitai_provider.py (fault-sensitive feature regressions) | active |

D4 is manual evidence, not a permanent automated guard. All 18 existing rows
remain; four new test items give 22 active rows. No supersession is authorized or
recorded. Sensitivity evidence above precedes these certification additions.

## Limits and disposition

**Offline:** fresh macOS checks with synthetic isolated HTTP/DB/bytes. The same
124 Backend platform skips and four optional MCP export skips remain; applicable
revision/lifecycle readers run with fresh exports separately. Windows untested.
Frontend code is unchanged and its tests/build were not repeated.

**Running service:** no probe, restart, deployment or reconfiguration.
**Provider:** bounded source-component HEAD observations only.
**Generation:** none. **Retrieval:** official artifacts plus synthetic fixture
bytes; no live model body or Gallery bytes. Broad real rate-limit/Early Access/
cancellation behavior is not inferred from fixtures.

Shared main and its concurrent dirty memory files were untouched. Existing private
settings/key, snapshots, runtime/backups, canonical environments, prior worktrees
and models/datasets/outputs/Gallery records were preserved. No merge, push,
parent status/owner write, automatic phase exit, zero-fix chain or aesthetic
judgment occurred. This QA card completes with independent **PASS at the exact
candidate above**. Producer owns acceptance and integration; any later product
change requires a new exact-commit review.
