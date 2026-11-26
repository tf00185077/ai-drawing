# p2-01 independent delivery review

Verdict: FAIL
Review round: 1
Issue: [QA AID-182](/AID/issues/AID-182)
Coding: [AID-181](/AID/issues/AID-181)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed final candidate: **160681d140879ba57ccb8a45bdaae07ca193de6f**
Reviewed tree: **97f0b476be2ce9baa86571ca8e662d6ba1669630**
Frozen software/live inputs: **8a77b9079ed4d60c9a7784713cc3525def3fdadf**,
tree **82ef1bb63cce947d378ee9cc4f84d016ba8233f5**.
Baseline: **b49bdc6695277b4c53ab50b973abbbd79a415316**.
The report/evidence commit and tree are recorded in this card's post-commit
delivery receipt, avoiding a circular self-hash.

The candidate fails the credential boundary because HTTPX's cookie jar can send
a credential from a canonical-origin response to the allowed CDN. All existing
product suites passed; they do not guard this path. This is one demonstrated P1
delivery finding, not a change to the cleared specification or an owner question.

## Findings

**R1 — P1, D3: provider cookies bypass the cross-origin credential boundary.**
`backend/app/services/civitai_provider.py:203` removes caller-supplied Cookie and
Authorization, but line 204 creates an ordinary cookie-accepting AsyncClient.
After a canonical response sets `session=<credential>; Domain=.civitai.com;
Path=/; Secure` and redirects to `https://b2.civitai.com/file`, line 212's
`client.build_request` adds that cookie from the jar. The `send_auth` check only
controls Authorization. The next request has no Authorization but does contain
the credential in Cookie, contrary to the task's requirement that credentials
go only in Authorization to canonical HTTPS civitai.com.

I reproduced this with a synthetic configured-file value, real Settings/resolver,
HTTPX factory/request/cookie machinery and an isolated external HTTP fixture.
The first independent guard failed with the CDN request containing
`cookie: session=qa-file-sentinel`; nine other checks passed. The same behavior
also reproduces through registered `civitai_resource_acquire`, the actual Backend
route, ORM admission, background `_run`/`_run_one`, streaming byte verification and
status retrieval. That path installs the fixture bytes and reports installed
while sending `session=qa-registered-sentinel` to b2. No credential, transport or
settings object was injected to make file loading work.

This is a fixture demonstration of the isolation failure. It does **not** claim
that the real provider currently sets a cookie containing CTY's key: the separate
live comparison observed no request Cookie at all. A canonical provider response
or future provider authentication cookie can exercise the production defect.
The security policy must prevent cookie replay across these hops, including
return hops, and a meaningful guard must observe the final outgoing request.
Coding owns the repair; this review makes no product-code correction.

Reproduction: [initial failed guard](review-evidence/independent.log),
[independent boundary checks](review-evidence/test_independent_boundary.py),
[restored checks](review-evidence/restored-feature.log). The two final cookie
tests explicitly assert that the defect reproduces; their green result is an
adverse observation, not certification that the boundary is safe.

## D1–D5 assessment

| Item | Level | Verdict | Independent evidence and scope |
|---|---|---|---|
| D1 | P1 | PASS | File precedence/trim/rotation, one metadata/download snapshot, all declared bad-file cases including FIFO/unreadable/64 KiB, legacy raw/Bearer and anonymous behavior pass. File-precedence mutation fails. A key rotated to empty after admission fails the existing acquisition ID before download traffic, with the stable setting-specific hint. |
| D2 | P1 | PASS | Registered MCP admission/status/reuse and retained inspect/select/install routes exercise the real resolver/factories, isolated HTTP/DB and real byte publication. Existing acquisition/resource identities, 31 catalog names/risks and common envelopes survive. This is the production-wiring result; R1 separately prevents D3 acceptance. |
| D3 | P1 | FAIL | R1 permits cookie-carried credentials on the CDN request. Original-origin Authorization, stripping that header, host/scheme/port/userinfo denial, five-hop limit, finite phase reads, nested/retry/backoff/slow-drip totals, refusal/network/status sanitization and closure otherwise pass. Three required mutations independently fail and restore. |
| D4 | P1 | PASS | All 2,298 declared frozen fingerprints match Git; software is unchanged in the final candidate. Original anonymous/keyed source evidence and six official uploads were audited. QA's separately justified same-route HEAD comparison records 401 versus 307→200, no request cookies/proxy authorization/key outside Authorization, closed responses and zero model-body access. This is a source component result only. |
| D5 | P1 | PASS | Exact manifest/current topic docs, independent full Backend/MCP, fresh cross-layer exports/readers and all 18 existing registry contracts checked. No product test deletion/new skips/registry supersession. Independent review is complete with the adverse D3 verdict; integration and Phase 2 acceptance remain Producer's work. |

The required obsolete `follow_redirects is True` assertion was replaced with
actual 307→b2 bytes and closure observations. The adjacent metadata fake moved
below AsyncClient while retaining authoritative model policy selection. These
are the only changed existing tests; all 26 original test names remain. I found
no undocumented removal or new product skip.

## Commands and results

Persistent QA worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-182-qa`, branch
`aid-182-exact-review`, created directly at the final candidate before substantive
review. No moving shared source or Coding worktree was used as the review target.

Each [runner](review-evidence/run_checks.py) record contains exact argv,
environment, cwd, timestamps, log hashes and child guard receipts. Commands have
the form `python3 -B docs/tasks/p2-01-civitai-key-file/review-evidence/run_checks.py
<label> <test paths>`. Every pytest run uses `--timeout=60`, unique scratch roots,
pinned QA Backend/MCP imports and a child-inherited private-file/network/write
[guard](review-evidence/offline_guard.py). The ignored QA venv references existing
dependency sites read-only; canonical environments were not installed into.

| Check | Result |
|---|---|
| `backend-full backend/tests` | **1,971 passed, 124 existing platform skips**, 76 deprecation warnings, 44.98 s |
| `mcp-full mcp-server/tests` | **666 passed, four existing optional export skips**, 64.51 s |
| `export` — revision/multi-LoRA/lifecycle/health Backend producers | **93 passed**; fresh exports produced in scratch and sanitized copies retained in review evidence |
| `cross-layer` — independent revision/multi-LoRA/lifecycle/health MCP readers | **73 passed**, fresh exports explicitly bound; no Backend modules imported |
| `registry-mcp` — named MCP registry guards plus independent PNG cases | **412 passed**, with lifecycle export enabled; Backend health guards also passed in full/93-case producer runs |
| `fresh-wait` — current source Backend route exporter in child, registered MCP reader in separate interpreter | **12 passed** across generation, training, cancellation/failure, legacy/mixed/unavailable artifact cases |
| `check_faults.py` | Header leakage, file-precedence bypass and removed total bound each produce **one failed guard**; exact candidate bytes restored in `finally` |
| `restored-feature` | **66 passed**: 55 Coding cases, nine additional safe-boundary cases and two explicit adverse R1 reproducers |
| `audit_source.py`, official bundle/payload audit, registry build and `git diff --check` | Source/task/history/fingerprints/secrecy and existing 18-row contracts verified; no registry certification added on FAIL |

The full suites ran before mutation. After all faults, the provider bytes match
the exact candidate and all affected feature/independent checks passed; later
cross-layer/registry runs used restored source. Repeating unchanged full suites
would add no coverage to the demonstrated missing cookie guard. Their recorded
results apply to the same product/test/dependency inputs. No p2-00 suite result
is substituted for this candidate's checks.

One initial registry invocation combined Backend and MCP tests in one process.
It produced **427 passed/one failed** because the now-enabled lifecycle reader
asserts that no `app.*` module was imported. Separating the MCP run restores that
intended isolation and gives 412 passed; no product/test change or skip masks it.
The initial guard's expected R1 failure remains recorded. QA's first live-gap
helper stopped before ProviderOperation/network because marshal serialization
was compared rather than code-object equality; the offline diagnostic confirmed
equal loaded code, the QA-only assertion was corrected and the bounded probe then
ran. The artifact audit initially assumed raw-log archive names were Git paths;
the corrected audit verifies all 15 declared whitespace-normalized pairs.

## Source, live evidence and secrecy

[Source audit](review-evidence/source-audit.json) independently checks completeness
of the frozen inventory against `git ls-tree`, every ordinary SHA-256/size/blob,
all **2,317** final-candidate blobs, unchanged task/p2-00/memory and unchanged
software since freeze. The [QA inventory](review-evidence/source-inventory.json)
retains ordinary source/tokenizer hashes. Current hashes do not reconstruct the
First check's five missing historical tokenizer fingerprints.

Coding's D4 profiler hashed the contextmanager helper for the decorated request,
not its underlying generator. File hashes plus resolver/run identities still
support the recorded source; QA's [separate gap probe](review-evidence/live-gap.json)
also verifies actual loaded, unwrapped request code against compiled exact source.
No production code changed for that observation.

The new read was warranted because the original D4 record observed Authorization
presence but omitted Cookie presence, leaving the newly demonstrated R1 channel
unobserved. Two ephemeral processes used actual configured-file resolution and
request machinery on version **1843039/file 1743033**. Anonymous HEAD returned
**401**; keyed HEAD returned **307** from canonical origin and **200** from b2.
Authorization was present only at the canonical origin; observed requests had no
Cookie or Proxy-Authorization and no configured key in other headers/URLs. All
responses closed. Production total remains 900 s; this read shortened the total
to 20 s and retained finite phase limits. There was no GET fallback, body read,
download, registration, generation or target change. Key content and permissions
were compared in memory and remained unchanged; no private digest was computed.
The observed provider behavior does not eliminate R1's demonstrated policy gap.

Actual private-value/URL-encoded-value equality scans cover candidate source and
new QA evidence. Static probe/verifier data-flow review finds no hashing of the
private input. This is the stated digest-exclusion check, not a claim to detect
every unknown derived encoding. Signed request locations are absent from live
records; offline signed values are visibly synthetic. Complete ordinary hashes
remain. Original artifacts, failed attempts and private snapshots are preserved.

[Official artifact audit](review-evidence/coding-artifact-audit.json) records six
independently downloaded uploads, **75 indexed payloads/76 ZIP members**:
60 exact Git bodies and 15 raw logs matching declared whitespace normalization.
Every hash/byte count matches. The downloaded bundle verified and fetched into a
fresh bare store which lacked the candidate before and after seeding the fixed
baseline; candidate SHA/tree and all indexed Git bodies agree. Expanded payloads
also passed actual private-value exclusion. Artifact integrity does not certify
the missing product boundary.

## Limits and disposition

**Offline:** fresh macOS checks and isolated synthetic bytes/DB/HTTP only. Existing
124 Backend skips remain platform-related; four full-MCP skips are optional
export checks, with applicable revision/lifecycle checks explicitly enabled in
the separate fresh-export runs. Windows was not exercised. Frontend is unchanged
from the baseline; no new frontend suite/build is claimed.

**Running service:** not probed, restarted, redeployed or reconfigured.
**Provider:** only the separately recorded bounded source-component HEAD reads.
**Generation:** none. **Retrieval:** official Coding attachments read back and
verified, plus synthetic local fixture bytes; no live Gallery/model-body retrieval.
No broad real rate-limit/Early Access/cancellation outcome is inferred from fixtures.

Shared main remains untouched, including all 13 concurrent dirty memory files.
No private setting/key rewrite, runtime migration, environment modification,
model/data/output/Gallery deletion, feature merge/push or parent owner/status write
was made. The ignored QA environment and persistent worktree remain available.

This QA card completes with **FAIL R1 (P1, D3)**. Producer owns the repair dispatch
and integration decision on its own card. Any changed product commit needs a new
independent exact-commit review. No self-PASS, automatic Phase 2 exit, zero-fix
automation or CTY aesthetic judgment is recorded.
