# Application workflows

Each JSON stores ComfyUI nodes, connections and inputs. Resource filenames, dimensions, sampler settings and seeds are in the linked JSON; do not maintain a second parameter table here. Style recipes and their saved workflows are separate: [style presets](../../style_presets/README.md).

**Output effects: Needs re-verification (需要再驗證).** Static graph inspection is not execution or aesthetic acceptance. Historical “verified” metadata and job IDs are provenance, not current validation.

## Select and execute

- Discover exposed templates with `list_available_resources` or Backend `GET /api/workflow-catalog/generation-forms`.
- `generate_image(template=<id>, ...)` applies parameters to a template. Custom-workflow interfaces accept a full graph. Both queue generation and require authorization.
- Check model/LoRA architecture, node packages and input mapping. Pose, subject, mask, first/last frame and audio inputs are not interchangeable. Stored input filenames may be placeholders.
- `LoraLoader` patches model and CLIP; `LoraLoaderModelOnly` patches only the model. These are inference workflows, not training.
- A checkpoint loader is not compatible with every model family. Split Anima/Qwen/Wan models require their loader/encoder/latent interfaces.

## Image workflows

| Graph | Purpose / required input |
|---|---|
| [default](default.json) | Checkpoint text-to-image; checkpoint-provided CLIP/VAE |
| [default_lora](default_lora.json) | Checkpoint text-to-image plus compatible LoRA |
| [anima](anima.json) | Anima text-to-image with separate diffusion model, Qwen encoder and VAE |
| [Anima model-only LoRA](gen_txt2img_anima_lora_model_only.json) | Text-to-image with one model-only LoRA |
| [Anima multiple LoRAs](gen_txt2img_anima_lora_model_only_multi_lora.json) | Text-to-image with chained model-only LoRAs |
| [Anima img2img](gen_img2img_anima_lora_model_only_image_ref.json) | Subject image encoded as initial latent; model-only LoRAs |
| [Anima masked repaint](gen_inpaint_anima_lora_model_only_multi_lora_image_ref_mask.json) | Subject + mask; composite repainted region over original |
| [ControlNet pose](controlnet_pose.json) | Subject + pose image; DWPose preprocessing and compatible ControlNet |
| [img2img LoRA pose](img2img_lora_pose.json) | Subject + pose image; checkpoint LoRA and ControlNet |
| [txt2img LoRA pose](txt2img_lora_pose.json) | Pose image; empty initial latent, checkpoint LoRA and ControlNet |
| [inpaint](inpaint.json) | Subject + mask; checkpoint VAE inpaint encoding |
| [Qwen pose-inspired generation](gen_txt2img_qwen_image_controlnet_pose_lora_model_only_multi_lora_image_ref.json) | Pose reference, Qwen Image GGUF, Union/DiffSynth and Lightning LoRAs; not precise pose-transfer acceptance |
| [Qwen pose transfer](gen_img2img_qwen_image_edit_lora_model_only_multi_lora_pose_transfer_image_ref_pose_ref.json) | Subject + pose reference; Qwen Image Edit GGUF, AnyPose base/helper and Lightning LoRAs |

## Video workflows

| Graph | Purpose / required input |
|---|---|
| [Wan first frame](gen_img2video_wan_first_frame.json) | First-frame image; Wan TI2V model, UMT5 encoder and Wan VAE |
| [Wan first/last frame](gen_img2video_wan_first_frame_last_frame.json) | Two keyframes; high/low GGUF models, LightX2V LoRAs and Wan conditioning |
| [Wan multiple keyframes](gen_img2video_wan_5keyframe_single_workflow.json) | Image batch, WanDancer nodes, high/low GGUF models and timing audio |
| [Discord AnimeGen](discord_animegen_i2v_fixed.json) | Stored image-to-video graph; GGUF high/low models and Lightning LoRAs |
| [Discord Wan Animate](discord_wan22_animate_fixed.json) | Image/video reference, vision encoder, pose preprocessing and Wan Animate GGUF |
| [Discord MiniMax H3](discord_minimax_h3_i2v_fixed.json) | Stored H3 ComfyUI graph; not the current Discord H3 runtime procedure |

The three `discord_*_fixed` graphs lack catalog metadata and are not automatically exposed in the ordinary workflow selector. Do not add metadata merely to make them appear. The current H3 command uses an Argus MLX runtime, not this stored ComfyUI graph.

## Resource checks

Read loader inputs in the chosen graph for exact model, encoder, VAE, LoRA, ControlNet and input filenames; neighboring `.meta.json` files describe catalog intent. Missing version/source/license or node-package information remains unverified. Confirm availability on the target before execution; filenames and historical paths do not prove installation.
