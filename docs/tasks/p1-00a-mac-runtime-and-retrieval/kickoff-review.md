Verdict: CLEAR

Reviewed specification/source: `edc91b096965f5c05ed58705441b96e143132bbf`
Task SHA-256: `be8814ca4f3bbaaa16e14f8a7b236a1fd5c34d0d1cd4a2ee88570631bea06359`
Review date: 2026-11-24 (UTC)
QA card: [AID-150](/AID/issues/AID-150)
Coordinator: [AID-142](/AID/issues/AID-142)

This clears the fixed specification for Coding dispatch. It does not accept a repair delivery, certify a running service, or release dependent work. There is no repair `manifest.md` at this snapshot; that is the expected kickoff state.

## My reading, recorded before repository comparison

I first read AGENTS, memory/index, README, the active roadmap/CURRENT, team and operating rules, and both owner source records: [fresh planning](../../requests/2026-11-24-fresh-producer-planning.md) and [follow-through](../../requests/2026-11-24-proceed-within-project-boundaries.md). I also read the authenticated `local-board` comment `afe71bd8-7e9e-434b-af00-813f94c8d131` on [the source issue](/AID/issues/AID-141#comment-afe71bd8-7e9e-434b-af00-813f94c8d131). The initial exact owner quotation requests a new run; broader initial planning language is Hermes intake. The later comment explicitly relays CTY's instruction to proceed within existing boundaries and adopt ordinary reference choices. These sources must not be collapsed into a claim that CTY individually chose a checkpoint or accepted aesthetics.

I then read the accepted baseline manifest, raw stdio, flow/count evidence, QA report and Producer acceptance: execution `c02ebe75a25b949ca3408b5f5bfb0569225832cc`, independent review/registry `37f016135388a7c49a6445077b64751ab78f767f`, and acceptance at the fixed specification snapshot. Relevant memory covers runtime-source verification, ordinary revision lineage, compute scope and explicit empty LoRAs.

My expectation from those sources: repair the two demonstrated boundaries with existing mechanisms, identify the source actually loaded by the Backend, provide a locator the intended client consumes, and prove one fresh original plus one new generate-based revision with decoded bytes and persisted canonical-artifact lineage. Runtime/configuration/docs can suffice; product source changes need a demonstrated reason, meaningful regression coverage and independent exact-commit review. Preserve existing configuration, database/Gallery locations, all data and the original no-repair accounting. Keep later Phase 1 redesign and the three-run exit separate.

This reading was saved on this QA card at `2026-11-24T08:41:32.637Z`, [before opening the repository task for comparison](/AID/issues/AID-150#comment-db48c6d4-75c6-4e2d-b359-75dfc4051605). The assignment already supplied the specification inline; this is a source-derived reading recorded before repository comparison, not a claim of a blind review.

## Comparison and concrete differences

Difference from my source-derived expectation: none requiring a specification change or owner answer.

The repair deliberately changes the acceptance threshold from the baseline. Baseline D2 permitted a documented blocker; this task D3 expressly rejects a blocked journey. The accepted baseline proves job `88891201-d6c1-4fad-a40d-98622b32f0ed` completed, with image `4447` and canonical artifact `3862`, but only metadata was retrieved and context remained null. Its 90 transcript rows reconcile to 19 JSON-RPC pairs, 17 tool calls, one generation and 12 status calls. The attempted relative URL failed locally before HTTP. Missing bytes or a broken HTTP endpoint cannot be inferred from that exception.

The fixed task requires diagnosing those boundaries rather than presupposing a source defect. Its configured locator/client path, preservation of working absolute URLs and existing tool names/arguments/fields allow the smallest correction. A returned host path counts only if the intended client actually reads it. Neither inventing an origin after failure nor copying the output separately satisfies the stated proof. The current source already declares revision context; an old runtime's missing contract does not itself justify changing that source.

The adopted `Illustrious-XL-v2.0.safetensors` / `default`, `loras=[]`, explicit local target and small baseline parameters are delegated technical choices. No reconfirmation is needed. CTY retains aesthetics, demo and phase-close acceptance.

## Done when review

These are judgments about whether the five criteria define observable, bounded outcomes. None is marked delivered by this kickoff.

| Item | Kickoff assessment | Observable delivery requirement and scope |
|---|---|---|
| D1 — identified runtime and revision contract | CLEAR | Full clean source SHA/fingerprints, launch command/cwd, process identity, effective non-secret data/URL settings and live schema identify the actual MCP Backend. Source/process transition, active-job check and any restart/recovery must be disclosed. Checkout hash, cwd or ping alone cannot pass. This is bounded deployment evidence, not a new attestation subsystem. |
| D2 — consumed locator and original bytes | CLEAR | Raw tool result and exact consumed locator accompany fetch/read receipt, byte size, SHA-256 and successful image decode. Baseline artifact accessibility must also be demonstrated without rewriting its record. Any locator change needs behavioral checks, including preservation of working absolute URLs; both Gallery tools are within the stated locator boundary. Metadata success and a constructed alternate path alone cannot pass. |
| D3 — fresh original/revision and lineage | CLEAR | One ordered current-tool stdio journey retrieves both images. It uses a new request reference shared by the pair, a new brief revision and a new generation request with the fresh original's canonical artifact ID. Status and Gallery records must persist context and Backend-derived parent job/request/brief matching the original. Image ID is a different namespace; `gallery_rerun` is insufficient. Timeouts require checking the existing job before resubmission; interventions remain visible. |
| D4 — regression checks | CLEAR | Necessary source changes require meaningful behavioral coverage and passing changed-component checks; a changed Backend/MCP component requires its full suite. Commands, exit codes, durations, isolated roots below TMPDIR and `--timeout=60` make results inspectable. Reviewed unchanged-source results may be reused only with source equivalence recorded and applicable dependencies/environment disclosed. No feature-test removal to hide a failure or implied Frontend/Windows certification. |
| D5 — exact delivery and baseline separation | CLEAR | Manifest, complete redacted transcripts/configuration, byte receipts, change inventory, exact commit and uploaded deliverables make independent review possible. F4/F5/F8 must be resolved for this journey; F1/F2/F3/F6/F7 retain explicit later mappings. Original 23-unit/eight-incident accounting and legacy null lineage stay intact; repair interventions are reported separately. One repaired pair does not establish zero-intervention phase exit. |

## Error handling, recovery and boundaries

The active-job check and preservation requirement constrain the authorized restart; they do not authorize discarding in-flight state. The timeout rule prevents treating an uncertain submission as failure and duplicating it. Cancellation is not a newly required feature or a reason to add a general queue/durability redesign; any cancellation/recovery actually used must be disclosed. An unrelated failure returns to Producer for scope, rather than expanding this repair.

Configuration/receipt redaction and preservation of existing data locations apply to runtime work as well as source edits. The task preserves all models, datasets, outputs and Gallery records, introduces no worker-control exposure, and excludes downloads, workers, training, video and architecture changes. Response envelopes/consolidation remain p1-01/02, waiting p1-03, general health p1-04 and permanent smoke/three consecutive zero-intervention runs p1-05.

## Verification performed and delivery gate

I used Git objects and the isolated branch `aid-150-p1-00a-kickoff` at `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-150-kickoff`; the shared checkout remains on `main`. Checks included fixed-file hashing and link resolution, raw transcript/count reconciliation, baseline checksum verification, and source-tree comparison. Backend tree `bb4bccbb9b4be913d11f7eeceee075bfd5377a34` and MCP tree `8e1a6251e39b6f06a65fd700da857b745122921d` are identical between accepted execution and this specification snapshot. No product source/test changes are present in that interval. All task links resolve; this review adds only this file.

Offline suite evidence inspected: Coding's accepted full Backend result is `1900 passed, 124 skipped, 77 warnings in 43.84s`, exit 0, wall 49.973s. The independent accepted QA report records the same counts in 44.13s, exit 0, wall 48.177s, and audits all skips as Windows-only. This kickoff runs document/evidence integrity checks, not software suites, and makes no new suite-pass claim. The existing registry's full Backend guard remains unchanged. No live service probe, runtime change, new generation or generated-image byte retrieval was performed here. Those delivery outcomes remain unverified.

Producer may read this CLEAR and create separate Coding and exact-commit delivery-review cards. Coding delivers a manifest/evidence at a named final commit; independent QA checks that commit and the applicable tests/real boundaries before PASS. That PASS precedes merge/push and dependent release. New code after review requires another exact-commit review. No merge/push, disposition on Producer's card, aesthetics or phase-close acceptance is performed by this kickoff.
