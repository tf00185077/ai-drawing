# Windows Worker Bootstrap Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Windows Setup install a complete uv standalone Python runtime and safely remove only installer-created internal uv alias junctions before managed bootstrap.

**Architecture:** Keep migration's no-follow security boundary unchanged. Add narrowly scoped installer helpers for checked external commands, concrete Python discovery, and trusted alias normalization; exercise those helpers through a dot-sourced PowerShell harness and then rebuild the canonical distribution artifacts.

**Tech Stack:** PowerShell 5.1, Python 3.11/pytest, uv, Git, deterministic ZIP builder

---

### Task 1: Checked uv dependency installation

**Files:**
- Modify: `backend/tests/test_worker_operational_recovery.py`
- Modify: `worker/windows/Install-Worker.ps1`

- [ ] **Step 1: Write a failing behavioral test**

Add a PowerShell harness test that dot-sources an extracted installer-helper block with a fake `uv.cmd`. The fake returns exit code 23 and the test asserts that `Invoke-CheckedInstallerCommand` terminates with `INSTALL_DEPENDENCY_FAILED`. Add a success case whose fake records arguments and assert the real helper passes `pip install --system --python <path>`.

```python
def test_installer_checked_uv_install_uses_system_and_stops_on_failure(tmp_path: Path) -> None:
    result = _run_installer_helper_harness(tmp_path, "Invoke-WorkerPipInstall", fake_uv_exit=23)
    assert result.returncode != 0
    assert "INSTALL_DEPENDENCY_FAILED" in result.stderr
    assert "pip|install|--system|--python" in (tmp_path / "uv-args.txt").read_text()
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
pytest backend/tests/test_worker_operational_recovery.py::test_installer_checked_uv_install_uses_system_and_stops_on_failure -q
```

Expected: FAIL because the installer has no checked helper and omits `--system`.

- [ ] **Step 3: Implement the minimal checked-command helper**

Add helpers near the top of `Install-Worker.ps1`:

```powershell
function Invoke-CheckedInstallerCommand {
    param([string]$FilePath, [string[]]$Arguments, [string]$ErrorCode)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw $ErrorCode }
}

function Invoke-WorkerPipInstall {
    param([string]$Uv, [string]$Python, [string[]]$Arguments)
    Invoke-CheckedInstallerCommand -FilePath $Uv `
        -Arguments (@("pip", "install", "--system", "--python", $Python) + $Arguments) `
        -ErrorCode "INSTALL_DEPENDENCY_FAILED"
}
```

Replace the ComfyUI, PyTorch, Worker, and custom-node pip calls with `Invoke-WorkerPipInstall`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the new test and existing installer tests:

```powershell
pytest backend/tests/test_worker_operational_recovery.py backend/tests/test_worker_all_entrypoints.py -q
```

Expected: all focused tests pass (Windows-only tests may skip when privileges are unavailable).

### Task 2: Concrete Python discovery and trusted uv alias normalization

**Files:**
- Modify: `backend/tests/test_worker_operational_recovery.py`
- Modify: `worker/windows/Install-Worker.ps1`

- [ ] **Step 1: Write failing safe-alias integration tests**

Add Windows-only tests that build a temporary `runtime/python` tree with a concrete CPython directory and an internal junction alias. Invoke the real installer helpers and assert the concrete `python.exe` is selected, the alias is removed, and the target remains byte-identical.

```python
@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration")
def test_installer_normalizes_only_internal_uv_python_alias(tmp_path: Path) -> None:
    result = _run_python_alias_harness(tmp_path, target="internal", alias_name="cpython-3.12-windows-x86_64-none")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["alias_exists"] is False
    assert payload["target_sentinel"] == "preserved"
    assert "cpython-3.12.13-windows-x86_64-none" in payload["python"]
```

- [ ] **Step 2: Run the safe-alias test and verify RED**

Run the named test. Expected: FAIL because the helpers do not exist and bootstrap still sees the alias.

- [ ] **Step 3: Write failing hostile-reparse tests**

Add table-driven Windows cases for an external target, wrong alias name, and a target that is itself a reparse point. Assert normalization fails closed or leaves the link for the unchanged migration inventory to reject, and external sentinels remain untouched.

```python
@pytest.mark.parametrize("case", ["external", "wrong-name", "nested-reparse"])
def test_installer_never_removes_untrusted_python_reparse(case: str, tmp_path: Path) -> None:
    result = _run_python_alias_harness(tmp_path, target=case)
    assert result.returncode != 0
    assert "INSTALL_PYTHON_REPARSE_UNSAFE" in result.stderr
    assert (tmp_path / "outside" / "sentinel.txt").read_text() == "preserved"
```

- [ ] **Step 4: Implement concrete discovery and normalization**

Add `Get-ConcreteInstalledPython` and `Remove-TrustedUvPythonAliases`. Use canonical paths and `LinkType -eq "Junction"`; require direct children, a strict `^cpython-[0-9.]+-windows-[A-Za-z0-9_]+-none$` leaf, an internal concrete target, and a selected executable outside the alias. Remove only the junction object with `Remove-Item -LiteralPath $Alias.FullName -Force`.

Call concrete discovery immediately after `uv python install`, persist its path, and normalize aliases immediately before `Initialize-ManagedWorkerLayout`.

- [ ] **Step 5: Run all alias and migration-security tests and verify GREEN**

Run:

```powershell
pytest backend/tests/test_worker_operational_recovery.py backend/tests/test_worker_all_entrypoints.py -q
```

Expected: new alias tests pass; existing external reparse tests continue to pass unchanged.

### Task 3: Documentation, source/dist parity, and deterministic ZIP

**Files:**
- Modify: `worker/windows/README.md`
- Modify: `docs/PROGRESS.md`
- Regenerate: `dist/AI-Drawing-NVIDIA-Worker/**`
- Regenerate: `dist/AI-Drawing-NVIDIA-Worker.zip`

- [ ] **Step 1: Document recovery semantics**

Explain that Setup uses uv standalone Python with explicit system installation, removes only validated internal uv aliases, and aborts on any unknown reparse point or dependency failure. Record the real Windows failure and fix in `docs/PROGRESS.md` without including tokens.

- [ ] **Step 2: Rebuild the distribution**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
```

Expected: `Built ...\dist\AI-Drawing-NVIDIA-Worker.zip`.

- [ ] **Step 3: Verify byte parity and archive membership**

Run a Python verification that compares every included `worker/windows` file byte-for-byte with the extracted dist tree and every ZIP member, rejects missing/extra members, then print SHA-256.

```powershell
python scripts/build-windows-worker.py
Get-FileHash dist/AI-Drawing-NVIDIA-Worker.zip -Algorithm SHA256
```

Expected: no parity mismatches and one SHA-256 digest.

### Task 4: Regression gate and live Windows recovery

**Files:**
- No source changes unless a failing regression exposes a defect

- [ ] **Step 1: Run focused Worker gate**

```powershell
pytest backend/tests/test_worker_all_entrypoints.py backend/tests/test_worker_operational_recovery.py backend/tests/test_worker_pairing.py backend/tests/test_worker_runtime.py backend/tests/test_worker_updater_cli.py backend/tests/test_worker_updater_runtime.py backend/tests/test_worker_updater_state.py -q
```

Expected: all applicable tests pass; only documented privilege/platform skips remain.

- [ ] **Step 2: Run repository hygiene checks**

```powershell
python -m compileall -q scripts worker/windows
git diff --check
git status --short
```

Expected: compilation and whitespace checks succeed; status contains only intended changes plus the user's pre-existing untracked files.

- [ ] **Step 3: Build a temporary repaired package and rerun Setup as administrator**

Use the rebuilt `dist/AI-Drawing-NVIDIA-Worker` from a temporary location. Preserve existing Worker data and capture only the final success/error lines. Verify listeners 8188 and 8791 and Worker health without printing the token.

- [ ] **Step 4: Run the official D-drive migration only after Setup health succeeds**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\AI-Drawing-Worker-Source\worker\windows\Migrate-Worker.ps1
```

Expected: JSON result with `status: ready`; on failure, leave C/D roots and migration backups untouched.

- [ ] **Step 5: Commit the implementation**

Stage only intended source, tests, docs, and rebuilt distribution artifacts, then commit with:

```powershell
git commit -m "fix(worker): harden Windows managed bootstrap"
```
