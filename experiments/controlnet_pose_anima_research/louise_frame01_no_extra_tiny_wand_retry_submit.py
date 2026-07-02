#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
POSE='2026-06-30/louise_pose_skeleton_frame01_down_small_clean_no_wand_drawn.png'
STYLE_PROMPT=("masterpiece, best quality, score_7, safe, PosingDynamicsDaal, airy watercolor anime illustration, soft pastel gradient wash, translucent watercolor blooms, wet-on-wet color bleeding, fine paint speckles, delicate ink-like edge accents, dreamy high-key lighting, clean elegant composition")
CONTENT_PROMPT=(
"single full-body Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, no other characters, no mascot, no animal, no doll, no object near her feet, clean empty ground around her feet, "
"petite teenage anime girl, long wavy pink hair, pink eyes, black headband, academy uniform, white blouse, black capelet, pleated skirt, matching knee-high socks, shoes, "
"very small character in lower left corner, full body head-to-toe visible, three-quarter side view, character occupies no more than two cells of a 3x3 grid, wide establishing shot, "
"right hand holds a tiny short thin brown magic wand, pencil-thin short wand, subtle small wand, not a staff, not a stick, no branches, no decoration, left hand empty, both arms lowered, "
"only background is a large cartoon European castle, huge complete castle across the full frame, pointed spire towers, stone walls, rooftops, arched windows, castle much larger than character"
)
POS=f"{STYLE_PROMPT}, {CONTENT_PROMPT}, pastel watercolor wash background, clean open scene"
NEG=(
"extra person, second character, child, chibi, mascot, small figure, tiny person, animal, doll, object near feet, black blob, shadow figure, silhouette, crowd, duplicate character, multiple people, foreground object, "
"long staff, wooden staff, walking stick, cane, baton, club, rod, thick stick, long stick, pole, spear, branch, forked wand, ornate wand, gem wand, glowing wand, sword, second wand, left hand holding wand, both hands holding wand, no wand, "
"character too large, centered character, close-up, upper body, cropped feet, front view, back view, raised arm, explosion, magic effect, cropped castle, incomplete castle, modern building, text, watermark, logo, photorealistic, worst quality, low quality"
)

def workflow(prefix,prompt,negative,seed):
    return {"1":{"class_type":"UNETLoader","inputs":{"unet_name":"anima_preview3Base.safetensors","weight_dtype":"default"}},"2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_06b_base.safetensors","type":"qwen_image","device":"default"}},"3":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},"4":{"class_type":"EmptySD3LatentImage","inputs":{"width":W,"height":H,"batch_size":1}},"5":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["2",0]}},"6":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["2",0]}},"10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.62}},"14":{"class_type":"LoadImage","inputs":{"image":"pose.png"}},"15":{"class_type":"AnimaLLLiteApply","inputs":{"model":["10",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["14",0],"strength":1.75,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True}},"7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":30,"cfg":5.1,"sampler_name":"er_sde","scheduler":"simple","denoise":1.0,"model":["15",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},"8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},"9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}}}

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
for i,seed in enumerate([27063701,27063702,27063703],1):
    prefix=f'louise_frame01_no_extra_tiny_wand_retry_cand{i:02d}'
    payload={'workflow':workflow(prefix,POS,NEG,seed),'prompt':POS,'negative_prompt':NEG,'seed':seed,'steps':30,'cfg':5.1,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','lora':'posing-dynamics-anima.safetensors','lora_strength':0.62,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image_pose':POSE}
    res=post('/api/generate/custom', payload); print('SUBMITTED',i,res,flush=True); jobs.append((i,res['job_id'])); time.sleep(.5)
remaining={j[1]:j for j in jobs}; completed=[]
while remaining:
    for job_id,j in list(remaining.items()):
        st=get('/api/generate/job/'+job_id); print('STATUS',j[0],st,flush=True)
        if st.get('status') in ('completed','failed'):
            completed.append((j,st)); del remaining[job_id]
    if remaining: time.sleep(90)
print('COMPLETED_JSON')
print(json.dumps({'jobs':jobs,'completed':completed}, ensure_ascii=False, indent=2))
