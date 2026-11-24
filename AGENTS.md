# Agent guide

Read this file, then [project memory](docs/memory/MEMORY.md) and the [document map](docs/INDEX.md). The [README](README.md) explains what the system is. Goals and phases are in the [roadmap](docs/roadmap/ROADMAP.md); the active phase and current state are in [CURRENT](docs/CURRENT.md).

## Repository layout

| Path | Contents |
|---|---|
| `backend/app/api/` | FastAPI routers |
| `backend/app/schemas/` | Request/response contracts |
| `backend/app/core/`, `backend/app/services/` | Queue, ComfyUI client, domain logic |
| `backend/workflows/` | ComfyUI API graph templates + `.meta.json` |
| `backend/tests/` | Backend tests |
| `mcp-server/mcp_server/` | MCP server; `tool_catalog.py` is the tool list |
| `frontend/src/` | React UI |
| `worker/windows/` | Remote Windows worker |
| `discord-bot/` | Discord bot |
| `prompt_library/`, `style_presets/` | Authored prompt and preset data |
| `scripts/launcher/` | Lifecycle launcher |

## Conventions

- Backend: Python 3.11, FastAPI, Pydantic, SQLAlchemy. ComfyUI is called over REST/WebSocket.
- Frontend: React + Vite + Tailwind, functional `.tsx` components.
- MCP: intent-level tools. Keep `tool_catalog.py` and registration aligned (enforced by `test_tool_catalog.py`).
- Job state, artifacts and provenance live in the Backend. Return stable error codes and recovery hints so agents never reconstruct state.
- Keep the current stack. Do not add workflow engines (n8n, Zapier-style) as an incidental change.
- Documentation is English only. When behavior changes, update the matching topic doc.

## Operating policy

Follow [docs/OPERATING-POLICY.md](docs/OPERATING-POLICY.md). In short: almost every operation is allowed by default, including generation, downloads, training, ComfyUI restart, node installs, worker PowerShell and pushing to `main`. Never commit secrets, never delete models/datasets/outputs/Gallery records as cleanup, never expose worker control beyond the LAN, and check a job ID before resubmitting after a timeout.

## Verification

```bash
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-backend-tests" python -m pytest -c pytest.ini backend/tests -q
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-mcp-tests" python -m pytest -c pytest.ini mcp-server/tests -q
cd frontend && npm test && npm run build
```

All suites are expected to pass on `main`; a change must not add failures.

When reporting, separate what you verified: offline tests, a running service, a real generation, artifact retrieval.

## Team

Paperclip role agents also follow the [team guide](docs/team/README.md) and their role page in `docs/team/roles/`.

## Memory

Any agent may add or fix entries in [docs/memory/](docs/memory/MEMORY.md) when it learns a durable fact that will help future agents. Keep entries short (fact, how to apply, source path) and never store logs or incident history.
