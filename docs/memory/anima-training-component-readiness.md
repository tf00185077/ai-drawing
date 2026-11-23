---
name: anima-training-component-readiness
description: Anima LoRA training needs a VAE; the schema marks it optional but there is no VAE-free path.
metadata:
  type: project
---

The Anima recipe resolver treats the VAE path as optional and adds `--vae` only when one resolves (request value or configured default). The bundled sd-scripts Anima loader always loads a VAE, so training with no resolvable VAE fails at load time.

**How to apply:** before an Anima run, confirm the VAE, text encoder, tokenizer and diffusion model all resolve on the trainer host. Schema optionality is not evidence a component can be omitted.

Source: `backend/app/services/lora_training_recipe.py`, `backend/app/services/lora_trainer.py`.
