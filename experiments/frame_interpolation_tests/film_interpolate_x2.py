#!/usr/bin/env python3
"""Apple-Silicon friendly FILM x2 interpolation for short generated videos.

Uses ffmpeg for decode/encode and TorchScript FILM model directly via torch.jit.load.
Avoids ComfyUI FrameInterpolationModelLoader, which currently fails on TorchScript
models with torch.load(weights_only=True).
"""
import argparse, json, math, shutil, subprocess, tempfile
from pathlib import Path
import numpy as np
import torch
from PIL import Image


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def ffprobe(path):
    p = subprocess.run([
        "/opt/homebrew/bin/ffprobe", "-v", "error",
        "-show_entries", "format=duration,size:stream=width,height,nb_frames,r_frame_rate,codec_name",
        "-of", "json", str(path)
    ], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def load_img(path, device):
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype("float32") / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device=device, dtype=torch.float16)


def save_tensor(t, path):
    arr = t.clamp(0, 1).float().cpu()[0].permute(1, 2, 0).numpy()
    Image.fromarray((arr * 255).round().astype("uint8")).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model", default="/Users/tf00185088/comfyui/models/frame_interpolation/film_net_fp16.pt")
    ap.add_argument("--fps", type=float, default=32.0, help="Output fps. For 16fps source x2, use 32 to preserve duration; use 30 for target 30fps with slight slow-down.")
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    model_path = Path(args.model)
    out.parent.mkdir(parents=True, exist_ok=True)
    info = ffprobe(inp)
    print("input", json.dumps(info, indent=2), flush=True)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print("device", device, "model", model_path, flush=True)
    model = torch.jit.load(str(model_path), map_location=device).eval()

    temp_root = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="film_x2_"))
    frames_dir = temp_root / "frames"
    out_frames = temp_root / "out_frames"
    if frames_dir.exists(): shutil.rmtree(frames_dir)
    if out_frames.exists(): shutil.rmtree(out_frames)
    frames_dir.mkdir(parents=True)
    out_frames.mkdir(parents=True)

    run(["/opt/homebrew/bin/ffmpeg", "-y", "-i", str(inp), str(frames_dir / "%06d.png")])
    frames = sorted(frames_dir.glob("*.png"))
    print("decoded_frames", len(frames), flush=True)
    if len(frames) < 2:
        raise SystemExit("need at least 2 frames")

    idx = 1
    with torch.no_grad():
        prev_t = load_img(frames[0], device)
        # original first frame
        shutil.copy2(frames[0], out_frames / f"{idx:06d}.png"); idx += 1
        for i in range(len(frames)-1):
            a_path, b_path = frames[i], frames[i+1]
            a = prev_t if i == 0 else load_img(a_path, device)
            b = load_img(b_path, device)
            mid = model(a, b, torch.tensor([[0.5]], dtype=torch.float16, device=device))
            save_tensor(mid, out_frames / f"{idx:06d}.png"); idx += 1
            shutil.copy2(b_path, out_frames / f"{idx:06d}.png"); idx += 1
            prev_t = b
            if (i+1) % 10 == 0:
                print("pairs", i+1, "/", len(frames)-1, "out_frames", idx-1, flush=True)
    expected = (len(frames)-1)*2 + 1
    print("expected_out_frames", expected, "actual", idx-1, flush=True)

    run(["/opt/homebrew/bin/ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_frames / "%06d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)])
    out_info = ffprobe(out)
    print("output", json.dumps(out_info, indent=2), flush=True)
    if not args.workdir:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
