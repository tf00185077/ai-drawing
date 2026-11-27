# Current

2026-11-27 · `main` · Phase 0 and Phase 1 done · **Phase 2 active: p2-02a accepted; revised p2-04 needs fresh independent kickoff** ([roadmap](roadmap/ROADMAP.md))

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
- **Resource projection ([p2-02a](tasks/p2-02a-allowlist-projection/acceptance.md)).** Public metadata follows a typed allowlist; exact held keys, received download queries and auth transport are filtered. Free-text credential recognition and its 40 obsolete guard meanings are removed. Old rows and notes remain readable without rewriting storage. Accepted candidate `3e70e04c`, independent review 2 PASS; **1 rejected delivery retained**.

Task-by-task history: [PROGRESS](PROGRESS.md#task-log).

## Tests

Latest independent correction check (macOS, p2-02a candidate `3e70e04c`, `--timeout=60`): **1071 passed / 3 skipped** in one invocation. Overlapping subsets: affected **436 / 1**, REGISTRY **877 / 3**, independent signed-query reproduction **1 passed**. The [REGISTRY](tasks/REGISTRY.md) has **51 active / 40 superseded** items. Two immediate-expiry install cases are quarantined with p2-04 fix/re-enable links; the other skip is optional MCP lifecycle export.

Earlier full qualifications belong to rejected candidate `8d5f2968`: Backend **2340 / 125**, MCP **672 / 4**, frontend **226 / 1**, build passed. Correction review reuses those attributed results under the [settled rule](decisions/verification-scope.md); they are not full runs of the corrected SHA. No running-service probe, real generation or live model/Gallery retrieval was added.

Windows, 2026-11-24: Backend 2018 passed, 6 skipped; MCP 314 passed, 4 skipped. Non-feature tests that failed or hung on Windows were removed ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)).

## Phase 0

Done 2026-11-24 (`531a68d`). Research data removed (`experiments/`, `research/`, `model_benchmarks/`).

## Next work

1. **Read first: [verification scope](decisions/verification-scope.md)** (owner-directed 2026-11-27). Public resource metadata becomes a typed allowlist; committed evidence is capped at 2 MB per task; Git SHAs are the source identity; correction rounds are bounded.
2. **[p2-02a: accepted](tasks/p2-02a-allowlist-projection/acceptance.md)** — exact corrected source integrated after [review 2 PASS](tasks/p2-02a-allowlist-projection/review.md). The [first rejection](tasks/p2-02a-allowlist-projection/review-round-1.md) and its count remain; no history reset.
3. **[p2-04: durable download jobs](tasks/p2-04-durable-download-jobs/task.md)** (respecified 2026-11-27) is next: fresh independent kickoff against accepted main, followed by new Coding and exact-commit QA cards under [Producer AID-217](/AID/issues/AID-217). The [owner-requested partial implementation](tasks/p2-04-durable-download-jobs/owner-checkpoint-2026-11-27.md) is unfinished and unreviewed. The [handoff](tasks/p2-04-durable-download-jobs/source-handoff.md) names the two known deadline quarantines that this work must fix and re-enable.
4. **Then the agent-facing part of Phase 2:** Civitai search + inspect, record list/reuse through MCP, workflow selection, trigger words and recommended parameters, removals, and three real one-sentence runs.

Settled 2026-11-27: 3 review rejections of one task pause it for a CTY decision ([thresholds](roadmap/ROADMAP.md#thresholds)). Still a proposal: the `reviewspec-review` skill change in the verification-scope decision.

[Fresh Producer AID-217](/AID/issues/AID-217) continues under the
[verbatim owner instruction](requests/2026-11-27-fresh-producer-continuation.md).
Old p2-04 cards' descriptions and current native plans are superseded; their work
and prior plan revisions remain. Their terminal status is administrative retirement,
not product acceptance. New p2-04 execution/review cards follow p2-02a acceptance
and a fresh kickoff; no old Coding run or rejection-count reset is authorized.

## Team

Producer, Coding and QA are active; the other specialists are paused. Producer owns
Phase 2 sequencing under [CTY's delegation](requests/2026-11-26-phase-2-start-and-key-file.md).
