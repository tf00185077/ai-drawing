# p1-00 kickoff review

Verdict: CLEAR

Reviewed commit: `e443f2e22a17f3ca61f69527bdd392e703b0e88b`.
Review issue: [AID-147](/AID/issues/AID-147).
Date: 2026-11-24.

My reading: CTY's later instruction authorizes executable work inside the existing
project boundaries and delegates routine reference choices. Producer's installed
Illustrious/default, no-LoRA, local choice therefore requires no further ordinary
choice confirmation. Phase 1 first measures today's Mac path: run the full Backend
suite, then use existing MCP tools to produce and retrieve an image and a traceable
revision, logging every manual action, retry, workaround and non-MCP call with a
baseline count. A demonstrated run blocker may stop the flow; a failed suite still
fails its gate. The baseline collects evidence without repairs. Later tasks fix the
measured friction. Phase exit still requires three consecutive real runs with zero
manual fixes and the owner's roadmap review at phase close.

This reading was written from the two owner-source records, ROADMAP Phase 1 and
CURRENT before opening task.md or the execution plan. Its durable record is
[the independent-reading comment](/AID/issues/AID-147#comment-54f9093e-8a6d-4969-be06-d5c2434eb0ab).
The records distinguish exact owner words, intake framing and Producer's delegated
technical choice; they do not claim individual owner model selection or aesthetic
acceptance.

Difference: none demonstrated. The four Done when items and the execution plan
implement the same bounded first check.

## Comparison

| Item | Comparison with the owner sources and active milestone |
|---|---|
| D1 | Full Mac Backend suite first, with AGENTS commands and `--timeout=60`; summary and duration are required. The plan explicitly preserves a non-passing suite as a gate requiring a bounded repair and independent review before dependent work. |
| D2 | Today's tools over stdio: health/resources, generate, poll, retrieve, a new generate request with a parent artifact, poll, retrieve; raw outputs and timestamps or an explicit blocker. This measures current behavior without implementing future tools. |
| D3 | Every manual step, retry, workaround and non-MCP call must appear in the friction log, mapped to a later task or marked new with a proposed task. QA compares the transcript with the log. Fixing findings is explicitly excluded. |
| D4 | The manifest states the baseline manual-fix count. One baseline run is not the three-run Phase 1 exit. |

## Prerequisites and execution notes

- No unsatisfied kickoff prerequisite was demonstrated. The named fixed commit is
  present and contains the owner sources, adopted pair, task and execution plan.
  Publication readback is supplied by the authenticated handoff; this review did
  not repeat remote publication checks.
- `manifest.md` is absent from the reviewed task tree, as expected before execution.
  This is a kickoff verdict, not delivery PASS or evidence acceptance.
- Pass `checkpoint=Illustrious-XL-v2.0.safetensors`, `template=default` and
  `execution_target=local` through today's `generate_image`. Its existing signature
  forwards those values. The graph uses `CheckpointLoaderSimple` and its metadata
  identifies SDXL, but its saved checkpoint name is older. Do not edit the graph or
  download a replacement as a hidden baseline repair. Runtime compatibility remains
  unverified.
- Revision annotations belong in `revision_context`; the existing Backend request
  schema requires `request_ref` and `brief_revision`, with `parent_artifact_id` for
  the revision. Use the canonical artifact identity and a new generation request,
  following the linked MCP documentation and revision memory. `gallery_rerun` does
  not establish revision lineage.
- A timeout requires checking the existing job ID before resubmission under the
  operating policy. Log failures, recovery actions and any workaround; the baseline
  does not authorize repairs. No worker, training, video, architecture or aesthetic
  scope is added.

## Checks performed and limits

- Read snapshot files with `git show e443f2e22a17f3ca61f69527bdd392e703b0e88b:<path>`:
  AGENTS, MEMORY, INDEX, README, CURRENT, ROADMAP, both owner-source records, operating
  policy, team guide, skill bindings, MCP/setup docs, MCP decisions, compute/model/
  revision/explicit-LoRA memory, p1-00 task and Phase 1 execution plan.
- Checked the commit with `git show --no-patch --format=fuller` and task contents
  with `git ls-tree -r --name-only` at the same hash. The task tree contained only
  task.md. Inspected fixed-commit generation forwarding, revision schema, Gallery
  retrieval fields and default graph/metadata. The inspected commands succeeded.
- Loaded reviewspec-core, reviewspec-review, paperclip-task-handoff, Paperclip,
  using-superpowers and verification-before-completion skills.
- Offline tests: not run in this kickoff-only assignment. Running service:
  not probed. Real generation: not run. Artifact retrieval: not performed.
  Cancellation, runtime error/recovery behavior and duplicate-submission behavior
  were not exercised. No execution acceptance or compatibility claim is made.
- Later Phase 1 specifications have not received kickoff clearance from this
  review; they require their own baseline-informed kickoff.

Producer on [AID-142](/AID/issues/AID-142) can read this CLEAR verdict and create
separate Coding and independent exact-commit evidence-review cards. A documented
run stop is evidence, not a suite pass or a Phase 1 exit.
