# Historical absorbed-skill excerpts

Original context is preserved in the verified migration backup. These excerpts are historical, not current authority or approval.

## Source lines 135–135: Image-generation project pipelines

## Image-generation project pipelines


## Source lines 137–137: Image-generation project pipelines

When applying this control plane to an image-generation/MCP codebase:


## Source lines 139–139: Image-generation project pipelines

- If the primary repo already has unrelated dirty work, create a dedicated Git worktree/branch first. Put the tracked spec, state bootstrap, role bindings, templates, and dispatcher tests there; commit that clean bootstrap before initializing runtime state or dispatching an executor.


## Source lines 140–140: Image-generation project pipelines

- Keep runtime image generation out of ordinary implementation stages. Reserve it for an explicit live-smoke stage after unit/integration gates pass.


## Source lines 141–141: Image-generation project pipelines

- For CTY, every completed smoke image must be delivered directly with original/reference/result labels, workflow type, control source, and path. Unless CTY explicitly asks, the pipeline and reporting agent must not analyze, score, or decide whether the image is visually acceptable; machine validators may check execution, files, dimensions, hashes, metadata, and workflow only.


## Source lines 142–142: Image-generation project pipelines

- A `cronjob run` request is not proof that the scheduler executed. Verify `last_run_at` or the project runtime state, then prove a real run record/handle exists. Also verify a later reconciliation tick does not create a duplicate run.
