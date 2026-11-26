# p2-01 Coding delivery

Issue: [Coding AID-181](/AID/issues/AID-181). Independent delivery review:
[QA AID-182](/AID/issues/AID-182); coordination: [Producer AID-146](/AID/issues/AID-146).
This is a Coding delivery, not independent PASS, integration, deployment or Phase 2 exit.

Implementation is frozen at **8a77b9079ed4d60c9a7784713cc3525def3fdadf**, tree
**82ef1bb63cce947d378ee9cc4f84d016ba8233f5**, based on fixed published
**b49bdc6695277b4c53ab50b973abbbd79a415316**. Final candidate SHA/tree are in the
native delivery receipt and official artifact index (a file cannot contain its
own commit hash). Later changes add only this manifest and evidence. Worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-181-key-file`,
branch `aid-181-p2-01-key-file`; retained with its ignored test environment/evidence.

## Implementation

`civitai_provider.py` owns the private UTF-8 file resolver, one credential snapshot,
exact-origin policy, explicit redirect loop and absolute transport deadline.
Existing synchronous service adapters drive cancellable HTTPX async reads on a
private loop. This internal bridge is necessary because finite inactivity
timeouts alone cannot stop a slow-drip stream within the operation total. It adds
no endpoint, scheduler, job schema, resource registry or dependency.

Ordinary registered MCP acquisition still posts through the existing Backend
route. Nested version/model reads share a 20-second metadata operation. Each
background file execution resolves a fresh snapshot and shares its 900-second
bound across its existing retries/backoff/stream. The retained resource-inspect
and resource-install adapters use the same policy. File rotation is observed by
the next operation; cached Settings do not cache key contents.

Configured bad files fail before provider traffic, without legacy/anonymous
fallback. Exact HTTPS canonical/www/b2 hosts and default port are validated at
initial request and every redirect; credentials go only to canonical origin and
stay stripped after an origin change. Responses close even if never consumed.
Stable errors survive catch-all/background status and MCP projection. HTTP logs,
stored provider URLs, metadata and diagnostics redact actual credentials and
signed query values, retaining ordinary source/tokenizer/model hashes. Raw signed
download locators are ephemeral internal inputs until consumed by the policy;
public inspect descriptors and durable records carry sanitized canonical identity.

Existing byte verification, scanning, partial-file behavior, adoption/dedupe and
record IDs remain. No broader pre-existing no-overwrite guarantee is claimed.
The old image/recipe import transport is outside this retained resource-file
contract; it was not redesigned or revived. No MCP name, risk or envelope changed.
Current configuration/limits are in [the credential guide](../../civitai-credentials.md)
and [setup guide](../../setup.md).

## Done when evidence

| Item | Check / level | Evidence and layer | Real boundary / substitutes |
|---|---|---|---|
| D1 | test / P1 | `backend/tests/test_civitai_provider.py`: precedence, trim/rotation, legacy/anonymous, bad files, FIFO, unreadable and exact 64 KiB | Real Settings/environment and local fixture files; only OS permission denial is simulated. No key/settings bridge. |
| D2 | test / P1 | Registered MCP admission/status/reuse and retained inspect/select/install route tests in the same file | Real registration/common envelopes, HTTP Backend client, FastAPI routes, resolver, ORM, safe byte publication and status. External HTTP only is replaced. DB/storage isolated. Background scheduling is deferred deterministically; actual `_run`/`_run_one` execute. |
| D3 | test / P1 | Same file: origin headers, initial/hop denial, five-hop limit, total across nested reads/retries/backoff, actual async slow drip, unconsumed/error/interruption closure, 401/403/429/network, signed logs/storage; [faults](evidence/faults.json) | Real HTTPX factories/request objects and response streams against HTTP fixtures. Synthetic clock for exact 20/900 totals; real async cancellation under a shortened deadline for slow drip. Actual production mutations fail then restore. |
| D4 | manual / P1 | [Live comparison](evidence/live.json), [frozen inventory](evidence/source-inventory.json), [verification](evidence/verification.json) | Actual configured-file resolver and production request machinery, no transport/key injection. Two ephemeral processes; HEAD same known version 1843039/file 1743033. Read-only profiler observes real HTTPX responses. |
| D5 | test + deliverable / P1 | Full suites, affected checks, registry guards, this manifest, official hashed/read-back uploads and Git bundle in native receipt | Exact frozen source plus evidence descendants. Existing 18 registry rows unchanged; only independent QA may certify additions. |

## Actual verification

Commands are reproducible through `python3 -B docs/tasks/p2-01-civitai-key-file/evidence/run_checks.py <label>`.
Exact argv, timestamps, interpreter, isolated root and results are in the
corresponding JSON/log files. All long suites use `--timeout=60`. The dedicated
ignored `.venv` references existing read-only Backend/QA site-packages and exports
this worktree's Backend/MCP source. Its child-inherited [guard](evidence/test_guard.py)
denies private .env/key access, remote traffic, live service ports and writes/DBs
outside the run scratch; existing ephemeral loopback/stdio fixtures are permitted.
Canonical environments were not installed into or changed.

| Command label | Result |
|---|---|
| `restored` (55 new feature cases, after all three faults) | **55 passed** |
| `backend` (affected acquisition/install/download/redactor/recipe/ledger) | **203 passed** |
| `mcp` (Civitai/client/catalog/stdio) | **31 passed** |
| `backend-full backend/tests` | **1,971 passed, 124 skipped**, 76 deprecation warnings |
| `mcp-full mcp-server/tests` | **666 passed, four skipped** |
| `registry` (named existing guards plus independent PNG tests) | **427 passed, one existing skip** |
| `check_faults.py` | Header leakage, precedence bypass and removed total bound each: **one meaningful failed test**; exact source restore and **55 passed** |
| `verify_delivery.py`, `git diff --check` | Private-value exclusion, 18 registry rows, task/p2-00/memory preservation and exact source checks; whitespace clean |

Full suites were run because the shared redactor has many retained consumers and
two existing registry rows name full suites. No frontend code changed; its suite
and build were not repeated. No test was deleted or newly skipped. All original
skip counts remain. Windows was not exercised. Dependency/API deprecation
warnings are disclosed; these checks do not certify Windows behavior.

**Live source component:** anonymous HEAD **401**; configured-file HEAD **307 →
200** on the allowed credential-free CDN. Every observed response closed, zero
model-body bytes read/saved, no GET fallback. The production file total remains
900 seconds; this probe shortened it to a 20-second cap, with finite phase
limits. The file opened independently as a readable regular file, its content
and permissions stayed unchanged. No private value/digest/length was emitted.
All loaded module paths/hashes and selected loaded code-object hashes match the
frozen source. The complete frozen inventory covers **2,298 tracked files**,
including ordinary tokenizer/source hashes. This never reconstructs the First
check's five missing historical tokenizer fingerprints.

**Running service:** not probed, restarted or redeployed. **Generation/model
acquisition:** none for delivery. **Retrieval:** no Gallery/model bytes fetched;
official delivery attachments are separately verified by byte readback. No
Phase 2 automation, zero-fix exit or aesthetic verdict is claimed.

## Failures, deviations and limits

Test log trailing whitespace is normalized for Git; diagnostic text is retained.
[Normalization hashes](evidence/log-normalization.json) identify original and saved
bytes; raw logs remain in the retained ignored worktree.

- No pre-existing product test failure is asserted. The first canonical test
  interpreter lacked `pytest-timeout`; it collected no tests. Existing prepared
  sites supplied it without a canonical environment change.
- Initial feature RED observations cover file precedence/invalid-file admission,
  stream deadline/error preservation, network retry count and HTTPX log leakage;
  fixture-only [initial RED logs](evidence/red-d1.log), [request RED logs](evidence/red-d3.log)
  and [log leakage RED](evidence/red-logs2.log) are retained.
- Required obsolete assertion update:
  `test_civitai_download_transport_follows_redirects_and_streams` no longer asserts
  `follow_redirects is True`. It now observes an actual explicit 307→b2 stream,
  bytes and response closure. The neighboring model-version permission test's
  old `httpx.get` fake was also moved below the real AsyncClient to preserve its
  original authoritative-model selection check. These are the only existing
  tests edited; neither was deleted or skipped.
- An early unguarded affected-suite invocation still had those obsolete mocks.
  It unintentionally made anonymous requests to their old provider fixture
  targets; the file request stopped at a denied redirect, with no model body
  read or saved and no configured credential. Its temporary raw signed-URL log
  was not promoted into artifacts. All subsequent regression runs used external
  network/private-file guards. These requests are not D4 evidence.
- The strict repository runner blocked existing stdio/loopback registry fixtures
  (three MCP failures and 20 registry setup errors). Switching to the isolated
  guarded environment restored the real feature tests without source edits.
- Initial full Backend result: 23 failures caused by removing the `httpx` module
  export used by existing no-side-effect bombs; restored that export, then full
  green. Initial full MCP result: 75 setup errors because the new runner had not
  created its scratch parent; fixed the runner, then full green. Both initial
  command/result/log pairs are retained. No new skips or test removals mask them.
- A repeated strict-run scratch path triggered pytest cleanup errors; unique
  scratch roots prevent reuse. This was a harness setup failure, not a provider
  outcome. Source faults always restored in `finally`, including that attempt.
- Abandoned: inactivity-timeout-only sync streaming cannot enforce the required
  total against slow drip. The shared cancellable async boundary replaces the
  two duplicated retained transports; existing services/public APIs remain sync.
- The key-file locator is configured in ephemeral probe processes only. Existing
  private settings, runtime roots/worktrees/backups/snapshots and every model,
  dataset, output and Gallery record were preserved. Shared main's concurrent
  memory edits were not staged, reset, stashed or copied. No merge/push occurred.

Independent QA should pin the actual final delivery receipt SHA and assess this
implementation and evidence. Producer owns subsequent findings and integration.
