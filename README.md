# AI Drawing

AI Drawing lets AI agents and people generate images through a local ComfyUI. A FastAPI Backend owns jobs, artifacts and provenance; an MCP server gives agents intent-level tools; a React UI covers prompt composition, generation, the Gallery and LoRA training.

## Goals

1. **Agent-ready MCP server**: an agent can request, track, retrieve and revise images without human help.
2. **LAN workers**: ComfyUI jobs can run on other Windows machines on the same network that run the same project.
3. **Prompt dashboard**: users build reusable prompt combinations for ComfyUI workflows.
4. **LoRA training**: train, register and use LoRA models from owner datasets.

Current state: [docs/CURRENT.md](docs/CURRENT.md).

## Components

| Component | Path | Role |
|---|---|---|
| Backend | `backend/` | FastAPI + SQLAlchemy. Job queue, ComfyUI REST/WebSocket client, Gallery, Prompt Library, style presets, Civitai, LoRA training, worker routing |
| Frontend | `frontend/` | React + Vite + Tailwind. Dashboard, Generate, Gallery, Prompt Workbench, LoRA pages |
| MCP server | `mcp-server/` | Python MCP SDK, stdio. Calls the Backend; a few tools call ComfyUI directly |
| Windows worker | `worker/windows/` | Runs on a remote Windows host and proxies its ComfyUI to the Backend |
| Discord bot | `discord-bot/` | Slash commands that call the Backend; result delivery for MCP |
| Workflow templates | `backend/workflows/` | ComfyUI API graphs with `.meta.json` form metadata |
| Prompt library | `prompt_library/` | Versioned prompt fragments and combinations |
| Style presets | `style_presets/` | Reusable recipes and saved graphs |
| Launcher | `setup.sh`, `setup.ps1`, `scripts/launcher/` | Bootstrap, start and stop the stack |

ComfyUI itself runs on the host, outside Docker.

## Quick start

Requirements: Git, Docker with Compose 2.24+, and a GPU driver if you generate on GPU.

```bash
./setup.sh        # macOS / Linux
```

```powershell
.\setup.ps1       # Windows
```

The launcher asks whether ComfyUI is `managed`, `external` or `disabled`, then starts the stack. It does not install models or custom nodes.

| Service | Default URL |
|---|---|
| Frontend | http://127.0.0.1:5173 |
| Backend | http://127.0.0.1:8001 (`/docs` for the API) |
| ComfyUI | http://127.0.0.1:8188 |

Full setup: [docs/setup.md](docs/setup.md). Connect an agent: [docs/mcp.md](docs/mcp.md).

## Data

| Location | Contents |
|---|---|
| `data/` | Database, Gallery, outputs, logs, datasets |
| `prompt_library/` | Prompt library (back it up together with `data/`) |
| `.env` | Private settings and secrets — never commit |
| `.ai-drawing/compose.local.yaml` | Generated ComfyUI mounts |

## Development

```bash
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-backend-tests" python -m pytest -c pytest.ini backend/tests -q
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-mcp-tests" python -m pytest -c pytest.ini mcp-server/tests -q
cd frontend && npm test
```

Backend tests refuse to run without `AI_DRAWING_TEST_ROOT`, a scratch directory that isolates the test database and paths from real data. Backend and MCP may need separate Python environments. Launcher tests live in `scripts/tests/`.

Known baseline: 26 Backend tests fail on `main` (Prompt Library inventory snapshots, worker packaging checks, PowerShell fixtures on non-Windows).

## Documentation

Start at the [document map](docs/INDEX.md). Agents start at [AGENTS.md](AGENTS.md).
