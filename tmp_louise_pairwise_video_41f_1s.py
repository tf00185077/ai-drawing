#!/usr/bin/env python3
from __future__ import annotations
import json, time, uuid, shutil, subprocess
from pathlib import Path
from urllib import request

COMFY = 'http://127.0.0.1:8188'
WORKFLOW = Path('/Users/tf00185088/Desktop/ai-drawing/backend/workflows/gen_img2video_wan_first_frame_last_frame.json')
INPUT_DIR = Path('/Users/tf00185088/comfyui/input')
OUTPUT_DIR = Path('/Users/tf00185088/comfyui/output')
FINAL_DIR = Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30')
TASK = 'louise_pairwise_wand_motion_41f1s_20260630'

IMAGES = [
    Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/anima_lora_test_00058_78cec5aa_2.png'),
    Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/louise_routec_base03_wand_hand_up30_ten_05_d86_00001_45e5b185_0.png'),
    Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30/louise_routec_base03_wand_hand_up30_ten_09_d88_00001_f250885f_0.png'),
]
PROMPT = (
    'smooth fast one-second transition between the provided start and end keyframes, natural in-between motion, '
    'Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, pink long curly hair, anime watercolor illustration, '
    'right hand holding a short thin wood grain wand, gradual wand hand motion, preserve character identity, preserve outfit design, '
    'preserve original color palette, preserve original lighting, preserve original saturation, preserve original contrast, full color, '
    'consistent colors across all frames, stable facial features, coherent European castle background, coherent pose transition, no sudden cuts, no camera shake'
)
NEG = (
    'low quality, blurry, jitter, heavy flicker, motion blur, morphing face, distorted face, changing identity, changing outfit, '
    'deformed hands, extra limbs, duplicate character, cropped body, missing feet, wrong character, long staff, flower wand, floral wand, '
    'background warping, camera shake, sudden cuts, text, watermark, logo, signature, monochrome, grayscale, washed out colors'
)

def log(msg):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), msg, flush=True)

def post_json(path, payload):
    req = request.Request(COMFY+path, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    with request.urlopen(req, timeout=30) as r:
        body = r.read().decode()
        return json.loads(body) if body else {}

def get_json(path):
    with request.urlopen(COMFY+path, timeout=30) as r:
        return json.loads(r.read().decode())

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

def configure(start_rel, end_rel, prefix, seed):
    w=json.loads(WORKFLOW.read_text())
    w['97']['inputs']['image']=start_rel
    w['109']['inputs']['image']=end_rel
    w['93']['inputs']['text']=PROMPT
    w['89']['inputs']['text']=NEG
    w['98']['inputs']['width']=512
    w['98']['inputs']['height']=704
    w['98']['inputs']['length']=41
    w['98']['inputs']['batch_size']=1
    w['94']['inputs']['fps']=41
    for nid in ('86','85'):
        w[nid]['inputs']['steps']=10
        w[nid]['inputs']['cfg']=1.5
        w[nid]['inputs']['sampler_name']='euler'
        w[nid]['inputs']['scheduler']='simple'
    w['86']['inputs']['noise_seed']=seed
    w['85']['inputs']['noise_seed']=seed
    w['86']['inputs']['start_at_step']=0
    w['86']['inputs']['end_at_step']=5
    w['85']['inputs']['start_at_step']=5
    w['85']['inputs']['end_at_step']=10
    w['95']['inputs']['model_name']='Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf'
    w['96']['inputs']['model_name']='Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf'
    w['108']['inputs']['filename_prefix']=f'video/{prefix}'
    return w

def output_from_history(pid):
    hist=get_json('/history/'+pid)
    if pid not in hist:
        return None, None
    item=hist[pid]
    outs=[]
    for node_id,node_out in item.get('outputs',{}).items():
        for key in ('videos','gifs','animated','files'):
            for v in node_out.get(key,[]) or []:
                if isinstance(v,dict) and v.get('filename'):
                    sub=v.get('subfolder','')
                    typ=v.get('type','output')
                    p=OUTPUT_DIR/sub/v['filename'] if typ=='output' else OUTPUT_DIR/v['filename']
                    outs.append(p)
    existing=[p for p in outs if p.exists()]
    return (existing[0] if existing else None), item.get('status',{})

def submit_and_wait(w, label):
    pid=post_json('/prompt', {'prompt':w, 'client_id':str(uuid.uuid4())})['prompt_id']
    log(f'{label} submitted prompt_id={pid}')
    start=time.time(); last=-1
    while True:
        out,status=output_from_history(pid)
        if out:
            log(f'{label} completed output={out} status={status}')
            return out, pid
        mins=int((time.time()-start)//60)
        if mins != last:
            q=get_json('/queue')
            log(f'{label} waiting {mins}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}')
            last=mins
        time.sleep(20)

def concat(paths):
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    final=FINAL_DIR/'louise_pairwise_1to2_2to3_wan22_q4ks_512x704_41f41fps_concat.mp4'
    listfile=FINAL_DIR/'louise_pairwise_41f41fps_concat_list.txt'
    with listfile.open('w') as f:
        for p in paths:
            f.write('file '+repr(str(p))+'\n')
    cmd=['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','18','-preset','medium','-an',str(final)]
    log('concat start')
    subprocess.check_call(cmd)
    log(f'FINAL {final}')
    return final

def main():
    stats=get_json('/system_stats')
    log(f"ComfyUI OK {stats['system']['comfyui_version']} {stats['devices'][0]['name']}")
    rels=stage_inputs()
    segs=[]
    for idx,(a,b,seed) in enumerate([(rels[0],rels[1],482910041),(rels[1],rels[2],482910042)], 1):
        prefix=f'louise_pairwise_wand_motion_seg{idx:02d}_q4ks_512x704_41f41fps'
        wf=configure(a,b,prefix,seed)
        (FINAL_DIR/f'{prefix}_submitted_workflow.json').write_text(json.dumps(wf,indent=2),encoding='utf-8')
        out,pid=submit_and_wait(wf, f'seg{idx:02d}')
        dst=FINAL_DIR/f'{prefix}{out.suffix}'
        shutil.copy2(out,dst)
        log(f'seg{idx:02d} copied {dst}')
        segs.append(dst)
    concat(segs)

if __name__=='__main__':
    main()
