## 1. Lock baseline, state-machine, weighted, and diagnostic contracts

- [ ] 1.1 Add read-only inventory fixtures/tests for 297 entries, 146 comma-containing entries, 151 retained atomic entries, 532 newly derived atoms, 683 final atoms, zero blank atoms, and the four named combinations.
- [ ] 1.2 Assert combination projection `character=2`, `niji基礎瑟瑟=25`, `portrait-detail=5`, and `portrait=4`, for 36 atomic fragments total.
- [ ] 1.3 Define typed migration states (`required`, `applying`, `incomplete`, `validating`, `rolled_back_required`, finalized), readiness, atomic-enforcement status, privilege, lock, and structured fail-closed error contracts.
- [ ] 1.4 Define the weighted fragment model: Backend `snapshot` is exact unweighted `snapshotRaw`, weight is structured, `renderedRaw=render(snapshotRaw,weight)`, and final text is `renderedAtoms.join(",")`.
- [ ] 1.5 Define typed curated-record, legacy-ref expansion, blocking document diagnostic, document-context token, acknowledge-convert token, dry-run, apply, resume, rollback, and finalize schemas.
- [ ] 1.6 Add legacy fixtures for comma-bearing literals/refs, duplicate refs, non-1 weights, parentheses, quotes, archives, blank subsegments, unknown refs, ordinary edits, explicit replacement refs, and explicit literal conversion.

## 2. Implement and deploy the migration-compatible Backend gate first

- [ ] 2.1 Implement durable marker discovery/creation before ordinary Prompt Library provider initialization and expose a catalog-independent migration status with readiness false.
- [ ] 2.2 Centralize a fail-closed guard before every ordinary catalog/list/search/category/entry read, combination list/load, compose, save/update/save-as, archive/restore, repair, and equivalent API/MCP operation.
- [ ] 2.3 Return one structured migration-unavailable error without reading live/staged documents, populating caches, resolving refs, or mutating revisions/etags whenever any marker state exists.
- [ ] 2.4 Implement an operator-privileged migration capability unavailable to Workbench/general MCP callers; require the migration lock for audit/dry-run/apply/resume/rollback/validate/finalize state access.
- [ ] 2.5 Implement dormant atomic-enforcement mode and a finalize precondition that refuses marker removal/readiness true until enforcement-active and all data gates are proven.
- [ ] 2.6 Test fail-closed behavior for every Backend route/provider and API/MCP read/write, migrated-but-unenforced state, privilege failure, lock ownership, and catalog-independent status.
- [ ] 2.7 Deploy/start the migration-compatible Backend gate against the legacy library before migration and verify marker present, readiness false, atomic enforcement inactive, every ordinary catalog operation blocked, and privileged audit available.

## 3. Build deterministic privileged audit and dry-run

- [ ] 3.1 Implement exact Python `split(",")` projection without trim/filter and report every source locator, raw segment, segment index, revision, and etag under the migration lock.
- [ ] 3.2 Require exactly 532 curation records for atoms newly derived from the 146 multi-token entries; reject missing/extra records and any curation record targeting the 151 retained entries.
- [ ] 3.3 Invariant-check the 151 retained entries as nonblank/comma-free while preserving their ID, prompt bytes, name, description, aliases, keywords, order, revision, and archive state.
- [ ] 3.4 Implement stable derived IDs from source provenance and SHA-256, deterministic digest-length collision expansion, same-provenance reuse, and blocking full-digest/unverifiable collisions.
- [ ] 3.5 Implement derived-atom metadata projection for exact whitespace, curated Chinese fields, inherited/deduplicated aliases and keywords, archive state, revision 1, and ordering without changing retained-entry order metadata.
- [ ] 3.6 Implement combination projection for comma-bearing literals and reviewed one-to-many refs, copying structured weights to every atom and reporting exact resulting `renderedRaw`.
- [ ] 3.7 Expose privileged write-free audit/dry-run reports containing counts, mapping coverage, retained invariants, IDs/collisions, blocking diagnostics, ref expansions, planned mutations, and pre/post hashes.
- [ ] 3.8 Test that audit/dry-run hold the lock but never change Prompt Library bytes, staged files, revisions, etags, marker, readiness, enforcement state, or caches.

## 4. Curate exactly the newly derived atoms

- [ ] 4.1 Generate the worksheet with exactly 532 records for atoms derived from the 146 multi-token entries and no rows for the 151 retained entries.
- [ ] 4.2 Manually curate/review every derived `name_zh`, description, alias, and keyword; allow explicitly equivalent tokens to share labels while requiring distinct Chinese decisions for semantically different tokens such as shirt types.
- [ ] 4.3 Add the reviewed legacy source-ref registry mapping every removed multi-token source locator to all ordered derived locators.
- [ ] 4.4 Run privileged dry-run until worksheet cardinality, retained invariants, hashes, collisions, and registry coverage pass with zero unresolved items.
- [ ] 4.5 Review representative quality, clothing, positive, negative, archived, duplicate-English, and non-1-weight cases before authorizing apply.

## 5. Implement guarded apply, resume, rollback, and finalize mechanics

- [ ] 5.1 Implement baseline/revision/etag preconditions and refuse apply whenever the reviewed 297/146/151/532/683/four-combination inventory or dry-run hashes drift.
- [ ] 5.2 Implement exact pre-image backup/checksums, run-specific rollback manifests, staged destination validation, and atomic replacements while retaining the pre-deployed marker.
- [ ] 5.3 Implement deterministic category/combination revision and etag changes, preserving all retained-entry metadata and all unaffected document metadata.
- [ ] 5.4 Implement interruption detection and privileged resume using the same plan/hash/lock; never expose partial state through ordinary operations.
- [ ] 5.5 Implement rollback with post-image etag checks, staged exact pre-image restore, and terminal `rolled_back_required` marker/readiness false rather than reopening ordinary access.
- [ ] 5.6 Implement post-write validation for 683 comma-free nonblank entries, exactly 532 curated derived atoms, unchanged 151 retained entries, 36 combination atoms, valid refs, expected revisions/etags, and zero-change second dry-run.
- [ ] 5.7 Implement privileged finalize that rechecks post-write gates plus `atomic_enforcement_active=true`, then atomically removes the marker and publishes readiness true.
- [ ] 5.8 Test stale-etag failure, interrupted apply/resume, marker persistence, rollback success/divergence, migrated-but-unenforced finalize refusal, and byte-stable idempotency.

## 6. Apply and validate the library migration while ordinary access stays blocked

- [ ] 6.1 Run final privileged dry-run and retain the reviewed report: 297 sources, 146 comma sources, 151 retained entries, exactly 532 curated derived atoms, 683 final entries, zero blanks, four combinations, 36 combination atoms, zero unresolved items/collisions.
- [ ] 6.2 Apply the reviewed plan under privilege and lock, creating pre-image backup/rollback artifacts before any replacement.
- [ ] 6.3 Verify all 151 retained atomic entries preserve every metadata field and only pass invariant validation.
- [ ] 6.4 Verify all 532 derived entries are nonblank/comma-free with exact raw whitespace, curated metadata, stable IDs/order, inherited archive state, and correct revisions/etags.
- [ ] 6.5 Verify the four combinations preserve exact rendered prompt text/metadata while storing 2/25/5/4 ordered atomic fragments and one new revision/etag each.
- [ ] 6.6 Run the zero-mutation second dry-run and confirm stable bytes, IDs, order, refs, revisions, and etags.
- [ ] 6.7 HARD GATE: keep the marker, readiness false, frontend disabled, and every ordinary API/MCP catalog operation blocked after data validation; do not finalize yet.

## 7. Activate Backend atomic enforcement before readiness

- [ ] 7.1 Preserve rejection of empty/whitespace `snapshotRaw` across persisted models, compose, save, repair, and canonical responses.
- [ ] 7.2 Activate comma-free Prompt Entry enforcement for category management, API, MCP, and import writes; reject `comma_not_atomic` without revision/etag change.
- [ ] 7.3 Implement canonical weighted rendering from exact `snapshotRaw` plus weight and join `renderedRaw` with literal `","` without trim/filter/inserted whitespace.
- [ ] 7.4 Implement privileged/post-readiness atomization of legacy comma literals, copying weight to every atom and rejecting the whole input on any blank subsegment.
- [ ] 7.5 Implement reviewed one-to-many ref expansion with exact derived snapshots/revisions, inherited structured weights, stable warning order, and blocking duplicate-ref detection.
- [ ] 7.6 Implement canonical save/load/lazy repair with rendered-atom equality, one revision/etag per repair, archive/missing-ref preservation, and idempotent second load.
- [ ] 7.7 Run focused Backend model/composer/API/writer/seed/migration and MCP contract tests while the marker remains; prove comma/blank writes fail and weighted compose/load/save round trips pass.
- [ ] 7.8 Mark atomic enforcement active only after all Backend tests pass; verify ordinary reads/writes are still blocked because the marker remains.
- [ ] 7.9 Run privileged finalize, revalidate data plus enforcement, atomically remove the marker/publish readiness true, then verify ordinary catalog access returns only the fully migrated enforced state.

## 8. Enforce blocking unresolved-provenance resolution

- [ ] 8.1 Return externally introduced unknown legacy refs as literal fallback atoms plus a blocking diagnostic bound to original ref, combination ID, revision/etag, diagnostic IDs, and atom hashes; never auto-persist.
- [ ] 8.2 Carry a Backend document-context token through loaded Update and Save As so ordinary edits or copying cannot drop a blocking diagnostic.
- [ ] 8.3 Reject Update, Save As, and any persistence derived from a blocked document until all diagnostics are explicitly resolved.
- [ ] 8.4 Implement reviewed-mapping and explicit replacement-source-entry resolution with current ref/concurrency validation.
- [ ] 8.5 Implement explicit acknowledge-convert-to-literals action issuing an opaque context-bound token; require Backend validation of that token on Update/Save As.
- [ ] 8.6 Test ordinary edit/save non-acknowledgment, Save As bypass attempts, stale/tampered conversion tokens, partial diagnostic acknowledgment, reviewed mapping, replacement refs, and successful explicit conversion.

## 9. Replace frontend state with the weighted lossless model

- [ ] 9.1 Define each segment with `snapshotRaw`, weight, derived `renderedRaw`, kind/ref metadata, and presentation-only label; define lane raw text as `renderedAtoms.join(",")`.
- [ ] 9.2 Implement exact U+002C split/join for leading/trailing/consecutive/quoted/parenthesized/weighted commas while treating U+FF0C as ordinary content.
- [ ] 9.3 Reconcile exact `renderedRaw` common prefix/suffix, preserving unchanged weighted snapshot/weight/ref/UI identity and demoting every changed atom to exact weight-1 literal without parsing.
- [ ] 9.4 Keep browser textarea values and selection start/end/direction stable through controlled rerenders and IME composition.
- [ ] 9.5 Implement card content edit, weight edit, append, reorder, and delete: content edit of an entry demotes provenance; weight-only edit preserves source snapshot/ref.
- [ ] 9.6 Add pure tests for empty lanes, `a,,b,`, duplicate text, source demotion, changed `(detail:1.2)`, unchanged non-1-weight refs, UI IDs, and exact rendered round trips.

## 10. Implement fixed labels, empty cards, and readiness UI

- [ ] 10.1 Implement exact NFKC/trim/whitespace-collapse/case-fold display lookup without modifying `snapshotRaw` or provenance.
- [ ] 10.2 Apply the label hierarchy for genuine refs, unique literal matches, English fallback, and fixed `自訂文字` for empty/unresolved/ambiguous tokens.
- [ ] 10.3 Omit display labels from persistence, provide no custom-label editor, recompute every label on load, and ensure users edit only prompt content.
- [ ] 10.4 Render empty/whitespace cards with invalid state, exact content, reorder/delete controls, true position, pagination, and focus/page navigation.
- [ ] 10.5 Before catalog initialization, read only migration status; while readiness is false/enforcement inactive/marker present, render a non-editing state and make no catalog-dependent request.
- [ ] 10.6 Test duplicate English/cross-polarity ambiguity, English fallback, fixed non-persisted labels, empty pagination/reorder/delete/fill, and no catalog calls before finalized readiness.

## 11. Add blank preflight before every client request

- [ ] 11.1 Implement one pure preflight over both lanes that reports every present blank/whitespace `snapshotRaw` or `renderedRaw` by polarity and 1-based position.
- [ ] 11.2 Render the required message explaining that every ASCII comma creates a prompt that must be filled or removed, and focus/open the first invalid card.
- [ ] 11.3 Wire preflight before any Save serialization/helper/request and prove no compose or write call runs on failure.
- [ ] 11.4 Wire preflight before Update and prove exact text, dirty state, revision, etag, and blocking diagnostic context remain unchanged on failure.
- [ ] 11.5 Wire preflight before Save As and prove no compose/combination request runs on failure.
- [ ] 11.6 Wire preflight before Generate and prove `/api/generate/` is not called and no job is created.
- [ ] 11.7 Test combined polarities, multiple positions, whitespace, leading/trailing commas, focus/page behavior, and valid zero-segment Negative lane.

## 12. Complete document, blocking-diagnostic, and generation flows

- [ ] 12.1 Serialize only preflight-valid atomic `snapshotRaw` plus weights/refs/order/source revisions and verify Backend canonical equality using recomputed `renderedRaw`.
- [ ] 12.2 Load canonical detail revisions/etags/warnings/blocking diagnostics and reconstruct final text only from returned rendered atoms.
- [ ] 12.3 Preserve dirty guard, new document, Save, Update, Save As, stale-response isolation, and conflicts for temporary empty cards and weighted fragments.
- [ ] 12.4 Keep Update/Save As disabled/rejected for blocking diagnostics until mapping, replacement-source selection, or explicit acknowledge-convert action obtains valid Backend resolution.
- [ ] 12.5 Add explicit UI for replacement refs and acknowledge-convert-to-literals; ordinary prompt edits and save buttons must not imply acknowledgment.
- [ ] 12.6 Build generation payloads from exact visible validated rendered Positive/Negative text without label or unweighted-snapshot recomposition.
- [ ] 12.7 Add Workbench tests for non-1-weight browser load/save/reload, textarea demotion, canonical mismatch, refs, lazy repair, blocking resolution, blank preflight, and generation payloads.

## 13. Verification and rollout evidence

- [ ] 13.1 Run focused migration/Backend tests and the complete Backend suite.
- [ ] 13.2 Run focused weighted composition, panel, label, toolbar, Workbench, preflight, and generation tests and the complete Frontend suite.
- [ ] 13.3 Run complete MCP tests for fail-closed marker behavior, finalized reads/writes, structured diagnostics, and resolution tokens.
- [ ] 13.4 Run TypeScript typecheck and Vite production build.
- [ ] 13.5 Re-run privileged audit/dry-run and confirm 151 unchanged retained entries, 532 curated derived atoms, 683 comma-free nonblank entries, four atomized combinations, valid refs, zero unresolved repository items, enforcement active, no marker, readiness true, and zero mutations.
- [ ] 13.6 In a real browser, verify readiness gating, caret, `a,,b,`, quotes/parentheses, empty cards, fixed labels, source-vs-typed provenance, non-1-weight load/save/reload and demotion, dirty guard, Save/Load/Update/Save As, and blocking diagnostic resolution.
- [ ] 13.7 Intercept/inspect exact generation requests after blank preflight; do not restart services or submit live image generation.
- [ ] 13.8 Update `docs/PROGRESS.md` only after implementation and every migration, enforcement, test, build, and browser gate passes.
