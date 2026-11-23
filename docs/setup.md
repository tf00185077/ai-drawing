# Setup

Run the Backend and Frontend with Docker Compose, and connect a host ComfyUI. MCP, the Discord bot and workers are set up separately ([MCP](mcp.md), [Windows worker](windows-worker.md)).

## Requirements

- Git and a running Docker daemon with Compose 2.24+ (`docker compose`).
- Network access for the first bootstrap and image build.
- A GPU driver on the host if ComfyUI should use the GPU. The launcher does not install drivers.

The launcher bootstraps its own pinned `uv`/Python in the user cache; no global Python or Node is needed.

## Start

```bash
git clone https://github.com/tf00185077/ai-drawing.git
cd ai-drawing
./setup.sh            # macOS / Linux
```

```powershell
.\setup.ps1           # Windows (if blocked: powershell -ExecutionPolicy Bypass -File .\setup.ps1)
```

The first run performs `setup`; later runs perform `start`. Setup checks Docker and ports, asks how to use ComfyUI, validates Compose and starts the services.

| Service | Default URL |
|---|---|
| Frontend | http://127.0.0.1:5173 |
| Backend | http://127.0.0.1:8001 (API docs at `/docs`) |
| ComfyUI (host) | http://127.0.0.1:8188 |

If a port is taken, setup offers another; use the port it reports.

## ComfyUI modes

| Mode | Behavior |
|---|---|
| `external` | Use a ComfyUI you already run. `stop` leaves it alone. |
| `managed` | The launcher starts ComfyUI from an existing folder (needs `main.py`, `models/` and Python) or from its own install. `stop` stops it. |
| `disabled` | Run without generation. |

The launcher never installs models or custom nodes. Device is chosen automatically; override with `--device nvidia|mps|cpu`.

## Launcher commands

Same arguments on `setup.sh` and `setup.ps1`.

| Command | Purpose |
|---|---|
| `setup` | Configure, validate and start |
| `start` / `stop` | Start or stop with the saved configuration |
| `status` | Read-only diagnostics |
| `reconfigure` | Choose modes, paths, devices or ports again |
| `logs` | Launcher, ComfyUI, relay and Compose logs (secrets masked) |
| `update-comfyui` | Update a stopped launcher-installed ComfyUI |
| `dry-run ...` | Show the plan without changing anything |

Non-interactive examples:

```bash
./setup.sh setup --non-interactive --comfyui-mode disabled
./setup.sh reconfigure --backend-port 8011 --frontend-port 5183
```

## Configuration

| File | Role |
|---|---|
| `.env.example` | Example values |
| `.env` | Local settings and secrets (private) |
| `docker-compose.yml` | Services, ports, mounts |
| `.ai-drawing/compose.local.yaml` | Generated ComfyUI mounts |
| `data/bootstrap/state.json` | Launcher state and process identity |

`setup` and `reconfigure` rebuild `.env` from a fixed list of launcher keys. Worker, trainer, caption-provider and other custom settings are dropped (only `CIVITAI_AUTHORIZATION` is kept). Copy `.env` first and re-add custom keys afterwards.

Backend settings are defined in `backend/app/config.py`.

## Data and backups

| Host path | In container | Contents |
|---|---|---|
| `data/database` | `/data/database` | SQLite database, digest cache |
| `data/gallery` | `/data/gallery` | Gallery files |
| `data/outputs` | `/data/outputs` | Generation output |
| `data/lora_train` | `/data/lora_train` | Datasets and training runs |
| `data/logs` | `/data/logs` | Logs |
| `prompt_library` | `/workspace/prompt_library` | Prompt library |

Back up `data/`, `prompt_library/`, `.env` and `.ai-drawing/` together, with the stack stopped. ComfyUI models live outside the repository.

## Troubleshooting

Start with `status` and `logs`. Logs are in `data/logs/` (`bootstrap.log`, `comfyui.log`, `comfyui-relay.log`).

`GET /api/system/status` reports `not_configured`, `unreachable`, `no_models`, `connected` or `degraded`.

| Problem | Fix |
|---|---|
| Docker unavailable | Start Docker; check `docker info` and `docker compose version` |
| Port in use | `reconfigure` with other ports |
| Mount failure | Check Docker file-sharing permissions and paths, then `reconfigure` |
| `no_models` | ComfyUI is running but has no models; add them yourself |
| Device error | Fix the driver, or choose `--device cpu` or `disabled` |
| Changing a managed ComfyUI | `stop` first |

## Running without Docker

```bash
cd backend && python -m pip install -r requirements.txt && uvicorn app.main:app --reload   # port 8000
cd frontend && npm ci && npm run dev                                                      # port 5173
```

Use host paths in settings (not `/data/...`). Point MCP and the Frontend at port 8000 instead of 8001.
