# LoRA Training Agent Handoff Runbook

This runbook defines the agent contract for handing an approved LoRA dataset from
decision preflight to an explicit user-directed training run. It is a reporting
and execution contract only; it does not add automatic training triggers.

## Scope

- Use existing MCP tools for decision, start, monitoring, logs, cancellation, and
  smoke testing.
- Do not call `lora_train_start` from a pre-start report, recommendation, or
  review summary.
- Start training only after the user explicitly asks to train the specific LoRA
  target from the reported dataset and parameters.
- Treat `dataset_hash` and `profile_hash` as approval evidence. If either hash
  is stale, stop and rerun inspection/decision before asking for approval again.

## Pre-Start Handoff Report Template

Produce this report after `lora_training_decision_preflight` and before any
training start. The report is non-executing.

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

Hashes:
- Dataset hash: <dataset_hash>
- Profile hash: <profile_hash or none>

Selected training parameters:
- LoRA target name: <lora_target_name>
- Checkpoint: <checkpoint>
- Epochs: <epochs>
- Resolution: <resolution>
- Batch size: <batch_size>
- Learning rate: <learning_rate>
- Network module: <network_module>
- Network dim / alpha: <network_dim>/<network_alpha>
- Repeats / keep tokens: <num_repeats>/<keep_tokens>
- Mixed precision: <mixed_precision>
- Model-family runtime args: <anima_qwen3/anima_vae/anima_t5_tokenizer_path or none>

Approval request:
- Explicit user training intent required: "Train <lora_target_name> from <dataset_folder> now with these parameters."
- Until the user gives that specific request, do not call `lora_train_start`.
```

## Execution Sequence

1. Run or reuse `lora_training_decision_preflight` for the target dataset. If
   the pre-start report is older than the current conversation context or the
   user edits files/profile data, rerun it with expected hashes.
2. Present the pre-start handoff report and wait.
3. Only after explicit user approval for the specific LoRA target, call
   `lora_train_start` with selected parameters and `expected_dataset_hash`.
   Verify `expected_profile_hash` through the immediately preceding decision
   preflight because the current start tool does not accept profile hashes.
4. Poll `lora_train_job_status` until the job is terminal, using bounded polling
   and reporting material changes.
5. Read bounded `lora_train_logs` when the job starts, stalls, fails, is
   cancelled, or reaches completion.
6. Review registration fields from terminal status: `output_path`,
   `registered_lora_name`, and `registration_error`.
7. If training completed and a registered LoRA exists, call
   `lora_train_smoke_test`.
8. Read final `lora_train_job_status` after smoke testing and produce the
   terminal report.

## Recovery Rules

- Failed job: do not retry automatically. Report `error_code`,
  `error_message`, recent logs, dataset/profile hashes, and the smallest useful
  next action such as fix dataset captions, update runtime paths, inspect the
  Kohya command, or rerun decision preflight.
- Cancelled job: confirm cancellation status, capture recent logs, keep the same
  hashes in the terminal report, and ask for a new explicit training request
  before any restart.
- Stale dataset/profile hash: stop before `lora_train_start`, inspect the
  dataset/profile, rerun decision preflight with current hashes, emit a new
  pre-start report, and wait for explicit approval again.
- Smoke-test failure after completed training: report training as completed and
  smoke testing as failed. Do not hide the registered LoRA; recommend generation
  parameter or resource checks before retesting.

## Terminal Report Template

```markdown
## LoRA Training Result

Job:
- Job id: <job_id>
- Final status: <completed | failed | cancelled>
- Dataset folder: <dataset_folder>
- Dataset hash: <dataset_hash>
- Profile hash: <profile_hash or none>
- Selected parameters: <selected_training_parameters>

Output:
- Output path: <output_path or none>
- Registered LoRA name: <registered_lora_name or none>
- Registration error: <registration_error or none>

Smoke test:
- Smoke-test status: <not_run | submitted | completed | failed>
- Smoke-test job id: <smoke_test_job_id or none>
- Generated artifact reference: <smoke_test_artifact or none>
- Smoke-test error: <smoke_test_error or none>

Logs and errors:
- Error or cancellation reason: <error_or_cancellation_reason or none>
- Recent log summary: <recent_log_summary>
- Logs/error summary: <logs_error_summary>

Recommended next actions:
- <next_action list>
```

## Machine-Readable Contract

```json handoff-contract
{
  "contract_id": "lora-training-agent-handoff-runbook",
  "version": 1,
  "approval_gate": {
    "requires_explicit_user_training_request": true,
    "specific_lora_target_required": true,
    "pre_start_report_is_non_executing": true,
    "forbidden_before_approval": [
      "lora_train_start"
    ],
    "accepted_intent_examples": [
      "Train <lora_target_name> from <dataset_folder> now with these parameters.",
      "Start training <lora_target_name> now using dataset hash <dataset_hash>."
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
      "suggested_params"
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
      "normalized_trigger_token",
      "log_path",
      "log_tail_lines",
      "log_truncated",
      "output_path",
      "registered_lora_name",
      "registration_error",
      "error_code",
      "error_message",
      "params",
      "smoke_test_status",
      "smoke_test_job_id",
      "smoke_test_artifact",
      "smoke_test_error"
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
      "selected_training_parameters",
      "known_risks",
      "lora_target_name",
      "explicit_user_training_intent"
    ],
    "must_state": [
      "This report does not start training.",
      "Do not call lora_train_start until the user explicitly asks to train this specific LoRA.",
      "If dataset_hash or profile_hash changes, rerun decision preflight and issue a new report."
    ]
  },
  "execution_sequence": [
    {
      "step": 1,
      "name": "decision_reverification",
      "tool": "lora_training_decision_preflight",
      "requires": [
        "dataset_folder",
        "expected_dataset_hash_if_known",
        "expected_profile_hash_if_known"
      ],
      "purpose": "Confirm decision, dataset hash, profile hash, reasons, and suggested parameters before asking for approval."
    },
    {
      "step": 2,
      "name": "training_start",
      "tool": "lora_train_start",
      "requires": [
        "explicit_user_training_request",
        "specific_lora_target",
        "selected_training_parameters",
        "expected_dataset_hash",
        "expected_profile_hash_verified_by_preflight"
      ],
      "submitted_fields": [
        "folder",
        "checkpoint",
        "trigger_token",
        "expected_dataset_hash",
        "model_family",
        "epochs",
        "resolution",
        "batch_size",
        "learning_rate",
        "class_tokens",
        "keep_tokens",
        "num_repeats",
        "mixed_precision",
        "network_module",
        "network_dim",
        "network_alpha",
        "anima_qwen3",
        "anima_vae",
        "anima_t5_tokenizer_path",
        "sdxl"
      ]
    },
    {
      "step": 3,
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
        "dataset_hash"
      ]
    },
    {
      "step": 4,
      "name": "bounded_log_review",
      "tool": "lora_train_logs",
      "requires": [
        "job_id",
        "line_limit"
      ],
      "reports": [
        "recent_log_summary",
        "log_path",
        "log_truncated"
      ]
    },
    {
      "step": 5,
      "name": "registration_review",
      "tool": "registration_review",
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
      "step": 6,
      "name": "smoke_test",
      "tool": "lora_train_smoke_test",
      "requires": [
        "completed_status",
        "registered_lora_name"
      ],
      "reports": [
        "smoke_test_status",
        "smoke_test_job_id",
        "generated_artifact_reference",
        "smoke_test_error"
      ]
    },
    {
      "step": 7,
      "name": "terminal_status_refresh",
      "tool": "lora_train_job_status",
      "requires": [
        "job_id"
      ],
      "reports": [
        "final_status",
        "smoke_test_status",
        "smoke_test_artifact"
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
      "selected_training_parameters",
      "recommended_next_actions"
    ],
    "completed_required_fields": [
      "output_path",
      "registered_lora_name",
      "smoke_test_status",
      "generated_artifact_reference",
      "registration_error"
    ],
    "failed_required_fields": [
      "error_or_cancellation_reason",
      "recent_log_summary",
      "logs_error_summary",
      "error_code",
      "error_message"
    ],
    "cancelled_required_fields": [
      "error_or_cancellation_reason",
      "recent_log_summary",
      "logs_error_summary"
    ],
    "smoke_test_required_fields": [
      "smoke_test_status",
      "smoke_test_job_id",
      "generated_artifact_reference",
      "smoke_test_error"
    ]
  },
  "recovery": {
    "failed": [
      "Do not retry automatically.",
      "Report error_code, error_message, recent_log_summary, dataset_hash, and profile_hash.",
      "Recommend the smallest useful next action before asking for a new explicit training request."
    ],
    "cancelled": [
      "Confirm cancelled terminal status with lora_train_job_status.",
      "Read bounded logs with lora_train_logs.",
      "Require a new explicit user training request before any restart."
    ],
    "stale_hash": [
      "Stop before lora_train_start.",
      "Inspect the dataset/profile and rerun lora_training_decision_preflight with current hashes.",
      "Emit a new pre-start report and wait for explicit approval again."
    ],
    "smoke_test_failed": [
      "Report training completion separately from smoke-test failure.",
      "Keep output_path and registered_lora_name visible.",
      "Recommend generation parameter or resource checks before another smoke test."
    ]
  }
}
```
