# LoRA Training Agent Handoff Runbook

This runbook defines the agent contract for handing an approved LoRA dataset from
decision preflight to an explicit user-directed training run. It is a reporting
and execution contract only; it does not add automatic training triggers.

## Scope

- Use existing MCP tools for decision, Start, status monitoring, logs,
  cancellation, and smoke-test submission. Registration review is an
  interpretation of terminal `lora_train_job_status`, not a separate MCP tool.
- Do not call `lora_train_start` from a pre-start report, recommendation, or
  review summary.
- Start training only after the user explicitly asks to train the specific LoRA
  target from the reported dataset and recipe.
- Treat `dataset_hash`, `profile_hash`, and the preflight `recipe_hash` as
  approval evidence. If any identity changes, stop, rerun preflight, issue a new
  report, and obtain approval again.
- Start only when preflight returns `decision="train"` and a non-null
  `start_payload`. Submit that payload exactly; do not reconstruct it from
  `effective_recipe`, legacy `params`, defaults, or conversation memory.

## Pre-Start Handoff Report Template

Produce this report after `lora_training_decision_preflight` and before any
training Start. The report is non-executing.

```markdown
## LoRA Training Handoff

Dataset:
- Folder: <dataset_folder>
- Dataset type: <dataset_type>
- Trigger token: <trigger_token>
- Model family: <model_family>
- Caption profile: <caption_profile>
- Caption suitability verdict: <caption_suitability_verdict>

Decision:
- Training decision: <train | needs_review | do_not_train>
- Reasons: <reason list>
- Blocking issues: <issue list or none>
- Warnings: <warning list or none>
- Known risks: <risk list>

Approval identities:
- Dataset hash: <dataset_hash>
- Profile hash: <profile_hash>
- Recipe schema version: <requested/effective/start_payload recipe schema_version>
- Recipe hash preview: <preflight recipe_hash>

Requested versus effective scope:
- Requested scope: <requested_scope or "not specified by caller">
- Effective scope: <denoiser_kind, train_denoiser, train_text_encoder,
  native_scope_flag, verification_status>
- Field-source summary: <caller | preflight_policy | server_policy | derived
  for every effective recipe leaf>

Canonical recipe preview:
- Requested recipe: <complete requested_recipe, preserving caller omissions>
- Effective recipe: <complete effective_recipe, including model, scope, dataset,
  optimization, caching, execution, and server sections>

Human-readable effective summary:
- LoRA target name: <lora_target_name>
- Checkpoint / component identities: <locator, verification status, reason,
  bypass flag for checkpoint/text encoder/VAE/tokenizer>
- Network module / dim / alpha: <network_module>/<network_dim>/<network_alpha>
- Resolution / keep tokens: <resolution>/<keep_tokens>
- Epochs / batch / repeats: <epochs>/<batch_size>/<num_repeats>
- Gradient accumulation: <gradient_accumulation_steps>
- Optimizer / args: <optimizer_type>/<optimizer_args>
- Scheduler / args / warmup: <lr_scheduler>/<lr_scheduler_args>/<warmup>
- Learning rates: <base, denoiser, text encoder list>
- Effective seed: <mode, value, source>
- Bucket policy: <enable, no-upscale, min/max/steps>
- Cache policy: <latents, text encoder outputs, disk, derived
  latent_cache_to_disk/text_encoder_cache_to_disk>
- Workers / persistent workers / save cadence / final-only: <values>
- Server-owned constants: <gradient_checkpointing, caption_extension,
  shuffle_caption, save_model_as, launcher_num_cpu_threads_per_process>
- Step plan: <examples, batches/epoch, optimizer steps/epoch, total optimizer
  steps, warmup steps>

Capability and evidence:
- Runtime capability: <platform, status, reason, versions, supported precision>
- Preflight execution evidence: <status and reason>
- Evidence limitation: <source-contract preview is not trainer initialization proof>

Approval request:
- If decision is `train` and `start_payload` is non-null, request explicit
  training intent: "Train <lora_target_name> from <dataset_folder> now using
  recipe <recipe_hash_preview>."
- If decision is `needs_review` or `do_not_train`, or `start_payload` is null,
  do not request training approval. Report repair/next actions and prohibit
  `lora_train_start`.
```

Preflight does not expose a separate top-level `recipe_schema_version`; read it
from `requested_recipe`, `effective_recipe`, or `start_payload.recipe`. Use the
top-level `recipe_hash` as the preview hash. A null `requested_scope` means the
caller did not choose a scope; it must not be reported as an explicit
`train_text_encoder=false`. The complete `effective_scope` is the policy result.

`field_sources` must cover every effective recipe leaf:

- `caller`: explicitly submitted by the caller; the caller is not necessarily a
  human user, so do not relabel it as direct user selection.
- `preflight_policy`: materialized by decision preflight policy.
- `server_policy`: server-owned policy/constants, including values already
  visible during preflight as well as Start-side policy values.
- `derived`: computed from other canonical recipe values.

## Execution Sequence

1. Run or reuse `lora_training_decision_preflight` for the target dataset. If
   files, profile data, requested recipe, or conversation intent changed, rerun
   it with known expected hashes.
2. Always present the pre-start handoff report for `train`, `needs_review`, or
   `do_not_train`. For non-train decisions, show blocking/repair actions without
   requesting training approval, then stop.
3. Only the train branch may proceed. Require `ok=true`, both approval hashes, a
   `recipe_hash`, and a non-null `start_payload`; otherwise prohibit Start and
   never construct a payload.
4. Present the train branch's approval request and wait.
5. Only after explicit user approval for the specific target and reported recipe,
   pass the four fields from `start_payload` to `lora_train_start`:
   `folder`, `expected_dataset_hash`, `expected_profile_hash`, and `recipe`.
   Do not merge flat parameters, substitute defaults, edit
   `expected_recipe_hash`, or draw a new random seed.
6. If the user changes any recipe intent after the report, rerun preflight,
   report the new identities and effective recipe, and obtain new approval.
7. Poll `lora_train_job_status` until terminal with bounded polling. Report
   material state changes and compare the durable recipe identity, effective
   scope, step plan, components, capability, and execution evidence.
8. Read bounded `lora_train_logs` when the job starts, stalls, fails, is
   cancelled, or reaches completion.
9. Review registration fields from terminal status: `output_path`,
   `registered_lora_name`, and `registration_error`.
10. If training completed and a registered LoRA exists, run
    `lora_train_smoke_test`. If the MCP tool is unavailable in the active client,
    use `POST /api/lora-train/jobs/{job_id}/smoke-test`.
11. Record the immediate smoke response (`smoke_test_status`,
    `generation_job_id`, `artifact`, `error`) and refresh
    `lora_train_job_status` for persisted `smoke_test_*` fields. This batch
    proves submission only: do not wait for or claim generation completion or
    an artifact. Smoke reconciliation is deferred.
12. Produce the terminal report.

## Monitoring Evidence

For every queued/running poll, retain and compare:

- `recipe_schema_version`, `recipe_hash`, `requested_recipe`,
  `effective_recipe`, `requested_scope`, and `effective_scope`;
- `field_sources`, `step_plan`, `component_identities`, and `capability`;
- `execution_evidence.status/reason` and, when available, exact `argv`, exact
  dataset TOML content and SHA-256, launcher evidence, runtime capability, and
  sd-scripts revision.

Preflight evidence is normally `unverified` with a reason stating that it is a
source-contract preview and that the bounded trainer probe is deferred. This is
not runtime initialization proof. Under the dataset lock, the worker persists
the exact TOML and argv plus launcher/capability/revision evidence before
launching that same argv. This expected enrichment is not identity drift.

Do not label composite execution evidence `verified` merely because exact argv
or TOML exists. The composite status is verified only when launcher, capability,
and sd-scripts revision evidence are all verified; otherwise report the returned
`unverified` or `unavailable` status and reason.

Queued jobs can legitimately have null argv/TOML/launcher/revision fields until
the worker persists pre-launch evidence. Report them as not yet available; do
not infer them from configuration or legacy params.

## Recovery Rules

Recipe parse/compile failures use two carriers: preflight exposes them through
`blocking_issues[]`, while Start exposes them through the MCP `error` envelope.
Use whichever carrier the failed operation returned; do not invent missing
evidence.

- Failed job: do not retry automatically. Report `error_code`,
  `error_message`, structured `error_details`, available execution evidence,
  recent logs, all three approval identities, and the smallest useful next
  action.
- Cancelled job: confirm terminal status, capture recent logs and available
  evidence, and require a new explicit training request before any restart.
- Missing approval hash, `decision != "train"`, or null `start_payload`: do not
  call Start and do not build a payload. Rerun inspection/preflight, emit a new
  report, and wait for explicit approval.
- `dataset_hash_mismatch`, `profile_hash_mismatch`, or `recipe_hash_mismatch`:
  do not patch or retry the old payload. Rerun preflight, report the new
  identities and recipe, and obtain explicit approval again.
- `recipe_validation_failed`: in preflight, read the structured failure from
  `blocking_issues[]`; in Start, read the MCP `error` envelope. Report available
  `code`, `message`, `hint`, canonical location, accepted forms, and suggestion.
  Never echo the submitted value. Retry preflight only after an unambiguous,
  explicitly applied correction.
- `recipe_field_conflict`: show the conflicting canonical location and aliases.
  Do not choose an alias silently; ask which intent is authoritative, then run a
  new preflight.
- `incompatible_training_recipe`: show all conflicting requested paths. Do not
  silently disable Text Encoder training, caching, persistent workers, or any
  other requested scope. A correction requires a new preflight, report, and
  approval.
- `unsupported_runtime_precision`: report capability evidence when available;
  compilation failure can leave top-level capability null, which must be labeled
  `unavailable`. Report the conservative `mixed_precision=no` option, but do not
  substitute it until the user approves a new preflight payload.
- `unsupported_network_module`: report family, allowed identifiers, and
  canonical location when available after sanitization. Do not swap modules
  automatically; rerun preflight after the user approves a corrected intent.
- `legacy_training_fields_removed`: report only the returned field names. Do not
  translate the old flat Start payload into recipe form; rerun preflight and
  submit its exact `start_payload`.
- Generic field-level 422: report the envelope message and each safe `loc`,
  `type`, context, and `msg` if present. Do not remove a field, invent a value,
  or retry with an implicit backend default.
- `model_family_mismatch`: report exact `code`, `message`, and `details`. Do not
  substitute `recipe.model.family` or checkpoint; rerun inspection and
  preflight, then obtain new explicit approval.
- `invalid_dataset_folder`: report exact `code`, `message`, and `details`. Do not
  rewrite, normalize, or substitute the path.
- Smoke-test failure after completed training: report training as completed and
  smoke testing as failed. Keep the registered LoRA visible and recommend
  generation parameter or resource checks.

## Historical Jobs

Historical status may have `recipe_schema_version`, `recipe_hash`, scopes,
sources, step plan, component identities, capability, and execution evidence as
null. Label missing v1 identity/evidence `unavailable`; never infer or invent it.
Legacy `params` is historical context only and is not a canonical recipe.

## Terminal Report Template

```markdown
## LoRA Training Result

Job:
- Job id: <job_id>
- Final status: <completed | failed | cancelled>
- Dataset folder: <dataset_folder>
- Dataset hash: <dataset_hash>
- Profile hash: <profile_hash>
- Recipe schema version / hash: <recipe_schema_version>/<recipe_hash>
- Requested / effective scope: <requested_scope>/<effective_scope>
- Canonical recipe context: <requested_recipe and effective_recipe, or an
  unavailable/historical-context label>
- Effective seed: <effective_recipe.optimization.seed or unavailable>
- Optimizer step plan: <step_plan or unavailable>

Execution evidence:
- Composite status / reason: <status>/<reason>
- Exact argv: <argv or unavailable>
- Dataset TOML / SHA-256: <content/hash or unavailable>
- Launcher evidence: <status/value/reason>
- Capability evidence: <status/platform/versions/reason>
- sd-scripts revision: <status/value/reason>

Output:
- Output path: <output_path or none>
- Registered LoRA name: <registered_lora_name or none>
- Registration error: <registration_error or none>

Smoke test:
- Immediate response: <smoke_test_status, generation_job_id, artifact, error>
- Persisted status: <smoke_test_status, smoke_test_job_id,
  smoke_test_artifact, smoke_test_error>
- Current-batch boundary: <submission only; artifact normally unavailable
  until deferred reconciliation>

Logs and errors:
- Error or cancellation reason: <error_or_cancellation_reason or none>
- Structured error details: <error_details or none>
- Evidence captured before failure/cancellation: <execution_evidence or unavailable>
- Recent log summary: <recent_log_summary>
- Logs/error summary: <logs_error_summary>

Recommended next actions:
- <next_action list>
```

## Machine-Readable Contract

```json handoff-contract
{
  "contract_id": "lora-training-agent-handoff-runbook",
  "version": 4,
  "approval_gate": {
    "requires_explicit_user_training_request": true,
    "specific_lora_target_required": true,
    "pre_start_report_is_non_executing": true,
    "required_approval_identities": [
      "dataset_hash",
      "profile_hash",
      "recipe_hash"
    ],
    "recipe_hash_transport_path": "start_payload.recipe.expected_recipe_hash",
    "forbidden_before_approval": [
      "lora_train_start"
    ],
    "accepted_intent_examples": [
      "Train <lora_target_name> from <dataset_folder> now using recipe <recipe_hash>.",
      "Start training <lora_target_name> now using the exact reported start_payload."
    ],
    "rejected_intent_examples": [
      "Looks good.",
      "What would you recommend?",
      "Prepare the report."
    ]
  },
  "source_fields": {
    "decision_preflight": [
      "folder",
      "decision",
      "reasons",
      "blocking_issues",
      "warnings",
      "next_actions",
      "dataset_hash",
      "profile_hash",
      "normalized_trigger_token",
      "requested_recipe",
      "effective_recipe",
      "requested_scope",
      "effective_scope",
      "field_sources",
      "step_plan",
      "component_identities",
      "capability",
      "execution_evidence",
      "recipe_hash",
      "policy_rationale",
      "start_payload"
    ],
    "dataset_metadata_or_inspection": [
      "dataset_type",
      "trigger_token",
      "model_family",
      "caption_profile",
      "caption_suitability_verdict"
    ],
    "job_status": [
      "job_id",
      "folder",
      "status",
      "stage",
      "progress",
      "current_epoch",
      "total_epochs",
      "dataset_hash",
      "profile_hash",
      "normalized_trigger_token",
      "recipe_schema_version",
      "recipe_hash",
      "requested_recipe",
      "effective_recipe",
      "requested_scope",
      "effective_scope",
      "field_sources",
      "step_plan",
      "component_identities",
      "capability",
      "execution_evidence",
      "log_path",
      "log_tail_lines",
      "log_truncated",
      "output_path",
      "registered_lora_name",
      "registration_error",
      "error_code",
      "error_message",
      "error_details",
      "params",
      "smoke_test_status",
      "smoke_test_job_id",
      "smoke_test_artifact",
      "smoke_test_error",
      "created_at",
      "updated_at",
      "started_at",
      "completed_at",
      "cancel_requested_at"
    ]
  },
  "pre_start_report": {
    "required_fields": [
      "dataset_folder",
      "dataset_type",
      "trigger_token",
      "model_family",
      "caption_profile",
      "caption_suitability_verdict",
      "training_decision",
      "reasons",
      "dataset_hash",
      "profile_hash",
      "human_readable_effective_summary",
      "known_risks",
      "lora_target_name",
      "explicit_user_training_intent",
      "recipe_schema_version",
      "recipe_hash_preview",
      "requested_scope",
      "effective_scope",
      "field_sources",
      "step_plan",
      "component_identities",
      "runtime_capability",
      "requested_recipe",
      "effective_recipe"
    ],
    "must_state": [
      "This report does not start training.",
      "Do not call lora_train_start until the user explicitly asks to train this specific LoRA.",
      "If dataset_hash, profile_hash, recipe_hash, or requested intent changes, rerun decision preflight and issue a new report.",
      "Preflight source-contract evidence is not runtime trainer initialization proof."
    ],
    "decision_branches": {
      "train": {
        "emit_report": true,
        "requires_non_null_start_payload": true,
        "request_training_approval": true,
        "allow_start": true
      },
      "needs_review": {
        "emit_report": true,
        "request_training_approval": false,
        "allow_start": false
      },
      "do_not_train": {
        "emit_report": true,
        "request_training_approval": false,
        "allow_start": false
      }
    }
  },
  "field_source_semantics": {
    "caller": "Explicitly submitted by the caller; caller does not necessarily mean a human user.",
    "preflight_policy": "Materialized by decision preflight policy.",
    "server_policy": "Includes server-owned constants or policy values visible during preflight and Start.",
    "derived": "Computed from other canonical effective recipe values."
  },
  "execution_sequence": [
    {
      "step": 1,
      "name": "decision_reverification",
      "tool": "lora_training_decision_preflight",
      "requires": [
        "dataset_folder",
        "expected_dataset_hash_if_known",
        "expected_profile_hash_if_known",
        "requested_recipe_if_any"
      ],
      "purpose": "Confirm decision, approval identities, canonical recipe, scope, field sources, step plan, components, capability, and exact start_payload."
    },
    {
      "step": 2,
      "name": "pre_start_report",
      "tool": null,
      "requires": [
        "decision_preflight_result"
      ],
      "branch_rule": "Always emit the report. Request training approval only for decision=train with a non-null start_payload; otherwise report repair actions and prohibit Start."
    },
    {
      "step": 3,
      "name": "training_start",
      "tool": "lora_train_start",
      "requires": [
        "explicit_user_training_request",
        "specific_lora_target",
        "canonical_start_payload",
        "expected_dataset_hash",
        "expected_profile_hash"
      ],
      "submitted_fields": [
        "folder",
        "expected_dataset_hash",
        "expected_profile_hash",
        "recipe"
      ],
      "submission_rule": "Submit the four start_payload fields exactly; do not reconstruct, merge, default, override expected_recipe_hash, or redraw seed."
    },
    {
      "step": 4,
      "name": "status_monitoring",
      "tool": "lora_train_job_status",
      "requires": [
        "job_id"
      ],
      "reports": [
        "status",
        "stage",
        "progress",
        "current_epoch",
        "total_epochs",
        "dataset_hash",
        "profile_hash",
        "recipe_schema_version",
        "recipe_hash",
        "requested_recipe",
        "effective_recipe",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "capability",
        "execution_evidence"
      ]
    },
    {
      "step": 5,
      "name": "bounded_log_review",
      "tool": "lora_train_logs",
      "requires": [
        "job_id",
        "lines"
      ],
      "reports": [
        "lines",
        "log_path",
        "truncated"
      ]
    },
    {
      "step": 6,
      "name": "registration_review",
      "tool": null,
      "source": "terminal_lora_train_job_status",
      "requires": [
        "terminal_lora_train_job_status"
      ],
      "reports": [
        "output_path",
        "registered_lora_name",
        "registration_error"
      ]
    },
    {
      "step": 7,
      "name": "smoke_test",
      "tool": "lora_train_smoke_test",
      "requires": [
        "completed_status",
        "registered_lora_name"
      ],
      "reports": [
        "smoke_test_status",
        "generation_job_id",
        "artifact",
        "error"
      ]
    },
    {
      "step": 8,
      "name": "terminal_status_refresh",
      "tool": "lora_train_job_status",
      "requires": [
        "job_id"
      ],
      "reports": [
        "status",
        "recipe_schema_version",
        "recipe_hash",
        "execution_evidence",
        "smoke_test_status",
        "smoke_test_job_id",
        "smoke_test_artifact",
        "smoke_test_error"
      ]
    }
  ],
  "terminal_report": {
    "required_common_fields": [
      "job_id",
      "final_status",
      "dataset_folder",
      "dataset_hash",
      "profile_hash",
      "canonical_recipe_context",
      "recipe_schema_version",
      "recipe_hash",
      "requested_scope",
      "effective_scope",
      "execution_evidence",
      "recommended_next_actions"
    ],
    "completed_required_fields": [
      "output_path",
      "registered_lora_name",
      "smoke_test_status",
      "smoke_test_job_id",
      "smoke_test_artifact",
      "registration_error",
      "effective_seed",
      "optimizer_step_plan",
      "exact_argv_revision_evidence_status"
    ],
    "failed_required_fields": [
      "error_or_cancellation_reason",
      "recent_log_summary",
      "logs_error_summary",
      "error_code",
      "error_message",
      "error_details",
      "execution_evidence_before_failure"
    ],
    "cancelled_required_fields": [
      "error_or_cancellation_reason",
      "recent_log_summary",
      "logs_error_summary",
      "execution_evidence_before_cancellation"
    ],
    "smoke_submission_response_fields": [
      "smoke_test_status",
      "generation_job_id",
      "artifact",
      "error"
    ],
    "smoke_status_fields": [
      "smoke_test_status",
      "smoke_test_job_id",
      "smoke_test_artifact",
      "smoke_test_error"
    ]
  },
  "smoke_lifecycle": {
    "current_batch_guarantee": "submission_only",
    "may_claim_generation_completed": false,
    "may_claim_generated_artifact": false,
    "submission_response_fields": [
      "smoke_test_status",
      "generation_job_id",
      "artifact",
      "error"
    ],
    "persisted_status_fields": [
      "smoke_test_status",
      "smoke_test_job_id",
      "smoke_test_artifact",
      "smoke_test_error"
    ],
    "deferred": "Generation reconciliation and artifact persistence belong to a later batch."
  },
  "recovery": {
    "failed": [
      "Do not retry automatically.",
      "Report error_code, error_message, error_details, recent logs, approval identities, and available execution evidence.",
      "Recommend the smallest useful next action before asking for a new explicit training request."
    ],
    "cancelled": [
      "Confirm cancelled terminal status with lora_train_job_status.",
      "Read bounded logs and retain available execution evidence.",
      "Require a new explicit user training request before any restart."
    ],
    "stale_hash": [
      "Do not retry lora_train_start after dataset_hash_mismatch or profile_hash_mismatch.",
      "Inspect the dataset/profile and rerun lora_training_decision_preflight with current hashes.",
      "Emit a new pre-start report and wait for explicit approval again."
    ],
    "missing_approval_hash": [
      "Do not call lora_train_start when either approval hash is missing.",
      "Inspect the dataset/profile and rerun lora_training_decision_preflight.",
      "Emit a new pre-start report containing both hashes and wait for explicit approval."
    ],
    "field_validation": [
      "Report the envelope message and every field-level 422 entry's exact loc and type; include safe ctx and msg if present.",
      "Do not retry by removing a field, inventing a value, or using an implicit backend default.",
      "If the approved payload must change, rerun preflight, emit a new pre-start report, and wait for new explicit approval."
    ],
    "model_family_mismatch": [
      "Report the exact model_family_mismatch code, message, and details.",
      "Do not retry or substitute recipe.model.family or checkpoint.",
      "Rerun inspection and preflight, issue a new report, and wait for new explicit approval."
    ],
    "unsafe_dataset_path": [
      "Report the exact invalid_dataset_folder code, message, and details.",
      "Do not retry, rewrite, normalize, or substitute the dataset path.",
      "After the user corrects the location, inspect and preflight it again, issue a new report, and wait for new explicit approval."
    ],
    "recipe_validation_failed": [
      "Read preflight recipe failures from blocking_issues[] and Start failures from the MCP error envelope.",
      "Report the returned code, message, hint, canonical location, accepted_forms, and suggestion.",
      "Never echo or retain the submitted value in the report.",
      "Retry preflight only after an unambiguous correction is explicitly applied."
    ],
    "recipe_field_conflict": [
      "Report the conflicting canonical location and alias names without values.",
      "Do not choose an alias silently; ask which user intent is authoritative.",
      "Run a new preflight after the conflict is resolved."
    ],
    "incompatible_training_recipe": [
      "Report every conflicting requested canonical path.",
      "Do not disable Text Encoder training, caching, workers, or another requested scope silently.",
      "Apply only a user-approved correction through a new preflight and report."
    ],
    "unsupported_runtime_precision": [
      "Report capability evidence when available; if compilation returned none, label it unavailable.",
      "Report the conservative mixed_precision=no option.",
      "Do not substitute precision until the user approves a new preflight payload."
    ],
    "unsupported_network_module": [
      "Report family, allowed identifiers, canonical location, and accepted modules when available after sanitization.",
      "Do not substitute a module automatically.",
      "Rerun preflight only after the user approves corrected intent."
    ],
    "recipe_hash_mismatch": [
      "Do not patch or retry the old Start payload.",
      "Rerun preflight and report the new dataset, profile, and recipe identities.",
      "Wait for explicit approval of the new exact start_payload."
    ],
    "legacy_training_fields_removed": [
      "Report only the returned removed field names and never their values.",
      "Do not translate the legacy flat payload into a recipe.",
      "Rerun preflight and submit its exact start_payload."
    ],
    "decision_without_start_payload": [
      "Do not call Start when decision is not train or start_payload is null.",
      "Do not construct a payload from effective_recipe or defaults.",
      "Resolve blocking issues and run a new preflight."
    ],
    "smoke_test_failed": [
      "Report training completion separately from smoke-test failure.",
      "Keep output_path and registered_lora_name visible.",
      "Recommend generation parameter or resource checks before another smoke test."
    ]
  },
  "historical_job": {
    "v1_fields_may_be_null": true,
    "legacy_params_are_context_only": true,
    "missing_evidence_status": "unavailable"
  }
}
```
