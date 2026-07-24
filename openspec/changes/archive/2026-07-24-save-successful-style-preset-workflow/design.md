## Context

`GeneratedImage` and `GeneratedArtifact` records already preserve the actual `workflow_json` used by completed queue jobs. Style presets currently store recipes under `style_presets/agent/presets/`, and the generation queue creates or modifies a graph at runtime. The accepted workflow intentionally avoids precompilation: a user first proves a graph by generating successfully, then explicitly asks to save it. The calling LLM extracts compact positive and negative keywords; the backend never summarizes prompt prose.

## Goals / Non-Goals

**Goals**

- Save only a graph backed by a successful recorded generation.
- Preserve the graph exactly except for positive/negative conditioning text.
- Ensure the persisted file is a raw, parseable ComfyUI API-format object.
- Accept practical source locator and keyword shapes while returning one stable response shape.
- Retest the exact saved bytes semantically represented by the parsed graph, without runtime parameter injection.
- Apply the same save contract to every known style preset without Niji, Anima, checkpoint-family, template-name, LoRA-count, or fixed node-id assumptions.

**Non-Goals**

- Automatic or batch save/backfill.
- Prompt keyword extraction by backend logic.
- Full ComfyUI schema/resource prevalidation.
- Hashing, snapshot/version registries, provenance envelopes, or activation state.
- Modifying the declarative preset recipe prompts.
- Making Civitai Source Alias executable.

## Decisions

### 1. Source-of-truth is a successful Gallery record

The save service accepts a loose `source` locator:

- integer: Gallery image id;
- `image:<id>` or numeric string: Gallery image id;
- `artifact:<id>`: generated image artifact id;
- `job:<job-id>` or an unprefixed nonnumeric string: completed generation job id.

Resolution returns a recorded image-compatible row with a nonempty JSON-object `workflow_json` plus that same row's exact `prompt` and `negative_prompt` fields as confidentiality evidence. A job locator may select any completed image record for that job because all outputs of one queue submission share the submitted graph. Missing, unfinished, failed, video-only, ambiguous, or graph-less sources return a structured repairable error and do not write files.

The MCP tool description states that it MUST NOT be called automatically and is only for an explicit user request after a successful generation. No redundant confirmation boolean is added.

### 2. LLM supplies keywords; backend only normalizes syntax

The save request includes `prompt_keywords` and `negative_prompt_keywords`, each accepting a string or list of strings. String values may be comma- or newline-separated. Normalization trims whitespace, drops empty entries, removes exact duplicates while preserving first-seen order, and joins entries with `, `. It does not add, rank, translate, or infer words.

The positive keyword set must contain at least one item. An empty negative set is accepted because an empty negative conditioning text is a valid graph value. The full original round prompt is never written to the saved artifact or MCP response.

### 3. Replace conditioning text by graph links, not title guessing

The sanitizer deep-copies the recorded graph. For every sampler-like node that has `positive` and/or `negative` link inputs, it walks upstream through graph links to collect reachable `CLIPTextEncode` nodes. A directly stored string receives the normalized keywords in `inputs.text`. A link-valued text input keeps its link and may update a Primitive/String carrier only when that carrier has one unambiguous string field and every carrier consumer is a targeted text input of the same polarity. Shared-polarity carriers, unsupported carriers, and carriers with non-conditioning consumers are rejected rather than guessed.

After targeted replacement, the sanitizer recursively inspects the complete graph, including node metadata, mapping keys, and nested list/object values. If either nonempty exact source-record prompt remains, it returns `prompt_confidentiality_unproven` before any temporary or target file is written. It does not delete or mutate the orphan node, metadata, or unrelated field that caused rejection.

At minimum, `KSampler` and `KSamplerAdvanced` inputs are supported. Pass-through conditioning nodes are handled by generic upstream link traversal rather than a hard-coded title. The service rejects graphs in which no positive text node can be resolved. It does not modify `_meta`, loader resources, samplers, dimensions, seeds, node ids, links, or any non-text input.

The implementation must be resource-family agnostic. It may inspect graph structure and standard ComfyUI link inputs, but must not branch on a preset id, Niji/Anima names, a particular template, fixed node ids, or a fixed number/type of model or LoRA loaders. Focused tests use at least two structurally different graph fixtures so a Niji-shaped happy path cannot become the de facto implementation contract.

### 4. Fixed conventional path and atomic replacement

A known preset id and optional known profile are required. Existing preset/provider validation supplies slug/path safety and available profiles. The target path is derived, not caller-controlled:

```text
style_presets/agent/workflows/<preset-id>/<profile-or-__base__>.api.json
```

The file body is only the graph object. It contains no manifest, source metadata, hash, snapshot id, or envelope. The service writes a temporary file in the target directory, parses it back as a JSON object whose nodes each contain string `class_type` and object `inputs`, then uses `os.replace` for atomic publication. An explicit later save to the same preset/profile replaces the old graph.

### 5. Backend API owns state; MCP remains a thin client

Backend endpoints:

- `POST /api/style-presets/{preset_id}/workflow/save`
  - body: `source`, optional `profile`, `prompt_keywords`, `negative_prompt_keywords`;
  - response: stable metadata including canonical source type/id, preset/profile, relative workflow path, normalized keyword arrays, and `retest_required=true`;
  - never returns the original full prompts.
- `GET /api/style-presets/{preset_id}/workflow?profile=...`
  - returns the raw graph object as the HTTP JSON body;
  - 404 when no saved graph exists.
- `POST /api/style-presets/{preset_id}/workflow/test`
  - body contains optional `profile` only;
  - reads the saved graph server-side and queues it verbatim;
  - returns a normal generation job id.

MCP tools:

- `save_successful_workflow_as_style_preset(source, preset_id, profile=None, prompt_keywords=..., negative_prompt_keywords=...)`
- `test_saved_style_preset_workflow(preset_id, profile=None)`

MCP does not transfer the large graph. It returns parseable JSON with `ok`, `tool`, canonical identifiers/path, normalized keywords or queued job status, and a repairable error object on failure.

### 6. Verbatim retest bypasses custom-workflow defaults

The existing `GenerateCustomRequest.prompt` defaults to `"1girl, solo"`, and the custom queue path calls `apply_params`; therefore it cannot prove the saved graph unchanged. Add a narrowly scoped queue method for a server-owned saved graph. It deep-copies and submits the graph without calling `apply_params` or injecting prompt, negative prompt, seed, steps, cfg, model names, or dimensions. Prompt metadata for Gallery recording is read from the sanitized graph or passed separately as already-normalized metadata, but must not be written back into the graph.

A successful retest is observed through the existing `get_generation_status` lifecycle. ComfyUI validation failures remain terminal and expose structured `node_errors` through the existing status contract.

Every exception raised by ComfyUI submission in this server-owned branch, including non-JSON HTTP status failures, malformed success payloads without `prompt_id`, and unexpected exceptions, releases the running slot and records the job as terminal `failed`. The next pending job may then proceed. Existing custom, audited recipe, and default successful submission semantics remain unchanged.

## Error Contract

Representative codes:

- `source_not_found`
- `source_not_successful`
- `source_has_no_workflow`
- `source_not_image`
- `preset_not_found`
- `profile_not_found`
- `positive_keywords_required`
- `conditioning_not_found`
- `ambiguous_conditioning`
- `prompt_confidentiality_unproven`
- `invalid_workflow_graph`
- `saved_workflow_not_found`

Every error includes a concise message and hint. No failure writes or replaces the target file.

## Test Strategy

- Unit tests for locator parsing and keyword normalization.
- Genericity tests using at least one traditional checkpoint graph and one diffusion-family or multi-loader graph with different node ids/order.
- RED/GREEN service tests proving only polarity-linked text changes and the source graph object is not mutated.
- Privacy tests for orphan encoders, exclusive and non-exclusive linked text carriers, metadata copies, exact source-record prompt evidence, serialized non-leakage, and zero-create/zero-replace rejection.
- API tests for successful records, graph-less/failed/missing sources, unknown preset/profile, atomic path output, and raw GET.
- Queue/API tests proving verbatim retest does not call `apply_params` and preserves graph values.
- Queue liveness tests proving every verbatim submit exception becomes terminal and the next pending job proceeds.
- MCP request-body and response-shape tests plus tool-catalog registration.
- Regression tests for existing style preset, custom generation, queue, Gallery, and MCP suites.
- After deterministic gates pass, perform one low-load real ComfyUI retest using a disposable preset/profile fixture or another reversible target, then clean up the test artifact. Do not inspect, rank, or regenerate the image beyond checking successful completion.

## Risks / Trade-offs

- Replacing prompts can alter image content but cannot structurally invalidate a previously successful graph; the dedicated retest is the runtime proof.
- Some exotic graphs may use custom conditioning nodes with no reachable `CLIPTextEncode`; fail with `conditioning_not_found` rather than guessing.
- Fixed-path replacement intentionally provides no history. Git or external backups remain the rollback mechanism for tracked artifacts.
