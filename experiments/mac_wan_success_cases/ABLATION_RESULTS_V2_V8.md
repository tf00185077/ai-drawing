# Mac Wan2.2 I2V V2–V8 ablation results

Baseline: `mac_i2v_baseline_asuka_faithful_00001_.mp4` — Lightning LoRA strength 1.0, 480×480, 81 frames, 6 steps, CFG 1.0, Q4_K_S.

| ID | Change | Status | Duration | Output |
|---|---|---|---:|---|
| V2 | Lightning LoRA strength 1.0 → 0.5 | success | 5.062500 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v2_lora_half_asuka_00001_.mp4` |
| V3 | no-Lightning LoRA + steps 6 → 12 | success | 5.062500 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v3_no_lora_steps12_asuka_00001_.mp4` |
| V4 | baseline Lightning + steps 6 → 10 | success | 5.062500 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v4_lora_steps10_asuka_00001_.mp4` |
| V5 | baseline Lightning + CFG 1.0 → 1.5 | success | 5.062500 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v5_cfg15_asuka_00001_.mp4` |
| V6 | baseline Lightning + resolution 480×480 → 512×512 | success | 5.062012 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v6_512x512_asuka_00001_.mp4` |
| V7 | baseline Lightning + length 81 → 41 frames | success | 2.562500 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v7_41frames_asuka_00001_.mp4` |
| V8 | baseline Lightning + GGUF Q4_K_S → Q4_K_M | success | 5.062500 | `/Users/tf00185088/comfyui/output/video/mac_i2v_v8_q4km_asuka_00001_.mp4` |

## V2 — Lightning LoRA strength 1.0 → 0.5
- prompt_id: `1cee9c3a-717f-4de5-904d-d35ac0e54020`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v2_lora_half_strength.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v2_lora_half_asuka_00001_.mp4`
- contact: `/tmp/v2__half_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 480,
      "height": 480,
      "r_frame_rate": "16/1",
      "nb_frames": "81"
    }
  ],
  "format": {
    "duration": "5.062500",
    "size": "1161577"
  }
}
```

## V3 — no-Lightning LoRA + steps 6 → 12
- prompt_id: `3352cc86-5932-460d-bfea-b5c6b0ab34e4`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v3_no_lora_steps12.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v3_no_lora_steps12_asuka_00001_.mp4`
- contact: `/tmp/v3_eps12_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 480,
      "height": 480,
      "r_frame_rate": "16/1",
      "nb_frames": "81"
    }
  ],
  "format": {
    "duration": "5.062500",
    "size": "1775764"
  }
}
```

## V4 — baseline Lightning + steps 6 → 10
- prompt_id: `e07cafc8-eda5-47e6-9d88-ae3e978a2594`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v4_lora_steps10.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v4_lora_steps10_asuka_00001_.mp4`
- contact: `/tmp/v4_eps10_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 480,
      "height": 480,
      "r_frame_rate": "16/1",
      "nb_frames": "81"
    }
  ],
  "format": {
    "duration": "5.062500",
    "size": "924610"
  }
}
```

## V5 — baseline Lightning + CFG 1.0 → 1.5
- prompt_id: `9d64d6af-ca28-4d51-b9a5-9807730fc854`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v5_cfg15.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v5_cfg15_asuka_00001_.mp4`
- contact: `/tmp/v5_cfg15_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 480,
      "height": 480,
      "r_frame_rate": "16/1",
      "nb_frames": "81"
    }
  ],
  "format": {
    "duration": "5.062500",
    "size": "930231"
  }
}
```

## V6 — baseline Lightning + resolution 480×480 → 512×512
- prompt_id: `e826505b-d5fc-4ab9-9d4c-4cdcf18ca21b`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v6_512x512.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v6_512x512_asuka_00001_.mp4`
- contact: `/tmp/v6_2x512_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 512,
      "height": 512,
      "r_frame_rate": "16/1",
      "nb_frames": "81"
    }
  ],
  "format": {
    "duration": "5.062012",
    "size": "966963"
  }
}
```

## V7 — baseline Lightning + length 81 → 41 frames
- prompt_id: `23b3b187-d011-4ffa-9e93-1a7d49132a0d`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v7_41frames.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v7_41frames_asuka_00001_.mp4`
- contact: `/tmp/v7_rames_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 480,
      "height": 480,
      "r_frame_rate": "16/1",
      "nb_frames": "41"
    }
  ],
  "format": {
    "duration": "2.562500",
    "size": "458189"
  }
}
```

## V8 — baseline Lightning + GGUF Q4_K_S → Q4_K_M
- prompt_id: `a0a1d5c4-2ebf-425b-a212-6b22f615d975`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v8_q4km.json`
- video: `/Users/tf00185088/comfyui/output/video/mac_i2v_v8_q4km_asuka_00001_.mp4`
- contact: `/tmp/v8__q4km_asuka_00001__contact.jpg`
- ffprobe:
```json
{
  "programs": [],
  "stream_groups": [],
  "streams": [
    {
      "codec_name": "h264",
      "width": 480,
      "height": 480,
      "r_frame_rate": "16/1",
      "nb_frames": "81"
    }
  ],
  "format": {
    "duration": "5.062500",
    "size": "873094"
  }
}
```
