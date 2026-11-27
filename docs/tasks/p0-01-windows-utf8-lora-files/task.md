# Task specification

## Task
Read and write LoRA run files as UTF-8 so LoRA training can be started on Windows.

## Purpose
On Windows, starting a LoRA training job fails with `training_parameters_write_failed` (API 503). `lora_parameters.py` and `lora_trainer.py` call `read_text()` without an encoding, so Windows decodes the UTF-8 run files (`manifest.json`, `training-parameters.json`) as cp950 and fails on non-ASCII names such as `水彩旅人`. Phase 5 (LoRA) trains on the Windows worker, so this blocks it.

## Outcome
Starting, running and recording a LoRA training job works on Windows exactly as on macOS, and the LoRA feature tests that are skipped on Windows run and pass there.

## Scope
Included: every text read/write in `backend/app` without an explicit encoding (7 places found on 2026-11-24, including `services/lora_parameters.py:84,97,110` and `services/lora_trainer.py:1451,1548`) uses `encoding="utf-8"`; remove the `_WINDOWS_UTF8_BUG` skip marker from the backend tests.
Excluded: other Windows-only test problems; changes to LoRA behavior.
Open questions: none.
Read first: [docs/lora-training.md](../../lora-training.md), `backend/app/services/lora_parameters.py`.

## Done when
- [x] No `read_text()`, `write_text()` or text-mode `open()` in `backend/app` lacks an explicit encoding. Check: `grep` in the manifest. Evidence: command output.
- [x] The `_WINDOWS_UTF8_BUG` marker no longer exists in `backend/tests`, and the tests it skipped pass on Windows. Check: Backend suite on Windows. Evidence: test output.
- [x] The full Backend suite passes on Windows with no hang; the macOS rerun moved to [p1-05](../p1-05-mcp-e2e-smoke-mac/task.md). Check: the commands in AGENTS.md. Evidence: test output.

## Result
2026-11-24, in the planning session: 7 reads in `backend/app` and 20 in `backend/tests` now use UTF-8; the skip marker is gone. Windows: Backend 2018 passed, 6 skipped; MCP 314 passed, 4 skipped. macOS rerun moved to p1-05 (owner, 2026-11-24). Commit `531a68d`.

## Delivery
- Artifact: commit on a feature branch, `manifest.md`.
- Known limitations: a real training run is verified in Phase 5.
