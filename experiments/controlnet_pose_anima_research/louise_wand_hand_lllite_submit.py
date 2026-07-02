#!/usr/bin/env python3
import json, time, urllib.request
BASE='http://127.0.0.1:8001'
W,H=832,1216
POS_BASE=(
"masterpiece, best quality, score_7, safe, PosingDynamicsDaal, airy watercolor anime illustration, "
"full body, complete head-to-toe character, entire body visible, feet visible, shoes visible, zoomed out camera, long shot, "
"Louise Françoise Le Blanc de La Vallière from Zero no Tsukaima, petite teenage anime girl, long wavy pink hair, pink eyes, black headband, "
"white blouse, black capelet, academy uniform, pleated skirt, "
"character fixed in the lower right of the canvas, fixed 3/4 side view facing left, consistent camera angle, consistent full body scale, consistent outfit, "
"the wand is held in the raised casting hand, wand hand only moves upward, the empty non-wand hand hangs straight down beside the body, empty hand holds nothing, "
"one raised arm only, one lowered empty arm only, watercolor silhouette style, soft pastel wash, delicate ink-like edges, broad white negative space, "
"upper left of the canvas reserved for the explosion magic target, explosion separated from the character, not a background-wide explosion"
)
NEG=(
"wand in lowered hand, wand in wrong hand, empty hand holding object, both hands holding wand, two wands, both hands raised, two raised hands, arms crossed, "
"half body, upper body, close-up, portrait, bust shot, cropped body, cropped legs, cropped feet, feet out of frame, out of frame, "
"extra arms, extra hands, missing arm, missing hand, bad hands, extra fingers, fused fingers, missing fingers, duplicate character, multiple people, "
"front view, back view, centered character, character in center, explosion behind character, full background explosion, "
"worst quality, low quality, score_1, score_2, score_3, photorealistic, harsh outlines, muddy colors, dull palette, heavy black shadows, noisy texture, cluttered background, text, watermark, logo, signature"
)
pose_files=[
('01_down','2026-06-30/louise_wand_hand_raise_pose_ref_01_01_down.png','wand hand hanging low beside the body, wand gripped in casting hand, empty opposite hand hanging down, no spell effect'),
('02_waist','2026-06-30/louise_wand_hand_raise_pose_ref_02_02_waist.png','wand hand lifted to waist level pointing toward upper left, empty opposite hand hanging down, tiny pink sparks near wand tip'),
('03_chest','2026-06-30/louise_wand_hand_raise_pose_ref_03_03_chest.png','wand hand lifted to chest height pointing toward upper left, empty opposite hand hanging down, small spell circle between wand tip and upper-left target'),
('04_diagonal','2026-06-30/louise_wand_hand_raise_pose_ref_04_04_diagonal.png','wand hand raised diagonally toward upper left, wand tip aimed at upper-left target, empty opposite hand hanging down, growing magic trail'),
('05_overhead','2026-06-30/louise_wand_hand_raise_pose_ref_05_05_overhead.png','wand hand fully raised diagonally overhead toward upper left, empty opposite hand hanging down, pink-orange explosion bloom in upper-left quadrant separated from the character'),
]

def workflow(prefix,prompt,negative,seed):
    return {
      "1":{"class_type":"UNETLoader","inputs":{"unet_name":"anima_preview3Base.safetensors","weight_dtype":"default"}},
      "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_06b_base.safetensors","type":"qwen_image","device":"default"}},
      "3":{"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
      "4":{"class_type":"EmptySD3LatentImage","inputs":{"width":W,"height":H,"batch_size":1}},
      "5":{"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["2",0]}},
      "6":{"class_type":"CLIPTextEncode","inputs":{"text":negative,"clip":["2",0]}},
      "10":{"class_type":"LoraLoaderModelOnly","inputs":{"model":["1",0],"lora_name":"posing-dynamics-anima.safetensors","strength_model":0.65}},
      "14":{"class_type":"LoadImage","inputs":{"image":"placeholder.png"}},
      "15":{"class_type":"AnimaLLLiteApply","inputs":{"model":["10",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["14",0],"strength":1.55,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True}},
      "7":{"class_type":"KSampler","inputs":{"seed":seed,"steps":28,"cfg":5.2,"sampler_name":"er_sde","scheduler":"simple","denoise":1.0,"model":["15",0],"positive":["5",0],"negative":["6",0],"latent_image":["4",0]}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["7",0],"vae":["3",0]}},
      "9":{"class_type":"SaveImage","inputs":{"filename_prefix":prefix,"images":["8",0]}},
    }

def post(path,data):
    req=urllib.request.Request(BASE+path, data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=30) as r: return json.loads(r.read().decode())

jobs=[]
for i,(label,pose,desc) in enumerate(pose_files,1):
    prompt=POS_BASE+f', keyframe {i:02d}, {desc}'
    prefix=f'louise_fullbody_wandhand_lllite_{i:02d}_{label}'
    payload={'workflow':workflow(prefix,prompt,NEG,27062100+i),'prompt':prompt,'negative_prompt':NEG,'seed':27062100+i,'steps':28,'cfg':5.2,'width':W,'height':H,'sampler_name':'er_sde','scheduler':'simple','lora':'posing-dynamics-anima.safetensors','lora_strength':0.65,'diffusion_model':'anima_preview3Base.safetensors','text_encoder':'qwen_3_06b_base.safetensors','vae':'qwen_image_vae.safetensors','image_pose':pose}
    res=post('/api/generate/custom', payload)
    print('SUBMITTED',i,label,res, flush=True)
    jobs.append((i,label,res['job_id'],pose)); time.sleep(.5)
remaining={j[2]:j for j in jobs}; completed=[]
while remaining:
    for job_id,j in list(remaining.items()):
        st=get('/api/generate/job/'+job_id)
        print('STATUS',j[0],j[1],st, flush=True)
        if st.get('status') in ('completed','failed'):
            completed.append((j,st)); del remaining[job_id]
    if remaining: time.sleep(90)
print('COMPLETED_JSON')
print(json.dumps({'jobs':jobs,'completed':completed}, ensure_ascii=False, indent=2))
