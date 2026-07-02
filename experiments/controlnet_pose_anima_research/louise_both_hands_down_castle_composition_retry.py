#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
# Use the previously approved composition / stand pose: small character in right-middle + right-bottom grid cells.
POSE='2026-06-30/louise_small_right_wand_straight_pose_ref_01_01_down.png'
POS=(
"masterpiece, best quality, score_7, safe, PosingDynamicsDaal, airy watercolor anime illustration, clean anime linework, "
"same composition as reference pose, small full body character on the right side, character occupies only the right middle and right bottom ninth-grid cells, left side open, "
"full body, complete head-to-toe character, entire body visible, feet visible, shoes visible, zoomed out camera, long shot, "
"Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, petite teenage anime girl, long wavy pink hair, pink eyes, black headband, "
"academy uniform, white blouse, black capelet, pleated skirt, matching knee-high socks on both legs, identical knee-high socks, shoes, "
"both arms hanging down naturally, both hands lowered beside the body, one lowered hand holds a plain short straight brown wooden wand, simple unadorned twig-colored stick wand, no decoration on wand, no curve, no bending, no ornament, no gem, no glowing tip, the other lowered hand is empty and holds nothing, "
"fixed 3/4 side view facing left, calm neutral standing pose, no spell casting yet, no explosion, no magic effect, "
"complete simple European castle background, full medieval stone castle visible in the left and center background, multiple pointed spire towers, castle walls and rooftops, arched windows, coherent castle silhouette, light daytime sky, soft watercolor wash background"
)
NEG=(
"changed composition, large character, centered character, character occupying center, character too big, close-up, half body, upper body, portrait, bust shot, cropped body, cropped legs, cropped feet, feet out of frame, out of frame, "
"different socks, mismatched socks, thighhighs, stockings, bare legs, socks missing, raised hand, raised arm, casting pose, magic, explosion, blast, spell circle, glowing wand, ornate wand, curved wand, bent wand, long staff, decorated staff, gem wand, two wands, "
"empty hand holding object, both hands holding wand, extra arms, extra hands, bad hands, extra fingers, fused fingers, missing fingers, duplicate character, multiple people, front view, back view, "
"night, dark night sky, stars, modern building, incomplete background, cropped castle, cluttered background, photorealistic, worst quality, low quality, text, watermark, logo, signature"
)

def workflow(prefix,prompt,negative,seed):
    return {
      "1":{"class_type":"UNETLoader","inputs":{"unet_name":"anima_preview3Base.safetensors","weight_dtype":"default"}},
      "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_06b_base.safetensors","type":"qwen_image","device":"default"}},
      "3":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
      "4":{"class_type":"EmptySD3LatentImage","inputs":{"width":W,"height":H,"batch_size":1}},
      "5":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["2",0]}},
      "6":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["2",0]}},
      "10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.60}},
      "14":{"class_type":"LoadImage","inputs":{"image":"placeholder.png"}},
      "15":{"class_type":"AnimaLLLiteApply","inputs":{"model":["10",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["14",0],"strength":1.62,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True}},
      "7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":28,"cfg":5.15,"sampler_name":"er_sde","scheduler":"simple","denoise":1.0,"model":["15",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
      "9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}},
    }

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
for i,seed in enumerate([27062401,27062402],1):
    prompt=POS+f", candidate {i}, preserve previous approved standing composition"
    prefix=f'louise_same_composition_castle_complete_cand{i:02d}'
    payload={'workflow':workflow(prefix,prompt,NEG,seed),'prompt':prompt,'negative_prompt':NEG,'seed':seed,'steps':28,'cfg':5.15,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','lora':'posing-dynamics-anima.safetensors','lora_strength':0.60,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image_pose':POSE}
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
