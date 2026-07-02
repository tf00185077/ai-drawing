#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from urllib import request

from PIL import Image, ImageOps

COMFY = "http://127.0.0.1:8188"
WORKFLOW = Path("/Users/tf00185088/Desktop/ai-drawing/backend/workflows/gen_img2video_wan_first_frame_last_frame.json")
INPUT_DIR = Path("/Users/tf00185088/comfyui/input")
OUTPUT_DIR = Path("/Users/tf00185088/comfyui/output")
GALLERY_DIR = Path("/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-07-01")
TASK = "louise_red_electric_pairwise_from_prev_lastframe_20260701"

PREV_VIDEO = Path("/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/louise_pairwise_2s_concat_regen_seg02_from_seg1_lastframe.mp4")
RAW_KEYFRAMES = [
    GALLERY_DIR / "louise_prev_video_last_frame.png",
    GALLERY_DIR / "louise_user_keyframe_red_electric_01.png",
    GALLERY_DIR / "louise_user_keyframe_red_electric_02.png",
]
KEYFRAMES_512 = [
    GALLERY_DIR / "louise_red_electric_kf00_prev_last_512x704.png",
    GALLERY_DIR / "louise_red_electric_kf01_user_512x704.png",
    GALLERY_DIR / "louise_red_electric_kf02_user_512x704.png",
]

PROMPT = (
    "smooth two-second magical transition between the provided start and end keyframes, "
    "Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, anime watercolor illustration, "
    "pink long hair, right hand holding a short thin wood grain wand, red electric magic effect, "
    "crimson jagged lightning without forming a circle, red-white electric discharge, scattered red sparks, "
    "preserve character identity, preserve outfit design, stable face, stable body, coherent European castle background, "
    "preserve original warm watercolor color palette, no sudden cuts, no camera shake"
)
NEG = (
    "low quality, blurry, jitter, heavy flicker, motion blur, morphing face, distorted face, changing identity, changing outfit, "
    "deformed hands, extra limbs, duplicate character, cropped body, missing feet, wrong character, long staff, flower wand, floral wand, "
    "background warping, camera shake, sudden cuts, red ring, circular red halo, magic circle, enclosing ring, text, watermark, logo, signature, "
    "monochrome, grayscale, washed out colors, overexposed full screen flash"
)


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def post_json(path: str, payload: dict) -> dict:
    req = request.Request(
        COMFY + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=30) as r:
        body = r.read().decode()
        return json.loads(body) if body else {}


def get_json(path: str) -> dict:
    with request.urlopen(COMFY + path, timeout=30) as r:
        return json.loads(r.read().decode())


def ensure_keyframes() -> None:
    if not RAW_KEYFRAMES[0].exists():
        log(f"extracting previous video last frame from {PREV_VIDEO}")
        subprocess.check_call([
            "ffmpeg", "-y", "-sseof", "-0.1", "-i", str(PREV_VIDEO),
            "-frames:v", "1", str(RAW_KEYFRAMES[0]),
        ])
    for src, dst in zip(RAW_KEYFRAMES, KEYFRAMES_512):
        if not src.exists():
            raise FileNotFoundError(src)
        im = Image.open(src).convert("RGB")
        # Match the existing Wan segment portrait size. A small center crop is preferable
        # to letterboxing because it preserves full-frame continuity for Wan.
        im = ImageOps.fit(im, (512, 704), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        im.save(dst)
        log(f"keyframe {src.name} -> {dst.name} size={dst.stat().st_size}")


def stage_inputs() -> list[str]:
    task_dir = INPUT_DIR / TASK
    task_dir.mkdir(parents=True, exist_ok=True)
    rels: list[str] = []
    for i, src in enumerate(KEYFRAMES_512, 1):
        dest = task_dir / f"keyframe_{i:02d}.png"
        shutil.copy2(src, dest)
        rels.append(f"{TASK}/{dest.name}")
    return rels


def configure(start_rel: str, end_rel: str, prefix: str, seed: int) -> dict:
    w = json.loads(WORKFLOW.read_text())
    w["97"]["inputs"]["image"] = start_rel
    w["109"]["inputs"]["image"] = end_rel
    w["93"]["inputs"]["text"] = PROMPT
    w["89"]["inputs"]["text"] = NEG
    w["98"]["inputs"]["width"] = 512
    w["98"]["inputs"]["height"] = 704
    w["98"]["inputs"]["length"] = 41
    w["98"]["inputs"]["batch_size"] = 1
    # 41 frames / 20.5 fps = 2 seconds per segment.
    w["94"]["inputs"]["fps"] = 20.5
    for nid in ("86", "85"):
        w[nid]["inputs"]["steps"] = 10
        w[nid]["inputs"]["cfg"] = 1.5
        w[nid]["inputs"]["sampler_name"] = "euler"
        w[nid]["inputs"]["scheduler"] = "simple"
        w[nid]["inputs"]["noise_seed"] = seed
    w["86"]["inputs"]["start_at_step"] = 0
    w["86"]["inputs"]["end_at_step"] = 5
    w["85"]["inputs"]["start_at_step"] = 5
    w["85"]["inputs"]["end_at_step"] = 10
    w["95"]["inputs"]["model_name"] = "Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf"
    w["96"]["inputs"]["model_name"] = "Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf"
    w["108"]["inputs"]["filename_prefix"] = f"video/{prefix}"
    return w


def output_from_history(prompt_id: str) -> tuple[Path | None, dict | None]:
    hist = get_json("/history/" + prompt_id)
    if prompt_id not in hist:
        return None, None
    item = hist[prompt_id]
    outs: list[Path] = []
    for node_out in item.get("outputs", {}).values():
        for key in ("videos", "gifs", "files", "images"):
            vals = node_out.get(key, []) or []
            if isinstance(vals, bool):
                continue
            for v in vals:
                if isinstance(v, dict) and v.get("filename"):
                    sub = v.get("subfolder", "")
                    typ = v.get("type", "output")
                    p = OUTPUT_DIR / sub / v["filename"] if typ == "output" else OUTPUT_DIR / v["filename"]
                    outs.append(p)
    existing = [p for p in outs if p.exists()]
    return (existing[0] if existing else None), item.get("status", {})


def submit_and_wait(workflow: dict, label: str) -> Path:
    prompt_id = post_json("/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())})["prompt_id"]
    log(f"{label} submitted prompt_id={prompt_id}")
    start = time.time()
    last_min = -1
    while True:
        out, status = output_from_history(prompt_id)
        if out:
            log(f"{label} completed output={out} status={status}")
            return out
        mins = int((time.time() - start) // 60)
        if mins != last_min:
            q = get_json("/queue")
            log(f"{label} waiting {mins}m running={len(q.get('queue_running', []))} pending={len(q.get('queue_pending', []))}")
            last_min = mins
        time.sleep(20)


def concat(paths: list[Path]) -> Path:
    final = GALLERY_DIR / "louise_red_electric_from_prev_lastframe_2segments_concat.mp4"
    listfile = GALLERY_DIR / "louise_red_electric_from_prev_lastframe_concat_list.txt"
    with listfile.open("w") as f:
        for p in paths:
            f.write("file " + repr(str(p)) + "\n")
    # Re-encode for stable Discord playback and to avoid stream-copy mismatches.
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-crf", "18", "-preset", "medium", "-an", str(final),
    ])
    log(f"FINAL {final}")
    return final


def main() -> None:
    q = get_json("/queue")
    if q.get("queue_running") or q.get("queue_pending"):
        log(f"warning: queue not empty at start running={len(q.get('queue_running', []))} pending={len(q.get('queue_pending', []))}")
    stats = get_json("/system_stats")
    log(f"ComfyUI OK {stats['system'].get('comfyui_version')} {stats['devices'][0].get('name')}")
    ensure_keyframes()
    rels = stage_inputs()
    segments: list[Path] = []
    pairs = [
        (rels[0], rels[1], "louise_red_electric_prevlast_to_user01_2s_512x704_41f20p5fps", 8831051),
        (rels[1], rels[2], "louise_red_electric_user01_to_user02_2s_512x704_41f20p5fps", 8831052),
    ]
    for idx, (start_rel, end_rel, prefix, seed) in enumerate(pairs, 1):
        wf = configure(start_rel, end_rel, prefix, seed)
        (GALLERY_DIR / f"{prefix}_workflow.json").write_text(json.dumps(wf, indent=2), encoding="utf-8")
        out = submit_and_wait(wf, f"seg{idx:02d}")
        dst = GALLERY_DIR / f"{prefix}{out.suffix}"
        shutil.copy2(out, dst)
        log(f"seg{idx:02d} copied {dst}")
        print("MEDIA:" + str(dst), flush=True)
        segments.append(dst)
    final = concat(segments)
    print("MEDIA:" + str(final), flush=True)


if __name__ == "__main__":
    main()
