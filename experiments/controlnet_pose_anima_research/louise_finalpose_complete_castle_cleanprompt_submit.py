#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
POSE='2026-06-30/louise_smaller_thin_wand_handle_pose_ref.png'

# Clean prompt: only the necessary requirements, no duplicated/contradictory style stacks.
POS=(
"watercolor anime illustration, clean linework, full body Louise Françoise Le Blanc de La Vallière, "
"petite girl with long wavy pink hair, pink eyes, black headband, white academy blouse, black capelet, pleated skirt, matching knee-high socks, shoes, "
"small character placed on the right side of the image, occupying the right-middle and right-bottom thirds only, left and center kept for background, "
"standing in a calm neutral pose, both arms hanging down, one lowered hand holding a thin straight brown wooden wand with a simple plain grip handle, the other lowered hand empty, "
"fixed three-quarter side view facing left, complete head-to-toe visible, zoomed out long shot, "
"complete European medieval castle background, full castle visible behind her, pointed spire towers, stone walls, rooftops, arched windows, castle fills left and center background, daylight sky"
)
NEG=(
"close-up, upper body, cropped body, cropped legs, cropped feet, character centered, character too large, raised arm, spell casting, explosion, magic effect, "
"mismatched socks, bare legs, thighhighs, ornate wand, curved wand, thick wand, branch wand, gem wand, glowing wand, staff, sword, second wand, "
"extra arms, extra hands, bad hands, duplicate character, multiple people, incomplete castle, cropped castle, modern building, night sky, text, watermark, logo, low quality"
)

def workflow(prefix,prompt,negative,seed):
    return {
      "1":{"class_type":"UNETLoader","inputs":{"unet_name":"anima_preview3Base.safetensors","weight_dtype":"default"}},
      "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_06b_base.safetensors","type":"qwen_image","device":"default"}},
      "3":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
      "4":{"class_type":"EmptySD3LatentImage","inputs":{"width":W,"height":H,"batch_size":1}},
      "5":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["2",0]}},
      "6":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["2",0]}},
      "10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.58}},
      "14":{"class_type":"LoadImage","inputs":{"image":"placeholder.png"}},
      "15":{"class_type":"AnimaLLLiteApply","inputs":{"model":["10",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["14",0],"strength":1.68,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True}},
      "7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":28,"cfg":5.0,"sampler_name":"er_sde","scheduler":"simple","denoise":1.0,"model":["15",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
      "9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}},
    }

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
# Near the liked C candidate, but seed variations for better complete castle.
for i,seed in enumerate([27062701,27062702,27062703],1):
    prefix=f'louise_finalpose_complete_castle_cleanprompt_cand{i:02d}'
    payload={'workflow':workflow(prefix,POS,NEG,seed),'prompt':POS,'negative_prompt':NEG,'seed':seed,'steps':28,'cfg':5.0,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','lora':'posing-dynamics-anima.safetensors','lora_strength':0.58,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image_pose':POSE}
    res=post('/api/generate/custom', payload)
    print('SUBMITTED',i,res,flush=True)
    jobs.append((i,res['job_id'])); time.sleep(.5)
remaining={j[1]:j for j in jobs}; completed=[]
while remaining:
    for job_id,j in list(remaining.items()):
        st=get('/api/generate/job/'+job_id); print('STATUS',j[0],st,flush=True)
        if st.get('status') in ('completed','failed'):
            completed.append((j,st)); del remaining[job_id]
    if remaining: time.sleep(90)
print('COMPLETED_JSON')
print(json.dumps({'jobs':jobs,'completed':completed}, ensure_ascii=False, indent=2))
