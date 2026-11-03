# Project goal

## Product

A complete art team: when a user requests images, generate and deliver them through the user's local ComfyUI, support user-specified styles, and provide LoRA training capability. When users request new features, create native issues for Producer to assess and plan. The Backend owns jobs/provenance; ComfyUI performs generation; MCP provides the agent interface. The frontend supports inspection and manual use.

Source interfaces include image generation/custom graphs, Civitai resources/recipes, Gallery, Prompt Library and style presets. See [Progress](PROGRESS.md) for acceptance limits.

## Company preparation

The approved workstreams are art production/delivery and software/platform engineering. Once configured, requests go to a designated project channel; Paperclip handles coordination and native review, while the Backend retains job state.

The [seven approved responsibilities](team/README.md) separate requirements/workflow execution, resource management, training, engineering and independent technical QA. CTY owns aesthetic evaluation and final artwork acceptance. Workflow research may proceed within authorized task/test scope. Producer prioritizes all company software work through the platform engineer.

The AI Drawing company (`AID`) and its two Paperclip projects exist. All seven hires are approved and available for native assignments; the six specialist roles report to Producer. Both workstreams use the [designated project channel](team/channel-routing.md).

[CTY's current native instruction](http://127.0.0.1:3100/AID/issues/AID-4#comment-71655f19-384a-4aa9-af39-d2ba7bdcd9d7) delegates continuous company operation to Producer: independently assess priorities, maintain the backlog, plan and dispatch work, coordinate independent QA, resolve defects, integrate deliveries and continue to the next useful item. The earlier first-agenda confirmation stage and Hermes-added per-item waiting/single-package cutoff no longer govern ordinary work. [CTY's supplementary delegation](http://127.0.0.1:3100/AID/issues/AID-4#comment-d8af5865-ed01-47cf-8e5f-37bef39e0e5f) makes Hermes the decision liaison for ordinary follow-through, routine decisions and assessment of functional completeness or a reasonable milestone. Producer remains the independent native coordinator and chooses priorities and technical approaches with the team. Hermes does not impose topics, task/time counts, a Worker/LoRA-only scope or a one-repair cutoff. Escalate only a concrete decision beyond delegated authority or reliable judgment, with options and a recommendation; missing owner-authored completion criteria are not a blocker.

Producer retains a long-lived native coordination path with explicit owners, dependencies, successor actions and applicable watchdog coverage. Completed engineering and original FAIL/PASS records remain evidence; they do not stop the company or require rebuilding completed features. Frozen candidates keep their original bytes; their older instructions must be interpreted under the latest native owner authority and current canonical entry documents.

Windows Worker installation/reporting remains deferred and unconfirmed. Independent technical QA, CTY aesthetic acceptance, data protection, budgets and genuinely owner-reserved irreversible actions or external commitments remain applicable under their original authority. Escalate a concrete reserved decision while progressing other available work; do not turn those boundaries into a new work-type whitelist or repeated permission gate. See [Progress](PROGRESS.md) for the active backlog and next owners. Actual task/run state establishes execution; approval or configuration does not establish runtime or product acceptance.

## Milestone assessment

Producer maintains evidence-based criteria in the [current native plan](http://127.0.0.1:3100/AID/issues/AID-4#document-plan), using real image/style requests and revisions, LoRA preparation-to-product/smoke retrieval, and native feature intake-to-reviewed delivery. These are assessment dimensions, not an exhaustive feature list or fixed implementation order. Record source implementation, integrated/running capability, retrieved/delivered results and CTY aesthetic acceptance separately. A mock-only PASS or unmerged candidate does not establish complete functionality.

At a coherent milestone, report supporting evidence, meaningful remaining limits/risks and a recommended continuation or pause through the project channel for Hermes follow-through. Do not invent speculative hardening to keep busy or end the company mandate just because one child tree finishes. Explain genuine external constraints and work still possible.

## Current owner completion mandate

CTY explicitly delegates proactive follow-through to Hermes until the project's ComfyUI MCP, LoRA training and existing simple user UI are complete, Hermes judges a coherent milestone reached, or a concrete decision genuinely requires CTY. This supplements the standing native delegation on AID-4; it does not replace Producer's independent priorities, technical judgment or specialist dispatch.

Assess actual user journeys, not file counts or source-only task closure:

- **ComfyUI MCP:** supported requests reach the intended ComfyUI route, retain canonical job identity and useful errors/status, and produce retrievable results through the MCP interface. A listed tool/schema or healthy listener alone is insufficient.
- **LoRA training:** preparation and actual effective parameters lead to a valid new, correctly attributed model with readable naming, run isolation and preserved parameter records; supported selection and smoke-result retrieval have real execution evidence. Offline fixtures alone do not establish training completion.
- **Existing simple UI:** the current frontend supports the implemented generation/training flows, understandable progress/errors and result inspection through real Backend integration and independent technical QA. This is completion of the existing UI, not permission for an unrelated UI rewrite.

[CTY's latest proxy direction](http://127.0.0.1:3100/AID/issues/AID-4#comment-db58231a-9d01-4838-88b9-e9b55c857b35) defines Hermes as the delegated human/Board proxy for Producer questions through supported operator surfaces, with attributed judgment rather than a fabricated personal vote. Each resolved question receives a Discord report naming the original problem, solution/reason, verified writeback and actual continuation. [The clarified human/Board proxy mandate](http://127.0.0.1:3100/AID/issues/AID-4#document-board-proxy-operation-review) permits Hermes to review and issue a new exact operation approval within project authority; a new approval requirement does not itself require CTY personally. Only actual CTY-reserved permission, material project-direction changes or a reliably unresolvable decision return to CTY. Each verified advancement also receives a prompt Discord report, separating decision, handoff, actual execution, partial stop and delivery. An interaction label alone is not the substantive boundary. Hermes handles decisions it can responsibly make under current authority and verifies native writeback and continuation. Producer continues useful work without per-item start confirmation. Return a decision-ready report to CTY when the journeys are complete, a useful milestone warrants handback, or a specific unresolved/reserved choice requires CTY: state proven outcomes, remaining limits, options and recommendation. Do not equate a single package's completion or an unanswered routine card with project handback.

[CTY's later clarification, relayed by Hermes](http://127.0.0.1:3100/AID/issues/AID-4#document-w19-decision-producer-adoption), keeps routine technical, checking and responsibly decidable operational questions with Hermes, with a report in the project channel. Project-architecture decisions and concrete matters beyond its authority or reliable judgment return to CTY. A design decision does not replace the exact operation grant or actual execution conditions.

Existing data protection, independent QA, finite recovery, resource/spending/remote-operation authority and CTY's aesthetic judgment remain applicable. Windows installation/reporting remains deferred; an outcome mandate alone does not identify a dataset/base model, approve a new compute campaign or authorize a ComfyUI restart. Resolve concrete scope under the latest native authority rather than using these boundaries as a permanent work-type whitelist.

## Training direction

The approved [training responsibility](team/roles/lora-training.md) covers owner images, dataset/caption preparation and authorized LoRA training with an owner-specified supported base model. Propose supplemental-image scope for owner approval and coordinate it through the generation specialist. Preserve original/generated provenance.

Verify model support, per-task settings and execution readiness before use. Role approval grants neither activation nor training acceptance; see [Training status](training-status.md).

## Engineering principles

Distinguish source capability, installed behavior, owner requirements and execution authority. Keep reproducible Backend records without requiring users to manage graph internals. Repair verified defects rather than rewrite from assumptions. Maintain topic authorities; remove superseded instructions and task history.
