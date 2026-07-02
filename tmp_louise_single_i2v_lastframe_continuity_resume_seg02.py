#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, time, uuid
from pathlib import Path
from urllib import request
COMFY='http://127.0.0.1:8188'
WORKFLOW=Path('/Users/tf00185088/Desktop/ai-drawing/backend/workflows/gen_img2video_wan_first_frame.json')
INPUT_DIR=Path('/Users/tf00185088/comfyui/input')
OUTPUT_DIR=Path('/Users/tf00185088/comfyui/output')
G=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-07-01')
TASK='louise_single_i2v_lastframe_test_20260701_resume'
LAST=G/'louise_single_i2v_raise_hand_test_seg01_last_frame.png'
SEG1=G/'louise_single_i2v_raise_hand_test_seg01_5b_512x704_32f16fps.mp4'
SEG2=G/'louise_single_i2v_raise_hand_test_seg02_from_seg1_last_5b_512x704_32f16fps.mp4'
FINAL=G/'louise_single_i2v_raise_hand_test_seg01_seg02_lastframe_concat.mp4'
PROMPT='anime watercolor illustration, Louise Françoise Le Blanc de La Vallière, pink long hair, European castle background, continue the previous motion, the character gently raises her right hand and short thin wand slightly upward a little more, subtle natural motion, small right hand lift, slight wrist movement, hair and cape gently swaying, stable face, stable outfit, stable background, preserve character identity, preserve composition, no sudden camera move'
NEG='low quality, blurry, jitter, heavy flicker, motion blur, morphing face, distorted face, changing identity, changing outfit, deformed hands, extra limbs, duplicate character, cropped body, missing feet, wrong character, long staff, flower wand, floral wand, background warping, camera shake, sudden cuts, text, watermark, logo, signature, monochrome, grayscale, washed out colors'
def log(s): print(time.strftime('%Y-%m-%d %H:%M:%S'), s, flush=True)
def post_json(path,payload):
 req=request.Request(COMFY+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with request.urlopen(req,timeout=30) as r:
  body=r.read().decode(); return json.loads(body) if body else {}
def get_json(path):
 with request.urlopen(COMFY+path,timeout=30) as r: return json.loads(r.read().decode())
def stage(src,name):
 d=INPUT_DIR/TASK; d.mkdir(parents=True,exist_ok=True); dst=d/name; shutil.copy2(src,dst); return f'{TASK}/{name}'
def configure(rel):
 w=json.loads(WORKFLOW.read_text())
 w['57']['inputs']['image']=rel; w['6']['inputs']['text']=PROMPT; w['7']['inputs']['text']=NEG
 w['55']['inputs']['width']=512; w['55']['inputs']['height']=704; w['55']['inputs']['length']=32; w['55']['inputs']['batch_size']=1
 w['94']['inputs']['fps']=16
 w['3']['inputs']['seed']=9101002; w['3']['inputs']['steps']=16; w['3']['inputs']['cfg']=4.5; w['3']['inputs']['sampler_name']='uni_pc'; w['3']['inputs']['scheduler']='simple'
 w['108']['inputs']['filename_prefix']='video/louise_single_i2v_raise_hand_test_seg02_from_seg1_last_5b_512x704_32f16fps'
 return w
def output_from_history(pid):
 hist=get_json('/history/'+pid)
 if pid not in hist: return None
 outs=[]
 for node_out in hist[pid].get('outputs',{}).values():
  for key in ('videos','gifs','files','images'):
   vals=node_out.get(key,[]) or []
   if isinstance(vals,bool): continue
   for v in vals:
    if isinstance(v,dict) and v.get('filename'):
     p=OUTPUT_DIR/v.get('subfolder','')/v['filename'] if v.get('type','output')=='output' else OUTPUT_DIR/v['filename']
     outs.append(p)
 existing=[p for p in outs if p.exists()]
 return existing[0] if existing else None
def submit_wait(w):
 pid=post_json('/prompt',{'prompt':w,'client_id':str(uuid.uuid4())})['prompt_id']; log(f'seg02 submitted {pid}')
 start=time.time(); last=-1
 while True:
  out=output_from_history(pid)
  if out: log(f'seg02 completed {out}'); return out
  m=int((time.time()-start)//60)
  if m!=last:
   q=get_json('/queue'); log(f'seg02 waiting {m}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}'); last=m
  time.sleep(10)
def probe(p):
 return subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,avg_frame_rate,duration,nb_frames','-of','json',str(p)],text=True)
def main():
 rel=stage(LAST,'seg01_last_frame.png')
 out=submit_wait(configure(rel)); shutil.copy2(out,SEG2); print('MEDIA:'+str(SEG2),flush=True)
 listfile=G/'louise_single_i2v_raise_hand_lastframe_concat_list.txt'; listfile.write_text(f"file '{SEG1}'\nfile '{SEG2}'\n")
 subprocess.check_call(['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','18','-preset','medium','-an',str(FINAL)])
 print('MEDIA:'+str(FINAL),flush=True)
 for p in [SEG1,SEG2,FINAL]: log(str(p)); print(probe(p),flush=True)
main()
