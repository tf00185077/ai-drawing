# Phase 1 close and Phase 2 roadmap review

## Source

CTY in a Claude Code session on 2026-11-26, answering the
[phase-exit proposal](../tasks/p1-05-mcp-e2e-smoke-mac/phase-exit.md) and a
review of the Phase 2 roadmap against the current code.

## Owner words preserved verbatim

> 我要關閉Phase 1進到phase2了，但交給AI前，我想確定phase 2的roadmap有沒有需要補充或修改的

> 不要使用商用的，另外API KEY我有免費的，我會放在電腦某個位置讓AI去讀取

Asked whether that meant "personal use, no license filtering" or "exclude paid
models", CTY chose: **personal use, no filtering**.

## Application

- Phase 1 is closed; phase order and Not now are unchanged; Phase 2 is active.
- Phase 2 scope, Remove, Unknowns, First check and Exit are revised as recorded in
  [ROADMAP](../roadmap/ROADMAP.md#phase-2--one-sentence-flow-resources--workflow--image-active-2026-11-26)
  and the [roadmap decisions](../decisions/roadmap.md).
- Licenses: use is personal and non-commercial, so models are not filtered by
  commercial-use permission; the license is still recorded.
- API key: CTY subsequently supplied the file at
  `/Users/tf00185088/Desktop/civitai.txt`, outside the repo. The approved Phase 2
  private setting is `CIVITAI_API_KEY_FILE`; [credential guidance](../civitai-credentials.md)
  records the current locator and distinguishes planned file loading from existing
  runtime support. Agents never commit, log or return the key. A missing or
  unreadable file is recorded at this known path; its location is no longer pending.
  [The later start direction](2026-11-26-phase-2-start-and-key-file.md) supplies
  executable continuation and routine-choice authority.
