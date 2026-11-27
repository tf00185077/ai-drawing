# p2-02a independent kickoff review

Verdict: CLEAR

Issue: [QA AID-218](/AID/issues/AID-218), coordinated by
[Producer AID-217](/AID/issues/AID-217). Reviewed 2026-11-27.
Fixed source: `1f8e1155b3426d62e101e802b564ca761ff9f026`.
The task is unchanged from owner source
`03b86bd22ede433a7c1be4357ffbf392b2d520c4`; no delivery manifest exists.

## Independent reading

My reading: CTY wants executable Phase 2 progress from revised main, replacing
open-ended credential recognition with typed public resource metadata and bounded
protection of actual held secrets. Preserve resource identity, useful public names
and trigger words, internal acquisition state and legacy-row readability. Remove
recognizer-only code/tests and keep evidence small. Producer handles routine
in-boundary choices; three rejected deliveries pause the same product task for
CTY. p2-02a comes before a fresh p2-04 kickoff.

This reading was recorded from the request files and active milestone before
opening the on-disk task; the assignment had already supplied its text inline.
The continuation request separately attributes CTY's quoted words, inherited
versioned rules and Hermes's operator procedure. None is silently attributed to
another author.

Difference: none material. No demonstrated spec conflict requires AMBIGUITY.
No owner question is needed for this kickoff.

## Comparison with the current task

| Item | Kickoff assessment |
|---|---|
| D1 / P1 | Registered list/detail HTTP tests cover the complete allowlist, malformed input and existing filtering, pagination, 404 and 422 behavior. The linked table bounds names/triggers, recommendation keys and values, licenses and diagnostics; removes public `source_evidence`; and rebuilds `source_url` from IDs. |
| D2 / P1 | One real acquisition caller with mocked HTTP and a synthetic configured key reaches provider input, persistence, notes, list/detail/status and captured logs. Raw/URL-encoded held key values and signed queries are the secrecy boundary, together with the scope's URL and fixed transport-field filtering. This does not authorize a credential-looking-text recognizer. |
| D3 / P2 | Existing migration/read tests cover legacy notes, incomplete snapshots, read-only projection and idempotent startup/backfill. Removing public evidence does not remove internal acquisition state or authorize rewriting old rows. |
| D4 / P2 | Recognizer removal is explicit, including its test deletions. Non-recognizer feature cases remain. The manifest records deletions and final Backend/MCP counts; affected historical REGISTRY guards are superseded during delivery review. |

The source contains the named projection, schema, shared filter, acquisition
caller and migration/read fixtures. Their boundaries support the specified checks;
this source inspection does not establish that the future implementation passes.
The shared filter retains its interface for existing consumers. Recipe services,
MCP changes, UI and p2-04 job behavior remain excluded.

## Verification and handoff boundaries

- Apply the settled [verification scope](../../decisions/verification-scope.md)
  over older recognizer/evidence requirements. Third-party public text that merely
  resembles a credential is at most a P3 note. Protect actual held secrets.
- Evidence stays within 2 MB/task and 1 MB/file. Use the full Git SHA for source
  identity; add no inventories, bundles, raw logs or new D-level review mechanics.
- Delivery QA independently runs final-candidate full suites once, reruns active
  REGISTRY guards, and makes one smallest violating production change per `test`
  item. Corrections run affected tests and REGISTRY guards. A further same-class
  finding after the second rejection is AMBIGUITY for Producer redesign.
- ROADMAP Thresholds remain verbatim: after three rejected deliveries of one
  product task, pause for CTY before a fourth correction. Counts carry across
  cards/runs. p2-02a has no delivery; accepted p2-02/p2-03 history stays intact.
- This CLEAR permits Producer to dispatch p2-02a implementation. It does not
  resume withdrawn p2-04 work, alter the owner-library skill, approve aesthetics
  or satisfy the three-real-zero-fix-run phase exit.

Checks run: `git diff --exit-code 03b86bd22ede433a7c1be4357ffbf392b2d520c4
1f8e1155b3426d62e101e802b564ca761ff9f026 --
docs/tasks/p2-02a-allowlist-projection/task.md` exited 0. Report link/size/scope
checks and `git diff --cached --check` passed before publication.

Offline product tests and fault injection: not run; this is kickoff, with no
implementation candidate. Running service, real generation and artifact
retrieval: not checked. No product delivery PASS is implied.
