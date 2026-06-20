## Context

The system has three image-generation entry points, but only `generate_image_custom_workflow` lets the agent author its own ComfyUI workflow JSON. That path has no grounding: ComfyUI accepts any JSON and the agent only knows graph shapes from training memory or by fetching whole template JSON. The de-facto default is therefore the human-authored fixed-template path (`generate_image` + `backend/workflows/*.json`), where a person must hand-craft a template before the agent can produce a variant.

The product decision (agreed with the maintainer) is to invert this: make agent-authored workflows the primary path for variants, with the template library growing itself from verified successes. This is fundamentally a **memoization design** — the workflow template catalog becomes a cache of workflow constructions keyed by a capability tag-set; the agent is both the cache consumer (reuse) and the cache populator (backfill).

Current relevant code:
- `backend/app/api/generate.py` — `/api/generate/` (template path), `/api/generate/custom` (custom path), `/workflow-templates*` endpoints.
- `backend/app/core/queue.py` — `submit()` / `submit_custom()` converge into one worker that loads a template (by name) or uses the supplied JSON, injects params, calls ComfyUI `/prompt`, and records output.
- `backend/app/core/workflow.py` — `load_template(name)` reads `backend/workflows/{name}.json`.
- `backend/app/core/style_presets.py` — independent recipe catalog (resource + prompt), references a template by name; the manifest/validation pattern here is a useful precedent to mirror.
- `mcp-server/mcp_server/tools/` — `generate.py`, `comfyui.py` (currently only `free_comfyui_memory`).

## Goals / Non-Goals

**Goals:**
- Give the agent reliable grounding (live ComfyUI node schema) so self-authored workflows are valid against the actual instance.
- Make "is there a usable template?" a deterministic, binary set test — no fuzzy matching.
- Let the template catalog self-extend from verified successes, with dedup and versioning that resist library rot.
- Surface ComfyUI's own validation errors to the agent for a build → submit → read-error → fix → resubmit loop.
- Keep the simple template-name fast path and the style-preset mechanism working unchanged.

**Non-Goals:**
- Building an independent ComfyUI graph validator (we forward ComfyUI's authoritative errors instead).
- Auto-merging two workflow graphs into one parameterized graph (correctness risk; explicitly excluded).
- Semantic / scored template matching (the gray zone is intentionally pushed into controlled-vocabulary tag definition, not into matching).
- Replacing `generate_image` (template-name) or `style-preset-catalog`.
- Re-enabling `generate_image_from_description` / `suggest_workflow_from_description`.

## Decisions

### D1. Capability tag-set as the catalog key (controlled vocabulary, binary)
A template's identity for matching is a fixed-vocabulary tag-set: `modality` (single enum), `conditioning` (set), `io` (set), `model_family` (single). Reuse = `template_tags ⊇ required_tags`; backfill dedup = exact-key equality.
- **Why:** Makes both reuse and backfill deterministic binary set operations, satisfying the "no gray zone" requirement, and gives both ops a single shared definition.
- **Alternatives considered:** (a) Semantic description match like skills — rejected, inherently fuzzy. (b) Free-form tags — rejected, leads to namespace rot (`controlnet_pose` vs `pose_control`).
- **Cost:** The fuzziness doesn't vanish; it moves to *defining the vocabulary*. Requires a controlled-vocabulary registry and a rule for introducing new tags.

### D2. Strict (superset) matching, biased toward "miss"
Matching requires the template to cover every required tag, including `modality`. A partial overlap is a miss.
- **Why:** The cost asymmetry favors strictness — a false miss costs only a rebuild (which the backfill loop reconverges), while a false match yields a wrong image. So bias toward rebuild.

### D3. Single-point node-schema query, not full dump
Expose `search_nodes(query)` and `get_node_schema(node_type)` proxying ComfyUI `/object_info`, never the whole catalog.
- **Why:** `/object_info` is hundreds of nodes / large JSON; dumping it blows the agent's context. On-demand lookup keeps grounding cheap.
- **Alternatives:** Curated node whitelist (re-introduces human curation); full cached dump (context blowup) — both rejected.

### D4. Forward ComfyUI validation errors (option B), no self-validator
The custom path submits to ComfyUI `/prompt` and maps returned `node_errors` to a structured `{node_id, class_type, reason}` payload for the agent.
- **Why:** ComfyUI is the authoritative validator; relaying its errors is minimal code and always correct. A self-built validator would duplicate and drift from ComfyUI's rules.
- **Trade-off:** A bad graph still consumes one queue submission before failing. Acceptable; a pre-check can be added later if error churn proves noisy.

### D5. Backfill = verified-success promotion gate + version-on-change, never in-place mutate
Only a workflow whose ComfyUI output image was recorded is eligible. New capability key → new family-filed entry; existing key → no duplicate (broken originals superseded by a new version, prior marked deprecated). Stored shape is parameterized (no baked content prompt / seed). "Similar" templates are build-time scaffolds only.
- **Why:** The promotion gate keeps unverified junk out. Versioning instead of in-place edits protects other flows' reuse from being silently broken. Storing the shape (not the one-off) keeps templates reusable. Banning auto-merge avoids the highest-risk correctness failure.
- **Alternatives:** In-place "extend the similar one" — rejected, mutating a shared template can break existing reuse and merging graphs is error-prone.

### D6. Two independent libraries
Workflow-template catalog (graph *shapes*) and style-preset catalog (resource + prompt *recipes*) stay separate; backfill only touches templates. Presets continue to reference a template by name.
- **Why:** Different concerns, different lifecycles; coupling them would entangle prompt recipes with graph evolution.

### D7. Manifest storage mirrors the style-preset split
Machine-readable capability tags live in a structured index (queryable without parsing prose); human `description` is metadata only. Reuse the precedent set by `style_presets/catalog.json` + `docs/style-presets/`.
- **Why:** Consistency with an existing, working pattern in this repo; keeps the machine index compact and parse-safe.

## Risks / Trade-offs

- **Controlled-vocabulary rot** (new tags coined inconsistently by the agent) → Mitigation: a registry of allowed tags; manifests with unknown tags are rejected/flagged (see spec); periodic consolidation.
- **Template-library rot** (near-duplicates, broken entries accumulating) → Mitigation: capability-key dedup, verified-success gate, version-with-deprecate, optional periodic consolidation pass.
- **Bad graphs consuming queue slots before ComfyUI rejects them** (D4) → Mitigation: structured errors enable fast agent self-correction; add an optional pre-submission existence check only if churn is measured to be a problem.
- **Stale node-schema cache** reporting nodes that no longer exist → Mitigation: invalidate cache on ComfyUI restart / custom-node change (spec requirement).
- **Strict matching causing unnecessary rebuilds** (D2) → Accepted by design; the backfill loop reconverges and the cost asymmetry justifies it.
- **Agent over-promoting one-off workflows as templates** → Mitigation: parameterized-shape storage + verified-success gate; promotion is the only write path.

## Migration Plan

1. Add node-schema query (D3) — additive, no behavior change to existing paths.
2. Add capability manifests to the existing `backend/workflows/*.json` templates and the index/matching read API (D1, D2, D7) — additive; existing template-name generation keeps working.
3. Add ComfyUI error forwarding to the custom path (D4) — changes only the *failure* result shape; success path unchanged.
4. Add backfill write path + versioning/family layout + consolidation (D5) — gated, opt-in; nothing auto-writes until enabled.
5. Update MCP tool docstrings/guidance so the agent default is "match-then-build".

Rollback: each step is independent and additive; disabling backfill or reverting tool guidance returns the system to today's behavior without data loss (existing templates untouched).

## Open Questions

- Manifest storage shape: sidecar file per template (`workflows/<name>.meta.json`) vs a single central index (`workflows/index.json`)? Central index is easier to query; sidecars are easier to version with the graph.
- Controlled-vocabulary registry: where does it live and who edits it — a committed config file, or an agent-extendable registry with a promotion gate of its own?
- Consolidation cadence: fully automatic, or a human-reviewed periodic pass (tension with the "human not the bottleneck" goal)?
- Versioned naming scheme and family layout on disk (e.g. `workflows/<family>/<key>@v2.json`).
- Whether backfill should run inside the generation worker after recording, or as a separate explicit MCP tool the agent calls after a verified success.
