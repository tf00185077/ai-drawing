#!/usr/bin/env python3
import copy
import json
import shutil
import time
import urllib.request
from pathlib import Path

HOST = "http://127.0.0.1:8188"
ROOT = Path("/Users/tf00185088/Desktop/ai-drawing")
EXP = ROOT / "experiments/controlnet_inpaint_template_research/anima_smoke"
COMFY_INPUT = Path("/Users/tf00185088/comfyui/input")
COMFY_OUTPUT = Path("/Users/tf00185088/comfyui/output")
SRC_IMAGE = ROOT / "outputs/gallery/2026-06-23/asuka_ruins_eva02_angle_b_side_profile_00001_93842c40_6.png"
BASE = json.loads((ROOT / "backend/workflows/gen_txt2img_anima_lora_model_only.json").read_text())
EXP.mkdir(parents=True, exist_ok=True)

PROMPT = "1girl, solo, anime illustration, simple portrait, clean lineart, soft lighting, test image"
NEG = "worst quality, low quality, blurry, deformed, bad anatomy"


def jget(path, timeout=30):
    with urllib.request.urlopen(HOST + path, timeout=timeout) as r:
        return json.load(r)


def jpost(path, obj, timeout=60):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def wait_done(prompt_id, label, poll=10):
    start = time.time()
    while True:
        h = jget(f"/history/{prompt_id}", 30)
        if prompt_id in h:
            return h[prompt_id], round(time.time() - start, 1)
        q = jget("/queue", 20)
        print(label, "elapsed", int(time.time() - start), "queue", q, flush=True)
        time.sleep(poll)


def collect_images(item, prefix):
    images = []
    for out in (item.get("outputs") or {}).values():
        for img in out.get("images") or []:
            if not isinstance(img, dict) or "filename" not in img:
                continue
            base = COMFY_OUTPUT if (img.get("type") or "output") == "output" else Path("/Users/tf00185088/comfyui/temp")
            p = base / str(img.get("subfolder") or "") / str(img["filename"])
            if p.exists():
                images.append(p)
    if not images:
        images = sorted(COMFY_OUTPUT.rglob(prefix + "*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
    return [str(p) for p in images]


def make_txt2img():
    p = copy.deepcopy(BASE)
    p["4"]["inputs"].update({"width": 512, "height": 512, "batch_size": 1})
    p["5"]["inputs"]["text"] = PROMPT
    p["6"]["inputs"]["text"] = NEG
    p["7"]["inputs"].update({"seed": 26062601, "steps": 1, "cfg": 1.0, "denoise": 1.0})
    p["9"]["inputs"]["filename_prefix"] = "anima_smoke_txt2img"
    return p


def make_img2img():
    dst = COMFY_INPUT / "anima_smoke_img2img_input.png"
    shutil.copy2(SRC_IMAGE, dst)
    p = copy.deepcopy(BASE)
    # Replace txt2img latent with LoadImage -> VAEEncode using Anima/Qwen VAE.
    p.pop("4", None)
    p["14"] = {
        "class_type": "LoadImage",
        "inputs": {"image": dst.name},
        "_meta": {"title": "Load img2img input"},
    }
    p["15"] = {
        "class_type": "VAEEncode",
        "inputs": {"pixels": ["14", 0], "vae": ["3", 0]},
        "_meta": {"title": "Encode image to Anima/Qwen latent"},
    }
    p["5"]["inputs"]["text"] = PROMPT
    p["6"]["inputs"]["text"] = NEG
    p["7"]["inputs"].update({"seed": 26062602, "steps": 1, "cfg": 1.0, "denoise": 0.35, "latent_image": ["15", 0]})
    p["9"]["inputs"]["filename_prefix"] = "anima_smoke_img2img"
    return p


def run(label, prompt):
    api_path = EXP / f"{label}_api.json"
    api_path.write_text(json.dumps(prompt, ensure_ascii=False, indent=2))
    resp = jpost("/prompt", {"prompt": prompt, "client_id": label}, 60)
    pid = resp["prompt_id"]
    print(label, "submitted", pid, flush=True)
    item, elapsed = wait_done(pid, label)
    status = item.get("status", {}).get("status_str")
    rec = {
        "label": label,
        "prompt_id": pid,
        "api": str(api_path),
        "status": status,
        "elapsed_seconds": elapsed,
        "images": collect_images(item, f"anima_smoke_{label}"),
        "messages": item.get("status", {}).get("messages", []),
    }
    return rec


def main():
    q = jget("/queue")
    if q.get("queue_running") or q.get("queue_pending"):
        raise SystemExit(f"queue not empty: {q}")
    results = []
    for label, wf in [("txt2img", make_txt2img()), ("img2img", make_img2img())]:
        rec = run(label, wf)
        results.append(rec)
        (EXP / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
        jpost("/free", {"unload_models": True, "free_memory": True}, 30)
        time.sleep(5)
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
