---
name: anima-training-component-readiness
description: "Trace the optional Anima VAE field through effective defaults and the native loader before treating omission as component-free training."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

The inspected Anima resolver accepts a missing effective VAE path and adds `--vae` only when resolved. The bundled native loader passes `args.vae` into the Qwen Image VAE loader and then safetensors loading. No usable VAE-free fallback was established when both supplied and configured paths are absent; omitting the public field can still select a configured VAE.

## Why

Schema optionality does not establish that the execution path can omit a required model component.

## How to apply

For an authorized Anima assessment, trace supplied and configured values through argv to the current native loader. Validate VAE, text encoder, tokenizer and diffusion-model compatibility on the approved trainer host. Keep file presence, successful loading and completed training as separate evidence. Route a missing guard through engineering and independent QA rather than using a training trial or download to infer compatibility.

## Evidence

- [Anima resolver and argv construction](../../backend/app/services/lora_trainer.py).
- [Native Anima loader](../../sd-scripts/library/anima_train_utils.py) and [Qwen Image VAE loader](../../sd-scripts/library/qwen_image_autoencoder_kl.py).
- [Training authority](../training-status.md) — integration support is not end-to-end acceptance.
