# Independent kickoff review

Verdict: CLEAR

Own review: [AID-137](/AID/issues/AID-137). Coordination consumer: [AID-136](/AID/issues/AID-136). Review method: live `reviewspec-review` with `reviewspec-core`.

## My reading

Written before opening the repository `task.md` or comparing the source checkpoints, from CTY's exact request, canonical Goal, and the four named native engineering/QA records.

CTY's 2026-11-23 words ask to switch Producer, coding agent, QA agent and Auto Dreamer to the live role skills in `my-skills`, activate those four, and have Producer make its first work assessment. Those words do not themselves request a new Gallery feature, select an artwork, approve installation/deployment, or reopen frozen integration. The standing Goal separately authorizes Producer to choose ordinary necessary engineering work toward the existing MCP/LoRA/simple-UI journeys, with independent QA and CTY's aesthetic responsibility preserved.

For M1 image and revision inspection, a user must be able to enter/reload the existing Gallery page, inspect the recorded seed without decimal corruption, and read the initial metadata and full prompts with usable images/controls. The prior independent routing/seed review records a failing baseline followed by exact-candidate PASS; the readability review likewise records a meaningful parent failure followed by exact-candidate PASS. Rebuilding these already accepted repairs on the same input would be redundant. If the current canonical source has advanced elsewhere while still lacking those repairs, a minimal isolated forward-port is a reasonable necessary source step. It must preserve the newer source and all dirty authority inputs, reuse rather than erase the prior evidence, and receive its own verification for the new composition.

The result I would expect is one precisely identified source candidate and evidence for those existing behaviors, with separately resolved Vite/Vitest caches. The earlier Vitest shared-cache write and lack of a preimage remain historical limitations. This work cannot establish installed UI, new MCP/generation execution, full M1 completion, canonical adoption, deployment, a replenished operation allowance or CTY aesthetic acceptance. Any subsequent integrated journey or installation needs its own disposition under the existing freezes.

Evidence read before this section was written:

- [Routing/seed engineering handoff](/AID/issues/AID-115#document-engineering-handoff), revision `4cb74b94-9e54-4941-8ff2-414cd096a458`.
- [Independent routing/seed QA](/AID/issues/AID-116#document-qa-report), revision `b9b69e24-788d-41fb-b6aa-d578becc27c6`: baseline 14 failed / 8 passed, repaired focused 22 passed and exact original/seed inspection; all results belong to that earlier review.
- [Readability engineering handoff](/AID/issues/AID-122#document-engineering-handoff), revision `d79ab96b-8aab-4b70-84c7-54300f78d1b2`.
- [Independent readability QA](/AID/issues/AID-123#document-qa-report), revision `8448ada7-f9c4-427d-b010-eb60c8270b52`: parent initial modal 655/669 client/scroll width and clipped seed, candidate PASS including 639/640 reflow; initial shared Vitest cache write disclosed and later explicit-cache check bounded.

## Difference

None material between my reading and the exact proposed task. The owner-method request is not being relabeled as a Gallery feature request: necessity follows from the standing existing-UI/M1 purpose, the independently observed defects, and the independently verified source gap. This is a new composition of accepted repairs on an advanced checkpoint, not another repair round on the already accepted candidate. It neither reopens canonical integration nor consumes/replenishes a product-operation allowance.

The repository brief was opened only after the My reading section above was written. Its SHA-256 is `9c4d485e7993861d3a53a900dfd5ecf7a36f90d58359df60cdb9ad17007b42e2`. No `manifest.md` exists: this is kickoff adequacy, not delivery PASS.

## Independent source findings

Read-only Git inspection confirms current branch `main`, HEAD `cd92ad4d8b0ef74e8d8ce62b1d4770217fc4dc27`, tree `a9ac931e9c8a51ace482d8206b4881937d93146c`. The following blobs and Git modes are identical on that base and the observed pre-repair input `c7e238304e883baf6e7c509713216250640e3683`:

| Path | Identical blob | Mode |
| --- | --- | --- |
| `frontend/src/pages/Gallery.tsx` | `0ef46b3539e1f4583147f0b0eb2e1e27d1d95ae0` | 100644 |
| `frontend/src/pages/Gallery.test.tsx` | `5960af62c56d3f5f19dce03492b415b8ad73721a` | 100644 |
| `frontend/vite.config.js` | `ebafceb4aff298142b101918968442452334e1fb` | 100644 |
| `frontend/package.json` | `82ed2a603759ae7a34392eba8bc0f630b8696a7d` | 100644 |

`frontend/src/api/gallery.ts` is absent in both trees. The entire `frontend/` tree and `backend/app/schemas/gallery.py` also have no delta between the observed input and new base. Current source still uses `res.json()`, numeric `seed?.toString()`, a broad `/gallery` proxy, unconstrained image/flex metadata columns and unwrapped parameter rows. This establishes the source gap; I did not execute those defects again in this kickoff.

The accepted routing/seed candidate `0dfd958df04703791dc3415cf5f0e522ef7961cc` has sole parent `c7e238304e883baf6e7c509713216250640e3683`; accepted readability candidate `d232bc7dd0dfe9815ffb96e883ed216dc526be96` has sole parent `0dfd958df04703791dc3415cf5f0e522ef7961cc`. Their targeted deltas are respectively six and five paths, with overlap in Gallery and setup-guide; the combined frontend delta is eight paths. The new base has additional Backend content, including `backend/app/services/argus_mlx_i2v.py`, its tests and `backend/workflows/discord_minimax_h3_i2v_fixed.json`, which the old full candidate lacks. Other Backend files and MCP documentation/tests also differ. Replacing the current tree with that old candidate would discard unrelated work. A targeted port is justified; no full-tree replacement or merge is needed to establish this candidate.

The current Gallery schema remains `seed: int | None`; rerun input remains only `execution_target`, located by Gallery ID. The old parser protects integer lexemes before JSON parsing and the old component retains the string display model. Its tests supply raw integer tokens rather than already-rounded JavaScript numbers. These are relevant reusable checks, not proof that a future composed candidate passes.

## Brief adequacy against D1–D5

| Item | Kickoff assessment |
| --- | --- |
| D1 | Required page entry/reload, slash/query and separate asset-path checks cover the observed route collision; synthetic upstream traces avoid current product services. |
| D2 | Raw-token red/green fixtures, null/prompt preservation and mocked ID-based rerun checks cover precision without submitting jobs or changing the public numeric contract. |
| D3 | Initial fragment visibility, full content, aspect ratio, controls and vertical scrolling at 540/639/640/1200 px cover the observed overflow and both sides of the breakpoint. Synthetic evidence is correctly bounded. |
| D4 | Exact base/parent/delta, canonical preservation, explicit separate Vite/Vitest caches and exit-bearing compatibility evidence protect the newer checkpoint and expose failures/side effects. |
| D5 | A frozen candidate, per-item manifest, native evidence and independent delivery review provide an inspectable handoff. Neither previous PASS nor this CLEAR accepts that future candidate. |

Implementation notes within the existing brief, not new owner questions:

- The old layout script explicitly visits real Gallery record 4446 on Backend 8001 and omits fixture width 639. It must be adapted for this task's synthetic-only preview and all four required widths; copying and running it unchanged would violate this brief. Its setup-guide command paragraph must be reconciled accordingly. Browser checks should retain the prior independent QA's stronger control visibility/hit-test evidence rather than only button width.
- Reusing the seed repair adds `text()` to the existing test response helper while retaining the rerun assertion. Record any existing-test change in manifest deviations as required by `reviewspec-core`.
- The initial shared Vitest results-cache write in the prior readability QA remains disclosed; a final explicit-cache pass did not erase it. This task must resolve Vite and Vitest destinations separately before running either.
- Actual installed integration/real-image journey evidence remains a later decision under existing freezes. Synthetic preview PASS cannot close that gap or answer the pending artwork preference.

There is no demonstrated owner-intent conflict, missing input or need for an owner question. Producer can consume CLEAR for this exact brief and arrange Coding, followed by a separately owned delivery review with Coding as its native prerequisite. That next handoff remains Producer's action.

## Checks, reads and limits

Actual checks in this kickoff were file/native-document reads and Git object/delta inspection only: `git status --short`, `git rev-parse HEAD`, `git branch --show-current`, `git show -s --format`, `git ls-tree`, scoped `git diff --name-status` / `--stat`, and pinned `git show` source reads, plus SHA-256/mode inspection. These completed with exit 0. Empty scoped diff output establishes identical compared source; it does not establish runtime behavior. Raw identities, changed-path lists and preservation preimages are retained in `source-checks.json` in the issue evidence package.

Final read-only preservation check also exited 0: HEAD/main/index SHA-256 remained unchanged, all 14 captured dirty/authority/request/task input files retained their bytes and numeric modes, the four current frontend working blobs still matched the pinned base, and the parser and delivery manifest remained absent. See `preservation-final.json`. This is the checked source/authority scope, not a full audit of ignored runtime data or shared tooling caches. No shared tooling runner was invoked.

Physical required reads: installed `using-superpowers` SKILL.md and Codex host reference; current live `reviewspec-core`, `reviewspec-review`, `paperclip-task-handoff`; canonical installed-source `paperclip` SKILL.md and artifacts reference; common-original `verification-before-completion`. Canonical `AGENTS.md`, `README.md`, `docs/agent-reading.md`, `docs/GOAL.md`, `docs/INDEX.md`, team README/QA contract/skill-bindings/channel-routing; exact owner-request file; memory index and the three designated Gallery/cache refs; the four native handoff/review documents with revisions above; the native root plan's acceptance/limit context; then task.md, setup-guide, current Gallery/test/App/Vite/package/schema and pinned parser/component deltas/tests/routing/layout fixtures/script. Producer ROADMAP/CURRENT/PROGRESS were not used to select different work. The known schema comment referencing missing `docs/api-contract.md` is stale; current source schema is available and was used, so no missing required input blocks this kickoff.

No tests, builds, browser/product probes, code/runtime/memory changes, production operations, commits/ref/index writes, peer dispatch/wake, parent mutations, new question cards or aesthetic judgment were performed. Only this role-owned repository report and this QA issue's native deliverables are written. Prior FAIL/PASS and frozen candidates retain their identity and scope.

Memory candidates: None. The Gallery precision/routing/layout and shared-cache lessons are already covered by the three designated canonical memory refs; this kickoff adds a task-specific source comparison rather than a new reusable rule.
