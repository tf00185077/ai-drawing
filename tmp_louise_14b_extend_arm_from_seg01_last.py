#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, time, uuid
from pathlib import Path
from urllib import request

COMFY='http://127.0.0.1:8188'
BASE=Path('/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases/video_wan2_2_14B_i2v_mac_api_v7_41frames.json')
INPUT_DIR=Path('/Users/tf00185088/comfyui/input')
OUTPUT_DIR=Path('/Users/tf00185088/comfyui/output')
G=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-07-01')
TASK='louise_14b_extend_arm_from_seg01_last_20260701'
SEG1=G/'louise_single_i2v_raise_hand_test_seg01_14b_q4ks_512x704_33f16fps.mp4'
START=G/'louise_single_i2v_raise_hand_test_seg01_14b_q4ks_last_frame.png'
SEG2=G/'louise_14b_extend_right_arm_straight_from_seg01_last_512x704_33f16fps.mp4'
FINAL=G/'louise_14b_raise_then_extend_right_arm_straight_concat.mp4'
CONTACT=G/'louise_14b_raise_then_extend_right_arm_splice_contact.jpg'
PROMPT=(
 'high quality anime watercolor illustration, continue the previous subtle motion from the current frame, Louise Françoise Le Blanc de La Vallière, pink long hair, pink eyes, black cloak, white blouse, European castle background, '
 'the character slowly extends her right arm forward and outward until the right arm is straighter, holding a short thin wooden wand, wand points outward, '
 'subtle controlled motion, only right forearm and wrist extend, hair and cloak barely swaying, '
 'preserve the exact current composition, preserve sharp detailed Japanese anime European castle background, preserve architecture lines, stable background, stable face, stable outfit, no camera move, no zoom'
)
NEG=(
 'low quality, blurry, soft background, blurred castle, smeared architecture, background blur, depth of field blur, bokeh, haze, fog, heavy motion blur, jitter, flicker, background warping, camera shake, camera move, zoom, pan, '
 'morphing face, distorted face, changing identity, changing outfit, deformed hands, extra fingers, extra limbs, duplicate character, wrong character, long staff, flower wand, floral wand, magic effect, explosion, text, watermark, logo, signature, arm disappearing, missing wand, broken arm'
)

def log(s): print(time.strftime('%Y-%m-%d %H:%M:%S'), s, flush=True)
def post_json(path,payload):
    req=request.Request(COMFY+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with request.urlopen(req,timeout=30) as r:
        body=r.read().decode(); return json.loads(body) if body else {}
def get_json(path):
    with request.urlopen(COMFY+path,timeout=30) as r: return json.loads(r.read().decode())
def stage(src,name):
    d=INPUT_DIR/TASK; d.mkdir(parents=True,exist_ok=True); dst=d/name; shutil.copy2(src,dst); return f'{TASK}/{name}'
def configure(start_rel):
    w=json.loads(BASE.read_text())
    w['97']['inputs']['image']=start_rel
    w['93']['inputs']['text']=PROMPT
    w['89']['inputs']['text']=NEG
    w['98']['inputs']['width']=512
    w['98']['inputs']['height']=704
    w['98']['inputs']['length']=33
    w['94']['inputs']['fps']=16
    w['108']['inputs']['filename_prefix']='video/louise_14b_extend_right_arm_straight_from_seg01_last_512x704_33f16fps'
    w['110']['inputs']['unet_name']='Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf'
    w['111']['inputs']['unet_name']='Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf'
    w['101']['inputs']['strength_model']=1.0
    w['102']['inputs']['strength_model']=1.0
    w['86']['inputs']['noise_seed']=914101
    w['86']['inputs']['steps']=6; w['85']['inputs']['steps']=6
    w['86']['inputs']['cfg']=1.0; w['85']['inputs']['cfg']=1.0
    w['86']['inputs']['end_at_step']=3; w['85']['inputs']['start_at_step']=3; w['85']['inputs']['end_at_step']=6
    return w
def output_from_history(pid):
    hist=get_json('/history/'+pid)
    if pid not in hist: return None, None
    item=hist[pid]; outs=[]
    for node_out in item.get('outputs',{}).values():
        for key in ('videos','gifs','files','images'):
            vals=node_out.get(key,[]) or []
            if isinstance(vals,bool): continue
            for v in vals:
                if isinstance(v,dict) and v.get('filename'):
                    p=OUTPUT_DIR/v.get('subfolder','')/v['filename'] if v.get('type','output')=='output' else OUTPUT_DIR/v['filename']
                    outs.append(p)
    existing=[p for p in outs if p.exists()]
    return (existing[0] if existing else None), item.get('status',{})
def submit_wait(w):
    pid=post_json('/prompt',{'prompt':w,'client_id':str(uuid.uuid4())})['prompt_id']
    log(f'seg02 submitted prompt_id={pid}')
    start=time.time(); last=-1
    while True:
        out,status=output_from_history(pid)
        if out:
            log(f'seg02 completed output={out} status={status}')
            return out
        m=int((time.time()-start)//60)
        if m!=last:
            q=get_json('/queue'); log(f'seg02 waiting {m}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}')
            last=m
        time.sleep(20)
def ffprobe(p):
    return subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,avg_frame_rate,duration,nb_frames','-of','json',str(p)],text=True)
def make_contact(final):
    tmp=Path('/tmp/louise_14b_extend_arm_splice_contact'); shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True)
    dur=float(json.loads(ffprobe(SEG1))['streams'][0]['duration'])
    times=[dur-0.36,dur-0.24,dur-0.12,dur-0.02,dur+0.02,dur+0.12,dur+0.24,dur+0.36]
    for i,t in enumerate(times,1):
        subprocess.call(['ffmpeg','-y','-ss',str(max(t,0)),'-i',str(final),'-frames:v','1',str(tmp/f'f{i:02d}.jpg')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.check_call(['ffmpeg','-y','-pattern_type','glob','-i',str(tmp/'*.jpg'),'-vf','scale=256:-1,tile=4x2:padding=8:margin=8','-frames:v','1',str(CONTACT)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def main():
    log('ComfyUI queue '+json.dumps(get_json('/queue'))[:300])
    rel=stage(START,'seg01_actual_last_frame.png')
    out=submit_wait(configure(rel))
    shutil.copy2(out,SEG2); print('MEDIA:'+str(SEG2),flush=True)
    listfile=G/'louise_14b_raise_then_extend_right_arm_concat_list.txt'
    listfile.write_text(f"file '{SEG1}'\nfile '{SEG2}'\n")
    subprocess.check_call(['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','18','-preset','medium','-an',str(FINAL)])
    make_contact(FINAL)
    print('MEDIA:'+str(FINAL),flush=True); print('MEDIA:'+str(CONTACT),flush=True)
    for p in [SEG1,SEG2,FINAL]: log(str(p)); print(ffprobe(p),flush=True)
if __name__=='__main__': main()
