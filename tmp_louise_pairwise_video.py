#!/usr/bin/env python3
from __future__ import annotations
import json, time, uuid, shutil, subprocess, sys
from pathlib import Path
from urllib import request, parse

COMFY = 'http://127.0.0.1:8188'
WORKFLOW = Path('/Users/tf00185088/Desktop/ai-drawing/backend/workflows/gen_img2video_wan_first_frame_last_frame.json')
INPUT_DIR = Path('/Users/tf00185088/comfyui/input')
OUTPUT_DIR = Path('/Users/tf00185088/comfyui/output')
FINAL_DIR = Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30')
TASK = 'louise_pairwise_wand_motion_20260630'

IMAGES = [
    Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/anima_lora_test_00058_78cec5aa_2.png'),
    Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/louise_routec_base03_wand_hand_up30_ten_05_d86_00001_45e5b185_0.png'),
    Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/louise_routec_base03_wand_hand_up30_ten_09_d88_00001_f250885f_0.png'),
]

PROMPT = (
    'smooth transition between the provided start and end keyframes, natural in-between motion, '
    'Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, pink long curly hair, anime watercolor illustration, '
    'right hand holding a short thin wood grain wand, gradual wand hand motion, preserve character identity, preserve outfit design, '
    'preserve original color palette, preserve original lighting, preserve original saturation, preserve original contrast, full color, '
    'consistent colors across all frames, stable facial features, coherent European castle background, coherent pose transition, '
    'no sudden cuts, no camera shake'
)
NEG = (
    'low quality, blurry, jitter, heavy flicker, motion blur, morphing face, distorted face, changing identity, changing outfit, '
    'deformed hands, extra limbs, duplicate character, cropped body, missing feet, wrong character, long staff, flower wand, floral wand, '
    'background warping, camera shake, sudden cuts, text, watermark, logo, signature, monochrome, grayscale, washed out colors'
)


def post_json(path: str, payload: dict):
    data = json.dumps(payload).encode('utf-8')
    req = request.Request(COMFY + path, data=data, headers={'Content-Type':'application/json'})
    with request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def get_json(path: str):
    with request.urlopen(COMFY + path, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def wait_ready():
    stats = get_json('/system_stats')
    print('ComfyUI OK:', stats['system']['comfyui_version'], stats['devices'][0]['name'], flush=True)


def stage_inputs():
    task_dir = INPUT_DIR / TASK
    task_dir.mkdir(parents=True, exist_ok=True)
    rels=[]
    for i, src in enumerate(IMAGES, 1):
        if not src.exists():
            raise FileNotFoundError(src)
        dest = task_dir / f'keyframe_{i:02d}{src.suffix.lower()}'
        shutil.copy2(src, dest)
        rels.append(f'{TASK}/{dest.name}')
    return rels


def configure_workflow(start_rel, end_rel, prefix, seed):
    w = json.loads(WORKFLOW.read_text())
    # Keyframes
    w['97']['inputs']['image'] = start_rel
    w['109']['inputs']['image'] = end_rel
    # Prompt
    w['93']['inputs']['text'] = PROMPT
    w['89']['inputs']['text'] = NEG
    # Wan first-last frame settings: portrait preserving, high quality on CTY Mac
    w['98']['inputs']['width'] = 512
    w['98']['inputs']['height'] = 704
    w['98']['inputs']['length'] = 81
    w['98']['inputs']['batch_size'] = 1
    # fps
    w['94']['inputs']['fps'] = 16
    # samplers
    for nid in ('86','85'):
        w[nid]['inputs']['steps'] = 10
        w[nid]['inputs']['cfg'] = 1.5
        w[nid]['inputs']['sampler_name'] = 'euler'
        w[nid]['inputs']['scheduler'] = 'simple'
    w['86']['inputs']['noise_seed'] = seed
    w['85']['inputs']['noise_seed'] = seed
    w['86']['inputs']['end_at_step'] = 5
    w['85']['inputs']['start_at_step'] = 5
    w['85']['inputs']['end_at_step'] = 10
    # Q4_K_S model variant
    w['95']['inputs']['model_name'] = 'Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf'
    w['96']['inputs']['model_name'] = 'Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf'
    # output
    w['108']['inputs']['filename_prefix'] = f'video/{prefix}'
    return w


def submit_and_wait(w, label):
    client_id = str(uuid.uuid4())
    resp = post_json('/prompt', {'prompt': w, 'client_id': client_id})
    pid = resp['prompt_id']
    print(f'[{label}] submitted prompt_id={pid}', flush=True)
    last = ''
    start = time.time()
    while True:
        hist = get_json('/history/' + pid)
        if pid in hist:
            item = hist[pid]
            status = item.get('status', {})
            print(f'[{label}] completed status={status}', flush=True)
            # collect video outputs
            outs=[]
            for node_id, node_out in item.get('outputs', {}).items():
                for v in node_out.get('videos', []) or []:
                    filename=v.get('filename')
                    sub=v.get('subfolder','')
                    typ=v.get('type','output')
                    if filename:
                        path = OUTPUT_DIR / sub / filename if typ == 'output' else OUTPUT_DIR / filename
                        outs.append(path)
                # Some SaveVideo versions use gifs or images key
                for key in ('gifs','animated','files'):
                    for v in node_out.get(key, []) or []:
                        filename=v.get('filename') if isinstance(v, dict) else None
                        sub=v.get('subfolder','') if isinstance(v, dict) else ''
                        if filename:
                            outs.append(OUTPUT_DIR / sub / filename)
            existing=[p for p in outs if p.exists()]
            if not existing:
                print(json.dumps(item.get('outputs', {}), indent=2), flush=True)
                raise RuntimeError(f'No output video found for {label}')
            print(f'[{label}] output={existing[0]}', flush=True)
            return existing[0]
        q = get_json('/queue')
        msg = f"running={len(q.get('queue_running',[]))} pending={len(q.get('queue_pending',[]))} elapsed={(time.time()-start)/60:.1f}m"
        if msg != last:
            print(f'[{label}] {msg}', flush=True)
            last = msg
        time.sleep(30)


def concat_segments(paths):
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    final = FINAL_DIR / 'louise_pairwise_1to2_2to3_wan22_q4ks_512x704_81f16fps_concat.mp4'
    listfile = FINAL_DIR / 'louise_pairwise_concat_list.txt'
    with listfile.open('w') as f:
        for p in paths:
            f.write("file " + repr(str(p)) + "\n")
    # Re-encode for consistent Discord-compatible output.
    cmd = [
        'ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),
        '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',
        '-crf','18','-preset','medium','-an',str(final)
    ]
    print('concat:', ' '.join(cmd), flush=True)
    subprocess.check_call(cmd)
    print('FINAL', final, flush=True)
    return final


def main():
    wait_ready()
    rels = stage_inputs()
    seeds = [382910457, 382910773]
    segs=[]
    for idx, (a,b) in enumerate([(rels[0], rels[1]), (rels[1], rels[2])], 1):
        prefix = f'louise_pairwise_wand_motion_seg{idx:02d}_q4ks_512x704_81f16fps'
        wf = configure_workflow(a,b,prefix,seeds[idx-1])
        wf_path = FINAL_DIR / f'{prefix}_submitted_workflow.json'
        wf_path.write_text(json.dumps(wf, indent=2), encoding='utf-8')
        seg = submit_and_wait(wf, f'seg{idx:02d}')
        copy_to = FINAL_DIR / f'{prefix}{seg.suffix}'
        shutil.copy2(seg, copy_to)
        print(f'[seg{idx:02d}] copied={copy_to}', flush=True)
        segs.append(copy_to)
    concat_segments(segs)

if __name__ == '__main__':
    main()
