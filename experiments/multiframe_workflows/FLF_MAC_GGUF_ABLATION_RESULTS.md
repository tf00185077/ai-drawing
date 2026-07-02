# FLF Mac GGUF 2-keyframe ablation results

Source: official Comfy Wan2.2 FLF structure adapted to local Apple/MPS-safe GGUF route.
Inputs: `flf_start_keyframe_01.png` → `flf_end_keyframe_02.png`.

| ID | Change | Status | Output |
|---|---|---|---|
| B0 | baseline FLF Mac GGUF: 512² length41 steps10 CFG1.5, keyframe_01→02 | success | `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_2kf_test_512_41f_00001_.mp4` |
| V1 | length 41→81, other settings unchanged | success | `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_v1_len81_512_00001_.mp4` |
| V2 | steps 10→6, length41 unchanged | success | `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_v2_steps6_41f_00001_.mp4` |
| V3 | CFG 1.5→1.0, length41 unchanged | success | `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_v3_cfg10_41f_00001_.mp4` |

## B0 — baseline FLF Mac GGUF: 512² length41 steps10 CFG1.5, keyframe_01→02
- prompt_id: `ac6d2ba6-a32a-4e39-ad39-fe391edbdedf`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/flf_mac_gguf_2kf_test_api.json`
- video: `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_2kf_test_512_41f_00001_.mp4`
- contact: `/tmp/b0_est_512_41f_00001__contact.jpg`
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
      "nb_frames": "41"
    }
  ],
  "format": {
    "duration": "2.562500",
    "size": "658700"
  }
}
```

## V1 — length 41→81, other settings unchanged
- prompt_id: `c12ea862-0453-46f2-af08-7aac71a92099`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/flf_mac_gguf_v1_len81_api.json`
- video: `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_v1_len81_512_00001_.mp4`
- contact: `/tmp/v1_1_len81_512_00001__contact.jpg`
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
    "duration": "5.062500",
    "size": "1059720"
  }
}
```

## V2 — steps 10→6, length41 unchanged
- prompt_id: `96465d84-8496-4536-b894-1fe27c4d5510`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/flf_mac_gguf_v2_steps6_api.json`
- video: `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_v2_steps6_41f_00001_.mp4`
- contact: `/tmp/v2__steps6_41f_00001__contact.jpg`
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
      "nb_frames": "41"
    }
  ],
  "format": {
    "duration": "2.562500",
    "size": "672021"
  }
}
```

## V3 — CFG 1.5→1.0, length41 unchanged
- prompt_id: `41e3a4e7-d5a7-4ec9-a84e-c916989120c0`
- status: `success`
- api: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/flf_mac_gguf_v3_cfg10_api.json`
- video: `/Users/tf00185088/comfyui/output/video/flf_mac_gguf_v3_cfg10_41f_00001_.mp4`
- contact: `/tmp/v3_3_cfg10_41f_00001__contact.jpg`
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
      "nb_frames": "41"
    }
  ],
  "format": {
    "duration": "2.562500",
    "size": "677080"
  }
}
```