# Setup guide

Docker Compose runs Frontend/Backend. Optional host ComfyUI can use an existing installation or a launcher installation; disabled mode needs neither. Install/connect MCP separately using [MCP setup](mcp-setup.md).

## Requirements

- Git and a running Docker daemon (Docker Desktop or Docker Engine).
- Docker Compose `2.24+`, using `docker compose` rather than legacy `docker-compose`.
- Network access for the initial runtime bootstrap and container build. On macOS/Linux, the wrapper needs `curl` or `wget` for a cold cache.
- Docker permission to access the project and any selected ComfyUI directories.
- A compatible host GPU driver if using GPU generation. The launcher does not install drivers.

The launcher bootstraps pinned uv/Python in the user cache, without global Python/Node.js. A cold-cache wrapper may bootstrap even for `dry-run`.

## Start the application

From a checkout of this repository:

```bash
# macOS / Linux
./setup.sh
```

```powershell
# Windows PowerShell
.\setup.ps1
```

With no subcommand, the first invocation runs setup; an existing configuration uses start. If PowerShell execution policy blocks the script, a process-scoped invocation is:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Setup checks Docker/ports, asks about ComfyUI, validates Compose configuration and starts services. It leaves occupied ports' processes alone; review offered alternative ports.

| Service | Default host URL | Container port |
|---|---|---|
| Frontend | <http://127.0.0.1:5173> | `80` |
| Backend | <http://127.0.0.1:8001> | `8000` |
| Backend API documentation | <http://127.0.0.1:8001/docs> | `8000` |
| Optional host ComfyUI | <http://127.0.0.1:8188> | Not in Compose |

Use the actual port reported by setup. Host Backend port `8001` and container port `8000` are different addresses.

## ComfyUI modes

| Mode | Behavior | Effect of launcher stop |
|---|---|---|
| `disabled` | Frontend/Backend start without generation connectivity | No ComfyUI process is stopped |
| `external` | Uses an already running, reachable instance | The user-owned instance is not stopped |
| `managed` | Starts a controllable existing directory or a launcher installation | Stops only a process whose recorded identity matches |

An existing ComfyUI root needs `main.py` and `models/`; managed mode also needs Python. Installation stages files without overwriting nonempty destinations. It installs runtime dependencies, **not models (checkpoints, LoRAs, VAEs, text encoders) or custom nodes**.

Device selection is automatic; override with `--device nvidia|mps|cpu`. MPS needs native arm64 on Apple Silicon; Intel macOS uses CPU. ComfyUI runs on the host, Frontend/Backend in Docker. [Windows Worker](windows-worker.md) is a separate setup/execution path.

## Launcher commands

The examples use `./setup.sh`; Windows uses `.\setup.ps1` with the same arguments.

| Command | Purpose |
|---|---|
| `./setup.sh setup` | Configure, validate, and start |
| `./setup.sh start` | Start using saved configuration |
| `./setup.sh stop` | Stop Compose and verified launcher-owned processes; leave external ComfyUI alone |
| `./setup.sh status` | Read-only service, ComfyUI, resource, and ownership diagnostics |
| `./setup.sh reconfigure` | Select modes, paths, devices, or ports again; regenerates configuration |
| `./setup.sh logs` | Show launcher, ComfyUI, relay, and recent Compose logs with secret-line masking |
| `./setup.sh update-comfyui` | Update a stopped launcher-installed ComfyUI with valid provenance, not a user-owned installation |
| `./setup.sh dry-run ...` | Show the plan without changing project configuration or starting/stopping services; wrapper bootstrap can still use the network |
| `./setup.sh --help` | Show current arguments |

Examples:

```bash
./setup.sh dry-run --non-interactive --comfyui-mode disabled
./setup.sh setup --non-interactive --comfyui-mode disabled
./setup.sh reconfigure --backend-port 8011 --frontend-port 5183
```

Non-interactive managed setup requires an explicit `--comfyui-path`. Recoverable failures require the applicable `--on-comfy-failure` or `--on-mount-failure` choice; automatic alternate ports require `--accept-alternate-ports`. Consult `--help` for accepted values.

## Configuration and reconfiguration

| File | Role |
|---|---|
| `.env.example` | Versioned example defaults and secret placeholders |
| `.env` | Local Backend/Compose values and secrets |
| `docker-compose.yml` | Versioned service definitions, ports, health checks, and persistent mounts |
| `.ai-drawing/compose.local.yaml` | Generated mounts for the selected host ComfyUI directory |
| `data/bootstrap/state.json` | Launcher configuration, installation provenance, and process identity |

**Back up `.env` before setup/reconfigure.** `scripts/launcher/configuration.py::render_env` rebuilds launcher keys from a fixed whitelist, preserving only nonempty existing `CIVITAI_AUTHORIZATION` as an extra. Worker, caption-provider, trainer and other custom settings can disappear; generated keys lose custom values. Compare the backup and reapply required deployment-specific paths/URLs after success. Transaction rollback protects failed configuration, not custom settings after a successful rewrite.

Keep `.env`, local state and secret-bearing backups private. Redact tokens from examples, committed YAML, shared logs and issue reports.

## Persistent data and backups

These are the default bind mounts in `docker-compose.yml`, relative to the repository root:

| Host path | Backend container path | Contents |
|---|---|---|
| `./data/database` | `/data/database` | SQLite database and digest cache |
| `./data/gallery` | `/data/gallery` | Gallery files |
| `./data/outputs` | `/data/outputs` | Generation output |
| `./prompt_library` | `/workspace/prompt_library` | Prompt Library files |
| `./data/lora_train` | `/data/lora_train` | Existing dataset/training storage |
| `./data/logs` | `/data/logs` | Application and launcher logs |

`PROMPT_LIBRARY_DIR` defaults to `/workspace/prompt_library` in Compose. **The host Prompt Library is `./prompt_library`, not `./data/prompt_library`.** Backing up only `data/` misses it.

Stop the application for a consistent backup of `data/`, `prompt_library/`, `.env`, `.ai-drawing/` and custom recovery paths. Include ComfyUI models/local presets outside `data/` as needed. Restored PIDs do not prove process ownership. Rebuild/recreate and launcher operations do not delete these bind mounts.

Environment paths do not create Docker mounts: verify paths and Compose mappings for persistence. Enabled ComfyUI mounts expose resource directories read/write at `/comfyui/...`; setup does not supply models.

## Diagnostics and recovery

```bash
./setup.sh status
./setup.sh logs
```

Backend `/api/system/status` reports `not_configured`, `unreachable`, `no_models`, `connected` or `degraded`. Backend health does not establish ComfyUI/model/Worker/training readiness. CLI status uses its own probes and ownership checks, not identical Dashboard state.

- **Docker unavailable:** start Docker and check `docker info` and `docker compose version`.
- **Port occupied:** leave the existing process alone; select another port through reconfigure.
- **Mount failure:** check Docker file-sharing permissions and host paths, then reconfigure. Do not edit temporary generated YAML.
- **No models:** a connected empty ComfyUI is not an installation failure. Supply compatible resources yourself.
- **Device/runtime failure:** correct the host driver or native architecture, or deliberately choose CPU/disabled. The launcher does not repair drivers.
- **Reconfigure/update requires stop:** run `stop` before changing a managed runtime. Updates require launcher installation provenance and a stopped instance.
- **Recovery/cleanup warning:** preserve the exact backup or staging paths reported. Do not delete by wildcard or terminate guessed PIDs. If rollback or process ownership cannot be proved, inspect state and logs before retrying a mutation or starting ComfyUI.

Logs include `data/logs/bootstrap.log`, `data/logs/comfyui.log`, and `data/logs/comfyui-relay.log`. Check them before sharing diagnostics; masking is not a reason to publish secrets.

## Current scope and API references

LoRA code/storage exists without end-to-end acceptance; see [Training status](training-status.md), not removed automation procedures.

Tools: [MCP setup](mcp-setup.md), [source catalog](../mcp-server/mcp_server/tool_catalog.py). REST: running Backend `/docs` or `/openapi.json` (default <http://127.0.0.1:8001/openapi.json>). Offline: `backend/app/api/`, schemas and `backend/app/main.py` router registration. Archived API notes are not current contracts.

## Manual development (optional)

Developers can run Backend and Frontend outside Compose using their respective dependency manifests. Set host-readable paths and the correct ComfyUI URL; container paths such as `/data/...` and `/comfyui/...` are not portable host settings.

```bash
# Backend, in a prepared Python environment
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
# Frontend, in a separate terminal
cd frontend
npm ci
npm run dev
```

Manual Uvicorn defaults to `8000`, Compose host to `8001`. Match MCP/frontend settings to the actual Backend. Manual development does not configure Windows Worker or establish training acceptance.

## Maintenance startup and drain source contract

`AI_DRAWING_MAINTENANCE=closed` is checked before Backend Settings, database,
router imports, Gallery directory creation, migration/init or automatic workers.
Only `GET /maintenance/status` returns a safe typed source/owner/epoch receipt;
all other paths return 503. No state is loaded and no release/migration occurs.
Invalid mode values refuse startup. A fresh separately authorized normal startup
is required for release; there is no public reopen endpoint.

Normal shutdown fences the history and caption producers, queue admission and
trainer queue before joining. Accepted generation/trainer work may finish;
shutdown does not terminate the Argus runner or request trainer cancellation.
Pending jobs are left intact, never cleared or replayed by drain. Each stop
helper returns a boolean, retains live handles after timeout and checks actual
worker/timer/child exit. Lifespan records each result in
`app.state.maintenance_drain` and logs incomplete shutdown. These receipts certify
local checks only; remote ComfyUI acceptance and old processes remain unknown.
An Environment operation must keep its verified external whole-listener/writer
fence and verify actual process/children termination; an ASGI shutdown return or
log alone does not authorize checkpoint/restore or establish zero remote work.

The Bot uses the bound durable history and authenticated loopback controls in
[its maintenance contract](../discord-bot/README.md#維護-admission-與交付歷史source-contract).
Checkpoint/restore must preserve ledger and its checkpoint together under the
single-owner lease and compare an external trusted checkpoint. A complete local
rollback cannot certify absence of later remote effects. Never provision over
legacy/missing history, adopt source/dependencies, start/stop services or replay
jobs based solely on this source documentation. Those remain separately scoped
Environment operations. Windows remains deferred.

The Vite development server reserves `/gallery` and `/gallery/` (with optional
query strings) for the React Gallery page. Only paths below `/gallery/` proxy to
the Backend for original assets; `/api` remains the API proxy. This routing rule
is specific to the development server, not evidence about managed deployments.
Gallery reads the existing numeric API response as text and preserves integer
seed tokens in an internal string display model before JSON parsing can round
them. The public Backend/MCP numeric contract and ID-based rerun are unchanged.
The Gallery detail modal uses two bounded image/metadata columns at widths of
640px and above, and stacks them below that width. Long metadata values wrap;
the image keeps its aspect ratio and prompts remain complete with vertical
scrolling when needed. To check initial visibility against the existing test
result and a long-content fixture, use `sh scripts/check-gallery-modal-layout.sh`
from `frontend/` with a task-owned Vite preview on loopback port 5175 and the
existing Backend on 8001. This read-only browser check requires `ego-browser`;
it does not submit generation or export requests.
