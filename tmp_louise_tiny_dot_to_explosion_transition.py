#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, time, uuid
from pathlib import Path
from urllib import request

COMFY='http://127.0.0.1:8188'
WORKFLOW=Path('/Users/tf00185088/Desktop/ai-drawing/backend/workflows/gen_img2video_wan_first_frame_last_frame.json')
INPUT_DIR=Path('/Users/tf00185088/comfyui/input')
OUTPUT_DIR=Path('/Users/tf00185088/comfyui/output')
G=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-07-01')
TASK='louise_tiny_dot_to_small_explosion_14b_20260701'
SEG1=G/'louise_single_i2v_raise_hand_test_seg01_14b_q4ks_512x704_33f16fps.mp4'
V1=G/'louise_14b_extend_right_arm_straight_variant_v01_seed914201_512x704_33f16fps.mp4'
START=G/'louise_14b_extend_arm_v01_last_frame_tiny_white_dot_start.png'
END=G/'louise_small_explosion_right_inpaint_variant_v02_seed7621003.png'
SEG_EXP=G/'louise_14b_tiny_white_dot_expand_to_small_explosion_v02_512x704_33f16fps.mp4'
FINAL=G/'louise_14b_seg01_v1_extend_tiny_dot_to_explosion_v02_concat.mp4'
CONTACT=G/'louise_14b_tiny_dot_to_explosion_v02_contact.jpg'
PROMPT=(
 'smooth two-second magical effect growth between the provided start and end keyframes, anime watercolor illustration, Louise Françoise Le Blanc de La Vallière, '
 'a tiny white point of light just beyond the wand tip gradually expands outward into one small compact orange yellow white magical explosion, '
 'small starburst grows from the center, short radial shockwave, tiny sparks spread outward, controlled compact blast, '
 'preserve character identity, preserve right arm and wand position, preserve outfit, preserve sharp detailed European castle background, stable background, no camera move, no zoom, no sudden cut'
)
NEG=(
 'low quality, blurry, jitter, heavy flicker, motion blur, morphing face, distorted face, changing identity, changing outfit, deformed hands, extra limbs, duplicate character, '
 'changed background, blurry background, smeared castle, background warping, camera shake, camera move, zoom, pan, huge explosion, full screen explosion, explosion covering character, fire everywhere, large smoke cloud, overexposed full screen flash, text, watermark, logo, signature'
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
def configure(start_rel,end_rel):
    w=json.loads(WORKFLOW.read_text())
    w['97']['inputs']['image']=start_rel
    w['109']['inputs']['image']=end_rel
    w['93']['inputs']['text']=PROMPT
    w['89']['inputs']['text']=NEG
    w['98']['inputs']['width']=512
    w['98']['inputs']['height']=704
    w['98']['inputs']['length']=33
    w['98']['inputs']['batch_size']=1
    w['94']['inputs']['fps']=16
    for nid in ('86','85'):
        w[nid]['inputs']['steps']=10
        w[nid]['inputs']['cfg']=1.5
        w[nid]['inputs']['sampler_name']='euler'
        w[nid]['inputs']['scheduler']='simple'
        w[nid]['inputs']['noise_seed']=915301
    w['86']['inputs']['start_at_step']=0
    w['86']['inputs']['end_at_step']=5
    w['85']['inputs']['start_at_step']=5
    w['85']['inputs']['end_at_step']=10
    w['95']['inputs']['model_name']='Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf'
    w['96']['inputs']['model_name']='Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf'
    w['108']['inputs']['filename_prefix']='video/louise_14b_tiny_white_dot_expand_to_small_explosion_v02_512x704_33f16fps'
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
    log(f'explosion transition submitted prompt_id={pid}')
    start=time.time(); last=-1
    while True:
        out,status=output_from_history(pid)
        if out:
            log(f'explosion transition completed output={out} status={status}')
            return out
        m=int((time.time()-start)//60)
        if m!=last:
            q=get_json('/queue'); log(f'waiting {m}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}')
            last=m
        time.sleep(20)
def ffprobe(p):
    return subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,avg_frame_rate,duration,nb_frames','-of','json',str(p)],text=True)
def concat():
    listfile=G/'louise_14b_seg01_v1_extend_tiny_dot_to_explosion_v02_concat_list.txt'
    listfile.write_text(f"file '{SEG1}'\nfile '{V1}'\nfile '{SEG_EXP}'\n")
    subprocess.check_call(['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','18','-preset','medium','-an',str(FINAL)])
def contact():
    tmp=Path('/tmp/louise_dot_explosion_contact'); shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True)
    times=[0.0,0.4,0.8,1.2,1.6,2.0]
    for i,t in enumerate(times,1):
        subprocess.call(['ffmpeg','-y','-ss',str(t),'-i',str(SEG_EXP),'-frames:v','1',str(tmp/f'f{i:02d}.jpg')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.check_call(['ffmpeg','-y','-pattern_type','glob','-i',str(tmp/'*.jpg'),'-vf','scale=192:-1,tile=6x1:padding=8:margin=8','-frames:v','1',str(CONTACT)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def main():
    q=get_json('/queue'); log(f"queue running={len(q.get('queue_running',[]))} pending={len(q.get('queue_pending',[]))}")
    start_rel=stage(START,'tiny_white_dot_start.png')
    end_rel=stage(END,'small_explosion_v02_end.png')
    out=submit_wait(configure(start_rel,end_rel))
    shutil.copy2(out,SEG_EXP); print('MEDIA:'+str(SEG_EXP),flush=True)
    concat(); contact()
    print('MEDIA:'+str(FINAL),flush=True); print('MEDIA:'+str(CONTACT),flush=True)
    for p in [SEG_EXP,FINAL]: log(str(p)); print(ffprobe(p),flush=True)
if __name__=='__main__': main()
