# Operating policy

Adopted by the owner on 2026-11-23. This is the single source for what agents may do. Other documents link here instead of restating rules.

## Allowed by default

| Action | Notes |
|---|---|
| Read source, docs, data, logs and API state | — |
| Run tests, type checks and builds | — |
| Generate images and videos on local ComfyUI | — |
| Dispatch generation to a LAN worker | — |
| Restart ComfyUI (`comfyui_admin(action=restart)`) | — |
| Install custom nodes (`comfyui_admin(action=install_node)`) | — |
| Free ComfyUI memory (`comfyui_admin(action=free_memory)`) | — |
| Cancel jobs, including jobs submitted by others | — |
| Download models and resources (`civitai_resource_acquire`, manual) | — |
| Start LoRA training runs | — |
| Edit the Prompt Library (save, archive, restore) | — |
| Save a result as a style preset | — |
| Send results to Discord | Allowlisted destinations only |
| Start/stop the stack with the launcher | — |
| Run launcher `setup` / `reconfigure` | Rewrites `.env`; copy it first to keep custom settings |
| Run remote PowerShell on a worker | — |
| Commit, merge to `main` and push | — |

## Never

- Commit secrets. Keep them in `.env` or private config and redact them in shared logs.
- Delete or overwrite models, datasets, outputs or Gallery records as cleanup.
- Expose worker control endpoints beyond the private LAN.

## Job handling rules

- A timeout does not prove a job failed. Query the job ID before resubmitting.
- A failed worker job is not silently retried on local ComfyUI; report it and let the caller choose.
