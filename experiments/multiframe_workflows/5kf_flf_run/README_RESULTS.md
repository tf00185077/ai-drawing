# 5-keyframe FLF segmented pipeline results

Route: 4 FLF segments using local Mac/MPS GGUF Wan2.2 route, then ffmpeg stitch, then direct FILM x4/62fps.

## Segments

### seg01_01_to_02 — success
- prompt_id: `eed03663-7627-49f4-b49a-7c45c7697d4c`
- elapsed_seconds: `6434.7`
- video: `/Users/tf00185088/comfyui/output/video/5kf_flf_seg01_flf5_keyframe_01_to_flf5_keyframe_02_00001_.mp4`
- contact: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/seg01_01_to_02_contact.jpg`
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
    "size": "1179247"
  }
}
```
### seg02_02_to_03 — success
- prompt_id: `e451846f-17fb-451d-9e1d-ed4ece4cb6ca`
- elapsed_seconds: `6254.2`
- video: `/Users/tf00185088/comfyui/output/video/5kf_flf_seg02_flf5_keyframe_02_to_flf5_keyframe_03_00001_.mp4`
- contact: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/seg02_02_to_03_contact.jpg`
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
    "size": "1179248"
  }
}
```
### seg03_03_to_04 — success
- prompt_id: `f66bf1c7-bf7d-42d4-8bf5-0aa59095508f`
- elapsed_seconds: `6434.7`
- video: `/Users/tf00185088/comfyui/output/video/5kf_flf_seg03_flf5_keyframe_03_to_flf5_keyframe_04_00001_.mp4`
- contact: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/seg03_03_to_04_contact.jpg`
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
    "size": "1290512"
  }
}
```
### seg04_04_to_05 — success
- prompt_id: `3bbfd918-c0c2-4b47-b96e-6be4cb2fd296`
- elapsed_seconds: `6314.8`
- video: `/Users/tf00185088/comfyui/output/video/5kf_flf_seg04_flf5_keyframe_04_to_flf5_keyframe_05_00001_.mp4`
- contact: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/seg04_04_to_05_contact.jpg`
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
    "size": "1186994"
  }
}
```

## Final stitched outputs
- stitched_16fps: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_16fps.mp4`
- stitched_contact: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_16fps_contact.jpg`
- FILM_x4_62fps: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_FILM_x4_62fps.mp4`
- FILM_contact: `/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_FILM_x4_62fps_contact.jpg`

### final ffprobe
```json
{
  "stitched": "/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_16fps.mp4",
  "stitched_ffprobe": {
    "programs": [],
    "stream_groups": [],
    "streams": [
      {
        "codec_name": "h264",
        "width": 512,
        "height": 512,
        "r_frame_rate": "16/1",
        "nb_frames": "324"
      }
    ],
    "format": {
      "duration": "20.250000",
      "size": "4820575"
    }
  },
  "stitched_contact": "/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_16fps_contact.jpg",
  "film_x4_62": "/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_FILM_x4_62fps.mp4",
  "film_x4_62_ffprobe": {
    "programs": [],
    "stream_groups": [],
    "streams": [
      {
        "codec_name": "h264",
        "width": 512,
        "height": 512,
        "r_frame_rate": "62/1",
        "nb_frames": "1293"
      }
    ],
    "format": {
      "duration": "20.854839",
      "size": "9986969"
    }
  },
  "film_x4_62_contact": "/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run/asuka_5kf_flf_stitched_FILM_x4_62fps_contact.jpg"
}
```