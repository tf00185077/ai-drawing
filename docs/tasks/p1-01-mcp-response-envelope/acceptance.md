# p1-01/02 — combined Producer acceptance

Accepted 2026-11-24 by [Producer AID-143](/AID/issues/AID-143), after reading
both actual manifests and independent same-candidate PASS reports.

## Accepted identity

- Corrected combined feature: **`616f67ff68fc27070e85861e94d70de1baf5082a`**,
  delivered by [Coding AID-159](/AID/issues/AID-159).
- Independent delivery review round 2: [QA AID-160](/AID/issues/AID-160),
  exact report/evidence/registry **`28cd4512b8ec7d6594ec972ab81161b8c2d09d03`**.
- Integration: **`7ba2059f7e46920eaf860e19e61aa84bae8bf02c`**. Reviewed product/tests, both manifests,
  reports, historical mirrors, evidence and registry are integrated unchanged.
  The final published main SHA and remote equality receipt are recorded in
  [AID-143's plan](/AID/issues/AID-143#document-plan). Subsequent acceptance/status
  changes are documentation only; they do not relabel the reviewed candidate.
- Original tasks/decisions remain independently CLEAR at
  `496cee2f842dc9386d336afb237075bf952271ce`, actual kickoff reports `9d79d20`.
  [p1-01 manifest](manifest.md), [p1-02 manifest](../p1-02-mcp-tool-consolidation/manifest.md),
  [p1-01 PASS](review.md), [p1-02 PASS](../p1-02-mcp-tool-consolidation/review.md).
  Author manifests remain immutable delivery snapshots; this acceptance records
  the later independent review and publication gate.

## Acceptance evidence

| Contract | Accepted observation |
|---|---|
| p1-01 D1–D2 | All 29 registered successes/failures use the common envelope, including non-LoRA pre-body MCP validation. Safe Backend codes, hints, details, HTTP status and domain/job recovery survive. Formal stdio and real adapters are exercised with test-only transport. |
| p1-01 D3–D4 | Current envelope/error docs agree with discovery/source, and the full corrected MCP suite passes independently. |
| p1-02 D1–D3 | Complete 40-old-name mapping delivers 29 intents, one approved risk each, and registered request coverage for every merged mode/action. Existing LoRA/Civitai names, fragments/concurrency/provenance, Gallery namespaces/locators and generation/training distinctions remain. |
| p1-02 D4–D5 | All F1–F8 retain their original 23 intervention units/eight incidents. Current executable flow uses transitional ping/status polling; wait/health remain explicitly staged. Updated topic/policy/team docs and full MCP pass. |
| F2-1 correction | An independent literal all-29 risk oracle checks catalog and real discovery. A one-field ComfyUI admin-to-read fault now fails both guards/full suite, while mocked restart still requests POST /manager/reboot. All source is restored before final GREEN. |

Read composition rejects any legacy `save_as` presence before Backend access.
Saving returned fragment arrays/metadata uses `prompt_write(save)` with existing
revision/ETag/provenance and conflict behavior. This is two calls with no
cross-call atomicity or automatic overwrite/retry. Backend APIs remain unchanged.
No later wait, health, worker or resource-record feature is accepted here.

## Verification and limits

Independent QA ran fresh offline checks at the exact corrected candidate:

| Check | Result |
|---|---|
| Full Backend | 1900 passed, 124 Windows-only skips, 76 warnings, 41.60s |
| Full MCP after restoration | 460 passed, 2 unchanged optional smoke-export skips, 1.95s |
| Cross-layer LoRA parity | 5 passed, 1 warning, 0.31s |
| Additional registered QA boundaries | 15 passed, 0.22s |
| False-admin-read fault | 2 targeted failures; full MCP 2 failed / 458 passed / 2 skipped, exit 1 |

Full suites used isolated roots and `--timeout=60`; fresh QA Backend revision,
multi-LoRA and lifecycle exports were consumed through registered MCP in its
separate interpreter. No prior Backend result was reused. Six other meaningful
faults fail afresh. The restored catalog hash is
`d57d6a93e3529ca31746e172a37c24574bf068e9d87e433a7e80a204383c9e70`.
All standing guards pass; the QA-owned registry has nine active items.
Frontend/build/native Windows checks were not rerun: their inputs are unchanged
and QA ran on macOS. Optional smoke-export skips remain disclosed.

Producer verified all thirteen official corrected Coding/QA uploads by size and
hash, both manifests/reports against Git, both exact Coding patches, the QA patch
and both bundles. Coding's 147 and QA's 123 indexed archive entries match; 138
Coding and 120 QA repository/reference entries equal named immutable Git bytes.
Prior official artifacts retain their previously verified hashes. Original
40-row mapping/friction and first-round reports/evidence are preserved. The
integration audit confirms all reviewed file bodies outside coordination docs
are unchanged. Producer runs document/identity/publication checks, with no extra
software suite on identical product/test inputs.

- **Offline software:** the independently observed suites and controlled mocked
  HTTP/stdio/serialized-fixture checks above. They establish source contracts.
- **Running services:** no product probe, deployment, restart or loaded-source
  claim. Preserve AID-151's active runtime/private configuration/canonical venvs.
- **Real generation:** none in this delivery/acceptance; no training/downloads
  or worker dispatch.
- **Generated artifact retrieval:** no live Gallery-byte read. Downloaded review
  materials are not new generated-image retrieval.

The prior colocated Mac client proof remains one cached-original/revision pair,
canonical lineage and decoded unmodified host paths. Remote URL consumption,
live cancel/timeout/dedup recovery, aesthetics, three zero-intervention runs and
phase closure remain unaccepted. Preserve models, datasets, outputs and Gallery
records. Inspect an existing job after timeout before resubmission.

## History and continuation

First candidate `b1082a8` was p1-01 PASS / p1-02 FAIL F2-1. The exact
[p1-01 round-1 PASS](review-round-1.md),
[p1-02 round-1 FAIL](../p1-02-mcp-tool-consolidation/review-round-1.md) and original
QA evidence remain intact. Keep **one p1-02 delivery rejection / correction
round 1 / delivery review round 2**, now PASS. Kickoff K2-1/clarification round
1/kickoff round 2 CLEAR and p1-00a's separate history are not reset or combined.
One QA helper initially imported an old installed package; its retained failed
attempt is excluded from product results, and QA corrected only helper source
binding before rerunning the meaningful probe and complete fault/restore/GREEN.

Combined publication and completion of AID-143 release
[Producer AID-144](/AID/issues/AID-144) for the existing
[p1-03 bounded wait/result task](../p1-03-mcp-wait-and-result/task.md).
That task requires its own fresh independent CLEAR before Coding and exact-commit
PASS before publication. Use the new envelope/intent surface, truthful training
output/media locators and an overall wait budget including request durations;
source the actual client limit or label it unknown with the approved 50-second
fallback. No ordinary owner/start confirmation is pending. Phase scope/order
and CTY's aesthetic/phase-close authority remain unchanged.
