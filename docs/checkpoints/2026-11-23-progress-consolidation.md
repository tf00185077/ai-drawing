# Progress consolidation — 2026-11-23

## Owner direction and release scope

CTY requested: “把有實際工作進度的都合併進main後進行push，沒有實際工作進度的就直接捨棄刪除。現在要先整理進度”.

This is a source-progress consolidation onto `main`, based on published checkpoint `f67edee035a83deae7a8d6474c031807c03fade9`. It replaces the earlier Git-integration hold for this consolidation. Producer remains paused; the native task hold, model/data directories, running services and deployment state are unchanged. The separate question about deleting native Paperclip tasks remains unresolved.

The integration uses a three-way squash composition and targeted Gallery patches. It preserves current role/skill bindings, project memory, owner decisions and newer Argus/Minimax/fixed-video source. It does not publish the original private-author commit ancestry, replace main with an older full tree, or restore an obsolete public-review snapshot.

## Actual progress retained

| Source branches | Retained result |
| --- | --- |
| `aid-2-worker-health-identity` | Backend-side Worker hostname/protocol validation and regression coverage; the Worker implementation is not replaced. |
| `aid-12-lora-delivery`, `aid-14-public-results`, `aid-16-projection-contract`, `aid-18-integrated-baseline`, `aid-20-frontend-node-types`, `aid-22-smoke-reconciliation`, `aid-24-smoke-image-validation`, `aid-26-explicit-lora-contract`, `aid-28-revision-lineage`, `aid-30-mcp-parent-recovery`, `aid-32-json-decoder-containment` | LoRA readable naming/serial reservation, isolated runs, effective-parameter records, validated no-clobber registration, safe public projections, smoke result reconciliation, exact-image checks, multi-LoRA fixtures and ordinary-image revision context across Backend/MCP/UI. The later source composition already contains these successive product changes, so they are not replayed repeatedly. |
| `aid-34-canonical-integration`, `aid-36-posix-kit`, `aid-43-lora-lifecycle`, `aid-48-maintenance`, `aid-50-close-receipt`, `aid-52-source-kit`, `aid-94-source-checkpoint`, `aid-99-bounded-git-checkpoint`, `aid-102-lock-correction` | Current-source composition, durable admission/delivery history, non-cancelling drain, uncertain-submission reconciliation, offline-test support and original checkpoint manifests/archive. `c991ddf4524e2f5bc78d7c1cb24f224ed3dcb040` supplies the cumulative product source, not an instruction to execute an old maintenance operation. Current main authority wins over historical planning/role copies. |
| `aid-56-offline-method`, `aid-58-partial-overflow` | The final independent offline method and its original inputs, controls, correction and evidence under `engineering/aid56-method/`. Four ignored original logs from aid56 are retained byte-for-byte under `docs/archive/progress-consolidation/aid56-original-logs/`. |
| `aid-62-g09-isolated`, `aid-64-g09-failure-contract`, `aid-70-m1-four-boundaries`, `aid-72-m2-sqlite-contract` | Corrected G09/M1/M2 source and synthetic controls under `tools/`, using the later retained source archive `docs/checkpoints/aid89-parent-reservation-v1.zip`. Its refusal/incomplete operational status remains explicit; this is reusable source progress rather than a new live-operation route. |
| `aid-115-gallery-correctness`, `aid-122-gallery-readability` | The two accepted source patches: SPA document/asset routing, raw-token seed precision, initial responsive modal readability, regressions and associated development instructions. Original numeric Backend/MCP contracts and ID-based rerun semantics remain. The old browser helper requires its documented existing-image environment and was not run against a product service during consolidation. |

Main's `argus_mlx_i2v.py`, `film_postprocess.py`, `fixed_video_workflows.py` and fixed MiniMax workflow retain their original bytes. The Discord submission/view integration keeps the newer video entrypoints alongside admission and durable-delivery controls.

## Branches without new retained product progress

| Branch | Disposition |
| --- | --- |
| `aid-138-gallery-checkpoint` | Withdrawn composition: `aa7bd009bc8e5363b8632422e3baae78c55d8c54` has exactly the pre-round `cd92ad4` tree. Its undone source/package commits are not adopted. The earlier accepted Gallery patches above are integrated independently under CTY's new direction; the withdrawn synthetic preview and manifest are not revived. |
| `feat/add-agent-workflow-authoring` | Already an ancestor of main; no extra progress to merge. |
| `local-backup/main-before-author-privacy-d0c65a4c` | Tree-equivalent to published ancestor `7c0da65`; preserves only the old private-author ancestry, not extra source progress. |
| `review/project-state-20261103` | Superseded curated public snapshot. Actual Argus/video progress is already in main. Remaining redaction changes include invalid network constants and a broken shell substitution, plus old document state and disclosure-only deletions; these are discarded rather than merged. The existing remote review snapshot is not part of this local-branch cleanup. |

The machine-readable [branch inventory](2026-11-23-progress-consolidation.json) pins every original local branch and its disposition. Local branch/worktree cleanup follows verified publication. Non-worktree input/delivery bundles and private canonical runtime data are preserved.

## Integration corrections and review

- Queue drain retained main's Argus runner but initially inherited a shutdown call that terminated its accepted child. A new regression first failed on the real runner boundary, then passed after removing that cancellation from drain. Pending/running state remains visible on incomplete drain.
- Native old tests expected task-local worker lifecycle state. The full integration exposed cross-test stop/admission flags; backend test fixtures now give each test fresh stop events and caption admission, following the existing maintenance-test pattern. This changes test isolation, not production restart behavior.
- The isolated offline runner now includes the repository root on its import path so the `worker` package can be collected. The complete Backend suite uses its scratch/bootstrap fixtures because the narrower legacy audit runner intentionally forbids Git/process/loopback fixtures.
- The LoRA protocol test now supplies the required output name when testing a missing recipe and independently checks that `output_name` is required.
- Independent static review found that a confirmed HTTP validation rejection could close all Bot admission. New regressions reproduced this for image, AnimeGen and MiniMax submissions. Explicit pre-admission validation/auth/routing refusals now leave the permit normally before rethrowing; timeout, server failure and other uncertain outcomes still close admission without retry. Both red and green evidence were executed.

## Executed verification

Fresh dependency environments were used with the integrated manifests/lockfile; test environment variables and writable roots were isolated from private runtime configuration. Vite, Vitest and build outputs use separate owned scratch locations.

| Check | Actual result |
| --- | --- |
| Full Backend suite | 2032 passed, 26 failed, 125 skipped. |
| Pinned original-main comparison | The exact same 26 failure IDs reproduced on `f67edee` with the same fresh test environment; selected baseline files returned 38 passed, 26 failed, 102 skipped. No newly failing Backend test ID was introduced. |
| MCP | 315 guarded tests plus 2 real stdio catalog/validation fixtures passed; 4 skipped. |
| Discord | 140 guarded tests plus 2 fixture-owned ephemeral-loopback operator tests passed. |
| Frontend | 23 test files passed; 226 tests passed, 1 skipped. Typecheck and production build exited 0. |
| Retained G09 / failure controls | 23 + 5 direct scratch tests passed. |
| Retained M1 / M2 | 40 + 15 direct scratch/synthetic SQLite tests passed. |

The 26 unchanged Backend failures cover existing Prompt Library inventory/migration snapshots, Worker distribution/source-package checks and macOS execution of Windows PowerShell fixtures. They remain recorded in the JSON inventory; assertions and source data were not weakened or rewritten to force green. This publication is not a claim of an entirely green global suite, installed integration, GPU/training execution or aesthetic acceptance.

No generation, training, job replay, product service restart or native worker resumption was performed. Existing compile/test deprecations and generated-evidence formatting warnings remain distinguishable from verification failures.

## Verified local cleanup

Source/evidence publication `30cac84a7f3c33d0a28751cdc088a405e9418329` was read back from GitHub before deletion; the cumulative remote tree matched all 222 changed blobs. Five original aid58 logs that matched the retained-source manifest were explicitly tracked despite the runtime-log ignore rule before cleanup.

Cleanup removed 25 existing linked worktrees, pruned 6 missing-path registry records, deleted the 33 classified original local branches and removed the temporary integration branch. Readback leaves only local `main` and its one primary worktree, with clean Git status. Rebuildable dependency/build/Python/pytest caches were checked separately from source and evidence; four original aid56 logs were verified against their published copies before deletion.

The four ordinary evidence/input/delivery packages (`aid-2-evidence`, `aid-26-delivery`, `aid-12-candidate-v1`, `aid-12-input-v1`) were preserved because they are actual data packages rather than redundant Git worktrees. Existing remote-only historical branch records were unchanged. Producer remains paused; no product process was started or restarted.
