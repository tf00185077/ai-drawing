# AI Drawing MCP server

stdio MCP server for AI Drawing (entry point `ai-drawing-mcp`, Python MCP SDK).

```bash
uv sync
uv run ai-drawing-mcp
```

Configuration, client setup and the tool list: [docs/mcp.md](../docs/mcp.md). The authoritative tool list is [tool_catalog.py](mcp_server/tool_catalog.py).

Tests (from the repository root):

```bash
AI_DRAWING_TEST_ROOT="$TMPDIR/ai-drawing-mcp-tests" python -m pytest -c pytest.ini mcp-server/tests -q
```
