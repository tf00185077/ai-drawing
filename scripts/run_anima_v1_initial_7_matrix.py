#!/usr/bin/env python3
"""Historical resumable runner for the initial 7-condition/21-image Anima V1 matrix.

This captures the first evaluation pass and intentionally does not include the
later Epoch 2 supplement. The authoritative final 8-condition/24-image record
is stored on the external volume as
``style_shampoohatslime-first50-anima-v1-matrix-jobs-final-8-conditions.json``.
"""
import json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://127.0.0.1:8001"
OUT = Path("/Volumes/AI-Drawing-16T/ai-drawing/training/lora/output/style_shampoohatslime-first50-anima-v1-matrix-jobs.json")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
NEG = "child, loli, nude, nipples, explicit, suggestive pose, worst quality, bad quality, lowres, displeasing, bad anatomy, bad hands, extra digits, fewer digits, missing fingers, malformed feet, blurry, signature, watermark"
TAIL = "1girl, solo, bikini, standing, full body, beach, ocean, outdoors, day, from above, looking at viewer, masterpiece, best quality, amazing quality, very aesthetic, absurdres"
CHARS = {"emma":"emma_verde", "karin":"asaka_karin", "kanata":"konoe_kanata"}
CONDS = [
 ("01_base_connexion", None, None, True),
 ("02_e4_070_connexion", "style_shampoohatslime-first50-anima-v1-000004.safetensors", 0.7, True),
 ("03_e6_070_connexion", "style_shampoohatslime-first50-anima-v1-000006.safetensors", 0.7, True),
 ("04_final_050_connexion", "style_shampoohatslime-first50-anima-v1.safetensors", 0.5, True),
 ("05_final_070_connexion", "style_shampoohatslime-first50-anima-v1.safetensors", 0.7, True),
 ("06_final_100_connexion", "style_shampoohatslime-first50-anima-v1.safetensors", 1.0, True),
 ("07_final_070_notrigger", "style_shampoohatslime-first50-anima-v1.safetensors", 0.7, False),
]

def now(): return datetime.now(timezone.utc).isoformat()
def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type":"application/json"})
    with opener.open(req, timeout=30) as r:
        return json.loads(r.read())
def save(m):
    m["updated_at"] = now()
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)

if OUT.exists():
    m = json.loads(OUT.read_text(encoding="utf-8"))
else:
    m = {"schema_version":1,"created_at":now(),"jobs":{},"results":{},"settings":{}}

m["settings"] = {
 "diffusion_model":"anima_baseV10.safetensors", "text_encoder":"anima_baseV10_txt.safetensors", "vae":"qwen_image_vae.safetensors",
 "seed":3174638636,"steps":30,"cfg":5.5,"sampler_name":"dpmpp_2m","scheduler":"normal","denoise":1.0,
 "width":1448,"height":2048,"batch_size":1,"negative_prompt":NEG,
 "architecture_adaptation":"Illustrious CheckpointLoaderSimple/LoraLoader 改為 Anima UNETLoader/CLIPLoader/VAELoader；Anima LoRA 使用 LoraLoaderModelOnly。內容與採樣條件不變。"
}
# Seed the two jobs submitted through MCP before this resumable runner.
m["jobs"].setdefault("01_base_connexion_emma", "48481af6-9ece-4c9c-8322-ea2f8c646390")
m["jobs"].setdefault("02_e4_070_connexion_emma", "f34f8cc6-074f-4dd5-8e4f-aff261a84e22")
save(m)

for cond, lora, strength, trigger in CONDS:
  for short, char in CHARS.items():
    label=f"{cond}_{short}"
    prompt=("connexion, " if trigger else "") + char + ", " + TAIL
    m.setdefault("effective",{})[label]={"condition":cond,"character":short,"character_tag":char,"prompt":prompt,"negative_prompt":NEG,"trigger":"connexion" if trigger else None,"lora":lora,"lora_strength":strength}
    if label in m["jobs"]: continue
    payload={"prompt":prompt,"negative_prompt":NEG,"seed":3174638636,"seed_mode":"fixed","use_workflow_defaults":False,
      "steps":30,"cfg":5.5,"width":1448,"height":2048,"batch_size":1,"sampler_name":"dpmpp_2m","scheduler":"normal","denoise":1.0,
      "diffusion_model":"anima_baseV10.safetensors","text_encoder":"anima_baseV10_txt.safetensors","vae":"qwen_image_vae.safetensors"}
    if lora:
      payload.update({"template":"gen_txt2img_anima_lora_model_only","lora":lora,"lora_strength":strength})
    else:
      payload["template"]="anima"
    while True:
      try:
        resp=request("POST","/api/generate/",payload)
        m["jobs"][label]=resp["job_id"]
        m["results"][label]={"status":"queued","job_id":resp["job_id"],"submitted_payload":payload}
        print("SUBMITTED",label,resp["job_id"],flush=True); save(m); break
      except urllib.error.HTTPError as e:
        detail=e.read().decode(errors="replace")
        if e.code==503:
          print("QUEUE_FULL",label,detail,flush=True); time.sleep(20); continue
        raise

terminal={"completed","failed","cancelled"}
while True:
  counts={}
  remaining=0
  for label,jid in list(m["jobs"].items()):
    try:
      st=request("GET",f"/api/generate/job/{jid}")
      status=st.get("status","unknown")
      old=m["results"].get(label,{})
      submitted=old.get("submitted_payload")
      m["results"][label]=st
      if submitted is not None: m["results"][label]["submitted_payload"]=submitted
    except Exception as e:
      status="poll_error"; m["results"].setdefault(label,{})["poll_error"]=repr(e)
    counts[status]=counts.get(status,0)+1
    if status not in terminal: remaining+=1
  m["summary"]=counts; save(m)
  print(now(),counts,flush=True)
  if remaining==0: break
  time.sleep(20)

failed=[k for k,v in m["results"].items() if v.get("status")!="completed"]
print("DONE failed=",failed,flush=True)
raise SystemExit(1 if failed else 0)
