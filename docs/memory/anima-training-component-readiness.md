---
name: anima-training-component-readiness
description: "Anima LoRA training needs a VAE although the schema marks it optional."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

The Anima recipe resolver treats the VAE path as optional and adds `--vae` only when one resolves (request value or configured default). The bundled sd-scripts Anima loader always loads a VAE, so training with no resolvable VAE fails at load time.

## Why

Schema optionality suggests the VAE can be left out; the run then fails only after it starts.

## How to apply

Before an Anima run, confirm the VAE, text encoder, tokenizer and diffusion model all resolve on the trainer host.

## Evidence

- `backend/app/services/lora_training_recipe.py`
- `backend/app/services/lora_trainer.py`
