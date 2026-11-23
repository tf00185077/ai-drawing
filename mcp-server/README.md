# AI Drawing MCP server

A stdio MCP interface for the AI Drawing application. The package uses the Python MCP SDK; its entry point is `ai-drawing-mcp`. It is separate from the Compose launcher and must be registered with each client.

## Package setup

From this directory, `uv sync` prepares the package environment; `uv run ai-drawing-mcp` starts the stdio server. Do not start it as a persistent GPU service. Repository wrappers under `scripts/` set the working directory for clients.

Configure process environment using `MCP_` variables. Application `.env` is not automatically read. Backend calls, direct ComfyUI maintenance and Discord delivery use separate configured endpoints; generation execution targets do not retarget direct maintenance tools.

## Current contract and operations

The [MCP setup guide](../docs/mcp-setup.md) owns connection examples, supported tool documentation and response categories. [tool_catalog.py](mcp_server/tool_catalog.py) and registered live schemas determine actual tool names/arguments. Removed low-level node/template and strict alias helpers must not be called from old examples.

LoRA tools remain implemented, but a complete training service has not been accepted; see [training status](../docs/training-status.md). This package README supplies no automated training procedure. Windows source and unresolved acceptance are described in [Windows worker](../docs/windows-worker.md).

## Verification

Use this package's prepared environment from repository root:

```bash
mcp-server/.venv/bin/python -m pytest -c pytest.ini mcp-server/tests -q
```

Catalog tests compare registration, implementation pointers, schemas and documented tools. Mocked HTTP tests do not establish Backend, GPU, Windows, model-loading or delivery readiness. Live operations require separate prerequisites and authorization.
