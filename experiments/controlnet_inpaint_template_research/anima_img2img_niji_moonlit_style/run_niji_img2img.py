#!/usr/bin/env python3
import copy, json, shutil, time, urllib.request
from pathlib import Path

HOST='http://127.0.0.1:8188'
ROOT=Path('/Users/tf00185088/Desktop/ai-drawing')
EXP=ROOT/'experiments/controlnet_inpaint_template_research/anima_img2img_niji_moonlit_style'
COMFY_INPUT=Path('/Users/tf00185088/comfyui/input')
COMFY_OUTPUT=Path('/Users/tf00185088/comfyui/output')
COMFY_TEMP=Path('/Users/tf00185088/comfyui/temp')
SRC=ROOT/'outputs/gallery/2026-06-26/anima_lora_test_00036_e86e7595_9.png'
BASE=json.loads((ROOT/'backend/workflows/gen_txt2img_anima_lora_model_only_multi_lora.json').read_text())
EXP.mkdir(parents=True, exist_ok=True)

PROMPT=(
    'masterpiece, best quality, high-quality Anima illustration, semi-realistic anime rendering, '
    'dark cinematic color grading, moonlit atmosphere, cool blue rim lighting, deep shadow contrast, '
    'glossy highlight rendering, sharp detailed hair, polished high-resolution finish, dramatic portrait lighting, '
    'semi-realistic niji anime style, cool moonlit color palette, high-contrast glossy lighting, sharp specular highlights, '
    'Asuka Langley Soryu from Evangelion, 1girl, solo, full body, entire body in frame, head-to-toe, visible boots, '
    'red plugsuit, orange hair, blue eyes, hair clips, confident expression, clean readable full-body silhouette, '
    'preserve character identity and full-body framing, style transfer from watercolor pastel into moonlit semi-real niji anime rendering, '
    'cinematic dark background separation, refined semi-real rendering, cool blue edge light on hair and plugsuit, subtle glossy red suit highlights'
)
NEG=(
    'worst quality, low quality, score_1, score_2, score_3, artist name, flat pastel coloring, bright daytime, washed out, low contrast, '
    'black armor, sword, moon, night sky, black hair, woman, armor, medieval costume, source character, exact source pose, '
    'cropped body, cropped head, cropped feet, feet out of frame, legs out of frame, close-up, portrait crop, out of frame, '
    'bad anatomy, deformed hands, extra fingers, extra limbs, broken legs, distorted face, text, watermark, logo'
)

def jget(path, timeout=30):
    with urllib.request.urlopen(HOST+path, timeout=timeout) as r: return json.load(r)
def jpost(path, obj, timeout=60):
    req=urllib.request.Request(HOST+path, data=json.dumps(obj).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode() or '{}')
def wait(pid):
    start=time.time()
    while True:
        h=jget(f'/history/{pid}',30)
        if pid in h: return h[pid], round(time.time()-start,1)
        q=jget('/queue',20)
        print('elapsed', int(time.time()-start), 'running', [x[1] for x in q.get('queue_running',[])], 'pending', [x[1] for x in q.get('queue_pending',[])], flush=True)
        time.sleep(20)
def collect(item):
    out=[]
    for node_out in (item.get('outputs') or {}).values():
        for img in node_out.get('images') or []:
            if not isinstance(img,dict) or 'filename' not in img: continue
            base=COMFY_OUTPUT if (img.get('type') or 'output')=='output' else COMFY_TEMP
            p=base/str(img.get('subfolder') or '')/str(img['filename'])
            if p.exists(): out.append(str(p))
    save=[p for p in out if '/output/' in p]
    return save or out

def make_wf():
    dst=COMFY_INPUT/'anima_img2img_niji_input4.png'
    shutil.copy2(SRC,dst)
    wf=copy.deepcopy(BASE)
    wf.pop('4',None)
    wf['14']={'class_type':'LoadImage','inputs':{'image':dst.name},'_meta':{'title':'Load input #4'}}
    wf['15']={'class_type':'VAEEncode','inputs':{'pixels':['14',0],'vae':['3',0]},'_meta':{'title':'Encode input #4'}}
    wf['1']['inputs']['unet_name']='anima_baseV10.safetensors'
    wf['2']['inputs']['clip_name']='anima_baseV10_txt.safetensors'
    wf['3']['inputs']['vae_name']='qwen_image_vae.safetensors'
    wf['10']['inputs'].update({'lora_name':'anima-highres-aesthetic-boost.safetensors','strength_model':0.7})
    wf['11']['inputs'].update({'lora_name':'Niji Reol v1 EP11.safetensors','strength_model':0.8})
    wf['12']['inputs'].update({'lora_name':'AnimaNSS4RE.safetensors','strength_model':0.65})
    wf['5']['inputs']['text']=PROMPT
    wf['6']['inputs']['text']=NEG
    wf['7']['inputs'].update({'seed':2606266501,'steps':24,'cfg':5.0,'sampler_name':'er_sde','scheduler':'simple','denoise':0.65,'latent_image':['15',0]})
    wf['9']['inputs']['filename_prefix']='anima_img2img_niji_moonlit_d065'
    return wf

def main():
    q=jget('/queue')
    if q.get('queue_running') or q.get('queue_pending'):
        raise SystemExit(f'queue not empty: {q}')
    wf=make_wf()
    api=EXP/'niji_moonlit_img2img_d065_api.json'
    api.write_text(json.dumps(wf,ensure_ascii=False,indent=2))
    resp=jpost('/prompt',{'prompt':wf,'client_id':'niji-moonlit-img2img-d065'},60)
    pid=resp['prompt_id']
    print('submitted',pid,resp,flush=True)
    item,elapsed=wait(pid)
    rec={'prompt_id':pid,'api':str(api),'status':item.get('status',{}).get('status_str'),'elapsed_seconds':elapsed,'outputs':collect(item),'prompt':PROMPT,'negative_prompt':NEG}
    (EXP/'result.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2))
    try: jpost('/free',{'unload_models':True,'free_memory':True},30)
    except Exception as e: print('free warn',repr(e),flush=True)
    print(json.dumps(rec,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
