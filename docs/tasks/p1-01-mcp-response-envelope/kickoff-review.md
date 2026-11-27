Verdict: CLEAR
Review round: 2

Review type: independent kickoff only, 2026-11-24. QA: [AID-156](/AID/issues/AID-156).
Fixed specification/source: `496cee2f842dc9386d336afb237075bf952271ce`.
Task: `docs/tasks/p1-01-mcp-response-envelope/task.md`.
Task SHA-256: `3b1cc30be86041c671627bb29720d4c973c8c5a7712b339437f94a3bb1ccd6a6`.
Done when count: **4**. [p1-02 round-2 verdict](../p1-02-mcp-tool-consolidation/kickoff-review.md): **CLEAR**.

## Independent owner reading and combined-contract comparison

My reading: Phase 1 should let an agent parse every MCP result once and choose
one tool per intent with a truthful risk. Preserve generation control, revision
lineage, Gallery locators and needed prompt/preset/admin capabilities; retain
Civitai/LoRA names, remove the three specified MCP generation entries, and ship
envelope/consolidation together. Wait, health/workers, repeatable smoke and the
three-real-run phase exit retain their existing order. Routine technical choices
are delegated to Producer; aesthetics/phase close remain CTY's.

I saved this reading after reading the preserved [owner direction](../../requests/2026-11-24-proceed-within-project-boundaries.md),
[MCP decisions](../../decisions/mcp.md) and active roadmap, before opening the
repository task files in this run. The inline assignment had already supplied
their text; this is independent reasoning, not a blind review.

Difference: none. I verified unchanged task bytes against the first fixed source,
then assessed the revised shared context and compose/save contract afresh.
The clarified `request_validation_failed` rejection fits D1's pre-body validation
and D3's documented error contract. The replacement save retains Backend codes
and hints under D2, including prompt `revision_conflict` (distinct from generation
`revision_request_conflict`). Nothing adds a tool, bypasses an envelope or asks
p1-01 to change the Backend. K2-1's resolution in p1-02 introduces no new p1-01
ambiguity. Prior CLEAR alone was not the basis for this reaffirmation.

## Acceptance items are judgeable

| Item | Verdict | Required later delivery evidence |
|---|---|---|
| D1 — every registered success/failure envelope | CLEAR | Catalog-parametrized registered MCP calls with mocked success/failure below real wrappers; Backend HTTP, connection and validation cases, including non-LoRA argument rejection before the body. Include retained Civitai/LoRA and temporary ping. After removal, the three excluded tools are not registered. |
| D2 — codes/hints/status preserved | CLEAR | Known Backend codes retain canonical code and recovery hint; unknown HTTP errors retain status in the documented generic error message. Preserve LoRA safe diagnostics and uncertain-admission job ID/do-not-resubmit guidance. The clarified save path must preserve prompt conflict errors without automatic overwrite/retry. |
| D3 — documented envelope/error list | CLEAR | Read `docs/mcp.md` against the actual helper, validation boundary and all public error branches. Same success/failure parse contract, including the legacy-save rejection and replacement-write hint. |
| D4 — full MCP suite | CLEAR | Full delivered MCP suite with an isolated test root and `--timeout=60`, exact command and summary. Preserve feature checks when updating intentional old-shape assertions; additional suites/registry guards follow actual change scope. |

Static source is unchanged: 40 baseline registrations/catalog entries still have
three plain-text, 18 JSON-string and 19 dict contracts. `ContractFastMCP` in
`mcp-server/mcp_server/server.py:94` specializes pre-body failures only for LoRA
start; helpers alone cannot prove the general boundary. `tools/responses.py`
and prompt-specific error helpers show why common wrapping must preserve error
meaning. These observations support observable future tests, not an assertion
that the proposed behavior is already implemented. The first source audit is
reused only after component-tree and exact-input equality checks.

## Baseline and friction preservation

The shared context retains every original row unchanged:

| Item | Units | Obligation and remaining boundary |
|---|---:|---|
| F1 — test setup | 1 | p1-05 binds interpreters/timeout setup; no packaging work here. |
| F2 — stdio bootstrap | 1 | Preserve explicit source/interpreter/Backend/Gallery binding; repeatable driver/setup is p1-05. |
| F3 — mixed parsing | 1 | Direct p1-01 fix, applied/documented across p1-02's entire delivered catalog. |
| F4 — runtime identity | 6 | Accepted repair identifies its controlled launch only; general visibility is p1-04. No attestation subsystem/restart here. |
| F5 — revision contract | 1 | Preserve `revision_context` and canonical parent artifact IDs; old baseline stays legacy/null; p1-05 rechecks deployed persistence. |
| F6 — repeated polling | 11 | Retain generation status/cancel; bounded wait is p1-03. Original had no timeout/resubmission. |
| F7 — execution visibility | 1 | Direct queue/history diagnostics remain disclosed; wait/result is p1-03, health visibility p1-04. |
| F8 — byte retrieval | 1 | Preserve distinct image/artifact IDs and supported locators; accepted colocated host-path proof does not certify remote URLs. p1-03/05 retain result/retrieval obligations. |
| Total | 23 | Eight incidents; later repair subtracts no original unit. |

Accepted repair `b6d58468147e11a21b3d7a26ea25ed4353a28a28`, independent review
`3d5d8902a89a8c3c8994ed89e944fcaee0260577`, publication
`a963386a3141194a6a08853d89224b548d112aa2` retain their actual limited acceptance.
The original unsuccessful no-repair retrieval/revision is not relabeled.

## History, verification and handoff

Round 1 was [AID-155](/AID/issues/AID-155), source
`d1ffb8d8d9db12f728ed98704e966e76489faafb`, report commit
`b32ac4fcabf8c57e2370aa81bb06f6708863ff22`: p1-01 CLEAR / p1-02 AMBIGUITY
K2-1. Accounting remains one p1-02 kickoff ambiguity, clarification round 1,
this kickoff review round 2; no p1-01/02 implementation delivery, delivery
rejection or delivery review exists. Both `kickoff-review-round-1.md` mirrors
are byte-identical to that exact report commit and are left unchanged.
The separate p1-00a history stays one delivery rejection, correction round 1,
delivery review round 2.

I read the preserved owner requests, approved map, both actual task files,
clarification, revised shared context, original reports, original baseline
manifest/review and corrected repair manifest/acceptance/final and historical
reviews. Neither reviewed task has a `manifest.md`; this is kickoff only.
Guides and skills: AGENTS, project memory/INDEX, team/QA role/bindings,
reviewspec-core, reviewspec-review, paperclip-task-handoff, Paperclip,
Git/worktree and verification-before-completion.

Recipient-owned worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-156-kickoff-review`,
branch `aid-156-fixed-kickoff-round-2`, created at the full fixed SHA above.
Checks used fixed Git objects, AST/schema inspection, `git diff`, `git ls-tree`,
SHA-256 and the uploaded static audit:

```sh
python3 "$PAPERCLIP_RUN_SCRATCH_DIR/kickoff-round2-audit.py"   /Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-156-kickoff-review   "$PAPERCLIP_RUN_SCRATCH_DIR/round2-audit.json"
git diff --check
```

The static audit exited 0: both digests/counts match; 40 catalog/registration/
original-discovery names and dispositions, 29 provisional destinations, 23 units/
eight incidents and unchanged source/evidence inputs reconcile. All 20 original
baseline files remain equal to `3081952e0ba12a339ab7e60b8081ede61a131b7f`;
all 91 repair-folder files equal the first kickoff source, with corrected
manifest/raw flow and final review also equal their named immutable commits.
The changed specification paths are documentation only. Backend/MCP and the
other checked product trees equal the prior source. The only tool-map row
changes concern composition and saving; the F1-F8 section is byte-identical.

I downloaded all four official AID-155 artifacts. Both standalone reports and
the patch equal the exact Git bytes. The archive has 17 members including its
receipt, with all 16 indexed non-self files verified by size/hash; all nine
reference snapshots equal their named first-source Git objects. This identifies
the prior static audit being reused; it is not an old clearance substituted for
this combined-contract review. Fresh report hashes, full report commit, exact
patch, audit source/result and fixed reference snapshots accompany the AID-156
uploads. Outgoing document links, allowed changed paths, whitespace and package
bytes are checked separately before handoff.

Verification boundaries:

- Offline software suites: none run. Static specification review changes no
  software. Historical repair Backend `1900 passed / 124 Windows-only skips`
  and MCP `314 passed / 4 exported-fixture skips` remain historical evidence;
  they do not verify future envelope/consolidation code.
- Running service: no new product probe, restart, private configuration or
  canonical Backend venv access/change. No loaded-source claim is inferred
  from a documentation commit.
- Real generation: none. Accepted evidence remains one original/revision pair,
  with a cached deterministic original and persisted canonical lineage.
- Generated artifact retrieval: no new live image-byte read. Accepted proof is
  decoded bytes from both Gallery tools' unmodified returned host paths for a
  colocated Mac filesystem client only. Remote/relative-URL consumption remains
  unproved. Review-file upload readback is a separate integrity check.
- Errors/cancellation/recovery/duplicate submission/security: static contracts
  only; no new live behavior certification. Existing job IDs must be inspected
  before resubmission after timeout. No worker exposure, data cleanup or changes
  to shared main, active AID-151 runtime/private files or retained data occurred.

Both fixed specifications now have explicit CLEAR. Producer on
[AID-143](/AID/issues/AID-143) owns separate Coding and delivery-QA cards, with QA
natively waiting on Coding. Delivery QA must read both actual manifests at one
combined exact final commit and return independent PASS before combined merge/
push and p1-03 release. New candidate code requires a new exact-commit review.
This kickoff adds no registry coverage, software acceptance, release of p1-03,
aesthetic/demo approval or phase-close authority.
