# Civitai credentials on the owner Mac

## Key-file locator

CTY's authorized Civitai API key file is:

`/Users/tf00185088/Desktop/civitai.txt`

The file is outside this repository and readable by the local owner account. Keep
its owner-only permissions (`0600`). The path is documentation; the key value
stays in that private file. Producer and its authorized executors read the file
locally when Phase 2 needs authenticated Civitai access. Read and trim its contents
inside the process that needs them; report only presence/readability and the
sanitized operation result. Do not print the key or put it in task descriptions,
evidence, URLs, shell arguments, shared logs, MCP results or Git.

## Configuration and implementation boundary

The approved Phase 2 Backend configuration contract is:

```dotenv
CIVITAI_API_KEY_FILE=/Users/tf00185088/Desktop/civitai.txt
```

Use this absolute host path in private configuration. A container or a different
machine needs an explicitly mapped readable private path; the host path does not
prove access there. Do not copy the key into a repository or an artifact bundle.

The accepted p2-01 source implements this setting on ordinary resource
acquisition and the retained resource-inspect/resource-install adapters, after
[independent exact review 2 PASS](tasks/p2-01-civitai-key-file/acceptance.md).
Source publication does not establish that the running Backend has loaded the
reader. No private on-disk setting is rewritten
by loading credentials. Launcher `setup`/`reconfigure` still rebuilds its fixed
settings list; preserve private custom settings before using those commands.

A nonblank file setting takes precedence over `CIVITAI_AUTHORIZATION`. The Backend
reads at most 64 KiB of UTF-8, trims outer whitespace, and requires one token.
Missing, unreadable, nonregular, empty, invalid UTF-8, oversized, header/JSON or
control-bearing contents fail with `civitai_credentials_unavailable` before
provider traffic. A configured file failure never falls back. Loading changes
neither content nor permissions. An unset/blank file setting preserves legacy raw
key/Bearer behavior. When neither credential is configured, requests are anonymous.

Each metadata/inspect operation has one credential snapshot and a total 20-second
HTTP deadline across nested reads (connect at most 5 seconds, read at most 10).
Each file's acquisition/install execution gets a fresh snapshot and a total
900-second transport deadline spanning redirects, retries/backoff and streaming
(connect at most 10 seconds, read at most 30). File rotation affects the next
operation. These are policy limits, not measured performance or MCP caller-wait
guarantees. The private key remains only in operation memory; Python memory
zeroing is not promised.

Requests permit exact HTTPS `civitai.com`, `www.civitai.com` and `b2.civitai.com`
hosts, default port, no userinfo, and at most five explicit redirects. Authorization
is sent only to the canonical `civitai.com` origin and stays stripped after an
origin change, including a redirect back. Other destinations produce
`civitai_redirect_blocked`; new CDN hosts require a separately reviewed policy
change. Provider requests reject cookie storage and replay. After HTTP client
preparation, each final request removes Cookie, Proxy-Authorization and implicit
Authorization, then applies only the operation's permitted Authorization header.
Same-origin, CDN and return hops use this boundary; provider Set-Cookie does not
create another credential channel. See the [credential transport decision](decisions/civitai-credentials.md).
Streams close on completion, refusal, deadline or interruption.

Provider 401/403 remain refusals, and 429/provider/network errors remain failures
with recovery hints. `civitai_timeout` describes a transport/deadline outcome.
After a caller timeout inspect the existing acquisition ID before resubmitting.
Do not put credentials or signed query values in logs, metadata, records, MCP
results or evidence; ordinary source/model hashes remain available. Authentication
can still fail for provider access restrictions or rate limits.

## First check evidence and current next task

The [accepted real First check](tasks/p2-00-civitai-first-check/acceptance.md)
demonstrates one selected login-required free-key file: anonymous same-file
HEAD/GET 401, credentialed route 307, credential-free CDN 200, exact downloaded
bytes/hash and completed local checkpoint+LoRA image. Seven in-process key bridges
were counted; private on-disk settings were preserved. This proves that selected
access case, not an implemented/deployed file reader, every restricted resource,
Early Access or sustained rate-limit capacity. Key presence is still a separate
observation from authentication.

[p2-01](tasks/p2-01-civitai-key-file/acceptance.md) accepts production file loading
and credential-safe retained request paths at corrected candidate 24dad88f,
independent review cdf63e71. Fresh anonymous/configured-file source HEADs observe
401 versus 307→200 with no body-method calls; no new acquisition/generation or
running-Backend deployment is claimed. Next is the
[resource-record foundation](tasks/p2-02-resource-record/task.md), under a fresh
independent kickoff before implementation.

## Authority

[CTY's Phase 2 start and key-file direction](requests/2026-11-26-phase-2-start-and-key-file.md)
fixes this locator and authorizes continued execution within the accepted roadmap.
The [Phase 2 roadmap](roadmap/ROADMAP.md#phase-2--one-sentence-flow-resources--workflow--image-active-2026-11-26)
and [operating policy](OPERATING-POLICY.md) govern the work.

## Current p2-01 delivery boundary

The first candidate 098120f8 was rejected by independent review 8609ba34 with
R1/P1/D3: an implicit HTTPX cookie jar can replay a canonical credential cookie
to b2 despite removing Authorization. The actual report
uses synthetic configured-file credentials; selected live HEADs had no cookies.
No actual owner-key disclosure is inferred from that original observation.
Correction 1 enforces the existing
Authorization-only policy at the final outgoing request and blocks cookie
acceptance/persistence/replay. This is [the technical transport decision](decisions/civitai-credentials.md),
implemented in the accepted exact source after fresh frozen evidence and
independent review 2 PASS. It does not certify the running Backend's loaded
identity. Changed product code requires another exact review.
