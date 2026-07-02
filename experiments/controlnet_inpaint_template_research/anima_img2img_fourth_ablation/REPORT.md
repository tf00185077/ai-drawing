# Anima img2img #4 ablation — denoise / prompt / CFG

Input image:

`/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-26/anima_lora_test_00036_e86e7595_9.png`

Contact sheet:

`/Users/tf00185088/Desktop/ai-drawing/experiments/controlnet_inpaint_template_research/anima_img2img_fourth_ablation/ablation_contact_input_v1_v4.jpg`

## Variants

All variants use:

- model: `anima_preview3Base.safetensors`
- text encoder: `qwen_3_06b_base.safetensors`
- vae: `qwen_image_vae.safetensors`
- LoRA: `posing-dynamics-anima.safetensors @ 0.65`
- sampler: `er_sde`
- scheduler: `simple`
- steps: `18`
- seed: `2606265501`
- output size: `832×1216`

| variant | change | result summary |
|---|---|---|
| V1 | denoise `0.35 → 0.55`, same prompt | Slight redraw: face/hair/details cleaned, pose/composition mostly preserved. |
| V2 | denoise `0.55 → 0.75`, same prompt | Stronger redraw of hair/face/background splashes, still keeps pose because prompt and input both reinforce same composition. |
| V3 | denoise `0.55`, stronger prompt | Prompt changes mostly affect details/background/face expression, not large pose change; denoise still anchors input strongly. |
| V4 | V3 + CFG `4.5 → 7.0` | Slightly stronger prompt adherence/contrast, but not a dramatic structural change; no clear benefit over V3 for this goal. |

## Parameter lessons

### Denoise

- `0.35`: too conservative; looks nearly unchanged.
- `0.55`: visible refinement, still composition-preserving.
- `0.75`: clear redraw but still not enough to force a new pose when the prompt says preserve framing and the input is strong.
- For obvious transformation, next test should use `0.85–0.95`, but risk losing identity/body stability.

### Prompt

The stronger prompt did not override pose much at denoise `0.55`. This means prompt wording alone is secondary when img2img latent anchor is strong.

To increase effect:

- remove or avoid terms like `preserve original full-body composition`
- use stronger transformation language:
  - `completely repainted pose`
  - `new dramatic action pose`
  - `large sweeping watercolor splash replacing the background`
- keep only safety framing terms:
  - `full body`, `head-to-toe`, `visible boots`, `no cropped feet`

### CFG

CFG `7.0` did not materially change pose/composition compared with CFG `4.5`; it mainly increases prompt pressure/contrast. On this Anima img2img setup, CFG is less important than denoise for visible change.

Recommended CFG range:

- `4.5–5.5`: safe
- `6.5–7.0`: stronger but not transformative by itself

## Next recommended sweep

If CTY wants stronger visible change while preserving full body:

1. `denoise=0.85`, strong transform prompt, CFG `5.0`
2. `denoise=0.95`, strong transform prompt, CFG `5.0`
3. `denoise=0.85`, same strong prompt, CFG `7.0`
4. Optional: add ControlNet/pose later if pose preservation/control becomes necessary.

Current conclusion: for this Anima img2img route, **denoise is the main knob**. Prompt and CFG have limited effect until denoise is high enough.
