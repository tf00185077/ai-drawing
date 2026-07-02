#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
POSE='2026-06-30/louise_pose_skeleton_frame01_down_tiny_short_thin_wand.png'
STYLE_PROMPT=(
"masterpiece, best quality, score_7, safe, PosingDynamicsDaal, airy watercolor anime illustration, soft pastel gradient wash, "
"translucent watercolor blooms, wet-on-wet color bleeding, fine paint speckles, delicate ink-like edge accents, dreamy high-key lighting, soft rim light, clean elegant composition"
)
CONTENT_PROMPT=(
"only one character in the image, no extra people, no silhouettes, no shadow figures, Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, "
"petite teenage anime girl, long wavy pink hair, pink eyes, black headband, academy uniform, white blouse, black capelet, pleated skirt, matching knee-high socks, shoes, "
"tiny full body, complete head-to-toe visible, three-quarter side view, very small character in the lower left corner, character occupies no more than two cells of a 3x3 grid, wide establishing shot, "
"right hand holds a short thin magic wand, pencil-thin wand, small slender wood-colored wand, short wand about the length of her forearm, tiny plain grip handle, no branches, no forked tip, no decoration, left hand empty, both arms lowered naturally, "
"large cartoon style European castle background only, huge complete European castle visible across the full frame, castle much larger than character, pointed spire towers, stone walls, rooftops, arched windows, full scene composition"
)
STYLE_SUFFIX="pastel cyan pink blue yellow palette, watercolor wash background, luminous airy negative space, clean open scene"
POS=f"{STYLE_PROMPT}, {CONTENT_PROMPT}, {STYLE_SUFFIX}"
NEG=(
"extra person, second character, silhouette person, black silhouette, black human shape, shadow figure, foreground silhouette, dark blob, black blob, crowd, duplicate character, multiple people, "
"left hand holding wand, wand switched hands, wrong hand holding wand, both hands holding wand, no wand, long wand, staff, magic staff, wooden staff, walking stick, cane, baton, club, rod, thick rod, thick stick, long stick, pole, spear, branch wand, forked wand, ornate wand, curved wand, gem wand, glowing wand, sword, second wand, "
"character centered, character too large, close-up, upper body, cropped body, cropped feet, portrait, front view, back view, raised arm, spell casting, explosion, magic effect, night sky, small castle, cropped castle, incomplete castle, modern building, cluttered background, text, watermark, logo, signature, photorealistic, worst quality, low quality"
)

def workflow(prefix,prompt,negative,seed):
    return {
      "1":{"class_type":"UNETLoader","inputs":{"unet_name":"anima_preview3Base.safetensors","weight_dtype":"default"}},
      "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_06b_base.safetensors","type":"qwen_image","device":"default"}},
      "3":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
      "4":{"class_type":"EmptySD3LatentImage","inputs":{"width":W,"height":H,"batch_size":1}},
      "5":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["2",0]}},
      "6":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["2",0]}},
      "10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.65}},
      "14":{"class_type":"LoadImage","inputs":{"image":"pose.png"}},
      "15":{"class_type":"AnimaLLLiteApply","inputs":{"model":["10",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["14",0],"strength":1.9,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True}},
      "7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":30,"cfg":5.35,"sampler_name":"er_sde","scheduler":"simple","denoise":1.0,"model":["15",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
      "9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}},
    }

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
for i,seed in enumerate([27063601,27063602,27063603],1):
    prefix=f'louise_frame01_short_thin_magic_wand_cand{i:02d}'
    payload={'workflow':workflow(prefix,POS,NEG,seed),'prompt':POS,'negative_prompt':NEG,'seed':seed,'steps':30,'cfg':5.35,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','lora':'posing-dynamics-anima.safetensors','lora_strength':0.65,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image_pose':POSE}
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
