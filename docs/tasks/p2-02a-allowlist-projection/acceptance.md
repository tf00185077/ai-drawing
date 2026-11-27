# p2-02a acceptance

Producer accepts corrected candidate **`3e70e04c5bb8fb104bcf0324d19d99629741cd4c`**
from [Coding AID-221](/AID/issues/AID-221), after reading independent
[QA AID-222](/AID/issues/AID-222) review 2 **PASS** at
**`28df4bcf165f2cfd2136a00b0e1b46fd77267175`**. The exact candidate, report and
generated REGISTRY are merged at **`1bbeb166020a70c5f47997e55b063ce84d1a383c`**.
Coordination: [Producer AID-217](/AID/issues/AID-217).

## Accepted behavior

Public resource fields use the typed allowlist: bounded creator names/triggers,
closed recommendation keys and license values, fixed diagnostics, and source URLs
rebuilt from IDs. Internal acquisition evidence stays out of the public projection.
The old credential-label recognizer and its eight test modules are removed.

The shared filter protects actual held raw/URL-encoded key values, received download
URL queries/userinfo and auth transport. R1's valid apostrophe no longer leaves a
received signed query in stored columns; the real acquisition caller guards it.
Old rows, notes and files remain readable and preserved, and retained state/identity
behavior remains covered. See the [manifest](manifest.md), [review](review.md) and
[resource-record topic](../../resource-records.md).

The accepted task retains **1 rejected delivery** across cards/runs. The rejected
`8d5f29686555119b1cbcc934cbb38af9d6edaafc` is not merged into main ancestry;
its [first FAIL report](review-round-1.md) remains unchanged. This PASS adds no rejection
and resets no history. Historical p2-02 and p2-03 acceptances/counts are unchanged.

## Verification

- Candidate changed-path comparison:
  `git diff --exit-code 3e70e04c5bb8fb104bcf0324d19d99629741cd4c 1bbeb166020a70c5f47997e55b063ce84d1a383c -- <all paths changed by the candidate from 39737296217ec1bb8f14df2744b85a0530d4b0c0>` — **exit 0**.
- QA report and `REGISTRY.md` comparison against `28df4bcf165f2cfd2136a00b0e1b46fd77267175`
  at the merged SHA — **exit 0**. Producer also checked exact published full SHAs,
  direct rewritten-main ancestry, approved task/history preservation and whitespace.
- Independent correction run: **1071 passed / 3 skipped**, exit 0, one invocation,
  `--timeout=60`. Overlapping subsets: affected **436 / 1**, REGISTRY **877 / 3**,
  independent R1 **1 passed**. These are not additive totals. The real-caller R1
  guard fails when only the rejected URL handling is restored, then passes on the
  corrected candidate. QA restores the candidate before the final run.
- REGISTRY: **51 active / 40 superseded**, generator exit 0. Only approved
  recognizer meanings are superseded; retained p2-02 identity/migration/read guards
  and p2-03 deadline guards remain active, with four p2-02a items added.
- Earlier full suites belong only to rejected `8d5f2968`: Backend **2340 / 125**,
  MCP **672 / 4**, frontend **226 / 1**, successful build. Bounded correction review
  reuses that attributed evidence under [verification scope](../../decisions/verification-scope.md),
  without claiming those full runs qualified the corrected SHA.

The two known immediate-expiry install skips retain task-linked reasons; p2-04 owns
their diagnostic fix and re-enabling. Other parameters pass. The remaining optional
MCP lifecycle-export skip is inherited. Producer ran merge/docs checks, with no
repeated product suites or evidence bundles.

Running service: not deployed/probed. Real generation: not run. Artifact retrieval:
synthetic fixtures only; no live model/Gallery retrieval. Windows was not run.
No artistic acceptance, Phase 2 exit or acceptance of the existing p2-04 WIP follows.

## Continuation

Adopted ordinary recommendation: accept this exact correction and start a fresh
independent kickoff of the [revised p2-04 task](../p2-04-durable-download-jobs/task.md)
from published accepted main, then new Coding and exact-commit delivery QA cards.
The old p2-04 kickoff is superseded. ROADMAP Thresholds remain verbatim: at three
rejected deliveries of a task, pause and ask CTY before another correction; cards
and fresh runs never reset the count. Agent-facing work and real qualification follow.

Memory review: reviewed; no change. The durable behavior is in the resource topic,
the settled decision and the permanent real-caller guard; no incident log is added.
