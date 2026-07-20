# Cross-Platform One-Click Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide one-command Windows, macOS, and Linux setup that starts the Dockerized AI Drawing web application and optionally discovers or installs a native, hardware-appropriate ComfyUI without downloading models.

**Architecture:** Thin PowerShell/Bash wrappers install a pinned `uv` runtime and invoke one standard-library Python launcher. The launcher owns host detection, atomic local configuration, native ComfyUI lifecycle, and Docker Compose orchestration; Compose owns Frontend and Backend, while a Backend status API exposes optional ComfyUI degradation to the UI.

**Tech Stack:** Python 3.12 standard library, uv 0.11.29, Docker Compose v2.24+, FastAPI/Pydantic/httpx, React 18/Vitest, Nginx, pytest

**Design:** `docs/superpowers/specs/2026-07-20-cross-platform-one-click-startup-design.md`

**Official references:** [ComfyUI manual install](https://docs.comfy.org/installation/manual_install), [ComfyUI requirements](https://docs.comfy.org/installation/system_requirements), [ComfyUI v0.28.0](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.28.0), [uv installer](https://docs.astral.sh/uv/getting-started/installation/), [uv installer options](https://docs.astral.sh/uv/reference/installer/), [PyTorch local install](https://docs.pytorch.org/get-started/locally/)

---

## File Structure

Host launcher:

- Create `setup.ps1`, `setup.sh`, and `scripts/bootstrap.py` as entry points.
- Create focused modules in `scripts/launcher/`: `constants.py`, `models.py`, `runner.py`, `platforms.py`, `configuration.py`, `comfyui.py`, `processes.py`, `relay.py`, `docker.py`, and `cli.py`.
- Create `scripts/comfyui_relay.py` as the isolated Linux TCP relay.
- Create `scripts/tests/`; tests use fake runners/prompts/HTTP and never install ComfyUI or launch real containers.

Containers and application:

- Create `.dockerignore`, `backend/scripts/docker_entrypoint.py`, `backend/tests/test_docker_entrypoint.py`, and `scripts/tests/test_compose_contract.py`.
- Modify `.gitignore`, `.env.example`, `docker-compose.yml`, `backend/Dockerfile`, and `frontend/nginx.conf`; add `frontend/package-lock.json`.
- Create Backend system-status schema/service/API/tests; modify Backend config/main.
- Create a tested Frontend system-status card; integrate it into Dashboard.
- Update README, setup guide, and progress only after verification.

---

### Task 1: Launcher foundation and wrappers

**Files:**
- Create: `setup.ps1`
- Create: `setup.sh`
- Create: `scripts/bootstrap.py`
- Create: `scripts/launcher/__init__.py`
- Create: `scripts/launcher/constants.py`
- Create: `scripts/launcher/models.py`
- Create: `scripts/launcher/runner.py`
- Create: `scripts/launcher/cli.py`
- Create: `scripts/tests/conftest.py`
- Create: `scripts/tests/test_models.py`
- Create: `scripts/tests/test_wrappers.py`

- [ ] **Step 1: Write failing command, state, and wrapper tests**

```python
def test_commands_are_stable():
    assert {item.value for item in LauncherCommand} == {
        "setup", "start", "stop", "status", "reconfigure", "logs", "update-comfyui"
    }


def test_state_round_trip(tmp_path):
    state = LauncherState(
        schema_version=1,
        comfy_mode=ComfyMode.MANAGED,
        comfyui_root=tmp_path / "Comfy UI",
        device=DeviceMode.MPS,
        comfyui_port=8188,
        managed_pid=42,
        managed_identity="python main.py --port 8188",
    )
    assert LauncherState.from_json(state.to_json()) == state
    assert "authorization" not in state.to_json().lower()


def test_wrappers_pin_uv_and_forward_arguments(project_root):
    ps1 = (project_root / "setup.ps1").read_text(encoding="utf-8")
    sh = (project_root / "setup.sh").read_text(encoding="utf-8")
    for content in (ps1, sh):
        assert "0.11.29" in content
        assert "UV_UNMANAGED_INSTALL" in content
        assert "scripts/bootstrap.py" in content
    assert "$args" in ps1
    assert '"$@"' in sh
```

- [ ] **Step 2: Run tests and confirm missing modules/files fail**

Run: `uv run --python 3.12 --with pytest pytest scripts/tests/test_models.py scripts/tests/test_wrappers.py -q`

Expected: collection/file assertions fail because the launcher does not exist.

- [ ] **Step 3: Implement stable types and the runner boundary**

`constants.py` defines:

```python
UV_VERSION = "0.11.29"
BOOTSTRAP_PYTHON = "3.12"
COMFYUI_PYTHON = "3.12"
COMFYUI_REPOSITORY = "https://github.com/Comfy-Org/ComfyUI.git"
COMFYUI_VERSION = "v0.28.0"
COMPOSE_MINIMUM = (2, 24, 0)
DEFAULT_FRONTEND_PORT = 5173
DEFAULT_BACKEND_PORT = 8001
DEFAULT_COMFYUI_PORT = 8188
STATE_SCHEMA_VERSION = 1
```

`models.py` defines string enums `LauncherCommand`, `ComfyMode(disabled/external/managed)`, and `DeviceMode(nvidia/mps/cpu)`, plus frozen `HostInfo`, `ComfyPaths`, `LocalSettings`, and `LauncherState`. JSON conversion explicitly handles enums/paths and rejects unknown schema versions.

`runner.py` defines `CommandResult`, a `Runner` protocol, and `SubprocessRunner.run(args, cwd=None, env=None, check=False, capture=True)`. Every command is an argument list; never use `shell=True`.

- [ ] **Step 4: Implement wrappers and delegation**

Both wrappers set `UV_NO_MODIFY_PATH=1`, use `UV_UNMANAGED_INSTALL` in the user cache, acquire pinned uv only when unavailable, and run:

```text
uv run --python 3.12 --no-project scripts/bootstrap.py <forwarded arguments>
```

`bootstrap.py` calls `launcher.cli.main`. Initially `cli.py` only parses all seven stable commands and returns an integer.

- [ ] **Step 5: Verify and commit**

Run the focused tests. Commit `feat: add cross-platform launcher foundation`.

---

### Task 2: Platform, device, path, and process identity detection

**Files:**
- Create: `scripts/launcher/platforms.py`
- Create: `scripts/tests/test_platforms.py`

- [ ] **Step 1: Write failing pure detection tests**

Cover Windows/Linux NVIDIA, Apple Silicon MPS, Intel macOS CPU, Linux CPU, `XDG_DATA_HOME`, Unicode/spaced paths, `.venv`, `venv`, Windows portable Python, `nvidia-smi` failure, and OS-specific identity commands.

```python
def test_apple_silicon_uses_mps():
    host = HostInfo("Darwin", "arm64", Path("/Users/test"))
    assert choose_device(host, nvidia_available=False) is DeviceMode.MPS
    assert default_comfyui_root(host) == Path(
        "/Users/test/Library/Application Support/ai-drawing/ComfyUI"
    )


def test_linux_without_nvidia_uses_cpu():
    host = HostInfo("Linux", "x86_64", Path("/home/test"))
    assert choose_device(host, nvidia_available=False) is DeviceMode.CPU
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --python 3.12 --with pytest pytest scripts/tests/test_platforms.py -q`

- [ ] **Step 3: Implement the injected detection interface**

Implement `detect_host(system, machine, home) -> HostInfo`, `nvidia_available(runner) -> bool`, `choose_device(host, nvidia_available) -> DeviceMode`, `default_comfyui_root(host, xdg_data_home) -> Path`, `comfyui_python_candidates(root, host)`, `process_identity_command(system, pid) -> list[str]`, and `read_process_identity(host, pid, runner) -> str | None`. Optional override arguments default to the actual host values; candidate results are immutable tuples of paths.

Detection order: NVIDIA on Windows/Linux, MPS on arm64 macOS, then CPU. AMD/Intel acceleration is outside this approved scope and must not be silently claimed.

- [ ] **Step 4: Verify and commit**

Run focused tests. Commit `feat: detect launcher platform and device`.

---

### Task 3: Atomic local configuration and redaction

**Files:**
- Create: `scripts/launcher/configuration.py`
- Create: `scripts/tests/test_configuration.py`
- Modify: `.gitignore`
- Modify: `.env.example`

- [ ] **Step 1: Write failing config tests**

```python
def test_connected_env_uses_only_container_model_paths(tmp_path):
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))
    rendered = render_env(settings)
    assert "COMFYUI_BASE_URL=http://host.docker.internal:8188" in rendered
    assert "COMFYUI_CHECKPOINTS_DIR=/comfyui/models/checkpoints" in rendered
    assert "DATABASE_URL=sqlite:////data/database/auto_draw.db" in rendered
    assert str(tmp_path) not in rendered


def test_disabled_override_is_empty():
    assert render_compose_override(LocalSettings.disabled()) == "services: {}\n"


def test_failed_validation_keeps_previous_config(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OLD=1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        write_configuration(tmp_path, settings, state, validate=lambda *_: False)
    assert env_path.read_text(encoding="utf-8") == "OLD=1\n"
```

Also test YAML quoting for Windows drives/spaces/non-ASCII, state schema rejection, preservation of `CIVITAI_AUTHORIZATION`, and redaction of authorization/token/secret/password.

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --python 3.12 --with pytest pytest scripts/tests/test_configuration.py -q`

- [ ] **Step 3: Implement the configuration interface**

Implement `parse_env(text)`, `render_env(settings, preserved)`, `render_compose_override(settings)`, `atomic_write(path, content)`, `load_state(path)`, `write_configuration(root, settings, state, validate)`, and recursive `redact(value)`. `write_configuration` writes same-directory temporary files, invokes the supplied Compose validator against those files, then uses `Path.replace` only after validation succeeds.

Generate `.ai-drawing/compose.local.yaml` with long bind syntax and JSON-quoted host paths. Map checkpoints, loras, diffusion models, text encoders, VAE, embeddings, controlnet, upscale models, and input to stable `/comfyui/<category>` container paths.

- [ ] **Step 4: Update safe defaults**

Ignore `.ai-drawing/` and `data/`. Make `.env.example` Docker-safe with `COMFYUI_MODE=disabled`, explicit `/data` and `/comfyui` subdirectories, host Backend 8001, and only a commented Civitai placeholder.

- [ ] **Step 5: Verify and commit**

Run tests, `git diff --check`, and a secret scan. Commit `feat: generate atomic local startup configuration`.

---

### Task 4: ComfyUI discovery, install, validation, and update

**Files:**
- Create: `scripts/launcher/comfyui.py`
- Create: `scripts/tests/test_comfyui_launcher.py`

- [ ] **Step 1: Write failing discovery/install-plan tests**

Cover root validation (`main.py`, `models/`), bounded candidates, duplicates, venv/portable Python, running external instances, nonempty target refusal, staging cleanup, NVIDIA/MPS/CPU plans, smoke failures, and update rollback.

```python
def test_nvidia_plan_is_pinned(tmp_path):
    plan = build_install_plan(tmp_path / "ComfyUI", DeviceMode.NVIDIA)
    args = [arg for command in plan.commands for arg in command.args]
    assert "v0.28.0" in args
    assert "3.12" in args
    assert "https://download.pytorch.org/whl/cu130" in args


def test_install_refuses_nonempty_target(tmp_path):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    (target / "user.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(InstallTargetNotEmpty):
        prepare_staging_target(target)
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --python 3.12 --with pytest pytest scripts/tests/test_comfyui_launcher.py -q`

- [ ] **Step 3: Implement discovery**

Implement `ComfyValidation`, `validate_comfyui_root`, `discover_comfyui`, and `probe_comfyui`. Never recursively scan a drive. A running installation without controllable Python is external; the launcher never owns/stops it.

- [ ] **Step 4: Implement pinned staged installation**

Exact sequence:

```text
git clone --branch v0.28.0 --depth 1 https://github.com/Comfy-Org/ComfyUI.git <staging>
uv python install 3.12
uv venv --python 3.12 <staging>/.venv
uv pip install --python <venv-python> <device-specific torch packages>
uv pip install --python <venv-python> -r <staging>/requirements.txt
<venv-python> -c <device smoke check>
```

Use CUDA 13.0 wheels for NVIDIA, default wheels for MPS, and PyTorch CPU index for CPU. Assert CUDA/MPS availability for accelerated modes. Move staging to final only after success. Never download models/custom nodes.

`update-comfyui` saves the old commit, checks out the pinned stable tag, reinstalls, smoke-tests, and restores the old commit on failure.

- [ ] **Step 5: Verify and commit**

Run focused tests. Commit `feat: manage optional native ComfyUI installation`.

---

### Task 5: Safe process and Linux relay lifecycle

**Files:**
- Create: `scripts/launcher/processes.py`
- Create: `scripts/launcher/relay.py`
- Create: `scripts/comfyui_relay.py`
- Create: `scripts/tests/test_processes.py`
- Create: `scripts/tests/test_relay.py`

- [ ] **Step 1: Write failing ownership/relay tests**

Test managed/external distinction, PID identity mismatch, stale cleanup, Windows hidden process, Unix group, CPU flag, readiness timeout, and relay address safety.

```python
def test_pid_reuse_is_not_terminated(fake_runner, managed_state):
    fake_runner.identity = "unrelated.exe --serve"
    result = stop_managed_process(managed_state, fake_runner, WINDOWS)
    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"


def test_external_is_never_stopped(fake_runner, external_state):
    assert stop_comfyui(external_state, fake_runner, LINUX).stopped is False
    assert fake_runner.commands == []
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --python 3.12 --with pytest pytest scripts/tests/test_processes.py scripts/tests/test_relay.py -q`

- [ ] **Step 3: Implement process ownership**

Start `<python> main.py --listen 127.0.0.1 --port <port>`, adding `--cpu` only for CPU. Windows uses hidden detached process flags; Unix uses `start_new_session=True`. Record PID/identity only after `/system_stats`. Stop only after identity matches.

- [ ] **Step 4: Implement Linux bridge relay**

Use `asyncio.start_server` to forward a validated local Docker bridge address to `127.0.0.1:<port>`. Reject wildcard, loopback, multicast, and public binds. Give relay separate ownership state/logs.

- [ ] **Step 5: Verify and commit**

Run tests. Commit `feat: manage safe ComfyUI host lifecycle`.

---

### Task 6: Docker preflight and CLI state machine

**Files:**
- Create: `scripts/launcher/docker.py`
- Modify: `scripts/launcher/cli.py`
- Create: `scripts/tests/test_docker_launcher.py`
- Create: `scripts/tests/test_cli.py`

- [ ] **Step 1: Write failing Docker tests**

Cover daemon, Compose >=2.24, list commands, occupied ports without terminating owners, alternate ports, mount probe, config validation, and readiness.

```python
def test_compose_command_uses_override(project_root):
    assert compose_command(project_root, "up", "-d", "--build") == [
        "docker", "compose", "--env-file", str(project_root / ".env"),
        "-f", str(project_root / "docker-compose.yml"),
        "-f", str(project_root / ".ai-drawing/compose.local.yaml"),
        "up", "-d", "--build",
    ]
```

- [ ] **Step 2: Write failing scripted CLI tests**

Cover decline, discovered instance, install, install failure then disabled continuation, explicit CPU fallback, external ownership, all commands, rollback, noninteractive fast failure, and secret-free output.

```python
def test_first_run_can_decline_comfyui(harness):
    harness.answers = [False]
    assert main(["setup"], services=harness.services) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.DISABLED
    assert harness.compose_started is True
```

- [ ] **Step 3: Run and confirm failure**

Run: `uv run --python 3.12 --with pytest pytest scripts/tests/test_docker_launcher.py scripts/tests/test_cli.py -q`

- [ ] **Step 4: Implement Docker operations**

Implement `preflight`, `port_available`, `mount_probe`, `compose_command`, `validate_compose`, `compose_up`, `compose_down`, and bounded HTTP readiness. Commands are lists. Mount probes use resolved explicit paths and a pinned image.

- [ ] **Step 5: Implement CLI**

Flow:

```text
preflight -> ports -> ask ComfyUI -> discover -> confirm/install/disable
-> device smoke -> process readiness -> mount probes -> staged config
-> docker compose config -> atomic replace -> compose up
-> Backend health -> Frontend readiness -> concise summary
```

Default is setup; valid state makes it start. Reconfigure rolls back on failure. Logs never print `.env`. Errors provide code, message, and hint.

- [ ] **Step 6: Verify and commit**

Run all launcher tests. Commit `feat: orchestrate one-command application startup`.

---

### Task 7: Persistent, reproducible Docker application

**Files:**
- Create: `.dockerignore`
- Modify: `docker-compose.yml`
- Modify: `backend/Dockerfile`
- Create: `backend/scripts/docker_entrypoint.py`
- Create: `backend/tests/test_docker_entrypoint.py`
- Create: `scripts/tests/test_compose_contract.py`
- Create: `frontend/package-lock.json`
- Modify: `frontend/nginx.conf`

- [ ] **Step 1: Write failing seed/Compose tests**

Test seed-only-when-empty. Parse Compose with PyYAML; assert loopback 8001/5173, persisted database/output/gallery/lora/prompt/log binds, Backend health, Frontend healthy dependency, Linux host gateway, optional `.env`, no base model mounts, and Nginx `/api`/`/gallery`.

```python
def test_seed_does_not_overwrite_user_data(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir(); target.mkdir()
    (source / "catalog.json").write_text("seed", encoding="utf-8")
    (target / "catalog.json").write_text("user", encoding="utf-8")
    assert seed_directory(source, target) is False
    assert (target / "catalog.json").read_text(encoding="utf-8") == "user"
```

- [ ] **Step 2: Run and confirm failure**

Run: `uv run --python 3.12 --with pytest --with pyyaml pytest backend/tests/test_docker_entrypoint.py scripts/tests/test_compose_contract.py -q`

- [ ] **Step 3: Implement entrypoint and image layout**

Entrypoint seeds `/data/prompt_library` from `/opt/ai-drawing-seed/prompt_library` only when empty, creates data dirs, and `os.execvp`s uvicorn. Build from root with:

```dockerfile
FROM python:3.11-slim
WORKDIR /workspace/backend
COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt
COPY backend /workspace/backend
COPY style_presets /workspace/style_presets
COPY prompt_library /opt/ai-drawing-seed/prompt_library
ENV PYTHONUNBUFFERED=1
ENV PROMPT_LIBRARY_SEED_DIR=/opt/ai-drawing-seed/prompt_library
ENTRYPOINT ["python", "scripts/docker_entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Implement Compose**

Use loopback host ports, optional `.env`, default disabled mode, `sqlite:////data/database/auto_draw.db`, explicit binds under `/data`, host gateway, healthcheck, `service_healthy`, init, and clean stop. Base Compose has no model mounts.

- [ ] **Step 5: Make builds deterministic**

Generate `frontend/package-lock.json` with `npm install --package-lock-only`, verify `npm ci`, proxy `/gallery`, and exclude secrets/runtime/caches/experiments/docs/MCP from root Docker context while retaining needed sources.

- [ ] **Step 6: Verify and commit**

Run tests, `docker compose config`, and both image builds. Commit `feat: make Docker startup persistent and reproducible`.

---

### Task 8: Backend dependency status API

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/schemas/system.py`
- Create: `backend/app/services/dependency_status.py`
- Create: `backend/app/api/system.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_system_status.py`
- Modify: `backend/tests/test_config_paths.py`

- [ ] **Step 1: Write failing status tests**

```python
def test_disabled_does_not_probe(settings, probe):
    settings.comfyui_mode = "disabled"
    result = get_system_status(settings, probe=probe)
    assert result.application == "healthy"
    assert result.comfyui.state == "not_configured"
    assert probe.calls == []


def test_reachable_without_model_is_no_models(settings, successful_probe):
    result = get_system_status(settings, probe=successful_probe)
    assert result.comfyui.state == "no_models"
```

Also cover unreachable, checkpoint/split-model counts, optional missing dirs/degraded, timeout, hints, and API serialization.

- [ ] **Step 2: Run and confirm failure**

From backend: `pytest tests/test_system_status.py -q`

- [ ] **Step 3: Add types**

Add `comfyui_mode: Literal["disabled", "external", "managed"] = "external"`; Compose sets disabled. Define `connected`, `not_configured`, `unreachable`, `no_models`, `degraded`, plus DTOs with `Field(default_factory=list)` warnings.

- [ ] **Step 4: Implement service and route**

Probe `/system_stats` with two-second timeout and never propagate dependency errors. Count checkpoints/diffusion models. Unreachable overrides filesystem; no generation model is no_models; usable model plus optional missing directories is degraded. Register `GET /api/system/status`; keep `/health` application-only.

- [ ] **Step 5: Verify and commit**

Run status/main/config/resource tests. Commit `feat: report optional ComfyUI dependency status`.

---

### Task 9: Frontend readiness display

**Files:**
- Create: `frontend/src/components/SystemStatusCard.tsx`
- Create: `frontend/src/components/SystemStatusCard.test.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/Dashboard.test.tsx`

- [ ] **Step 1: Write failing component/fetch tests**

Test all states, hints, warnings, fetch failure, and retained module cards.

```tsx
it("shows no-model state as connected but incomplete", () => {
  render(<SystemStatusCard status={{
    state: "no_models", configured: true, reachable: true,
    model_count: 0, warnings: [], hint: "將模型放入 checkpoints",
  }} />);
  expect(screen.getByText("ComfyUI 已連線，尚無模型")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run and confirm failure**

From frontend: `npm test -- --run src/components/SystemStatusCard.test.tsx src/pages/Dashboard.test.tsx`

- [ ] **Step 3: Implement**

Use an exhaustive state switch. Dashboard fetches `/api/system/status` once with AbortController, handles non-2xx/unmount, and places the card above modules. Do not rely only on color.

- [ ] **Step 4: Verify and commit**

Run `npm test` and `npm run build`. Commit `feat: show ComfyUI readiness on dashboard`.

---

### Task 10: End-to-end verification and documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/setup-guide.md`
- Modify: `docs/PROGRESS.md`
- Modify implementation only when verification demonstrates a defect

- [ ] **Step 1: Run regression**

```text
uv run --python 3.12 --with pytest --with pyyaml pytest scripts/tests -q
python -m compileall -q scripts
cd backend && pytest tests -q
cd ../frontend && npm ci && npm test && npm run build
cd .. && docker compose config
git diff --check
```

Expected: all pass except already-documented environment skips.

- [ ] **Step 2: Verify empty/disabled mode**

Start base Compose without `.env`. Verify Backend health, system status `not_configured`, Frontend 200, then stop.

- [ ] **Step 3: Verify connected mode and persistence**

Use fake `/system_stats` plus temporary model dirs/override. Verify connected/no_models. Write DB/Prompt Library markers, rebuild/recreate, assert persistence. Clean only resolved test paths under explicit test-data.

- [ ] **Step 4: Run real-platform smoke checks where available**

Run setup/start/status/stop on Windows NVIDIA, Linux NVIDIA, Linux CPU, Intel macOS CPU, Apple Silicon MPS, and a declined-ComfyUI flow. Mark unavailable hardware “not run”; mocks do not count as real platform passes.

- [ ] **Step 5: Rewrite startup docs**

Primary instructions become `git clone`, `cd`, then `./setup.ps1` or `./setup.sh`. State Git/Docker/network/driver prerequisites, optional ComfyUI, no automatic model download, and all launcher commands. Move manual development startup to advanced docs. Host Backend is 8001; container is 8000.

- [ ] **Step 6: Update progress with observed evidence**

Document launcher, native optional ComfyUI, persistence, UI status, exact automated results, and only actually-run platform rows.

- [ ] **Step 7: Final verification and staging audit**

Repeat all tests/build/config checks. Inspect status and staged names. The pre-existing unrelated repository-root `package-lock.json` must remain unstaged.

- [ ] **Step 8: Commit completion**

Stage only intended files and commit `feat: add cross-platform one-click startup`.
