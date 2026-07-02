# SVI official/Kijai baseline systematic tests — 2026-06-24

## B0 exact official/Kijai FP8 baseline

- Workflow: official `SVI-Wan22-1210-10-Clips.json`, truncated to first 2 clips for local runtime.
- Resources: exact KJ FP8 scaled high/low, bf16 UMT5, Wan2_1 bf16 VAE, SVI + LightX2V LoRAs.
- Prompt id: `28b8b950-2459-47a6-82f0-b3609e1a2356`
- Result: failed at `WanVideoModelLoader`.
- Error: `Trying to convert Float8_e4m3fn to the MPS backend but it does not have support for that dtype.`
- Interpretation: exact community FP8 baseline is CUDA/FP8-oriented and not Apple MPS compatible.

## B0a — one-variable change: FP8 high/low -> Q4 GGUF high/low

- Workflow: same official/Kijai route as B0.
- Only intended variable: `WanVideoModelLoader.model` changed to:
  - `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf`
  - `Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf`
  - model quantization set to `disabled`, base precision `bf16`.
- Prompt id: `104982a9-e093-4aaf-874b-21da5774c552`
- Result: failed during LoRA application.
- Error: `Trying to convert Float8_e4m3fn to the MPS backend but it does not have support for that dtype.`
- Evidence: log shows model variant detected as `i2v_14B_2.2`, loading Q4 GGUF succeeds far enough to begin `Merging LoRA to the model...`, then `stochastic_rounding_fp8` fails under MPS.
- Interpretation: after fixing model dtype, LoRA merge path still triggers fp8 rounding on MPS. Next one-variable test should keep Q4 GGUF and LoRAs but set `merge_loras=False` on WanVideoLoraSelect nodes.

## B0b — one-variable change from B0a: LoRA `merge_loras=False`, `low_mem_load=True`

- Prompt id: `604223ef-ddb9-45dc-8922-c6ac7cc5b2d0`
- Result: failed.
- Error excerpt:
```json
{
  "prompt_id": "604223ef-ddb9-45dc-8922-c6ac7cc5b2d0",
  "node_id": "27",
  "node_type": "WanVideoSampler",
  "executed": [
    "39",
    "35",
    "107",
    "38",
    "22",
    "92",
    "194",
    "68",
    "145",
    "140",
    "184",
    "163",
    "211",
    "89",
    "11",
    "16",
    "162",
    "56",
    "195",
    "67"
  ],
  "exception_message": "Invalid buffer size: 79.96 GiB\n",
  "exception_type": "RuntimeError",
  "traceback": [
    "  File \"/Users/tf00185088/comfyui/execution.py\", line 542, in execute\n    output_data, output_ui, has_subgraph, has_pending_tasks = await get_output_data(prompt_id, unique_id, obj, input_data_all, execution_block_cb=execution_block_cb, pre_execute_cb=pre_execute_cb, v3_data=v3_data)\n                                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/Users/tf00185088/comfyui/execution.py\", line 341, in get_output_data\n    return_values = await _async_map_node_over_list(prompt_id, unique_id, obj, input_data_all, obj.FUNCTION, allow_interrupt=True, execution_block_cb=execution_block_cb, pre_execute_cb=pre_execute_cb, v3_data=v3_data)\n                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/Users/tf00185088/comfyui/execution.py\", line 315, in _async_map_node_over_list\n    await process_inputs(input_dict, i)\n",
    "  File \"/Users/tf00185088/comfyui/execution.py\", line 303, in process_inputs\n    result = f(**inputs)\n             ^^^^^^^^^^^\n",
    "  File \"/Users/tf00185088/comfyui/custom_nodes/ComfyUI-WanVideoWrapper/nodes_sampler.py\", line 2498, in process\n    noise_pred, noise_pred_ovi, self.cache_state = predict_with_cfg(\n                                                   ^^^^^^^^^^^^^^^^^\n",
    "  File \"/Users/tf00185088/comfyui/custom_nodes/ComfyUI-WanVideoWrapper/nodes_sampler.py\", line 1671, in predict_with_cfg\n    raise e\n",
    "  File \"/Users/tf00185088/comfyui/custom_nodes/ComfyUI-WanVideoWrapper/nodes_sampler.py\", line 1518, in predict_with_cfg\n    noise_pred_cond, noise_pred_ovi, cache_state_cond = transformer(\n                                                        ^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/nn/modules/module.py\", line 1778, in _wrapped_call_impl\n    return self._call_impl(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/nn/modules/module.py\", line 1789, in _call_impl\n    return forward_call(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/Users/tf00185088/comfyui/custom_nodes/ComfyUI-WanVideoWrapper/wanvideo/modules/model.py\", line 3274, in forward\n    x, x_ip, lynx_ref_feature, x_ovi = block(x, x_ip=x_ip, lynx_ref_feature=lynx_ref_feature, x_ovi=x_ovi, x_onetoall_ref=x_onetoall_ref, onetoall_freqs=onetoall_freqs, attention_mode_override=attention_mode, **kwargs)\n                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/_dynamo/eval_frame.py\", line 473, in __call__\n    return super().__call__(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/nn/modules/module.py\", line 1778, in _wrapped_call_impl\n    return self._call_impl(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/nn/modules/module.py\", line 1789, in _call_impl\n    return forward_call(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/_dynamo/eval_frame.py\", line 1047, in compile_wrapper\n    result = fn(*args, **kwargs)\n             ^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/nn/modules/module.py\", line 1778, in _wrapped_call_impl\n    return self._call_impl(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/nn/modules/module.py\", line 1789, in _call_impl\n    return forward_call(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/Users/tf00185088/comfyui/custom_nodes/ComfyUI-WanVideoWrapper/wanvideo/modules/model.py\", line 1002, in forward\n    def forward(\n",
    "  File \"/opt/homebrew/lib/python3.11/site-packages/torch/_dynamo/eval_frame.py\", line 1298, in _fn\n    return fn(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^\n",
    "  File \"/op
```

## B0c — one-variable change from B0b: remove `compile_args`

- Prompt id: `4d065c5c-52ba-446f-b452-71b7811532d3`
- Result: failed.
- Error summary:
```json
{
  "node_id": "27",
  "node_type": "WanVideoSampler",
  "exception_type": "RuntimeError",
  "exception_message": "Invalid buffer size: 79.96 GiB\n"
}
```

## B0d — one-variable change from B0c: frame count 81 -> 41

- Prompt id: `052c65e8-cda1-4ae4-96bd-5d523bfc889c`
- Result: ComfyUI process aborted / exited with code 134 during run; API became `Connection refused`.
- Interpretation: reducing frames alone from 81 to 41 is not sufficient for this MPS path at 832×480. The next single-variable test should keep B0d's 41-frame settings and reduce spatial resolution, because attention memory still exceeds what the local stack can survive.

## B0e — one-variable change from B0d: resolution 832x480 -> 480x272

- Prompt id: `7fcba344-5600-420f-abc7-74f9ea92d547`
- Result: failed in `WanVideoSampler`.
- Error: `Expected all tensors to be on the same device, but found at least two devices, mps:0 and cpu!`
- Interpretation: lowering resolution avoided the prior huge-buffer crash, but exposed a CPU/MPS device mismatch, likely from the LoRA no-merge + low-memory/offload path. Next test changes only `low_mem_load=True -> False` while keeping `merge_loras=False`.

## B0f — one-variable change from B0e: `low_mem_load=True -> False`

- Prompt id: `73255a1d-2b2f-4143-a067-d5498d5b9c90`
- Result: failed in `WanVideoSampler`.
- Error: `Expected all tensors to be on the same device, but found at least two devices, mps:0 and cpu!`
- Interpretation: `low_mem_load` was not the device-mismatch cause. Next test changes only model loader `load_device` from `offload_device` to `main_device`.

## B0g — one-variable change from B0f: `load_device=main_device`

- Prompt id: `71225e6d-0fda-4f4d-b685-2d5b088a1e2c`
- Result: failed in `WanVideoSampler`.
- Error: `Expected all tensors to be on the same device, but found at least two devices, mps:0 and cpu!`
- Interpretation: model loader `load_device` is not the device-mismatch cause. Next test removes only LightX2V from the LoRA chain while keeping SVI LoRA.

## B0h — one-variable change from B0g: remove LightX2V, keep SVI LoRA

- Prompt id: `e137a869-2821-4496-bf9e-bb8c1a5e3acb`
- Result: failed in `WanVideoSampler`.
- Error: `Expected all tensors to be on the same device, but found at least two devices, mps:0 and cpu!`
- Interpretation: LightX2V is not the device-mismatch cause. With only SVI high LoRA executed before the high sampler, the same mismatch remains. Next test removes SVI LoRA entirely to isolate LoRA path vs base Q4/VACE route.

## B0i — one-variable change from B0h: remove all LoRA

- Prompt id: `509acdcf-6509-439d-9892-4d6cc7d5874d`
- Result: failed in `WanVideoSampler`.
- Error: `Expected all tensors to be on the same device, but found at least two devices, mps:0 and cpu!`
- Interpretation: LoRA is not the only cause; the no-LoRA Q4 graph still fails with `load_device=main_device`. Next test changes only model loader back to `offload_device` under the no-LoRA graph.
