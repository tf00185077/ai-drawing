# Bounded Gallery PNG and strict Mac smoke implementation plan

Goal: implement cleared task/clarification D1–D3; keep D4 pending owner-demo.
Spec: task.md and kickoff-clarification-1.md, unchanged at e540829376cc397b3dc509192643874fabad3459.
Architecture: preserve existing intent/Backend adapters. Validate canonical selectors before access; use existing locator validation plus opened-file identity/containment and bounded Pillow decoding. A separate SDK client runs the literal eight-call flow, writes append-only evidence, and stops safely on uncertain admission.
Stack: Python, existing MCP SDK/httpx, Pillow. Canonical environments remain untouched.

## Tasks

- [x] 1. Content contract: add registered-boundary tests in mcp-server/tests/test_gallery_content.py, observe RED, implement optional gallery_get content in tools/intents.py, tools/gallery.py and a focused gallery_content.py module. Preserve metadata default and 31/read catalog. Declare Pillow and lock dependencies. Test byte identity, invalid selectors before transport/storage, PNG limits/full decode, actual file opening, safe errors and no writes.
- [x] 2. SDK boundary/driver: real stdio to a test HTTP Backend, actual driver subprocess tests with controlled lower Backend/storage fixtures. Observe RED then implement scripts/mcp_smoke_mac.py. Exactly eight calls, six-attempt budget, three-streak stop, same-ID six-call recovery, unknown-admission stop, retained ledgers/bytes and new-session audit. Update docs/mcp.md.
- [ ] 3. Verify/freeze: affected MCP/Backend suites and standing guards with timeout=60, source/interpreter receipts, deliberate fault/restore/GREEN evidence. Commit product before real qualification and predeclare all inputs/seeds/references.
- [ ] 4. Runtime/qualification: preserve active source/configuration/data; identify active work before any controlled replacement. Record non-secret process/import/root/schema/value evidence. Run one frozen real SDK invocation; audit persistence and actual ComfyUI sampling. Preserve honest non-exit if finite policy stops.
- [ ] 5. Deliver: reconcile baseline F1–F8 and preparation/attempt/recovery/audit totals, manifest D1–D4 with four verification boundaries, final immutable commit, indexed packet/patch/bundle/readback receipt and official issue uploads. Complete Coding card so existing native QA AID-172 reviews exact candidate. No feature merge/push.

Review focus: coercible/boolean selectors; TOCTOU opening races; conflicting locators; strict total wait versus Backend status; unknown submit must stop rather than duplicate. Tests cover these in tasks 1/2.

Execution: native, continuously under already-authorized issue instruction. Independent final review is the existing recipient-owned AID-172; no additional owner/start/plan confirmation is requested.
