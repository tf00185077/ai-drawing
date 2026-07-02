#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
SOURCE='2026-06-30/louise_frame01_source_clean_thin_wand_img2img_cand02_00001_2c32ca1c_0.png'
STYLE_PROMPT=(
"masterpiece, best quality, score_7, safe, PosingDynamicsDaal, airy watercolor anime illustration, soft pastel gradient wash, "
"translucent watercolor blooms, wet-on-wet color bleeding, fine paint speckles, delicate ink-like edge accents, dreamy high-key lighting, clean elegant composition"
)
CONTENT_PROMPT=(
"use the source image as the base composition, preserve the small full-body Louise in the lower-left corner, preserve pose and character scale, only one character, no extra people, no objects near feet, "
"Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, long wavy pink hair, black headband, academy uniform, matching knee-high socks, right hand holding a small short thin brown magic wand, left hand empty, "
"improve the background castle into a cleaner animation-style cartoon European castle, anime background art, crisp cel-animation castle shapes, complete large castle across the frame, pointed spire towers, stone walls, rooftops, arched windows, castle much larger than character, "
"make her eyes more detailed and expressive, detailed pink anime eyes, sharper eye highlights, clearer eyelashes, refined face details, while keeping the whole character small and full body"
)
POS=f"{STYLE_PROMPT}, {CONTENT_PROMPT}, watercolor wash background, clean open scene"
NEG=(
"extra person, second character, small figure, tiny person near feet, mascot, animal, doll, object near feet, black blob, silhouette, duplicate character, multiple people, foreground object, "
"long staff, walking stick, cane, baton, club, rod, thick stick, long stick, pole, branch, forked wand, ornate wand, gem wand, glowing wand, sword, left hand holding wand, both hands holding wand, "
"changed pose, raised arm, character too large, centered character, close-up, upper body, cropped feet, front view, back view, explosion, magic effect, night sky, cropped castle, incomplete castle, modern building, photorealistic, text, watermark, logo, low quality"
)

def workflow(prefix,prompt,negative,seed,denoise):
    return {
      "1":{"class_type":"UNETLoader","inputs":{"unet_name":"anima_preview3Base.safetensors","weight_dtype":"default"}},
      "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_06b_base.safetensors","type":"qwen_image","device":"default"}},
      "3":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
      "14":{"class_type":"LoadImage","inputs":{"image":"source.png"}},
      "16":{"class_type":"ImageScale","inputs":{"image":["14",0],"upscale_method":"lanczos","width":W,"height":H,"crop":"disabled"}},
      "4":{"class_type":"VAEEncode","inputs":{"pixels":["16",0],"vae":["3",0]}},
      "5":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["2",0]}},
      "6":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["2",0]}},
      "10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.62}},
      "7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":26,"cfg":4.9,"sampler_name":"er_sde","scheduler":"simple","denoise":denoise,"model":["10",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
      "9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}},
    }

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
for i,(seed,denoise) in enumerate([(27063901,0.34),(27063902,0.40),(27063903,0.46)],1):
    prefix=f'louise_frame01_base_b2_animecastle_detailedeyes_cand{i:02d}'
    payload={'workflow':workflow(prefix,POS,NEG,seed,denoise),'prompt':POS,'negative_prompt':NEG,'seed':seed,'steps':26,'cfg':4.9,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','denoise':denoise,'lora':'posing-dynamics-anima.safetensors','lora_strength':0.62,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image':SOURCE}
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
