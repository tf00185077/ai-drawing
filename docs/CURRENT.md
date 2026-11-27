# Current

2026-11-27 · `main` · Phase 0 and Phase 1 done · **Phase 2 active: p2-02a independent kickoff dispatched; revised p2-04 follows its acceptance** ([roadmap](roadmap/ROADMAP.md))

## Goals at a glance

| Goal | Built | Verified in a real run | Biggest gap |
|---|---|---|---|
| 1. MCP for agents | Mostly | Yes: p1-05, three real Mac flows with zero manual fixes | Client call limit unverified (50 s fallback) |
| 2. One-sentence image flow | Partly | Hand run only (p2-00, 20 manual interventions) | No Civitai search tool; no agent-facing resource record; no workflow selection |
| 3. LAN Windows workers | Partly | No | One URL; no auth; no same-project check; serial in-memory queue |
| 4. Image-to-video clip | Partly (frozen Wan/Argus code) | No | No single image-to-video + interpolation tool; needs the NVIDIA worker |
| 5. LoRA training | Mostly | No | No real training run yet; cannot run on a worker |
| 6. Prompt dashboard | Mostly | Not end-to-end | Combinations hold prompt text only, not template/models |

## Built on main

- **Phase 1 (closed 2026-11-26).** 31 MCP intent tools with one envelope (`{ok, data}` / `{ok: false, error}`), bounded `wait_for_job` with result locators, `health` and `list_workers`, canonical PNG retrieval and a strict Mac smoke driver ([p1-05 acceptance](tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md), [phase exit](tasks/p1-05-mcp-e2e-smoke-mac/phase-exit.md)).
- **Phase 2 so far.** Private Civitai key file with credentials only on the final request ([p2-01](tasks/p2-01-civitai-key-file/acceptance.md)); one Backend resource row with typed metadata, SDXL base-model mapping, backfill and bounded list/detail reads ([p2-02](tasks/p2-02-resource-record/acceptance.md), [topic](resource-records.md)); bounded downloads with an 8 GiB per-file limit, a 20 GiB free-space floor, safetensors only, hash check, resume and no overwrite ([p2-03](tasks/p2-03-bounded-download/acceptance.md), [topic](civitai-downloads.md)). None of this is agent-facing yet, and none is deployed to the running Backend.

Task-by-task history: [PROGRESS](PROGRESS.md#task-log).

## Tests

Latest independent full runs (macOS, p2-03 review 3, `--timeout=60`): Backend **7174 passed, 124 Windows-only skips**; MCP **666 passed, 4 optional smoke-export skips**. The [REGISTRY](tasks/REGISTRY.md) lists 87 active guarded items.

Windows, 2026-11-24: Backend 2018 passed, 6 skipped; MCP 314 passed, 4 skipped. Non-feature tests that failed or hung on Windows were removed ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

## Phase 0

Done 2026-11-24 (`531a68d`). Research data removed (`experiments/`, `research/`, `model_benchmarks/`).

## Next work

1. **Read first: [verification scope](decisions/verification-scope.md)** (owner-directed 2026-11-27). Public resource metadata becomes a typed allowlist; committed evidence is capped at 2 MB per task; Git SHAs are the source identity; correction rounds are bounded.
2. **[p2-02a: allowlist projection](tasks/p2-02a-allowlist-projection/task.md)** — independent kickoff assigned to [QA AID-218](/AID/issues/AID-218), fixed source `1f8e1155b3426d62e101e802b564ca761ff9f026`. Producer reads the actual verdict before dispatching Coding and independent exact-commit delivery QA. No product delivery or acceptance yet. Replaces the free-text credential recognizer in `resource_records.py` with a typed allowlist and a bounded secret check, and deletes its tests.
3. **[p2-04: durable download jobs](tasks/p2-04-durable-download-jobs/task.md)** (respecified 2026-11-27, fresh kickoff after p2-02a). Continues from the [owner-requested partial implementation](tasks/p2-04-durable-download-jobs/owner-checkpoint-2026-11-27.md) on main, which is unfinished and unreviewed.
4. **Then the agent-facing part of Phase 2:** Civitai search + inspect, record list/reuse through MCP, workflow selection, trigger words and recommended parameters, removals, and three real one-sentence runs.

Settled 2026-11-27: 3 review rejections of one task pause it for a CTY decision ([thresholds](roadmap/ROADMAP.md#thresholds)). Still a proposal: the `reviewspec-review` skill change in the verification-scope decision.

[Fresh Producer AID-217](/AID/issues/AID-217) continues under the
[verbatim owner instruction](requests/2026-11-27-fresh-producer-continuation.md).
Old p2-04 cards' descriptions and current native plans are superseded; their work
and prior plan revisions remain. They are still held blocked: the server refused
two cancellation writes because prerequisites are unresolved. Producer stopped
those retries and must retire the obsolete prerequisites before eventual closure.
No old Coding run, product acceptance or rejection-count reset is authorized.

## Team

Producer, Coding and QA are active; the other specialists are paused. Producer owns
Phase 2 sequencing under [CTY's delegation](requests/2026-11-26-phase-2-start-and-key-file.md).
