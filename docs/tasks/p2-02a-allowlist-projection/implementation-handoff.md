# p2-02a correction 1 handoff

## Actual result and count

[QA AID-220](/AID/issues/AID-220) rejected candidate
`8d5f29686555119b1cbcc934cbb38af9d6edaafc`: **R1 / D2 / P1**. Exact report:
`35976f6f183336e67a923df55c15ad2883435928`, retained unchanged in
[review-round-1.md](review-round-1.md). The candidate remains unmerged.
This is **one rejected delivery** of p2-02a across all cards/runs.

Producer read the complete report and checked its mechanism against the candidate:
the shared URL match stops at an apostrophe legal in the received provider query,
so the signature suffix survives filtering and reaches `resolved_download_url`.
The report supplies a registered acquisition reproduction that fails on the
candidate and passes on its starting source. This is received transport data in
the settled held-secret scope. No actual owner-key disclosure is asserted.

## Correction scope

- Carry the unmerged implementation into a new branch/worktree from current
  rewritten main, then correct whole HTTP(S) URL handling so the complete received
  query is removed before storage, including the reported apostrophe case.
- Add the reported case to the real-caller held-secret test. Preserve typed public
  projection, useful creator text, exact configured-key replacement, transport-key
  filtering, internal operation state and legacy readability. Use synthetic keys
  and mocked provider HTTP only.
- Under AGENTS, quarantine only the known pre-existing guard parameter
  `deadline_checks.py::test_real_callers_return_before_held_owner_releases[-0.01-install]`
  in `../p2-03-bounded-download/review-3-evidence/`, with a skip reason linking
  [p2-04](../p2-04-durable-download-jobs/task.md). QA reproduced that diagnostic bug
  on the starting source. Keep its feature/REGISTRY row and all other deadline
  cases; p2-04 owns the product fix and re-enabling the case. Do not weaken assertions.
- Update the manifest with actual corrected source, commands/counts and limits.
  Attribute earlier full-suite results to the rejected candidate. Preserve this
  rejected-round report and the historical p2-02/p2-03 outcomes and counts.

Excluded: credential-label recognition or new synthetic spelling catalogs,
p2-04 product changes, task respec, owner-library edits, main feature merge,
inventories/bundles/raw logs, and full-suite repetition during this correction.

## Verification and continuation

Coding runs the reported regression, affected feature tests and active REGISTRY
guards. Independent QA pins the actual new full candidate SHA, checks R1 and
changed-code regressions, and reruns REGISTRY guards in one invocation. The
[settled verification scope](../../decisions/verification-scope.md) bounds the
correction; no full-suite-per-fault or new review obligations are introduced.

These are Producer's ordinary choices under the existing delegation, not new CTY
words. The cleared task and ROADMAP remain unchanged. A further same-class finding
after rejection 2 is AMBIGUITY for redesign; at rejection 3, pause the same product
task and ask CTY before any fourth correction. New cards never reset the count.
