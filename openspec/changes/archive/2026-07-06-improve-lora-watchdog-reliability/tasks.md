## 1. Watchdog Reliability

- [x] 1.1 Add failing watcher tests for stable-file waiting, modified/moved events, current caption skips, stale caption detection, manual caption preservation, and structured corrupt/unreadable image status.
- [x] 1.2 Implement watcher helpers for caption freshness, stable-file polling, protected caption restore, dataset-local watchdog status, and non-retry handling for unchanged invalid images.
- [x] 1.3 Wire created, modified, and moved image events through the existing debounce path without adding training triggers.

## 2. Caption Suitability Assessment

- [x] 2.1 Add failing backend service tests for coherent, scattered, missing/empty caption, and low trigger-token coverage datasets.
- [x] 2.2 Implement deterministic caption suitability schemas and service metrics/verdict logic without external LLM calls.
- [x] 2.3 Add a backend assessment API endpoint under `/api/lora-train/datasets` with path validation reuse and API tests.

## 3. Agent Access

- [x] 3.1 Add MCP tests for `lora_dataset_caption_assess` success forwarding and structured backend error forwarding.
- [x] 3.2 Implement the MCP assessment tool and catalog entry while preserving existing LoRA MCP response structure.

## 4. Documentation and Verification

- [x] 4.1 Update `docs/PROGRESS.md` with the completed watchdog/assessment scope and explicit no-auto-train note.
- [x] 4.2 Run focused backend and MCP tests, OpenSpec validation, and `git diff --check`.
