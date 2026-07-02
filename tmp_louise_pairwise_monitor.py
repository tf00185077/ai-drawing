#!/usr/bin/env python3
from __future__ import annotations
import json, time, uuid, shutil, subprocess, sys
from pathlib import Path
from urllib import request

COMFY='http://127.0.0.1:8188'
WORKFLOW=Path('/Users/tf00185088/Desktop/ai-drawing/backend/workflows/gen_img2video_wan_first_frame_last_frame.json')
OUTPUT_DIR=Path('/Users/tf00185088/comfyui/output')
FINAL_DIR=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-30')
RUNNING_SEG1_PROMPT='a7ed6a36-2b9b-4eab-9612-7fa1d1953080'
START_REL='louise_pairwise_wand_motion_20260630/keyframe_02.png'
END_REL='louise_pairwise_wand_motion_20260630/keyframe_03.png'
PROMPT=(
    'smooth transition between the provided start and end keyframes, natural in-between motion, '
    'Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, pink long curly hair, anime watercolor illustration, '
    'right hand holding a short thin wood grain wand, gradual wand hand motion, preserve character identity, preserve outfit design, '
    'preserve original color palette, preserve original lighting, preserve original saturation, preserve original contrast, full color, '
    'consistent colors across all frames, stable facial features, coherent European castle background, coherent pose transition, '
    'no sudden cuts, no camera shake'
)
NEG=(
    'low quality, blurry, jitter, heavy flicker, motion blur, morphing face, distorted face, changing identity, changing outfit, '
    'deformed hands, extra limbs, duplicate character, cropped body, missing feet, wrong character, long staff, flower wand, floral wand, '
    'background warping, camera shake, sudden cuts, text, watermark, logo, signature, monochrome, grayscale, washed out colors'
)

def log(msg):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), msg, flush=True)

def post_json(path,payload):
    data=json.dumps(payload).encode()
    req=request.Request(COMFY+path,data=data,headers={'Content-Type':'application/json'})
    with request.urlopen(req,timeout=30) as r:
        data=r.read().decode()
        return json.loads(data) if data else {}

def get_json(path):
    with request.urlopen(COMFY+path,timeout=30) as r:
        return json.loads(r.read().decode())

def output_from_history(pid):
    hist=get_json('/history/'+pid)
    if pid not in hist: return None, None
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

def wait_prompt(pid,label):
    start=time.time(); last=-1
    while True:
        out,status=output_from_history(pid)
        if out:
            log(f'{label} completed output={out} status={status}')
            return out
        mins=int((time.time()-start)//60)
        if mins!=last:
            q=get_json('/queue')
            log(f'{label} waiting {mins}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}')
            last=mins
        time.sleep(30)

def configure_seg2():
    w=json.loads(WORKFLOW.read_text())
    w['97']['inputs']['image']=START_REL
    w['109']['inputs']['image']=END_REL
    w['93']['inputs']['text']=PROMPT
    w['89']['inputs']['text']=NEG
    w['98']['inputs']['width']=512
    w['98']['inputs']['height']=704
    w['98']['inputs']['length']=81
    w['94']['inputs']['fps']=16
    for nid in ('86','85'):
        w[nid]['inputs']['steps']=10
        w[nid]['inputs']['cfg']=1.5
        w[nid]['inputs']['sampler_name']='euler'
        w[nid]['inputs']['scheduler']='simple'
    seed=382910773
    w['86']['inputs']['noise_seed']=seed
    w['85']['inputs']['noise_seed']=seed
    w['86']['inputs']['end_at_step']=5
    w['85']['inputs']['start_at_step']=5
    w['85']['inputs']['end_at_step']=10
    w['95']['inputs']['model_name']='Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf'
    w['96']['inputs']['model_name']='Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf'
    w['108']['inputs']['filename_prefix']='video/louise_pairwise_wand_motion_seg02_q4ks_512x704_81f16fps'
    return w

def submit(w):
    resp=post_json('/prompt', {'prompt':w, 'client_id':str(uuid.uuid4())})
    return resp['prompt_id']

def copy_seg(src, name):
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    dst=FINAL_DIR/name
    shutil.copy2(src,dst)
    log(f'copied {dst}')
    return dst

def concat(paths):
    final=FINAL_DIR/'louise_pairwise_1to2_2to3_wan22_q4ks_512x704_81f16fps_concat.mp4'
    listfile=FINAL_DIR/'louise_pairwise_concat_list.txt'
    with listfile.open('w') as f:
        for p in paths: f.write('file '+repr(str(p))+'\n')
    cmd=['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','18','-preset','medium','-an',str(final)]
    log('concat start')
    subprocess.check_call(cmd)
    log(f'FINAL {final}')
    return final

def main():
    log('monitor start')
    seg1=wait_prompt(RUNNING_SEG1_PROMPT,'seg01')
    seg1_copy=copy_seg(seg1,'louise_pairwise_wand_motion_seg01_q4ks_512x704_81f16fps.mp4')
    wf2=configure_seg2()
    wf2_path=FINAL_DIR/'louise_pairwise_wand_motion_seg02_q4ks_512x704_81f16fps_submitted_workflow.json'
    wf2_path.write_text(json.dumps(wf2,indent=2),encoding='utf-8')
    pid2=submit(wf2)
    log(f'seg02 submitted prompt_id={pid2}')
    seg2=wait_prompt(pid2,'seg02')
    seg2_copy=copy_seg(seg2,'louise_pairwise_wand_motion_seg02_q4ks_512x704_81f16fps.mp4')
    concat([seg1_copy,seg2_copy])
if __name__=='__main__': main()
