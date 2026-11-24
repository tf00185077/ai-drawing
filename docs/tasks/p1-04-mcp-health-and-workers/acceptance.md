# p1-04 — Producer acceptance

Accepted 2026-11-24 by [Producer AID-145](/AID/issues/AID-145), after reading
the actual Coding manifest and independent same-candidate PASS report.

## Accepted identity

- Final feature: **`72f483418524a613fb104b92ab483e39f7432bfc`**, delivered by
  [Coding AID-167](/AID/issues/AID-167), based on published
  `b075f36c0eec532071e11328eb4f2b21b52e1c0f`.
- Independent delivery review 1: [QA AID-168](/AID/issues/AID-168), **D1-D4 PASS**,
  exact report/evidence/registry **`3422ccda7a66514fe7dadf7d3c8785a5718ba472`**.
- Reviewed product/tests/manifest/evidence and QA report/registry are integrated
  unchanged. The final published main SHA and local/fetched/advertised equality
  receipt are in [the native publication ledger](/AID/issues/AID-145#document-plan).
  Producer acceptance/topic status documents do not relabel the reviewed candidate.
- [Cleared task](task.md) SHA-256 remains
  `28077043ebe82e1371657219e6bab0685a8ec1918ec8130b122dad097dbc88e8`;
  full MCP decision hash remains
  `d477af0600efb30ec35eccd9173e82ec01732294b8cc9257905208d1f345c7e0`;
  [clarification 1](kickoff-clarification-1.md) remains
  `8fc12d877dc004dddf4dbf09177ffcc7b2d7c98ee3ce91bf84aa3ac06768670f`.
  Kickoff round-2 CLEAR reviewed fixed `5cf158b`, report `e75a94e`.
  Original task/report/evidence and author manifest remain immutable snapshots;
  this acceptance records the actual later PASS/publication gate.

## Accepted behavior

| Requirement | Accepted observation |
|---|---|
| D1 — truthful three-component health | Health replaces ping and retains Backend, Backend-local ComfyUI and worker entries through up/down/unconfigured, Backend outage, invalid and partial reads. Reasons distinguish reported failed probes from dependencies not observed through Backend. Reachable no_models/degraded preserve their state/configuration/counts/hints. Health's success envelope describes the read result; callers inspect each component's reachable/reason fields. |
| D2 — authoritative worker configuration and current identity | Existing GET worker status is extended additively, preserving old flags/error_type/nested worker. Configured URL/expected identity survive failure; observed hostname/protocol and the same accepted probe's resolved URL are separate and null on failure, even if an older discovery cache remains. URL-only success can have null hostname. Current last_error is safe and null on success, with no persistent history. MCP returns empty only for confirmed unconfigured status, one configured entry even unavailable, and a common error when configuration cannot be read/validated. |
| D3 — 31 intents and read-only requests | Exactly 31 intents: replace temporary ping with health, add list_workers, both read, preserve the other 29 names/risks and capabilities. Independent literal catalog/discovery guards and actual registered requests use only existing Backend GET/status paths. Existing LAN discovery/cache is preserved; no registry, heartbeat, scheduling, submission or control path is added. |
| D4 — documentation and recovery | MCP table/current flow/examples/error guidance, worker/team topics and runtime-source memory match source/discovery. Backend-local ComfyUI is distinct from direct admin's MCP_COMFYUI_API_URL. Configuration/expectation/current-null distinctions, one-worker limits and unchanged wait/result/locator recovery are explicit. Producer changes only acceptance/status copy after the independent comparison. |

Health performs sequential **five-second HTTP reads**. It is neither an atomic
snapshot nor a wait-style overall deadline. Reachability proves no remote
ComfyUI, model/workflow parity, generation readiness, loaded source or artifact
access. Actual calling-client enforced limit remains **unverified**;
the unchanged **50-second total wait fallback is policy, not measurement**.
Wait retains the same job ID after timeout and never cancels or resubmits.

## Independent verification

QA ran fresh checks at the exact final candidate in its isolated worktree, with
canonical component interpreters, worktree-pinned imports, isolated roots below
TMPDIR, fresh Backend exports and pytest **--timeout=60**. Full argv, UTC times,
exits, output and restoration hashes are in
[QA evidence](qa-delivery-1-evidence/README.md).

| Check | Independent outcome |
|---|---|
| Final restored full Backend | **1916 passed, 124 Windows-only skips, 76 warnings in 42.21s**, exit 0 |
| Final restored full MCP | **606 passed, two unchanged optional smoke-export skips in 3.27s**, exit 0 |
| Separate literal/discovery/HTTP probe | **51 registered calls / 107 GETs**, exact 31 risks and other 29 preserved |
| Fresh wait-route consumer | **28 passed in 0.51s**; fresh route/SQLite shapes, same-domain recovery, identities/locators/smoke and partial-enrichment deadline |
| Ten meaningful production faults | Expected assertion RED for component loss, false no-models reachability, empty/false worker observations, configured/resolved URL confusion, skipped identity validation, POST reads and both new/retained false risk labels; exact restoration before final full GREEN |

Nineteen retained final Backend exports feed the registered MCP consumers.
All 13 earlier registry rows are unchanged; three independently certified D1-D3
items yield **16 active rows**, with no supersession. D4 is manual with catalog
support. Backend skips require Windows; the two MCP skips need optional smoke
HTTP/image exports. New health/wait-shape consumers execute. Existing warnings,
initial setup failures and corrections are preserved; no final failure or hang.
Frontend/build, native Windows and unchanged worker/launcher/bot execution were
not performed. Canonical environments are unchanged.

Producer verified all **ten official uploads** by hash/size, actual manifest/
report bytes, exact binary/full-index patches and bundle heads/prerequisites.
All **159 Coding / 296 QA indexed payloads** match hashes, sizes, blob IDs and
named immutable Git bytes (**160 / 297 archive members**). Actual final suite
receipts match raw outputs and exit zero; ten restoration hashes match the
candidate. [Identity audit](acceptance-evidence/producer-identity-audit.json).
Producer verifies document/integration/publication identity and reuses applicable
independent results on the unchanged reviewed product/test/dependency inputs. Two existing
catalog/documentation guards pass after acceptance-status topic edits; the
[command/output receipt](acceptance-evidence/producer-doc-guards.json) records
that narrow check separately from QA's full suites.

## Limits, preservation and continuation

- **Offline software:** independently observed full affected suites, real
  Backend routes/client validation under mocked transports/candidates, real
  registered/stdio boundaries, fresh fixtures, faults and source/docs checks.
- **Running product:** no probe, restart, deployment or loaded-source claim.
  Preserve [AID-151](/AID/issues/AID-151)'s active runtime/worktree/private
  configuration and canonical venvs. Source publication is not deployment.
- **Real generation/training/download/worker dispatch:** none in this delivery,
  review or acceptance. Existing read discovery submits or controls nothing.
- **Product-artifact retrieval:** no live Gallery bytes or remote URL
  consumption. Synthetic fixture PNGs and downloaded review packets are separate.

Keep all models/datasets/outputs/Gallery records. Historical 23-intervention /
eight-incident baseline and one cached-original/revision colocated-host-path
pair retain their limits. Locators do not prove bytes or client access. Live
recovery, remote consumption, aesthetics/demo, three zero-intervention runs and
Phase 1 close remain unaccepted. No Phase 2 activation or boundary change occurs.

Accounting: **p1-04 kickoff ambiguity 1 / clarification 1 / kickoff round 2
CLEAR; implementation delivery review 1 PASS, zero delivery rejections**.
Earlier p1-03/p1-02/p1-00a histories remain separate. The normative choice and
runtime-source lesson are already in decisions/memory; no duplicate memory topic
is needed for this acceptance.

Publication/completion of this coordinator releases
[Producer AID-146](/AID/issues/AID-146) for the existing p1-05 Mac smoke task's
own fresh independent kickoff. Read the actual accepted p1-01 through p1-04
deliveries and current 31-intent surface; verify loaded runtime/client contracts
when planning real execution rather than inferring them from this publication.
Preserve the adopted Illustrious/default, no-LoRA, explicit local target and
all real-run/demo/phase-close gates. CTY judges aesthetics and phase close;
no ordinary start/resource confirmation is pending.
