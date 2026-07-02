#!/usr/bin/env python3
import copy, json
from pathlib import Path
ROOT=Path('/Users/tf00185088/Desktop/ai-drawing')
EXP=ROOT/'experiments/controlnet_pose_anima_research'
EXP.mkdir(parents=True, exist_ok=True)
base=json.loads('''{"1": {"inputs": {"unet_name": "anima_baseV10.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader", "_meta": {"title": "Load Anima diffusion model"}}, "2": {"inputs": {"clip_name": "anima_baseV10_txt.safetensors", "type": "qwen_image", "device": "default"}, "class_type": "CLIPLoader", "_meta": {"title": "Load Anima text encoder"}}, "3": {"inputs": {"vae_name": "qwen_image_vae.safetensors"}, "class_type": "VAELoader", "_meta": {"title": "Load Qwen image VAE"}}, "4": {"inputs": {"width": 832, "height": 1216, "batch_size": 1}, "class_type": "EmptySD3LatentImage", "_meta": {"title": "Portrait latent"}}, "5": {"inputs": {"text": "", "clip": ["2", 0]}, "class_type": "CLIPTextEncode", "_meta": {"title": "Positive prompt"}}, "6": {"inputs": {"text": "", "clip": ["2", 0]}, "class_type": "CLIPTextEncode", "_meta": {"title": "Negative prompt"}}, "10": {"inputs": {"model": ["1", 0], "lora_name": "anima-highres-aesthetic-boost.safetensors", "strength_model": 0.7}, "class_type": "LoraLoaderModelOnly", "_meta": {"title": "Anima Highres/Aesthetic Boost @0.7"}}, "11": {"inputs": {"model": ["10", 0], "lora_name": "Niji Reol v1 EP11.safetensors", "strength_model": 0.8}, "class_type": "LoraLoaderModelOnly", "_meta": {"title": "NijiReol semi-realistic @0.8"}}, "12": {"inputs": {"model": ["11", 0], "lora_name": "AnimaNSS4RE.safetensors", "strength_model": 0.65}, "class_type": "LoraLoaderModelOnly", "_meta": {"title": "Niji Sweet Spot @0.65"}}, "7": {"inputs": {"seed": 2606269301, "steps": 26, "cfg": 5.0, "sampler_name": "er_sde", "scheduler": "simple", "denoise": 1.0, "model": ["12", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["4", 0]}, "class_type": "KSampler", "_meta": {"title": "KSampler"}}, "8": {"inputs": {"samples": ["7", 0], "vae": ["3", 0]}, "class_type": "VAEDecode", "_meta": {"title": "Decode"}}, "9": {"inputs": {"filename_prefix": "anima_lllite_pose_T0_no_control", "images": ["8", 0]}, "class_type": "SaveImage", "_meta": {"title": "Save"}}, "13": {"inputs": {"images": ["8", 0]}, "class_type": "PreviewImage", "_meta": {"title": "Preview"}}}''')
pos = '1girl, solo, full body, head-to-toe, orange hair, blue eyes, red futuristic plugsuit, dynamic asymmetrical standing pose, one arm raised high, one arm lowered, legs apart, clean anime illustration, detailed character, white background'
neg = 'low quality, worst quality, cropped, out of frame, close-up, portrait crop, missing feet, bad anatomy, extra limbs, extra fingers, distorted hands, multiple people, text, watermark, logo'
base['5']['inputs']['text']=pos
base['6']['inputs']['text']=neg
# T0 baseline
for name,strength in [('T0_no_control',None),('T1_pose_s10',1.0),('T2_pose_s14',1.4)]:
    wf=copy.deepcopy(base)
    wf['9']['inputs']['filename_prefix']='anima_lllite_pose_'+name
    if strength is not None:
        wf['14']={"class_type":"LoadImage","inputs":{"image":"anima_lllite_pose_ref_asym_832x1216.png"},"_meta":{"title":"Load pose reference"}}
        wf['15']={"class_type":"AnimaLLLiteApply","inputs":{"model":["12",0],"lllite_name":"anima-lllite-pose-1.safetensors","image":["14",0],"strength":strength,"start_percent":0.0,"end_percent":1.0,"preserve_wrapper":True},"_meta":{"title":f"Apply Anima pose LLLite strength {strength}"}}
        wf['7']['inputs']['model']=["15",0]
    out=EXP/(name+'.json')
    out.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
    print(out)
