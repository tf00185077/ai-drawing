---
name: anima-training-component-readiness
description: "Anima LoRA training needs a VAE although the schema marks it optional."
metadata:
  type: project
  curated_on: "2026-11-25"
---

## Context

The Anima recipe resolver treats the VAE path as optional; the runner adds `--vae` only when one resolves from the request or configured default. The project's trainer documentation requires a VAE for the sd-scripts Anima entry point.

## Why

An optional request field does not establish that the documented trainer has all required components.

## How to apply

Before an Anima run, confirm the VAE, text encoder, tokenizer and diffusion model all resolve on the trainer host.

## Evidence

- [Recipe resolver](../../backend/app/services/lora_training_recipe.py) — optional Anima VAE resolution.
- [Training runner](../../backend/app/services/lora_trainer.py) — conditional `--vae` argument.
- [Supported training models](../lora-training.md#supported-models) — Anima requires a VAE.
