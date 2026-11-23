---
name: explicit-lora-list-semantics
description: LoRA list in generation requests — omitted vs explicit empty list, loader bypass, late capacity check.
metadata:
  type: project
---

- Omitting `loras` keeps the template's LoRA loaders as-is. An explicit list (including `[]`) is the complete active set.
- Entries map to LoRA loaders in workflow JSON order; unused template loaders are bypassed by reconnecting their model (and CLIP, if present) inputs.
- Too many LoRAs for the template is detected during queued compilation, after the request was already acknowledged. Follow the job ID to see that failure.

**How to apply:** preserve the omitted/empty distinction in every caller (MCP, UI, presets). Don't truncate lists silently.
