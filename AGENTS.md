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

On Windows, also set `TMPDIR` (the test root must be below it) and `MCP_TEST_PYTHON` (the MCP venv's `python.exe`). Run long suites with a per-test timeout (`pytest-timeout`, `--timeout=60`) so a hang fails fast.

All suites are expected to pass on `main` on macOS and Windows; a change must not add failures. Keep only tests that check a feature. Never leave a test failing or hanging: a test that does not check a feature is removed; a feature test blocked by a known bug is skipped with a reason that links its task.

When reporting, separate what you verified: offline tests, a running service, a real generation, artifact retrieval.

## Team

Paperclip role agents also follow the [team guide](docs/team/README.md) and their role page in `docs/team/roles/`.

## Memory

Any agent may add or fix entries in [docs/memory/](docs/memory/MEMORY.md) when it learns a fact without which a future agent would act wrongly. One topic per question, with Context, Why, How to apply and Evidence sections and a `curated_on` date; `MEMORY.md` has one line per topic saying when to open it. Never store logs, receipts or incident history.
