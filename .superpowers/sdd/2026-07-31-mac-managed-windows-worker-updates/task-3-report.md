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
