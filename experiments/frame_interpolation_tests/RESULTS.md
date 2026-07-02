# Frame interpolation tests — Mac / Apple Silicon

Source video: `/Users/tf00185088/comfyui/output/video/mac_i2v_best_quality_512_cfg15_steps10_asuka_00001_.mp4`

## Test 0 — ComfyUI built-in FrameInterpolationModelLoader

Workflow: `builtin_film_x2_32fps_api.json`

Result: failed at `FrameInterpolationModelLoader`.

Error:

```text
Cannot use weights_only=True with TorchScript archives passed to torch.load
```

Interpretation: built-in ComfyUI interpolation nodes are present and detect `film_net_fp16.pt`, but this PyTorch/ComfyUI version cannot load this TorchScript model through `torch.load(weights_only=True)`. This is a loader/model-format blocker, not a video blocker.

## Test 1 — direct FILM TorchScript x2, output 32fps

Output: `/Users/tf00185088/Desktop/ai-drawing/experiments/frame_interpolation_tests/mac_i2v_best_quality_FILM_x2_32fps.mp4`

Input: 81 frames @ 16fps, 5.0625s.
Output: 161 frames @ 32fps, 5.031s.

This preserves near-original duration and is the mathematically correct x2 interpolation target.

## Test 2 — direct FILM TorchScript x2, output 30fps

Output: `/Users/tf00185088/Desktop/ai-drawing/experiments/frame_interpolation_tests/mac_i2v_best_quality_FILM_x2_30fps.mp4`

Input: 81 frames @ 16fps, 5.0625s.
Output: 161 frames @ 30fps, 5.366s.

This hits a nominal 30fps target but slightly slows the clip because 161 frames at 30fps is longer than source duration.

## Notes from web research

- ComfyUI-Frame-Interpolation on Mac/MPS commonly hits `MPS: Unsupported Border padding mode` for RIFE/FILM.
- RIFE Python implementations can sometimes be patched from `padding_mode="border"` to `reflection` or `zeros`.
- FILM TorchScript embeds the unsupported mode in the serialized graph for some models; direct TorchScript MPS works with this local `film_net_fp16.pt` model, while ComfyUI built-in loader fails earlier due `weights_only=True`.

## Next single-factor tests

1. x2 same frames, fps 32 vs 30 — already produced.
2. x4 to 64fps for near-60 target, then encode as 60fps and 64fps variants.
3. Compare direct FILM vs patched RIFE if a Mac-compatible RIFE node/model can be set up.

## Test 3 — direct FILM TorchScript x4, output 60fps and 62fps

Script: `film_interpolate_multi.py`

Input: 81 frames @ 16fps, 5.0625s.
Generated frames: `(81 - 1) * 4 + 1 = 321`.

### x4 @ 60fps

Output: `/Users/tf00185088/Desktop/ai-drawing/experiments/frame_interpolation_tests/mac_i2v_best_quality_FILM_x4_60fps.mp4`

ffprobe:

```text
512x512, 321 frames, 60fps, duration 5.350s, h264
```

### x4 @ 62fps

Output: `/Users/tf00185088/Desktop/ai-drawing/experiments/frame_interpolation_tests/mac_i2v_best_quality_FILM_x4_62fps.mp4`

ffprobe:

```text
512x512, 321 frames, 62fps, duration 5.177s, h264
```

Interpretation: Since the source is 16fps, exact duration preservation would be 64fps for x4. 62fps is closer to original timing than 60fps, while still near the common 60fps family.

## Mac workflow research notes for comparison

Candidate workflow family: `Fannovel16/ComfyUI-Frame-Interpolation`.

- Provides ComfyUI VFI nodes: RIFE 4.0–4.9, FILM, GMFSS, IFRNet, M2M, AMT, STMFNet, FLAVR, MoMo.
- Non-CUDA support is documented as experimental via Taichi backend:
  - install Taichi
  - set `config.yaml`: `ops_backend: taichi`
- Mac/MPS known blocker from issue #47 / PyTorch forum:
  - `RuntimeError: MPS: Unsupported Border padding mode`
- Reported RIFE workaround:
  - edit RIFE `warp()` implementation from `padding_mode="border"` to `padding_mode="reflection"` or `"zeros"`.
- FILM in ComfyUI nodes can fail because the unsupported padding mode is embedded inside TorchScript or, in built-in ComfyUI loader, because TorchScript archives are loaded through `torch.load(weights_only=True)`.

Comparison expectation:

- Direct Python FILM: already verified on this Mac, stable, not a ComfyUI graph, likely smooth/conservative but can soften details/ghost on large motion.
- Patched RIFE workflow: likely sharper/faster and ComfyUI-native, but requires installing/patching custom nodes and validating MPS/Taichi behavior locally.
