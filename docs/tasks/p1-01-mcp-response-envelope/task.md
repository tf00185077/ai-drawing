# Task specification

## Task
Make every MCP tool return one response envelope.

## Purpose
Tools now return plain text, JSON strings or JSON objects, so agents must special-case each tool. Phase 1 needs agents to work without help ([ROADMAP Phase 1](../../roadmap/ROADMAP.md), [decision](../../decisions/mcp.md)).

## Outcome
An agent parses every tool result the same way: `{"ok": true, "data": ...}` or `{"ok": false, "error": {"code", "message", "hint"}}`.

## Scope
Included: all tools registered in `mcp-server/mcp_server/server.py`; a shared envelope helper; a documented list of error codes with hints; the catalog's `response_category` replaced by the single envelope.
Excluded: renaming or merging tools (p1-02); new tools (p1-03, p1-04); Backend API changes.
Open questions: none.
Read first: [docs/mcp.md](../../mcp.md), [decisions/mcp.md](../../decisions/mcp.md), `mcp-server/mcp_server/tools/responses.py`, [memory](../../memory/MEMORY.md).

## Done when
- [ ] Every registered tool returns the envelope on success and on failure, including Backend HTTP errors, validation errors and connection errors. Check: test — one parametrized test calls every catalog tool with a mocked success and a mocked failure. Evidence: test name and output.
- [ ] Backend error details are kept: known Backend error codes (e.g. `revision_request_conflict`) appear as `error.code` with a `hint`; unknown errors use a generic code and keep the HTTP status in `error.message`. Check: test. Evidence: test output.
- [ ] `docs/mcp.md` documents the envelope and the error-code list. Check: manual (QA reads it against the code). Evidence: link to the doc section.
- [ ] MCP suite passes with no new failures. Check: test — `AI_DRAWING_TEST_ROOT=... python -m pytest -c pytest.ini mcp-server/tests -q`. Evidence: command and summary line.

## Delivery
- Artifact: commit on a feature branch, `manifest.md` in this folder.
- Known limitations: agent prompts written for the old shapes must be updated.
