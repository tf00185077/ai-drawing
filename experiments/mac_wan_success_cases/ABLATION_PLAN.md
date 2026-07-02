# Mac Wan2.2 I2V baseline ablation plan

Baseline source: `video_wan2_2_14B_i2v_mac.json` from Digital Life Innovator Mac workflow.
Baseline artifact: `/Users/tf00185088/comfyui/output/video/mac_i2v_baseline_asuka_faithful_00001_.mp4`.
Input: `/Users/tf00185088/comfyui/input/mac_i2v_asuka_keyframe_01.png` from approved gallery keyframe 01.

## Principle

Only change one conceptual factor per run. After each terminal run, compare against baseline using:

- contact sheet: structure / identity / motion coverage / artifacts
- ffprobe: frame count, duration, resolution, codec, file size
- prompt/workflow diff: exact modified node(s)

## Node influence map

| Area | Node(s) | Variables | Expected effect |
|---|---|---|---|
| Speed/motion prior | `LoraLoaderModelOnly` high/low | enabled, strength | Lightning LoRA likely enables 4-step viability and motion strength; removing may reduce motion or break low-step quality |
| Schedule split | `KSamplerAdvanced` x2 | start/end steps, high/low boundary | Controls denoising responsibility between high-noise and low-noise experts; affects structure vs detail stability |
| Sampling budget | `KSamplerAdvanced.steps` | 6 → 8/10/12 | More steps may improve detail/stability but slower; with Lightning, too many may overcook |
| Sampler | `sampler_name`, `scheduler` | euler/simple vs others | Changes motion texture, stability, speed; Mac-safe candidates only after baseline variants |
| CFG | `cfg` | 1.0 → 1.5/2.0 | Prompt adherence vs image preservation/artifacts |
| Resolution | `WanImageToVideo.width/height` | 480² → 640×480 / 512² / 320×320 | Quality/detail vs memory/time; key for Mac performance envelope |
| Frame length | `WanImageToVideo.length` | 81 → 41/121 | Duration and temporal coherence; longer risks drift/memory |
| Prompt | `CLIPTextEncode` positive/negative | motion/camera terms | Affects movement, identity drift, background changes |
| Input image preprocessing | external / image crop | square crop vs aspect-preserve | Affects composition and distortion |
| Model quant | `UnetLoaderGGUF` | Q4_K_S vs Q4_K_M | Quality/speed/memory tradeoff; Q4_K_M already installed |
| VAE | `VAELoader` | bf16 Wan2.1 vs local alternatives | Decode color/detail/stability; test only after sampler basics |

## Run order

1. V1 no-Lightning LoRA — submitted `55f10ae9-0bab-48d8-9fcf-c91d9acae4d0`.
2. V2 Lightning half strength: high/low LoRA strength 1.0 → 0.5.
3. V3 Lightning stronger asymmetry: high 0.5 / low 1.0 or high 1.0 / low 0.5 depending V1/V2.
4. V4 steps 8 or 10, preserve same split ratio.
5. V5 CFG 1.5.
6. V6 length 41 frames for faster iteration / motion diagnosis.
7. V7 resolution 640×480 or 512×512 if memory permits.
8. V8 model quant Q4_K_M using existing local files.

Only proceed to next after terminal output for current run is collected.
