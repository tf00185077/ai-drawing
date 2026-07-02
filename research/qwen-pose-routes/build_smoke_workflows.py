#!/usr/bin/env python3
import json
from pathlib import Path
base = Path(__file__).resolve().parent

route_b = {
  "37": {"class_type":"UNETLoader","inputs":{"unet_name":"qwen_image_fp8_e4m3fn.safetensors","weight_dtype":"default"},"_meta":{"title":"Load Qwen Image FP8"}},
  "38": {"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_2.5_vl_7b_fp8_scaled.safetensors","type":"qwen_image","device":"default"},"_meta":{"title":"Load Qwen text encoder"}},
  "39": {"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"},"_meta":{"title":"Load Qwen VAE"}},
  "69": {"class_type":"LoraLoaderModelOnly","inputs":{"model":["37",0],"lora_name":"qwen_image_union_diffsynth_lora.safetensors","strength_model":1.0},"_meta":{"title":"Qwen Union DiffSynth OpenPose LoRA"}},
  "79": {"class_type":"LoraLoaderModelOnly","inputs":{"model":["69",0],"lora_name":"Qwen-Image-Lightning-8steps-V1.1.safetensors","strength_model":1.0},"_meta":{"title":"Qwen Image Lightning 8 steps"}},
  "66": {"class_type":"ModelSamplingAuraFlow","inputs":{"model":["79",0],"shift":4.0},"_meta":{"title":"ModelSamplingAuraFlow"}},
  "6": {"class_type":"CLIPTextEncode","inputs":{"clip":["38",0],"text":"full body anime character standing in a dynamic asymmetrical pose, clean linework, detailed clothing, simple background"},"_meta":{"title":"Positive"}},
  "7": {"class_type":"CLIPTextEncode","inputs":{"clip":["38",0],"text":""},"_meta":{"title":"Negative"}},
  "73": {"class_type":"LoadImage","inputs":{"image":"anima_lllite_pose_ref_asym_832x1216.png"},"_meta":{"title":"Pose reference image"}},
  "98": {"class_type":"DWPreprocessor","inputs":{"image":["73",0],"detect_hand":"enable","detect_body":"enable","detect_face":"enable","resolution":1024,"bbox_detector":"yolox_l.onnx","pose_estimator":"dw-ll_ucoco_384_bs5.torchscript.pt","scale_stick_for_xinsr_cn":"disable"},"_meta":{"title":"DWPose Estimator"}},
  "77": {"class_type":"ImageScaleToTotalPixels","inputs":{"image":["98",0],"upscale_method":"lanczos","megapixels":1.0,"resolution_steps":0},"_meta":{"title":"Scale pose image"}},
  "72": {"class_type":"VAEEncode","inputs":{"pixels":["77",0],"vae":["39",0]},"_meta":{"title":"Encode pose/reference latent"}},
  "70": {"class_type":"ReferenceLatent","inputs":{"conditioning":["6",0],"latent":["72",0]},"_meta":{"title":"Positive reference latent"}},
  "71": {"class_type":"ReferenceLatent","inputs":{"conditioning":["7",0],"latent":["72",0]},"_meta":{"title":"Negative reference latent"}},
  "3": {"class_type":"KSampler","inputs":{"model":["66",0],"seed":347241068574736,"steps":10,"cfg":1.0,"sampler_name":"euler","scheduler":"simple","positive":["70",0],"negative":["71",0],"latent_image":["72",0],"denoise":1.0},"_meta":{"title":"KSampler"}},
  "8": {"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["39",0]},"_meta":{"title":"Decode"}},
  "60": {"class_type":"SaveImage","inputs":{"images":["8",0],"filename_prefix":"qwen_route_b_union_openpose_smoke"},"_meta":{"title":"Save"}}
}

prompt_c = "Make the person in image 1 do the exact same pose of the person in image 2. Changing the style and background of the image of the person in image 1 is undesirable, so don't do it. The new pose should be pixel accurate to the pose we are trying to copy. The position of the arms and head and legs should be the same as the pose we are trying to copy. Change the field of view and angle to match exactly image 2. Head tilt and eye gaze pose should match the person in image 2."
route_c = {
  "1": {"class_type":"LoadImage","inputs":{"image":"subject.png"},"_meta":{"title":"Image 1 subject"}},
  "2": {"class_type":"LoadImage","inputs":{"image":"pose.png"},"_meta":{"title":"Image 2 pose reference"}},
  "146": {"class_type":"VAELoader","inputs":{"vae_name":"qwen_image_vae.safetensors"}},
  "161": {"class_type":"UNETLoader","inputs":{"unet_name":"qwen_image_edit_2511_fp8mixed.safetensors","weight_dtype":"default"}},
  "162": {"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_2.5_vl_7b_fp8_scaled.safetensors","type":"qwen_image","device":"default"}},
  "160": {"class_type":"FluxKontextImageScale","inputs":{"image":["1",0]}},
  "151": {"class_type":"TextEncodeQwenImageEditPlus","inputs":{"clip":["162",0],"vae":["146",0],"image1":["160",0],"image2":["2",0],"prompt":prompt_c}},
  "149": {"class_type":"TextEncodeQwenImageEditPlus","inputs":{"clip":["162",0],"vae":["146",0],"image1":["160",0],"image2":["2",0],"prompt":""}},
  "148": {"class_type":"FluxKontextMultiReferenceLatentMethod","inputs":{"conditioning":["151",0],"reference_latents_method":"index_timestep_zero"}},
  "147": {"class_type":"FluxKontextMultiReferenceLatentMethod","inputs":{"conditioning":["149",0],"reference_latents_method":"index_timestep_zero"}},
  "145": {"class_type":"ModelSamplingAuraFlow","inputs":{"model":["161",0],"shift":3.1}},
  "152": {"class_type":"CFGNorm","inputs":{"model":["145",0],"strength":1.0}},
  "153": {"class_type":"LoraLoaderModelOnly","inputs":{"model":["152",0],"lora_name":"2511-AnyPose-base-000006250.safetensors","strength_model":0.7}},
  "154": {"class_type":"LoraLoaderModelOnly","inputs":{"model":["153",0],"lora_name":"2511-AnyPose-helper-00006000.safetensors","strength_model":0.7}},
  "155": {"class_type":"LoraLoaderModelOnly","inputs":{"model":["154",0],"lora_name":"Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors","strength_model":1.0}},
  "156": {"class_type":"VAEEncode","inputs":{"pixels":["160",0],"vae":["146",0]}},
  "169": {"class_type":"KSampler","inputs":{"model":["155",0],"seed":25110001,"steps":4,"cfg":1.0,"sampler_name":"euler","scheduler":"simple","positive":["148",0],"negative":["147",0],"latent_image":["156",0],"denoise":1.0}},
  "158": {"class_type":"VAEDecode","inputs":{"samples":["169",0],"vae":["146",0]}},
  "9": {"class_type":"SaveImage","inputs":{"images":["158",0],"filename_prefix":"qwen_route_c_edit2511_anypose_smoke"}}
}

(base / 'route-b-api-smoke.json').write_text(json.dumps(route_b, ensure_ascii=False, indent=2))
(base / 'route-c-api-smoke.json').write_text(json.dumps(route_c, ensure_ascii=False, indent=2))
print(base / 'route-b-api-smoke.json')
print(base / 'route-c-api-smoke.json')
