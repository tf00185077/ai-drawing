#!/usr/bin/env python3
import copy
import json
import shutil
import time
import urllib.request
from pathlib import Path

HOST = 'http://127.0.0.1:8188'
ROOT = Path('/Users/tf00185088/Desktop/ai-drawing')
EXP = ROOT / 'experiments/controlnet_inpaint_template_research/anima_img2img_fourth_test'
COMFY_INPUT = Path('/Users/tf00185088/comfyui/input')
COMFY_OUTPUT = Path('/Users/tf00185088/comfyui/output')
COMFY_TEMP = Path('/Users/tf00185088/comfyui/temp')
SRC = ROOT / 'outputs/gallery/2026-06-26/anima_lora_test_00036_e86e7595_9.png'
BASE = json.loads((ROOT / 'backend/workflows/gen_txt2img_anima_lora_model_only.json').read_text())
EXP.mkdir(parents=True, exist_ok=True)

PROMPT = (
    'masterpiece, best quality, score_7, safe, PosingDynamicsDaal, '
    'Asuka Langley Soryu from Evangelion, 1girl, solo, full body, entire body in frame, head-to-toe, '
    'red plugsuit, orange hair, blue eyes, hair clips, confident expression, dynamic standing pose, '
    'clean character silhouette, preserve original full-body composition, refined anime lineart, '
    'airy watercolor anime illustration, translucent watercolor blooms, wet-on-wet color bleeding, '
    'soft pastel gradient wash, luminous backlit silhouette, floating petals, broad white negative space'
)
NEG = (
    'worst quality, low quality, score_1, score_2, score_3, cropped body, cropped head, cropped feet, '
    'feet out of frame, legs out of frame, close-up, portrait crop, out of frame, bad anatomy, deformed hands, '
    'extra fingers, extra limbs, broken legs, distorted face, muddy colors, photorealistic, text, watermark, logo'
)

def jget(path, timeout=30):
    with urllib.request.urlopen(HOST + path, timeout=timeout) as r:
        return json.load(r)

def jpost(path, obj, timeout=60):
    req = urllib.request.Request(HOST + path, data=json.dumps(obj).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or '{}')

def collect(item, prefix):
    out=[]
    for node_out in (item.get('outputs') or {}).values():
        for img in node_out.get('images') or []:
            if not isinstance(img, dict) or 'filename' not in img:
                continue
            base = COMFY_OUTPUT if (img.get('type') or 'output') == 'output' else COMFY_TEMP
            p = base / str(img.get('subfolder') or '') / str(img['filename'])
            if p.exists(): out.append(str(p))
    if not out:
        out=[str(p) for p in sorted(COMFY_OUTPUT.rglob(prefix+'*.png'), key=lambda p:p.stat().st_mtime, reverse=True)[:3]]
    return out

def wait(pid):
    start=time.time()
    while True:
        hist=jget(f'/history/{pid}', 30)
        if pid in hist:
            return hist[pid], round(time.time()-start, 1)
        q=jget('/queue', 20)
        print('elapsed', int(time.time()-start), 'running', [x[1] for x in q.get('queue_running', [])], 'pending', [x[1] for x in q.get('queue_pending', [])], flush=True)
        time.sleep(20)

def make_workflow():
    dst = COMFY_INPUT / 'anima_img2img_fourth_input.png'
    shutil.copy2(SRC, dst)
    wf = copy.deepcopy(BASE)
    wf.pop('4', None)
    wf['14'] = {'class_type':'LoadImage','inputs':{'image':dst.name},'_meta':{'title':'Load fourth generated image'}}
    wf['15'] = {'class_type':'VAEEncode','inputs':{'pixels':['14',0],'vae':['3',0]},'_meta':{'title':'Encode input image'}}
    wf['5']['inputs']['text'] = PROMPT
    wf['6']['inputs']['text'] = NEG
    wf['7']['inputs'].update({
        'seed': 2606260401,
        'steps': 18,
        'cfg': 4.5,
        'sampler_name': 'er_sde',
        'scheduler': 'simple',
        'denoise': 0.35,
        'latent_image': ['15', 0],
    })
    wf['10']['inputs']['lora_name'] = 'posing-dynamics-anima.safetensors'
    wf['10']['inputs']['strength_model'] = 0.65
    wf['1']['inputs']['unet_name'] = 'anima_preview3Base.safetensors'
    wf['2']['inputs']['clip_name'] = 'qwen_3_06b_base.safetensors'
    wf['3']['inputs']['vae_name'] = 'qwen_image_vae.safetensors'
    wf['9']['inputs']['filename_prefix'] = 'anima_img2img_fourth_d035'
    return wf

def main():
    q=jget('/queue')
    if q.get('queue_running') or q.get('queue_pending'):
        raise SystemExit(f'queue not empty: {q}')
    wf=make_workflow()
    api=EXP/'anima_img2img_fourth_d035_api.json'
    api.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
    resp=jpost('/prompt', {'prompt':wf, 'client_id':'anima-img2img-fourth-d035'}, 60)
    pid=resp['prompt_id']
    print('submitted', pid, resp, flush=True)
    item, elapsed = wait(pid)
    status=item.get('status',{}).get('status_str')
    rec={'prompt_id':pid,'api':str(api),'status':status,'elapsed_seconds':elapsed,'outputs':collect(item,'anima_img2img_fourth_d035'),'messages':item.get('status',{}).get('messages',[])}
    (EXP/'result.json').write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    try:
        jpost('/free', {'unload_models':True,'free_memory':True}, 30)
    except Exception as e:
        print('free warn', repr(e), flush=True)
    print(json.dumps(rec, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
