# p1-03 — Producer acceptance

Accepted 2026-11-24 by [Producer AID-144](/AID/issues/AID-144), after reading
the actual Coding manifest and independent same-candidate PASS report.

## Accepted identity

- Final feature: **`10d45934191b5f86590aa6408feae170ee3bb9df`**, delivered by
  [Coding AID-163](/AID/issues/AID-163), based on published
  `faad28dc339b8b5d14aceea91d1fcfaad0a79ddd`.
- Independent delivery review 1: [QA AID-164](/AID/issues/AID-164), **D1-D5 PASS**,
  exact report/evidence/registry **`7ca903fd687a9eb1c83436e132d85f6c23377776`**.
- Reviewed product/tests/manifest, source evidence and QA report/registry are
  integrated unchanged. The final published main SHA and local/fetched/advertised
  equality receipt are recorded in [the native publication ledger](/AID/issues/AID-144#document-plan).
  Subsequent acceptance/status documents do not relabel the reviewed candidate.
- [Cleared task](task.md) SHA-256 remains
  `0d25f752ed4f17b28a01109c10c163e57532ae4b7e11832b8361f63a67af6688`;
  full normative decision hash remains
  `7e91e4392ccab45af01c16db6781a36345e711e0722b9c1260cdb3df6a76e065`.
  Kickoff round 2 CLEAR reviewed fixed `fe82c10`, report `c5d85f6`.
  [Manifest](manifest.md), [independent PASS](review.md),
  original ambiguity and
  clarification 1 retain their original bytes.
  The author manifest's awaiting-QA text is an immutable delivery snapshot;
  this acceptance records the later independent PASS/publication gate.

## Accepted behavior and evidence

| Requirement | Accepted observation |
|---|---|
| D1 — completed generation/results | One registered read intent returns every canonical media result with real identity/kind/order/provenance and supported host/Backend locators. Separate `images` retains real image IDs and null artifact IDs, including legacy image-only success. Missing/unsafe/mixed locators return `artifact_locator_unavailable` with completed Backend status, all known identities and available safe locators. No borrowed ID, result cap, basename remapping or file migration. |
| D2 — failure/recovery | Failed and cancelled jobs in both domains preserve target identity/state, safe reasons/codes/hints and generation/training context. A successful training status read is not successful training. Only actual initial 404 permits other-domain lookup; connection/5xx and later read failures retain recovery. |
| D3 — total deadline | One monotonic deadline and cancellable async reads cover lookup, status/body chunks, enrichment, sleep and preparation; high requests clamp. Timeout retains current/last-known or explicitly unknown state and same-ID call-again guidance. Recorded requests are GET only: no job cancellation/submission/resubmission. |
| D4 — training and smoke | Public model output/registration remains separate from Gallery media; no media means empty artifact/image lists. Real/legacy/absent/queued/running/failed/cancelled/unavailable independent smoke status, IDs, nullable canonical artifact and safe diagnostics survive. Training completion neither awaits nor submits smoke. |
| D5 — documentation | The delivered MCP table, result/error/timeout examples, host/URL/legacy rules and current/staged flows agree with discovery/source. Thirty tools are exposed, retaining all prior 29 risk labels and adding only wait=read. Ping stays; health/workers remain later. |

Actual calling-client enforced tool-call limit: **unverified**. Tracked client,
settings/wrappers/server and preserved source searches identify no such bound.
The **50-second overall maximum is the approved fallback policy, not a measured
client limit**. Existing 60-second per-request default does not extend wait's
overall cancellation scope. Independent short mocked-transport deadline tests
measured **71.5-73.7 ms for 70 ms budgets** and **47.4 ms for 45 ms partial
enrichment**, including SDK/setup overhead; 300-400 ms reads were aborted.
These establish bounded control behavior with disclosed overhead, not a live
50-second client/session measurement or production timing guarantee.

## Independent verification

QA ran fresh checks at the exact final candidate, with pinned import origins,
isolated roots and pytest `--timeout=60`. Commands, UTC times, exits, full logs,
fixtures and fault/restore hashes are in QA evidence.

| Check | Independent outcome |
|---|---|
| Full Backend | 1900 passed, 124 Windows-only skips, 76 warnings in 44.39s; exit 0 |
| Final restored full MCP | 540 passed, 2 unchanged optional smoke-export skips in 2.80s; exit 0 |
| Targeted wait | 77 passed in 1.29s; exit 0 |
| Additional registered QA cases | 28 passed in 0.39s; exit 0 |
| Fresh real-route/SQLite shape producer | Exit 0, 0.626s process; synthetic PNGs and mocked queue only |
| Seven meaningful production faults | Expected RED for media identity, hidden locator errors, terminal-success lie, missing deadline abortion, lost smoke reference and both old/new false risks; exact restoration before final GREEN |

Fresh Backend revision/multi-LoRA/lifecycle exports feed meaningful registered
MCP consumers; the complete Backend suite includes LoRA parity and historical
registry guards. No earlier Backend result/export substitutes for this proof.
All nine prior registry rows survive; QA certifies four new automated D1-D4
items, **13 active rows**, with no supersession. D5 is manual with catalog support.
The two MCP skips need optional smoke HTTP/image exports; all new wait/smoke-shape
cases execute. Frontend/build/native Windows/worker/launcher/bot inputs are
unchanged and unrun. Canonical component environments were preserved.

QA's initial missing-export run and overly literal raw-smoke-text helper oracle
are retained separately. Supplying its own fresh export and comparing safe
public training fields against the existing registered training-status tool
resolved those setup/oracle issues; no candidate fix or weakened product test
was made. Coding's setup/development REDs also remain in its manifest/evidence.

Producer verified all **ten** official Coding/QA uploads by size/hash, actual
manifest/report against Git, both exact full-index binary patches and bundle
heads/prerequisites. All **203 Coding** and **262 QA** indexed payloads match
sizes, hashes, blob IDs and named immutable Git bytes (205/264 archive members).
The identity audit records
those checks. Producer checks document/integration/publication identity, without
another software suite on unchanged reviewed product/test/dependency inputs.

## Limits, preservation and continuation

- **Offline software:** independently observed suites, registered/stdio mocked
  transport, fresh route/SQLite fixtures, meaningful faults and identity checks.
- **Running services:** no probe, restart, replacement/deployment or loaded-source
  claim. Preserve AID-151's active runtime/worktree/private configuration and
  canonical venvs. Published source is not a deployed service.
- **Real generation/training/download/worker dispatch:** none in this delivery,
  review or acceptance. Real wait behavior remains p1-05.
- **Generated-artifact retrieval:** no live Gallery-byte read or remote URL
  consumption. Fixture PNG validation and downloaded review packets are separate.

Constructed locators prove neither file existence nor host/client access or
bytes. The historical 23-unit/eight-incident baseline and one cached-original /
revision colocated Mac pair with canonical lineage retain their limits. Live
timeout/cancel/dedup recovery, remote consumption, aesthetics/demo, three
zero-intervention runs and phase close remain unaccepted. Retain all models,
datasets, outputs and Gallery records. Timeout requires inspecting the same
job before resubmission; wait never cancels/resubmits it.

Accounting: **one p1-03 kickoff ambiguity / clarification 1 / kickoff 2 CLEAR,
implementation delivery review 1 PASS, zero implementation rejections**. Separate
p1-02/p1-00a rejection/correction histories and original evidence stay intact.

Publication and completion of this coordinator release
[Producer AID-145](/AID/issues/AID-145) for the existing
[p1-04 health/configured-worker task](../p1-04-mcp-health-and-workers/task.md).
Read these actual accepted results and current 30-tool surface; obtain its own
fresh independent kickoff CLEAR before Coding and exact-commit PASS before
publication. Reuse existing status endpoints; Phase 3 registry/heartbeat/scheduling
remain excluded. No ordinary owner/start/resource confirmation is pending.
