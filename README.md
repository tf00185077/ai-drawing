# AI Drawing

Agent-facing ComfyUI generation with Backend jobs, recorded Gallery artifacts, Prompt Library, style presets, MCP and a web frontend. Docker Compose runs Frontend/Backend; ComfyUI and Windows Worker run separately.

LoRA training code exists but is **not accepted as a complete working feature**. See [Training status](docs/training-status.md), not removed automation instructions.

## Start here

- Agent guidance: [AGENTS.md](AGENTS.md).
- Purpose and company preparation: [Goal](docs/GOAL.md).
- Current state and blockers: [Progress](docs/PROGRESS.md).
- Topic authorities: [Document map](docs/INDEX.md).
- Installation: [Setup guide](docs/setup-guide.md).
- Agent connection/tools: [MCP setup](docs/mcp-setup.md).
- Prompt Workbench, authored prompts and saved recipes/graphs: [Resource guide](docs/prompt-and-workflow-resources.md).
- Remote execution/acceptance: [Windows worker](docs/windows-worker.md).

Documentation describes capabilities; it does not authorize installation, generation, downloads, restart or deployment.

## Product launcher

Requirements: Git, running Docker, Docker Compose 2.24+, initial bootstrap/build network access and a compatible driver for GPU use. The launcher needs no global Python/Node installation.

```bash
# macOS / Linux
./setup.sh
```

```powershell
# Windows PowerShell
.\setup.ps1
```

Choose managed, external or disabled host ComfyUI. The launcher does not install models/custom nodes or configure/start MCP. Setup/reconfigure can install/start services and rewrite local settings; do not use them for inspection.

Default URLs: Frontend `http://127.0.0.1:5173`, Backend `http://127.0.0.1:8001`, API docs `http://127.0.0.1:8001/docs`; optional ComfyUI uses port `8188`. Check deployment settings rather than assuming services are running.

## Data and configuration

| Location | Purpose |
|---|---|
| `data/` | Database, Gallery, output, logs and datasets |
| `prompt_library/` | Versioned library, mounted at `/workspace/prompt_library` |
| `.env` | Private runtime settings/secrets |
| `.ai-drawing/compose.local.yaml` | Generated ComfyUI mounts |
| `data/bootstrap/state.json` | Launcher settings/process identity |

Backing up only `data/` misses prompts and custom model/preset paths. Follow [backup and reconfiguration guidance](docs/setup-guide.md#persistent-data-and-backups): setup/reconfigure rebuilds `.env` and can discard custom settings. Keep secrets and backups/logs private.

## Company preparation

Art production and platform engineering are the approved workstreams. All [seven hires](docs/team/README.md) are approved and available for native assignments. Under [CTY's continuous-operation mandate](http://127.0.0.1:3100/AID/issues/AID-4#comment-71655f19-384a-4aa9-af39-d2ba7bdcd9d7), Producer autonomously prioritizes, dispatches and follows completed work with the next useful action; ordinary work does not require repeated start confirmation. CTY owns aesthetics; independent Engineering QA owns technical verification. Hermes handles delegated ordinary follow-through while Producer retains independent priorities; [Goal](docs/GOAL.md#milestone-assessment) defines how journey evidence supports milestone assessment. Windows installation/reporting remains deferred. Follow [Goal](docs/GOAL.md) and [Progress](docs/PROGRESS.md) for current authority, work and genuine decision boundaries.

## Development verification

Use each component's dependency manifests and prepared environment; Backend and MCP may need different environments. Repository `pytest.ini` defines Python paths.

```bash
# Repository root, appropriate component environment
python -m pytest -c pytest.ini backend/tests -q
python -m pytest -c pytest.ini mcp-server/tests -q
```

Frontend commands: `frontend/package.json`. Launcher tests: `scripts/tests/`. Windows, GPU, network and live-generation checks require prerequisites and authorization. Offline tests do not establish deployment or end-to-end acceptance.
