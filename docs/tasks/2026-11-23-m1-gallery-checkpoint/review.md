Verdict: AMBIGUITY
Review round: 1

## Findings

**A1 — independent manual verification method is unresolved (D3, delivered level P1).** No introduced P0/P1 product defect was demonstrated. This verdict withholds acceptance because the required independent D3 operation could not be completed using the assigned runtime path; it does not assert that the candidate layout fails.

The exact Review assignment requires: “Use native issue-workspace runtime controls for a task-owned loopback preview.” The authenticated heartbeat-context returned `currentExecutionWorkspace: null`; the documented controls require an already-realized workspace id. No native workspace-creation tool is available in this run. See `evidence/workspace-gap.json` and the captured `context.json`. No runtime start/restart/stop request was made against another workspace, and no unmanaged manual preview or replacement dispatcher was started.

Coding explicitly disclosed a finite foreground harness fallback. Its added setup-guide paragraph says to use native controls when a managed preview is configured. Those are delivered implementation/evidence and a declared deviation, rather than an explicit change to this Review's operating instruction. Producer should resolve the method: provide a task-owned realized native preview, or explicitly confirm an equally bounded synthetic foreground test-harness path for a follow-up independent review. This is an ordinary coordination decision for Producer, not a request for CTY to decide aesthetics or approve deployment.

Consequently, QA has **not** independently repeated D3 at 540/639/640/1200, generated new geometry/screenshots, operated the controls or reproduced the initial browser counterexample. The D1 React-browser direct/reload observations likewise remain author evidence. The real-Vite automated middleware/proxy checks and D2 fetch→render checks below were independently repeated. A supplied screenshot review is not a new browser run. Previous PASS and kickoff CLEAR do not fill this gap.

No code repair is requested on the strength of A1. Repair/rejection accounting was 0/0 at dispatch; this is delivery Review round 1 with AMBIGUITY. Producer owns disposition and any later accounting.

## Notes

### Exact candidate and custody

- Own Review: [AID-139](/AID/issues/AID-139). Sole native prerequisite [Coding](/AID/issues/AID-138) is actually done. Read its actual [engineering-handoff](/AID/issues/AID-138#document-engineering-handoff), revision `a0f61570-3bcd-409e-aaa1-bcc4dae0cdc8`, before review. Completion was not treated as PASS.
- Package commit `ca3884200e7e280940842ec03986ba3cad7d4646`; tree `d1f959b58f88c00aa6cc676d09c826f9ec103e2f`; sole parent/source `af64f2fc288bd8aa8ab21e4b3949488447012f8d`, source tree `15acbe48b55719386e0513e6b94a2379dfdfd129`; sole source parent/base `cd92ad4d8b0ef74e8d8ce62b1d4770217fc4dc27`, base tree `a9ac931e9c8a51ace482d8206b4881937d93146c`.
- Exact task SHA-256 `9c4d485e7993861d3a53a900dfd5ecf7a36f90d58359df60cdb9ad17007b42e2`; local task equals the frozen task-input bytes. [Kickoff CLEAR](/AID/issues/AID-137#document-kickoff-review), revision `e02ee4b1-c872-46c9-be60-f12c545f2d7d`, belongs to that brief and is not delivery acceptance.
- [Manifest](/AID/issues/AID-138#document-manifest) revision `52c6ce0e-7ff3-44df-9555-c2221e097023` equals both the committed file and ZIP payload: 16301 bytes, SHA-256 `e2e5757a84952f0d21e765686a0e963d60647a381bdfa0cf138d94c5660f43bf`.
- Independently downloaded [Coding package](/api/attachments/7e819f5c-d94f-4fa8-a892-6818373ab9c6/content?download=1): 1078790 bytes, SHA-256 `9b45ce54d33204cd270ce9f825849bdf90767314b678b5032a1dce73e74e70f9`; 78 safe unique ZIP members, CRC and all 77 payload lengths/hashes verified. All 11 changed payload bytes, Git blobs and 0644 modes matched. Exact base→package binary diff equals candidate.patch.
- Independent detached QA repository was reconstructed in this run's Paperclip scratch from the base and the downloaded incremental bundle. Clone, bundle verify, bundle fetch and checkout each exited 0. Canonical main/ref/index and the retained delivery checkout were not used for mutations. Original historical source comparisons were read-only in canonical Git because the independent base+bundle repository lacks those old branch objects.

### Manifest-to-Done-when reconstruction

Levels are retained. Nothing is raised to P0/P1 on speculation.

| Item | Check / level | Independent result and actual boundary | Limits |
| --- | --- | --- | --- |
| D1 | test / P1 | Real Vite middleware + synthetic upstream: all four slash/query document variants return SPA HTML, asset bytes/API still proxy; baseline and proxy mutation fail, candidate passes. Guard `frontend/gallery-routing.test.js`. | The automated index is a sentinel fixture, not the full React App. Source App route is present; author real-React direct/reload evidence was inspected but not independently repeated under a native preview. No installed/production route claim. |
| D2 | test / P1 | Actual Gallery fetch text→exact parser→selection→React rendering: unsafe raw integer tokens, null, prompt/CFG and explicit invalid-token cases pass. Original ID-only rerun payload assertion remains and passes with mocked fetch. Guard `frontend/src/pages/Gallery.test.tsx`. Rounding mutation is detected. | No Backend or job submission. Mocked rerun is not execution or Windows evidence. No database/generation range-support claim. |
| D3 | manual / P1 | Source/fixture/script and author geometry/screenshots audited. No independent manual result; A1 remains unresolved. | No new QA screenshot/geometry/control operation or browser baseline. Author PASS is not substituted for this required independent check. |
| D4 | manual / P1 | Exact parent/tree/11-path diff and reconstruction verified. Backend/MCP/Worker/launcher subtree identities equal base. Own focused tests, typecheck and build executed with explicit independent runner caches. Canonical/frozen preservation checked. | Source and tooling scope only; ignored runtime/private/model/dataset trees not comprehensively audited. |
| D5 | manual / P2 | Native handoff/manifest/artifact source can be reconstructed and judged; exact identities, commands, exits, deviations and A1 are inspectable. Review file, generated registry and native QA artifacts accompany this report. | Reconstructability does not resolve the missing D3 operation or establish candidate acceptance. |

### Actual commands, mutations and results

Prepared dependencies only, from the canonical frontend through a task-owned symlink. Effective Vite and separate Vitest roots/cache destinations were resolved **before** the runners: all four candidate/baseline caches resolve beneath this run's scratch. The finite in-process HTTP servers belong to the existing routing tests and close in their `afterAll`; no manual preview service was started. Test/build children use an OS-only environment allowlist plus task-owned TMPDIR; no Paperclip credentials/context is forwarded.

All command argv/cwd/exits and logs are in `evidence/`; exact runner/config files and mutation patches accompany the artifact. Candidate frontend cwd unless noted:

```sh
node <scratch>/resolve-caches.mjs
node node_modules/vitest/vitest.mjs run --config <scratch>/baseline-vitest.config.mjs src/pages/Gallery.test.tsx gallery-routing.test.js --maxWorkers=1 --minWorkers=1
node node_modules/vitest/vitest.mjs run --config <scratch>/candidate-vitest.config.mjs src/pages/Gallery.test.tsx gallery-routing.test.js --maxWorkers=1 --minWorkers=1
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
node node_modules/vite/bin/vite.js build --config <scratch>/candidate-vite.config.mjs --outDir <scratch>/qa-dist
python3 <scratch>/verify-source.py
```

| Check | Exit / observed result |
| --- | --- |
| Resolve both runner caches before testing | 0; separate Vite/Vitest paths for candidate and baseline |
| Pinned base + identical delivered regression tests | 1, expected; 14 failed / 8 passed (22), including real 307/404 and rounded raw seed |
| Exact candidate focused regressions | 0; 22 passed (16 Gallery + 6 routing) |
| D1 minimal production mutation: proxy regex key → broad `/gallery` | 1; 4 document cases failed / 2 asset+API cases passed |
| D2 minimal production mutation: `JSON.stringify(number)` → `JSON.stringify(String(Number(number)))` | 1; 6 precision cases failed / 10 other cases passed, with actual rounded decimal discrepancies |
| Both mutations restored byte-for-byte, same focused command | 0; 22 passed; parser/Vite hashes match delivered originals |
| Typecheck | 0; actual return code captured even though log is empty |
| Build | 0; 57 modules; output in task scratch |
| Bundle verify/fetch/checkout, patch/payload/manifest/parent/subtree checks | 0; source-verification.json binds exact candidate |

**Fake-green findings:** none for the selected targeted D1 proxy or D2 rounding mutations: both relevant suites went red. This does not certify every unrelated App/routing change; the routing suite intentionally tests Vite's document/proxy boundary with sentinel HTML, and D1 browser observations have not been independently repeated. No mocked assertion is promoted to a real API, job, browser layout or installed boundary. Repeated 22-test runs are not added together as independent test counts.

The base has unchanged product sources plus the same delivered tests only. Existing rerun coverage passed; no unrelated pre-existing failure was observed in the executed scope. Full frontend/Backend/MCP/Windows/GPU suites were not run. Build warnings are stale Browserslist data and external outDir not automatically emptied; no dependency update was attempted.

### Source, evidence and historical deviations

The production Gallery component/parser/Vite blobs are byte-identical to accepted `d232bc7dd0dfe9815ffb96e883ed216dc526be96`. The port has ten source/documentation paths (353+/12−); the final package adds only manifest.md as path eleven. Current newer Backend/MCP work is preserved. Existing Gallery.test.tsx changes only the necessary response helper `text()` addition plus reused precision tests; the original rerun assertions are retained. This declared existing-test deviation does not weaken assertions.

Independently read the four original native records, preserving their outcomes and scope:

- [Routing/seed handoff](/AID/issues/AID-115#document-engineering-handoff), revision `4cb74b94-9e54-4941-8ff2-414cd096a458`.
- [Routing/seed independent QA](/AID/issues/AID-116#document-qa-report), revision `b9b69e24-788d-41fb-b6aa-d578becc27c6`.
- [Readability handoff](/AID/issues/AID-122#document-engineering-handoff), revision `d79ab96b-8aab-4b70-84c7-54300f78d1b2`.
- [Readability independent QA](/AID/issues/AID-123#document-qa-report), revision `8448ada7-f9c4-427d-b010-eb60c8270b52`.

Prior routing/precision and readability FAIL→PASS remain historical evidence. Prior QA's first shared Vitest cache write, lack of a preimage and final explicit-cache correction remain intact. This review did not delete/restore that entry or erase the exception. Old layout code's real Gallery4446/Backend8001 references were inspected via the historical reports; the adapted delivered script/fixture was read and is synthetic-only, includes 639 and control hit tests. The old real-service script was never executed.

Author-record audit only: initial1200 baseline client/scroll width655/2023; candidate1200 655/655, 540 491/491, 639 590/590, 640 591/591. Recorded full prompt6600 chars, negative249 chars, complete seed fragments, natural1536×1024 / ratio1.5 and select+4 hit-testable controls satisfy the supplied assertions. QA viewed the author's baseline1200, candidate1200 and candidate540 captures. `author-layout-audit.json` explicitly labels those records as author data, not new QA captures. The author's foreground fallback, initial EOF/rewritten trace/cwd errors and packaging raw-SHA bundle correction stay disclosed in its manifest/handoff/package; they are not silently relabeled as QA executions.

Two QA verification-helper corrections are disclosed in `qa-harness-corrections.json`: historical object lookup initially ran in the independent base+bundle repository (old branch object absent; Git exit128), then was correctly read-only in canonical Git; a strict clean assertion initially failed because of the deliberately created dependency symlink, with no tracked diff. It was explicitly accounted for, then only the task-owned symlinks were removed. No product source was repaired. The final source verifier and clean detached checkout passed.

### Preservation, side effects and registry

Before role report/registry writes, all 1220 captured canonical source/authority files retained bytes and numeric modes; HEAD/main `cd92ad4d8b0ef74e8d8ce62b1d4770217fc4dc27`, raw index and raw status were unchanged. The specifically observed canonical shared cache retained SHA-256 `51078b1ce94a5bcdbaefaf63a3ea26b1d134d95176ed36c5c7514714de31c69b`. Own runner result files are in task cache directories. Original three frozen worktrees retain their expected HEADs and clean status. These are bounded source/observed-cache checks, not an all-ignored-files audit.

Coding's earlier concurrent Producer edits were exactly `docs/CURRENT.md`, `docs/PROGRESS.md`, `docs/decisions/m1-source-integration.md`, attributed to Producer run `dfead240-9b14-4340-b36a-fd451f77260d` by its native dispatch receipt revision `9fcd0f77-2418-469d-9d80-55bc8bcdbe72`. That evidence was read; none was overwritten. No concurrent captured source drift was observed during this QA window. The only intended canonical writes here are this role's review.md and the registry script output; final path/hash verification is included in preservation-final.json.

The live `reviewspec-review/scripts/build_registry.py` is run after this report. AMBIGUITY contributes no certified PASS items; D1/D2 are not falsely registered as full candidate acceptance. Registry output and verification are attached. No earlier review or coverage row is superseded by this composition.

### Required reads and operating limits

On resume, physically reread installed using-superpowers SKILL and Codex host reference; current live reviewspec-core before reviewspec-review, paperclip-task-handoff; common-original using-git-worktrees, verification-before-completion and systematic-debugging (for the verifier failures); ego-browser; applicable native Paperclip workspace/artifact instructions. The installed Paperclip heartbeat method was loaded in this continuing session. Required-read inventory records actual files and native revisions.

Canonical AGENTS, README, agent-reading, GOAL, INDEX, team README/QA contract/skill-bindings/channel-routing, exact owner request, memory index and all three designated Gallery/cache refs were reread; actual task bytes, setup-guide, current/pinned Gallery/test/parser/Vite/package/App/schema, delivered fixture/harness/layout script and full manifest/patch were read. Missing canonical parser on the pre-repair base is expected; the known stale api-contract.md schema reference is not a new missing acceptance specification. ROADMAP/CURRENT/PROGRESS were only hashed for preservation, not used to select work or independently rewritten.

No new browser task/manual preview, real Gallery/MCP/Backend request, job/rerun/export submission, generation/training, installation/resource download, runtime service control, remote/Windows/spending, canonical adoption/deployment, CTY preference or aesthetic evaluation occurred. There is no live monitor or polling process. Mac/MPS remains consumed1/1. Source/synthetic checks do not establish installed UI, real retrieval, full M1 or LoRA acceptance.

### Handoff

The completed **review verdict**, including A1 and all actual evidence, is delivered on this QA card and the card is done even though the candidate is not accepted. [Producer](/AID/issues/AID-136) consumes it through the existing native prerequisite, resolves the preview/method question within its authority and decides subsequent independent verification or acceptance. QA does not mutate Coding/Producer cards, dispatch a repair, grant a runtime exception, publish a site or add an owner confirmation gate.

Memory candidates: None. Reused Gallery/cache lessons already exist in the designated canonical memory; the preview gap and current composition evidence are task-specific. Auto Dreamer remains the sole routine memory curator.
