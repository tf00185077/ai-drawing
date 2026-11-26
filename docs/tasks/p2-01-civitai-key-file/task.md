# Civitai private key-file loading and credential-safe requests

## Task and purpose

Replace the First check's counted in-process key bridges with Backend-owned
private key-file loading on retained active Civitai provider paths. Users/agents
can use the configured file through current acquisition/inspect/install behavior
without supplying credentials to MCP, rewriting private settings or manually
injecting a transport. This bounded task advances approved Phase 2; it does not
claim the rest of the resource/search/download/default flow is implemented.

## Inputs and authority

Read [CTY's current direction](../../requests/2026-11-26-phase-2-start-and-key-file.md),
[Phase 2 scope](../../roadmap/ROADMAP.md), [credential guide](../../civitai-credentials.md),
[accepted First check](../p2-00-civitai-first-check/acceptance.md), its actual
[QA report](../p2-00-civitai-first-check/review.md) and [friction ledger](../p2-00-civitai-first-check/friction-ledger.md),
[evidence decision](../../decisions/evidence.md), [runtime memory](../../memory/runtime-source-contract-verification.md)
and [operating policy](../../OPERATING-POLICY.md). Measurement Coding full SHA
0d571b7d571561ebdea34c959ed6f16e2db06953 / exact QA 9caf92fefac6f30255bac528e3f4292f2c1bddf6
are source evidence, not CLEAR for this new software task.

Actual active paths include app.config settings, civitai_resource_acquire
_auth_headers/_JsonTransport/_StreamingDownloadTransport and resource-inspect/
resource-install adapters. Trace actual retained callers before editing; centralize
the credential/request boundary instead of adding another record or reviving
recipe/generate-like surfaces that Phase 2 removes. Keep current 31 MCP intent
names/risks/common envelopes and existing acquisition/resource identities.

## Scope and selected bounded contract

- Add optional private Backend CIVITAI_API_KEY_FILE. CTY's host file is
  /Users/tf00185088/Desktop/civitai.txt. It is not a tool parameter/URL, public
  endpoint, stored credential record or new secret manager. Read UTF-8/trim
  inside the Backend at operation start, bound the read to 64 KiB and retain
  credentials only in process memory for that operation. Later operations see
  file rotation; no stale process-wide file-content cache. Never modify file
  permissions/content or existing private on-disk settings as part of loading.
- Nonblank configured file takes precedence over legacy CIVITAI_AUTHORIZATION.
  Missing/unreadable/nonregular/empty/undecodable/oversized or header-control
  content fails with stable civitai_credentials_unavailable and a useful hint
  referencing the setting, before provider traffic. Do not silently fall back
  to legacy/anonymous when that configured file fails. Unset/blank file setting
  retains the current legacy raw-token/Bearer behavior; neither credential
  configured permits anonymous requests, with actual login refusal truthful.
  Resolve one credential snapshot per provider operation; never persist it in
  a resource/job/result. A metadata operation is one public metadata/inspect
  service call including nested HTTP reads. A download operation is the current
  acquisition/install execution for one file, including its retries/backoff.
  Normalize a raw key to one Bearer prefix; preserve already-prefixed legacy
  values. File contents are a trimmed key, not a JSON/header block. No promise of Python memory zeroing.
- Retained production metadata/acquire/install paths use the same resolver and
  request policy, including ordinary Backend HTTP/MCP acquisition—not just an
  isolated helper. The existing async admission/status/records stay; no new
  parallel registry, job schema or background scheduler in this task. Current
  acquisition IDs remain distinct from future generic download jobs.
- Credentials go only in the Authorization header to the canonical HTTPS
  civitai.com origin. Provider/CDN redirects use explicit bounded handling;
  never forward Authorization on an origin change, including b2.civitai.com.
  Initially permit exact HTTPS civitai.com/www.civitai.com/b2.civitai.com hosts,
  default HTTPS port, no userinfo; refuse other scheme/host/port with stable
  civitai_redirect_blocked. Match parsed hosts, not string suffixes. At most
  five redirects; metadata operation total 20 s (connect at most 5/read 10),
  download transport operation total 900 s (connect at most 10/read 30), including
  all redirects and any retained bounded retry/backoff. No read=None. Record
  truthful deadline outcomes and close response streams on success/error/
  interruption; no stale live stream after return. These are policy limits,
  not performance measurements. Preserve existing hash/size/scan/no-overwrite
  behavior and partial-file truth; transport timeout is not a failed caller wait.
- Preserve existing unauthorized/provider failure distinctions and envelopes;
  add the above credential/redirect errors and civitai_timeout only where needed.
  Refusal/rate-limit/network errors expose sanitized status/recovery hints,
  never a key/header/signed location/raw exception URL. Existing 401/403 is not
  generic success and never silently retries another target. Logs, metadata,
  diagnostics, resources/jobs, MCP errors and evidence exclude key values/digests
  and signed credential query values. Ordinary file hashes/tokenizer paths must
  remain available for source/byte proof. Do not alter p2-00 raw helper/evidence.

Excluded: model-search/inspect intent redesign, single resource-record migration,
SDXL workflow/default application, size/total-disk-budget reservations, generic
Backend download-job/wait integration, service/test deletions, new downloads/
registrations/generation, client-limit claims, worker/video/training/UI/architecture.
Those approved Phase 2 requirements remain pending in the [intake](../p2-00-civitai-first-check/implementation-intake.md).
No product change starts before this task's own actual independent CLEAR.

## Done when

- [ ] **D1 — private configuration behavior.** Check: meaningful tests cover file
  precedence, rotation/one-operation snapshot, valid trim, unusable/header-invalid
  files, unset-file legacy compatibility and anonymous mode. A configured bad
  file yields the stable actionable error with no provider call or silent fallback.
- [ ] **D2 — actual production wiring.** Check: registered MCP/Backend acquisition
  and retained inspect/install request paths consume the resolver under isolated
  HTTP/DB fixtures, preserve resource/acquisition IDs and existing envelopes/risk
  labels, and need no settings/transport monkeypatch to load the configured file.
  Existing data/root/private config and model/output bytes remain preserved.
- [ ] **D3 — credential-bound requests.** Check: factory/real route tests expose
  original-origin Authorization, stripped cross-origin credentials, allowed CDN
  streaming, denied URLs/redirect loops, finite reads/total time across retries,
  stream closure and truthful 401/403/429/network/deadline outcomes. Faults that
  leak a header, bypass file precedence or remove the total bound must fail
  meaningful guards, then restore before green. No tests mirror helper internals.
- [ ] **D4 — exact source live read plus secrecy.** Check: after software freeze,
  one bounded read-only comparison on the already-observed selected file route
  (version 1843039/file 1743033), using actual configured-file resolver/request
  machinery: anonymous refusal versus credentialed redirect/credential-free CDN
  HEAD or bounded equivalent. No full file/redownload/registration/generation.
  Record actual statuses/loaded component identity; API change/failure stays
  honest. This proves the source component, not redeployment of the running
  Backend. Private value/digest exclusion and complete ordinary source hashes
  verified before upload/Git; preserve the old five-hash limitation as historical.
- [ ] **D5 — independent deliverable and regression.** Check: own manifest,
  current credential/topic docs, exact full frozen final commit and sanitized
  evidence; meaningful feature/affected Backend+MCP checks with existing skips
  unchanged and long suites --timeout=60/isolated roots. QA independently reviews
  that exact commit, actual boundary evidence and fault sensitivity, preserving
  the 18 existing registry contracts. New software after review needs new exact
  review; no self-PASS or Phase 2 automation/exit/aesthetic claim.

## Delivery and preservation

Coding owns implementation on a persistent isolated worktree; QA owns its own
fixed-commit kickoff/delivery reports, completing adverse verdicts for Producer
to handle. Native Coding → exact Review → Producer prerequisites carry work.
No routine owner start/resource approval is pending; actual boundary changes
alone go to CTY. Preserve AID-178 private snapshot, AID-171/AID-151 runtime/private
configuration/backups, canonical environments, all concurrent memory edits and
all models/datasets/outputs/Gallery records. No service restart/deployment for
this source delivery; later controlled integration verifies source/jobs/roots.
