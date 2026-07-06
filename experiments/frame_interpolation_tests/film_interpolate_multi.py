#!/usr/bin/env python3
"""Apple-Silicon friendly FILM interpolation for generated videos.

Creates (input_frames - 1) * multiplier + 1 frames by querying FILM at
fractional times between each adjacent source frame. Uses torch.jit.load so it
works with the local TorchScript FILM model on MPS, bypassing ComfyUI's loader.
"""
import argparse, json, shutil, subprocess, tempfile
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


def encode_from_frames(frames_dir, output, fps):
    run([
        "/opt/homebrew/bin/ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(frames_dir / "%06d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(output)
    ])
    return ffprobe(output)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outputs", nargs="+", required=True, help="Pairs output.mp4:fps, e.g. out60.mp4:60 out62.mp4:62")
    ap.add_argument("--multiplier", type=int, default=4)
    ap.add_argument("--model", default="/Volumes/AI-Drawing-16T/ai-drawing/models/frame_interpolation/film_net_fp16.pt")
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()
    if args.multiplier < 2:
        raise SystemExit("multiplier must be >= 2")

    inp = Path(args.input)
    model_path = Path(args.model)
    info = ffprobe(inp)
    print("input", json.dumps(info, indent=2), flush=True)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print("device", device, "model", model_path, "multiplier", args.multiplier, flush=True)
    model = torch.jit.load(str(model_path), map_location=device).eval()

    temp_root = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix=f"film_x{args.multiplier}_"))
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
        shutil.copy2(frames[0], out_frames / f"{idx:06d}.png"); idx += 1
        for i in range(len(frames)-1):
            a = load_img(frames[i], device)
            b = load_img(frames[i+1], device)
            for k in range(1, args.multiplier):
                tval = k / args.multiplier
                mid = model(a, b, torch.tensor([[tval]], dtype=torch.float16, device=device))
                save_tensor(mid, out_frames / f"{idx:06d}.png"); idx += 1
            shutil.copy2(frames[i+1], out_frames / f"{idx:06d}.png"); idx += 1
            if (i+1) % 10 == 0:
                print("pairs", i+1, "/", len(frames)-1, "out_frames", idx-1, flush=True)
    expected = (len(frames)-1) * args.multiplier + 1
    print("expected_out_frames", expected, "actual", idx-1, flush=True)

    results = []
    for spec in args.outputs:
        output_s, fps_s = spec.rsplit(":", 1)
        output = Path(output_s)
        output.parent.mkdir(parents=True, exist_ok=True)
        fps = float(fps_s)
        out_info = encode_from_frames(out_frames, output, fps)
        results.append({"output": str(output), "fps": fps, "ffprobe": out_info})
        print("output", json.dumps(results[-1], indent=2), flush=True)

    if not args.workdir:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
