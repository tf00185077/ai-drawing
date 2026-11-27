# Project Memory

- [Compute target and resource scope](compute-target-and-resource-scope.md) — before judging where a job or training ran, or what models a worker has.
- [Explicit LoRA list](explicit-lora-list-semantics.md) — before building or forwarding a `loras` list.
- [Model family loaders](model-family-loader-compatibility.md) — before matching models, LoRAs and workflows.
- [Revision lineage](ordinary-generation-revision-lineage.md) — before revising a result.
- [Runtime source contract](runtime-source-contract-verification.md) — before claiming the running Backend implements the current checkout's revision or other contract.
- [Backend startup schema](backend-startup-additive-schema.md) — before relaunching current Backend source against an older SQLite database or reporting the runtime's database changes.
- [Style preset replay](style-preset-saved-graph-replay.md) — before composing, replaying or editing style presets.
- [Video frames and FILM](video-frame-and-film-rules.md) — before touching image-to-video or interpolation.
- [Anima training components](anima-training-component-readiness.md) — before an Anima LoRA run.
- [Media identities and locators](gallery-artifact-identity-and-locators.md) — before assuming every completed image has a canonical artifact ID or usable Gallery path/URL.
- [Gallery seed precision](gallery-seed-precision.md) — when reading or showing seeds.
- [Gallery routing](gallery-document-asset-routing.md) — before changing the Vite proxy.
- [Frontend cache isolation](frontend-shared-cache-isolation.md) — when running frontend tests in parallel worktrees.
- [Worker tests off Windows](windows-worker-offline-test-limits.md) — before exercising worker process creation on macOS or Linux.
- [Worker PowerShell control](worker-powershell-control.md) — before running, updating or redeploying the Windows worker.
- [Discord bot config and ledger](discord-bot-config-and-ledger.md) — before starting or reconfiguring the Discord bot.
- [Paperclip question cards](native-interaction-card-lineage.md) — before asking CTY several questions in Paperclip.
