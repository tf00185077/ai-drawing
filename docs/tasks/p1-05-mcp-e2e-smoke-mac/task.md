# Task specification

## Task
Prove the Phase 1 exit on the Mac: retrieve an original and its traceable revision through MCP, in three consecutive real runs with zero manual fixes or retries.

## Purpose
The accepted p1-01–04 source contracts need real execution proof. The original
[p1-00 baseline](../p1-00-mcp-friction-run-mac/manifest.md) remains 23 intervention
units/eight incidents. [Kickoff round 1](kickoff-review-round-1.md) found that
metadata-only Gallery and unspecified wait/preparation accounting cannot prove
the existing [Phase 1 exit](../../roadmap/ROADMAP.md). Deliver the missing bounded
Gallery content read and repeatable smoke driver, preserving that owner gate.

## Outcome
An agent using real SDK stdio receives and decodes both images from MCP results,
with canonical identities, persisted parent links and complete attempt evidence.
CTY sees the reviewed demo/images/Gallery records and explicitly replies. This
technical task does not itself close Phase 1 or activate Phase 2.

## Scope
Included: the normative [clarification 1](kickoff-clarification-1.md); a bounded
`gallery_get(artifact_id=..., include_content=true)` PNG byte-read option retaining
the metadata default and existing read risk/31-intent catalog; a repeatable
SDK stdio driver under `scripts/`; focused content/driver tests; a short run guide
in `docs/mcp.md`; disclosed runtime/client preparation; actual runs and F1–F8
comparison. Flow: `health` → `list_resources` → original `generate` → one
`wait_for_job` → `gallery_get` with content → revision `generate` with canonical
`parent_artifact_id` → one `wait_for_job` → `gallery_get` with content.

Use `Illustrious-XL-v2.0.safetensors` + `default`, explicit `execution_target=local`
and `loras=[]`. Predeclare 512×512, batch 1, four steps, CFG 7, Euler/normal,
original/revision prompts and fresh seed allocation for every permitted attempt
before qualification. These smoke parameters are technical choices, not
aesthetic acceptance.

Excluded: Backend endpoint/schema redesign, arbitrary file/URL retrieval,
new MCP intents, video/legacy byte reads, resource downloads, Windows worker
runs/registry/scheduling, general runtime attestation, and CTY's aesthetic or
phase-close decisions. Do not weaken MCP-only, no-retry or real-run rules.

Open questions: K5-1/K5-2 have a normative resolution in clarification 1;
fresh independent kickoff round-2 CLEAR is required before Coding.
Read first: the original [task](task-kickoff-round-1.md), actual kickoff report,
accepted p1-00/p1-00a and p1-01–04 manifests/reviews/acceptances,
[MCP decisions](../../decisions/mcp.md), [MCP guide](../../mcp.md),
[setup](../../setup.md), [runtime-source memory](../../memory/runtime-source-contract-verification.md),
[startup-schema memory](../../memory/backend-startup-additive-schema.md),
[revision lineage](../../memory/ordinary-generation-revision-lineage.md) and
[media identity/locators](../../memory/gallery-artifact-identity-and-locators.md).

## Done when
- [ ] The existing Gallery read intent optionally returns actual canonical static PNG bytes in the common envelope, under the exact selector, root, payload, decode-limit and error contract in clarification 1; metadata, namespaces, other risks/intents and job state are preserved. Check: meaningful registered/SDK stdio byte-identity, limits, unsafe-path, missing/invalid-content and compatibility tests plus applicable suites/standing guards. Evidence: source, commands/results and fault/restoration checks in the manifest.
- [ ] The frozen driver completes three consecutive qualifying original/revision pairs against the real Mac Backend/ComfyUI, printing both canonical artifact IDs/paths and decoding MCP-returned bytes; each pair has fresh persisted Gallery parent/job/request/brief lineage and fresh sampling evidence. Any nonqualifying attempt resets the streak. Check: real manual runs and independent artifact/lineage audit. Evidence: complete timestamped attempts/SDK messages, exact configuration/source, six distinct jobs/artifacts/prompt correlations, payload lengths/digests/dimensions, both Gallery records and new-session persistence reads.
- [ ] No qualifying attempt needs a manual fix, client retry, resubmission or product call outside MCP; one submit and one bounded wait per image are enforced. All failed attempts, preparation, recovery and post-result audit operations are retained and reconciled with unchanged F1–F8/unit rules; none disappears from the baseline comparison. Check: meaningful driver tests and independent script/log review against the strict finite-budget policy in clarification 1. Evidence: preparation/attempt/recovery/audit ledgers, streak resets, full command output and friction comparison, including honest non-exit outcomes.
- [ ] CTY sees the independently reviewed demo, original/revision and Gallery records and explicitly replies in the project channel. Check: owner-demo. Evidence: Producer records CTY's actual message/source identity. Coding delivers the technical candidate; QA reviews D1–D3 at the exact final commit and leaves this item unchecked/pending owner-demo; Producer obtains the reply and records D4 before whole-task acceptance. A send receipt or technical PASS does not satisfy it. Later phase-close roadmap review remains separate.

## Delivery
- Artifact: bounded content read, driver/tests, run guide, `manifest.md`, complete attempt/friction/lineage/runtime evidence and immutable integrity packet. Preserve original task/report/evidence and all prior histories.
- Known limitations: one Mac, one checkpoint/template, static PNG content only, host Gallery access required by the MCP server. The actual client call limit remains unverified; wait retains the 50-second total fallback. If strict qualification fails, report the existing job/attempt and non-exit honestly; no hidden retry or owner-gate waiver.
