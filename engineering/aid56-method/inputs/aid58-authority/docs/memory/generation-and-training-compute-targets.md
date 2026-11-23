---
name: generation-and-training-compute-targets
description: Generation target selection and the trainer process location are separate; a Worker smoke image does not prove Windows training.
metadata:
  type: project
---

## Context

In the source inspected on 2026-10-22, `GenerateRequest.execution_target` accepts `local` or `worker` and defaults to `local`. LoRA training launches the persisted argv through `subprocess.Popen` in the Backend process environment. The training smoke-test request separately selects a generation target. Its response records `submitted` and a generation job ID, with `artifact=None`.

## Why

A successful Worker generation or smoke submission cannot establish that training ran on Windows, that a new model is valid, or that the test image was retrieved. Confusing these paths can also silently select the Backend host when the project intends Windows compute.

## How to apply

Before execution, verify the deployed trainer location and approved compute route independently from generation routing. Specify the authorized generation target explicitly; do not infer it from the API default. Reconcile the training job, registered model and smoke-generation job/artifact separately. Recheck source and installed behavior when planning changes. This fact grants no compute, service, upload, spending or fallback permission; current owner authority and topic documents remain authoritative.

## Evidence

- [Generation request schema](../../backend/app/schemas/generate.py): `GenerateRequest.execution_target`.
- [Trainer implementation](../../backend/app/services/lora_trainer.py): `_run_training_subprocess` and `smoke_test_job`.
- [Training capability and acceptance limits](../training-status.md).
- [Team compute boundaries](../team/README.md#shared-operating-boundaries).
