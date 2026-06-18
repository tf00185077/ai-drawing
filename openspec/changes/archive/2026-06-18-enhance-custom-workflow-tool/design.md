## Context

`generate_image_custom_workflow` submits an arbitrary ComfyUI workflow JSON; the backend `apply_params` locates nodes by `class_type` and injects parameters. Two problems block the tool from covering most generation scenarios:

1. The MCP tool forwards `image_pose` but not `image`, so img2img cannot receive its subject image — even though the backend `/custom` endpoint and `apply_params` already support `image`.
2. `apply_params` unconditionally writes `steps`/`cfg` (defaults `20`/`7.0`) and a random `seed` onto **every** `KSampler`. This clobbers values an agent deliberately set in the workflow JSON and breaks multi-`KSampler` graphs (hires-fix), where both samplers get the same forced values.

`apply_params` and the queue are shared by the `generate_image` (template) path, so any change must keep that path's behavior identical.

## Goals / Non-Goals

**Goals:**
- Make `image` (img2img), `mask` (inpaint), `batch_size`, and `diffusion_model`/`text_encoder`/`vae` reachable from the MCP tool.
- Change injection to "override only when the caller provides a value" so the submitted workflow JSON is the source of truth for custom workflows.
- Add an `inpaint` template and a mask upload channel.
- Keep `generate_image` template-path behavior byte-for-byte (defaults `20`/`7.0`, randomized recorded seed).

**Non-Goals:**
- No new automatic node-graph construction by the backend (the agent still supplies the workflow JSON).
- No mask painting/editing UI; mask is supplied as an existing gallery image.
- No support for advanced samplers (`KSamplerAdvanced`/`SamplerCustom`) or `ControlNetApplyAdvanced` in this change (tracked as a follow-up).

## Decisions

### Decision 1: Move default/random-seed responsibility from `apply_params` into the queue

`apply_params` becomes purely "override when not None": `steps`/`cfg` are written only when non-None, and the random-seed fallback is removed (seed written only when non-None). The queue's `_process_pending` branches on whether the job carries a custom `workflow`:
- **Template path:** fill `steps`/`cfg` with `20`/`7.0` when omitted, and generate + store a random seed when omitted (preserving today's behavior and recording).
- **Custom path:** pass `steps`/`cfg`/`seed` through as-is (None when omitted) so the workflow JSON is respected.

*Alternative considered:* a `respect_json` flag threaded into `apply_params`. Rejected — it spreads branching into the node loop; keeping `apply_params` purely declarative ("write what you're given") is simpler and the policy lives in one place (the queue).

### Decision 2: Inject mask via `LoadImageMask`, not the positional `LoadImage` scheme

Subject/pose images use a fragile positional rule (sort `LoadImage` node ids; first = subject, second = pose). The mask uses a distinct `class_type` (`LoadImageMask`), so it is injected by type with no positional collision. This keeps inpaint orthogonal to the existing img2img/ControlNet handling.

*Alternative considered:* a third positional `LoadImage`. Rejected as more fragile and ambiguous.

### Decision 3: Make `steps`/`cfg` optional in `GenerateCustomRequest` only

Only the custom request schema relaxes `steps`/`cfg` to `Optional` (default None). `GenerateRequest` keeps `20`/`7.0` defaults, so the template path always passes concrete values and its behavior is unchanged at the schema layer too. Range validation (`ge`/`le`) is retained for non-None values.

### Decision 4: Schema-mirrored backend, no API-shape break

The MCP tool already omits None params from the request body, and the `/custom` endpoint already maps `image`. So the API contract gains optional fields only; existing callers that always send `steps`/`cfg` keep working unchanged.

## Risks / Trade-offs

- **[Shared-code regression in `generate_image`]** → The default/seed logic moves into the queue's template branch; cover with a test asserting the template path still yields `steps=20`, `cfg=7.0`, and a recorded random seed when omitted.
- **[Seed reproducibility for custom path]** → When a custom workflow omits seed and its JSON seed is `0`/fixed, runs are now deterministic instead of random. This is the intended "respect JSON" semantics; documented in the tool docstring so agents pass an explicit seed for variation.
- **[Inpaint template node-name drift]** → `VAEEncodeForInpaint`/`LoadImageMask` names must match the target ComfyUI build. Mitigate by mirroring node names from a known-good ComfyUI inpaint export and validating the template loads as JSON in a test.
- **[Mask path traversal]** → Reuse the existing `_upload_gallery_image` guard (resolve under `gallery_dir`, reject traversal) for masks; no new file-access surface.

## Migration Plan

Additive and backward compatible — no data migration. Deploy backend (schema + queue + workflow + template) and MCP server together; older MCP callers that never send the new params are unaffected. Rollback is a straight revert since no persisted format changes.

## Open Questions

- Inpaint `denoise` default and `grow_mask_by` value for the bundled template — pick sensible defaults (e.g. `denoise≈1.0`, `grow_mask_by=6`) in the template, adjustable per call via existing `denoise`.
