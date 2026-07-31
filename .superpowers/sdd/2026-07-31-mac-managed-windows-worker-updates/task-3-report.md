# Task 3: Exact Git Source Export

## RED

- Created `backend/tests/test_worker_updater_git.py` before adding production
  code. `py -3.11 -m pytest backend/tests/test_worker_updater_git.py -q`
  failed during collection with `ModuleNotFoundError` for
  `worker.windows.updater.git_source`, as expected.
- The new tests use real temporary bare remotes and clones. They cover an
  unequal target SHA, preservation of a dirty checkout, fetch failure with a
  token-like remote path, an unconfigured remote, a remote-tracking ref that
  resolves to a blob rather than a commit, a commit without
  `worker/windows/worker.py`, `../` archive traversal, and an archive symlink
  escape.

## GREEN

- `py -3.11 -m pytest backend/tests/test_worker_updater_git.py -q` passed:
  **8 passed**.
- `py -3.11 -m pytest backend/tests/test_worker_updater_git.py
  backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py -q`
  passed: **48 passed**.
- `py -3.11 -m compileall -q worker\\windows\\updater` passed.
- `git diff --check` passed.

## Changes

- Added `GitSource`, which runs every Git process through a captured,
  `check=False`, 300-second bounded invocation. It redacts URL credentials and
  common token/secret values before a `GIT_COMMAND_FAILED` error is exposed.
- The exporter verifies the configured remote exists; fetches only
  `refs/heads/<configured branch>` to its matching remote-tracking ref; resolves
  `refs/remotes/<remote>/<branch>^{commit}`; and requires byte-for-byte SHA
  equality with the requested target before exporting.
- It validates that the target contains the Windows worker source, uses
  `git archive --format=tar <target>`, and writes `source-commit.txt` with the
  verified SHA.
- Extraction is staged and never invokes `extractall`. It permits only canonical
  relative directory/regular-file paths, rejects traversal, backslashes,
  symlinks, hardlinks, and special members, and prevents a pre-existing export
  destination from being overwritten. The source checkout is never checked out,
  reset, stashed, cleaned, or otherwise modified.

## Self-review

- Confirmed the actual fetch refspec has exactly one configured remote and one
  configured branch; archive is addressed by the verified target SHA, not the
  checkout's `HEAD`.
- Confirmed all archive output is first written below a fresh temporary sibling
  directory, then atomically moved into a destination that did not exist.
- Confirmed tests interact only with test-created local repositories. No real
  Windows worker or other machine was contacted.

## Commit

- `feat(worker): export exact trusted Git revision`

## Concerns

- The focused test command emits one pre-existing Pydantic v2 deprecation
  warning from `backend/app/config.py:54`; this task does not modify that file.
- Git itself refuses to set `refs/heads/main` to a blob in the bare test remote.
  The non-commit regression therefore writes a real blob into the cloned test
  repository's `refs/remotes/origin/main` and exercises the same required
  `^{commit}` resolver directly.

## Fix round 1

### RED

- Added in-memory tar regressions for Win32 reserved device names (including
  extensions), ADS colons, trailing dots/spaces, controls/NUL, POSIX/drive
  absolute paths, case-only duplicates, and directory/file case collisions.
  The pre-fix extractor accepted the Windows-normalized path cases.
- Added selector tests that make any attempted `fetch` fail immediately. The
  pre-fix exporter reached fetch for wildcard and option-like remote/branch
  values, or exposed the generic Git error for an invalid remote.
- Added a real local submodule fixture: its repository config enables recursive
  fetching, its initialized submodule remote is deliberately missing, and the
  upstream project advances that gitlink. The pre-fix fetch contacted the
  missing submodule remote and failed.

### GREEN

- `py -3.11 -m pytest backend/tests/test_worker_updater_git.py -q` passed:
  **23 passed**.

### Changes

- Archive extraction now rejects Windows device names (`CON`, `AUX`, `COM1`,
  `LPT1`, and variants with extensions), colons/ADS, control characters,
  trailing dots/spaces, drive-like components, and all case-insensitive
  duplicate or file/directory-colliding paths before any member is written.
- Remote and branch selectors are rejected before remote lookup/fetch when
  empty, option-like, whitespace-bearing, or wildcard-bearing. The exporter
  then uses checked `git check-ref-format --branch <branch>` and validates the
  composed `refs/remotes/<remote>/<branch>` as a single ref.
- Fetch now passes `--no-recurse-submodules`, overriding a repository's
  `fetch.recurseSubmodules=true` setting while retaining the prior exact
  remote/branch refspec, time limit, cleanup, and stderr redaction behavior.

### Verification

- `py -3.11 -m pytest backend/tests/test_worker_updater_git.py
  backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py -q`
  passed: **63 passed**.
- `py -3.11 -m compileall -q worker\\windows\\updater` and `git diff --check`
  passed.
- The only test output warning remains the pre-existing Pydantic v2 deprecation
  at `backend/app/config.py:54`.

## Fix round 2

### RED

- Added archive tests for two implicit parent collisions:
  `Foo/a.txt` with `foo/b.txt`, and `Foo/Bar/a.txt` with `Foo/bar/b.txt`.
  Both failed before the fix because only complete tar member paths were
  tracked; implicit parent directories had no canonical spelling record.

### GREEN

- Each archive path prefix now records its casefold canonical key, the one
  allowed original spelling, and its required type (`directory` for implicit
  prefixes, otherwise the member type). A later spelling or type mismatch is
  rejected before extraction. Same-spelling siblings continue to share their
  recorded parent directory safely.
- `py -3.11 -m pytest backend/tests/test_worker_updater_git.py -q` passed:
  **25 passed**.
- `py -3.11 -m pytest backend/tests/test_worker_updater_git.py
  backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py -q`
  passed: **65 passed**. `compileall` and `git diff --check` also passed; the
  only output warning remains the unchanged Pydantic v2 deprecation.
