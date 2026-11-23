# Project Memory

Durable facts for future agents. No logs or incident history.

- [Compute target and resource scope](compute-target-and-resource-scope.md) — generation target vs training subprocess vs resource listing scope
- [Explicit LoRA list semantics](explicit-lora-list-semantics.md) — omitted vs empty list, loader bypass, late capacity check
- [Anima training components](anima-training-component-readiness.md) — Anima needs a VAE despite optional schema
- [Revision lineage](ordinary-generation-revision-lineage.md) — rerun is not a revision; use revision context fields
- [Gallery seed precision](gallery-seed-precision.md) — seeds exceed JS safe integers
- [Gallery routing](gallery-document-asset-routing.md) — Vite proxy must not catch the /gallery page
- [Frontend cache isolation](frontend-shared-cache-isolation.md) — Vitest cache leaks via shared node_modules
- [Worker offline tests](windows-worker-offline-test-limits.md) — CREATE_NO_WINDOW missing off Windows
- [Paperclip card lineage](native-interaction-card-lineage.md) — a new question card expires older pending ones
