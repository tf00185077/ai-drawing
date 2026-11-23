# Task specification

## Task
Consolidate the MCP tools to one tool per intent (about 20, from 40).

## Purpose
Forty overlapping tools make it hard for an agent to pick the right one. The owner approved consolidation ([decision](../../decisions/mcp.md)).

## Outcome
An agent sees about 20 tools, each with a clear intent and a risk label, and can still do everything it could before.

## Scope
Included: the [proposed tool map](../../decisions/mcp.md#proposed-tool-map); `tool_catalog.py` gains a `risk` field (`read`, `mutate`, `admin`); old tool names removed; `docs/mcp.md` tool table and flows rewritten.
Excluded: new behavior beyond the map (`wait_for_job` in p1-03; `health` and `list_workers` in p1-04); Backend API changes.
Open questions: final tool names may differ from the map if QA agrees each intent still has exactly one tool.
Read first: [decisions/mcp.md](../../decisions/mcp.md), the p1-01 result, [docs/mcp.md](../../mcp.md).

## Done when
- [ ] The registered tools match the catalog, and every old tool's capability is reachable through exactly one new tool (mapping table in the manifest). Check: test (`test_tool_catalog.py`) + manual review of the mapping. Evidence: test output and the table.
- [ ] Every tool has a `risk` label in the catalog and its description states it. Check: test. Evidence: test output.
- [ ] Each mode or action of a merged tool has at least one test through the MCP call path. Check: test. Evidence: test names.
- [ ] `docs/mcp.md` lists the new tools and the common flow `list_resources → generate → wait_for_job → gallery_get`. Check: manual. Evidence: doc link.
- [ ] MCP suite passes with no new failures. Check: test. Evidence: command and summary line.

## Delivery
- Artifact: commit on a feature branch after p1-01, `manifest.md` with the old → new mapping.
- Known limitations: breaking change for existing MCP clients.
