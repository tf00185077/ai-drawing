#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
SOURCE='2026-06-30/louise_stylepreset_lowerleft_castle_cand01_00001_dffb8397_0.png'
POSE='2026-06-30/louise_lowerleft_same_right_wand_hand_slight_raise_pose_ref.png'
STYLE_PROMPT=(
"masterpiece, best quality, score_7, safe, PosingDynamicsDaal, airy watercolor anime illustration, luminous backlit silhouette, "
"soft pastel gradient wash, cyan blue and cotton candy pink sky, warm yellow orange foreground glow, translucent watercolor blooms, wet-on-wet color bleeding, "
"fine paint speckles, floating petals, delicate ink-like edge accents, broad white negative space, dreamy high-key lighting, soft rim light, clean elegant composition"
)
CONTENT_PROMPT=(
"same composition and same complete cartoon European castle background as the reference image, Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, "
"full body petite teenage anime girl in the lower left corner, long wavy pink hair, pink eyes, black headband, academy uniform, white blouse, black capelet, pleated skirt, matching knee-high socks, "
"her right hand is the wand hand and remains the only hand holding the wand, the same right hand is slightly raised from the lowered position, "
"her left hand stays lowered and empty, short straight wood-colored wand with a plain grip handle, no branches, no forked tips, no decoration, "
"no spell effect, no explosion, complete castle visible across the whole frame"
)
STYLE_SUFFIX=("soft backlight, pastel cyan pink blue yellow palette, watercolor wash background, paint splatter particles, floating petals, luminous airy negative space, silhouette-friendly lighting")
POS=f"{STYLE_PROMPT}, {CONTENT_PROMPT}, {STYLE_SUFFIX}"
NEG=(
"worst quality, low quality, score_1, score_2, score_3, artist name, photorealistic, harsh outlines, muddy colors, dull palette, heavy black shadows, noisy texture, cluttered background, text, watermark, logo, signature, "
"changed background, different castle, missing castle, cropped castle, modern building, character centered, character too large, "
"left hand holding wand, wand switched hands, wrong hand holding wand, both hands holding wand, raised arm high, spell casting, explosion, magic effect, ornate wand, curved wand, thick wand, branch wand, forked wand, gem wand, glowing wand, staff, sword, second wand, extra arms, extra hands, bad hands, duplicate character, multiple people"
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
      "10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.65}},
      "15":{"class_type":"LoadImage","inputs":{"image":"pose.png"}},
      "17":{"class_type":"AnimaLLLiteApply","inputs":{"model":["10",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["15",0],"strength":1.55,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True}},
      "7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":24,"cfg":4.8,"sampler_name":"er_sde","scheduler":"simple","denoise":denoise,"model":["17",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
      "9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}},
    }

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
for i,(seed,denoise) in enumerate([(27063001,0.45),(27063002,0.50),(27063003,0.54)],1):
    prefix=f'louise_same_right_wand_hand_slight_raise_cand{i:02d}'
    payload={'workflow':workflow(prefix,POS,NEG,seed,denoise),'prompt':POS,'negative_prompt':NEG,'seed':seed,'steps':24,'cfg':4.8,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','denoise':denoise,'lora':'posing-dynamics-anima.safetensors','lora_strength':0.65,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image':SOURCE,'image_pose':POSE}
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
