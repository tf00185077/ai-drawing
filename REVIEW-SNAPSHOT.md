# Public review snapshot — 2026-11-03

This branch is a point-in-time review snapshot of the canonical AI Drawing checkout after project-memory curation. It is **not a merge, release, deployment, or full-product acceptance**. The active local `main` checkout and its Git index were not switched or overwritten.

## Start here

- [Current project state and remaining acceptance gaps](docs/PROGRESS.md)
- [Project goal and continuing mandate](docs/GOAL.md)
- [Curated project memory](docs/memory/MEMORY.md)
- [Team responsibilities](docs/team/README.md)
- [Product entry](README.md)

At capture, the current state document records that the two indirect OS-effect accounting/risk facets have conditional acceptance, and that the operation-specific profile engineering and independent QA are separate from future operational permission and real execution. Source/offline milestones do not establish working LoRA training, real image delivery, UI runtime acceptance, or aesthetic acceptance.

## Scope

Captured on **2026-11-03 at 10:59:21 Asia/Taipei**. The snapshot contains versionable canonical source, tests, manifests, workflows, prompt/style resources, current documentation, role contracts, and all twelve curated memory topics. Existing deletions from the checkout are represented. Work in separate agent worktrees is not silently merged into this branch; subsequent local edits are outside this frozen capture.

The following are deliberately omitted, including previously tracked copies where present:

- Credentials, private environment/configuration, databases, datasets, model files, local inventories, caches, and ignored runtime directories.
- Generated media and retained experiment/research/benchmark data; their versioned Python source tools are retained. Synthetic test fixtures are also retained.
- Built distribution packages, historical transient agent reports, prompt-library rollback state, and root-level temporary scripts.

## Public-review privacy transforms

Local user paths, private network endpoints, and contextual messaging identifiers are consistently deidentified in this snapshot only. The live product files remain unchanged. Known synthetic credential-shaped values in security-rejection tests are retained as test fixtures. Example configuration must be reviewed and configured for an actual installation; this branch does not certify runtime behavior after deidentification.

Some current project records link to a local Paperclip installation and therefore are not publicly navigable. Ignored trainer dependencies, including `sd-scripts/`, are not bundled; links into such local dependencies are evidence locators, not a claim that those dependencies were uploaded. This snapshot does not copy private native task stores, logs, sessions, or binary QA evidence.

## Verification boundary

The publication checks cover the frozen tree, explicit file scope, credential-signature review, syntax/data parsing, selected navigation, Git identities, and remote commit/file readback. They are not product tests, Windows/GPU execution, training, generation, service maintenance, or production acceptance.
