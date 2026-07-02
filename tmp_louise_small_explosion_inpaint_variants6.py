#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, time, uuid
from pathlib import Path
from urllib import request

COMFY='http://127.0.0.1:8188'
INPUT_DIR=Path('/Users/tf00185088/comfyui/input')
OUTPUT_DIR=Path('/Users/tf00185088/comfyui/output')
G=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-07-01')
TASK='louise_small_explosion_variants_20260701'
GUIDE=G/'louise_14b_extend_arm_v01_last_frame_small_explosion_right_guide.png'
MASK=G/'louise_14b_extend_arm_v01_last_frame_small_explosion_right_mask.png'
SEEDS=[7621002,7621003,7621004,7621005,7621006,7621007]
PROMPT='high quality anime watercolor illustration, preserve the exact same character, pose, wand, castle background and composition. Add only one small compact magical explosion on the right side of the image, just beyond the wand tip, small orange yellow white starburst, compact explosion core, short radial shockwave, tiny sparks, watercolor anime effect. Everything outside the small masked area must stay unchanged.'
NEG='changed character, changed pose, changed face, changed hands, changed wand, changed background, blurry background, smeared castle, camera move, zoom, pan, huge explosion, full screen explosion, explosion covering character, overexposed whole image, fire everywhere, large smoke cloud, second character, text, watermark, logo, low quality'

def workflow(img_rel, mask_rel, seed, prefix):
    return {
        '1': {'inputs': {'unet_name': 'anima_baseV10.safetensors', 'weight_dtype': 'default'}, 'class_type': 'UNETLoader'},
        '2': {'inputs': {'clip_name': 'anima_baseV10_txt.safetensors', 'type': 'qwen_image', 'device': 'default'}, 'class_type': 'CLIPLoader'},
        '3': {'inputs': {'vae_name': 'qwen_image_vae.safetensors'}, 'class_type': 'VAELoader'},
        '5': {'inputs': {'text': PROMPT, 'clip': ['2',0]}, 'class_type': 'CLIPTextEncode'},
        '6': {'inputs': {'text': NEG, 'clip': ['2',0]}, 'class_type': 'CLIPTextEncode'},
        '10': {'inputs': {'model': ['1',0], 'lora_name': 'anima-highres-aesthetic-boost.safetensors', 'strength_model': 0.7}, 'class_type': 'LoraLoaderModelOnly'},
        '11': {'inputs': {'model': ['10',0], 'lora_name': 'Niji Reol v1 EP11.safetensors', 'strength_model': 0.8}, 'class_type': 'LoraLoaderModelOnly'},
        '12': {'inputs': {'model': ['11',0], 'lora_name': 'AnimaNSS4RE.safetensors', 'strength_model': 0.65}, 'class_type': 'LoraLoaderModelOnly'},
        '7': {'inputs': {'seed': seed, 'steps': 24, 'cfg': 5.2, 'sampler_name': 'er_sde', 'scheduler': 'simple', 'denoise': 0.76, 'model': ['12',0], 'positive': ['5',0], 'negative': ['6',0], 'latent_image': ['17',0]}, 'class_type': 'KSampler'},
        '8': {'inputs': {'samples': ['7',0], 'vae': ['3',0]}, 'class_type': 'VAEDecode'},
        '9': {'inputs': {'filename_prefix': prefix, 'images': ['18',0]}, 'class_type': 'SaveImage'},
        '14': {'inputs': {'image': img_rel}, 'class_type': 'LoadImage'},
        '15': {'inputs': {'pixels': ['14',0], 'vae': ['3',0]}, 'class_type': 'VAEEncode'},
        '16': {'inputs': {'image': mask_rel, 'channel': 'red'}, 'class_type': 'LoadImageMask'},
        '17': {'inputs': {'samples': ['15',0], 'mask': ['16',0]}, 'class_type': 'SetLatentNoiseMask'},
        '18': {'inputs': {'destination': ['14',0], 'source': ['8',0], 'x': 0, 'y': 0, 'resize_source': False, 'mask': ['16',0]}, 'class_type': 'ImageCompositeMasked'},
    }

def log(s): print(time.strftime('%Y-%m-%d %H:%M:%S'), s, flush=True)
def post_json(path,payload):
    req=request.Request(COMFY+path, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    with request.urlopen(req, timeout=30) as r:
        body=r.read().decode(); return json.loads(body) if body else {}
def get_json(path):
    with request.urlopen(COMFY+path, timeout=30) as r: return json.loads(r.read().decode())
def stage(src,name):
    d=INPUT_DIR/TASK; d.mkdir(parents=True,exist_ok=True); dst=d/name; shutil.copy2(src,dst); return f'{TASK}/{name}'
def output_from_history(pid):
    hist=get_json('/history/'+pid)
    if pid not in hist: return None, None
    item=hist[pid]; outs=[]
    for node_out in item.get('outputs',{}).values():
        for key in ('images','videos','gifs','files'):
            vals=node_out.get(key,[]) or []
            if isinstance(vals,bool): continue
            for v in vals:
                if isinstance(v,dict) and v.get('filename'):
                    p=OUTPUT_DIR/v.get('subfolder','')/v['filename'] if v.get('type','output')=='output' else OUTPUT_DIR/v['filename']
                    outs.append(p)
    existing=[p for p in outs if p.exists()]
    return (existing[0] if existing else None), item.get('status',{})
def submit_wait(w,label):
    pid=post_json('/prompt', {'prompt': w, 'client_id': str(uuid.uuid4())})['prompt_id']
    log(f'{label} submitted prompt_id={pid}')
    start=time.time(); last=-1
    while True:
        out,status=output_from_history(pid)
        if out:
            log(f'{label} completed output={out} status={status}')
            return out
        m=int((time.time()-start)//60)
        if m!=last:
            q=get_json('/queue'); log(f'{label} waiting {m}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}')
            last=m
        time.sleep(5)
def make_sheet(paths):
    tmp=Path('/tmp/louise_small_explosion_variants_sheet'); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    for i,p in enumerate(paths,1):
        shutil.copy2(p, tmp/f'v{i:02d}.png')
    sheet=G/'louise_small_explosion_right_inpaint_variants_v01-v06_contact.jpg'
    subprocess.check_call(['ffmpeg','-y','-pattern_type','glob','-i',str(tmp/'*.png'),'-vf','scale=192:-1,tile=3x2:padding=8:margin=8','-frames:v','1',str(sheet)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sheet

def main():
    img_rel=stage(GUIDE,'guide.png')
    mask_rel=stage(MASK,'mask.png')
    outputs=[]
    for i,seed in enumerate(SEEDS,1):
        prefix=f'louise_small_explosion_right_inpaint_variant_v{i:02d}_seed{seed}'
        out=submit_wait(workflow(img_rel, mask_rel, seed, prefix), f'v{i:02d}')
        dst=G/f'{prefix}.png'
        shutil.copy2(out,dst); outputs.append(dst)
        print('MEDIA:'+str(dst), flush=True)
    sheet=make_sheet(outputs)
    print('MEDIA:'+str(sheet), flush=True)
if __name__=='__main__': main()
