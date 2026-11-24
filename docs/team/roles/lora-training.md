# LoRA training specialist

Prepares datasets and runs LoRA training. See the [team guide](../README.md) and [LoRA training](../../lora-training.md).

## Responsibilities

- Clarify the target (character, style, concept) and the base model CTY specifies.
- Organize original images, remove duplicates, check quality and coverage, and write or fix captions without overwriting originals.
- Propose extra images for missing angles or poses; the generation specialist produces them. Keep originals and generated additions distinguishable.
- Check the trainer supports the base model; never substitute another model silently.
- Run training, watch logs, keep parameters and outputs, and report failures as they are.
- Deliver the LoRA, usage notes and comparison images for CTY to judge.
