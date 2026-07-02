# Any-test v2 / Qwen control pose research

Date: 2026-06-26

## T4 Anima any-test-like-v2 smoke test

Goal: abandon the legacy Anima pose-1 route for now and test Anima-Base v1.0 `any-test-like-v2` as a generic structure-control route.

### Installed/used resources

Downloaded:

```text
/Users/tf00185088/comfyui/models/controlnet/anima-lllite-any-test-like-v2.safetensors
```

Generated lineart-like control image from the earlier pose skeleton:

```text
/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-26/anima_anytest_pose_lineart_black_on_white_832x1216.png
```

### T4 workflow

```text
UNETLoader(anima_baseV10.safetensors)
CLIPLoader(anima_baseV10_txt.safetensors, type=qwen_image)
VAELoader(qwen_image_vae.safetensors)
EmptySD3LatentImage(832x1216)
LoraLoaderModelOnly chain:
  anima-highres-aesthetic-boost.safetensors @ 0.7
  Niji Reol v1 EP11.safetensors @ 0.8
  AnimaNSS4RE.safetensors @ 0.65
LoadImage(anima_anytest_pose_lineart_black_on_white_832x1216.png)
AnimaLLLiteApply(lllite_name=anima-lllite-any-test-like-v2.safetensors, strength=1.0)
KSampler(seed=2606269401, steps=26, cfg=5.0, sampler=er_sde, scheduler=simple, denoise=1.0)
VAEDecode
SaveImage
```

Job:

```text
job_id: 7f82b8ff-c176-457d-a7d7-c6fa0504b874
image_id: 713
output: /Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-26/anima_lllite_anytest_v2_T4_lineart_pose_s10_00001_7f82b8ff_0.png
contact: /Users/tf00185088/Desktop/ai-drawing/experiments/controlnet_pose_anima_research/anima_anytest_v2_T4_contact.jpg
```

No visual judgement recorded here per CTY preference.

---

## Research: Qwen Image Union Control

Source: `InstantX/Qwen-Image-ControlNet-Union` and ComfyUI workflow pages.

Key facts:

- Base model: `Qwen/Qwen-Image`.
- Unified ControlNet supporting:
  - canny
  - soft edge
  - depth
  - pose
- Model card says it was trained from scratch for 50K steps on 10M general/human images at 1328x1328.
- Inference uses `controlnet_conditioning_scale`.
- ComfyUI pages describe it as usable for pose / composition control.

Implication for pose:

- This is a real pose-control route, but for **Qwen-Image**, not directly for Anima.
- It may be useful as a first-stage pose/composition generator, followed by Anima img2img/style transfer.

---

## Research: Qwen Image DiffSynth Control

ComfyUI/Comfy docs distinguish two Qwen control families:

1. `Qwen-Image DiffSynth ControlNets Model Patch`
   - supports canny
   - depth
   - inpaint

2. `Qwen-Image Union DiffSynth LoRA`
   - supports lineart
   - softedge
   - normal
   - openpose / pose

Implication for pose:

- For pose, the relevant DiffSynth route appears to be **Union DiffSynth LoRA**, not the model-patch canny/depth/inpaint set.
- This is again Qwen-Image family control, not Anima-native.

---

## Research: Qwen Image / Anima Image Edit for pose

Found a ComfyUI issue asking whether `Qwen Image Edit + ControlNet OpenPose` can be combined. It was closed stale/not-planned without a maintainer solution.

Search results also show community interest in:

- Qwen-Image-Edit 2509 pose transfer
- Qwen-Image-Edit 2511 AnyPose
- Qwen Edit + pose reference / anime stylize workflows

Implication:

- Qwen Image Edit may be useful for pose transfer, but the official ComfyUI issue does not confirm a native `Qwen Image Edit + OpenPose ControlNet` workflow.
- It should be treated as a separate image-edit/model route, not assumed to combine cleanly with Anima or Qwen ControlNet without a known workflow.

---

## Practical route candidates for CTY

1. Anima native-ish generic control:
   - `anima-lllite-any-test-like-v2.safetensors`
   - use lineart/scribble/grayscale structure control
   - T4 smoke test completed

2. Qwen-Image pose-first route:
   - `InstantX/Qwen-Image-ControlNet-Union` or Qwen DiffSynth Union LoRA
   - generate/control pose in Qwen-Image
   - optionally pass output to Anima img2img/style transfer

3. Qwen Image Edit pose-transfer route:
   - investigate concrete AnyPose / Qwen-Image-Edit workflow if CTY wants edit-based pose transfer
   - not yet locally verified

4. SDXL/OpenPose route:
   - mature pose control
   - optionally use as first-stage pose/composition image, then Anima refinement
