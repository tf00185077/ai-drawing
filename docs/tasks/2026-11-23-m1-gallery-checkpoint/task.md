# Task specification

## Task
Forward-port the accepted Gallery routing, exact-seed and initial-readability fixes onto the current canonical source checkpoint as one isolated, reviewable M1 candidate.

## Purpose
M1 asks whether a user can obtain and inspect an image and its revision through MCP and the existing UI. This task supplies the current-source UI candidate needed before any installed-version decision. The canonical checkpoint `cd92ad4d8b0ef74e8d8ce62b1d4770217fc4dc27` retains the exact pre-repair Gallery and Vite blobs; the independently accepted fixes are on another branch. Replacing the whole checkpoint with that branch would remove newer Backend work. Reuse the verified frontend repairs while preserving the current checkpoint. This is source composition and isolated verification, not protected canonical adoption or a product-operation retry.

## Outcome
Producer receives one frozen candidate based on the current checkpoint in which direct Gallery entry/reload, exact large-seed display and readable initial metadata work together. Independent QA can judge that precise composition without reconstructing priorities or granting deployment.

## Scope
Included:
- Base the isolated candidate on `cd92ad4d8b0ef74e8d8ce62b1d4770217fc4dc27`. Reconcile drift explicitly if that input is unavailable; do not silently change the base.
- Reuse the targeted frontend changes and meaningful checks from `0dfd958df04703791dc3415cf5f0e522ef7961cc` and `d232bc7dd0dfe9815ffb96e883ed216dc526be96`, following source inspection rather than replacing an entire old tree. Their observed pre-repair input is `c7e2383`.
- Expected paths: `frontend/src/pages/Gallery.tsx`, its tests, `frontend/src/api/gallery.ts`, `frontend/vite.config.js`, Gallery routing/layout checks and fixtures, and only directly affected paragraphs of `docs/setup-guide.md`. Explain any necessary change outside this scope before proceeding.
- Use prepared component dependencies; keep Vite, Vitest and build outputs in task-owned locations. Run focused compatibility checks and the existing meaningful regressions. Browser/layout fixtures and a task-owned loopback preview may be used with synthetic responses; no existing product service is controlled or queried in this task.
- Supply the frozen commit/tree, parent and source delta, a manifest mapping D1–D5 to actual evidence and limits, and an inspectable native handoff. No coding starts until the separately owned QA kickoff returns CLEAR for this exact brief. Delivery receives a separate QA card with Coding as its native prerequisite.

Excluded: canonical main/ref/index/working-source adoption, full-tree merge of the old candidate, Git transaction helper/rebinding/preflight, private runtime/DB inspection, Backend/MCP/LoRA changes, current service or real Gallery HTTP/MCP queries, deployment, installation/downloads, generation/rerun/training, Windows/remote operations, service or ComfyUI restart, and CTY aesthetic judgment. Preserve all originals, datasets, models, frozen candidates and unrelated edits. Existing D0/full-start and canonical-integration freezes are unchanged.

Open questions: any source incompatibility introduced by the new checkpoint must be demonstrated. Do not invent a new feature or widen this package into the old maintenance route. Installation and integrated real-journey verification are subsequent decisions after the exact source candidate passes QA; this task cannot establish their authority or success.

Read first:
- Shared current canonical `AGENTS.md`, `README.md`, `docs/agent-reading.md`, `docs/GOAL.md`, `docs/INDEX.md`, `docs/team/README.md`, the assigned role contract and `docs/team/skill-bindings.md`; physically read the selected live role methods and common startup package. Historical branch instructions are not current authority.
- Owner words: `docs/requests/2026-11-23-role-skills-and-first-reasoning.md`; standing product/coordination authority in Goal. This request selects live methods and four active roles; it does not answer the artwork card or grant deployment.
- `docs/memory/MEMORY.md`, `gallery-seed-precision.md`, `gallery-document-asset-routing.md` and `frontend-shared-cache-isolation.md` in that directory.
- [Original routing/seed delivery](/AID/issues/AID-115#document-engineering-handoff), [independent routing/seed review](/AID/issues/AID-116#document-qa-report), [readability delivery](/AID/issues/AID-122#document-engineering-handoff), [independent readability review](/AID/issues/AID-123#document-qa-report). Retain original FAIL/PASS and cache-exception history; previous PASS is evidence to reuse, not acceptance of this new base.
- `docs/setup-guide.md`, current and pinned Gallery/API/Vite/test sources, `frontend/package.json` and relevant Backend Gallery schema read-only. Do not use Producer planning/history documents to select different work.

## Done when
- [ ] Direct navigation and reload of `/gallery` and `/gallery/`, with and without a query, reach the React page; nonempty Gallery image subpaths still proxy as assets. Check: test. Evidence: focused routing regression results on the identified new base/candidate and task-owned preview request traces using synthetic assets.
- [ ] Raw JSON integer seed tokens beyond JavaScript's safe integer range retain their exact decimal display; null, prompt text and ID-based rerun behavior retain their contracts without submitting a job. Check: test. Evidence: raw-token fixtures and focused Gallery tests; show a meaningful failing baseline and passing candidate, reusing prior check sources where applicable.
- [ ] The initial modal shows the full seed and unbroken metadata without horizontal scrolling at 540, 639, 640 and 1200 px; full prompt/negative content, image aspect ratio and controls remain usable with vertical scrolling. Check: manual. Evidence: task-owned browser geometry/screenshots on synthetic fixtures, source identity, and at least one meaningful pre-repair counterexample. Clearly label fixtures; this is not new real-image retrieval evidence.
- [ ] The candidate preserves the current checkpoint outside the justified frontend/documentation delta, including its newer Backend/MCP work and canonical dirty authority files. Check: manual. Evidence: exact parent/tree/diff, before/after canonical preservation checks, separately resolved Vite/Vitest cache destinations, and focused tests/typecheck/build outputs with real exit codes; disclose existing failures and side effects.
- [ ] An independent reviewer can reconstruct and judge the exact candidate and each criterion. Check: manual. Evidence: `manifest.md`, frozen candidate/delta and native artifacts with command results, known limitations and source-only claims. Report `Memory candidates: <fact, evidence, future reuse>` or `Memory candidates: None`; Auto Dreamer alone curates shared memory.

## Delivery
- Artifact: isolated frozen source candidate, `docs/tasks/2026-11-23-m1-gallery-checkpoint/manifest.md`, native engineering handoff and associated review artifacts. Review owns `kickoff-review.md` / `review.md`; Producer alone owns this `task.md`.
- Known limitations: source/candidate PASS cannot establish canonical adoption, installed UI, new MCP execution, full M1, real LoRA training or CTY artwork acceptance. No consumed operation allowance is refilled. Coding and Review report findings on their own native cards and complete their deliverables even when the result is adverse; Producer decides the disposition.
