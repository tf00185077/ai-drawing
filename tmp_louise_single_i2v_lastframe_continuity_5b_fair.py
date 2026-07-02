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
TASK='louise_single_i2v_lastframe_test_5b_fair_20260701'
START=G/'louise_single_i2v_raise_hand_test_input_512x704.png'
SEG1=G/'louise_single_i2v_raise_hand_test_seg01_5b_fair_512x704_33f16fps.mp4'
LAST=G/'louise_single_i2v_raise_hand_test_seg01_5b_fair_last_frame.png'
SEG2=G/'louise_single_i2v_raise_hand_test_seg02_from_seg1_last_5b_fair_512x704_33f16fps.mp4'
FINAL=G/'louise_single_i2v_raise_hand_test_5b_fair_seg01_seg02_lastframe_concat.mp4'
CONTACT=G/'louise_single_i2v_5b_fair_lastframe_concat_splice_contact.jpg'
PROMPT1=(
 'high quality anime watercolor illustration, Louise Françoise Le Blanc de La Vallière, pink long hair, pink eyes, black cloak, white blouse, European castle background, '
 'the character gently raises her right hand and short thin wooden wand slightly upward, very subtle motion, small wrist movement only, hair and cloak barely swaying, '
 'preserve the original composition exactly, preserve sharp detailed Japanese anime European castle background, preserve architecture lines, stable background, stable face, stable outfit, no camera move, no zoom'
)
PROMPT2=(
 'high quality anime watercolor illustration, continue the previous subtle motion, Louise Françoise Le Blanc de La Vallière gently raises her right hand and short thin wooden wand a little more, '
 'very subtle small wrist movement only, hair and cloak barely swaying, preserve the exact current composition, preserve sharp detailed Japanese anime European castle background, stable background, stable face, stable outfit, no camera move, no zoom'
)
NEG=(
 'low quality, blurry, soft background, blurred castle, smeared architecture, background blur, depth of field blur, bokeh, haze, fog, heavy motion blur, jitter, flicker, background warping, camera shake, camera move, zoom, pan, '
 'morphing face, distorted face, changing identity, changing outfit, deformed hands, extra fingers, extra limbs, duplicate character, wrong character, long staff, flower wand, floral wand, magic effect, explosion, text, watermark, logo, signature'
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
def configure(start_rel,prompt,prefix,seed):
    w=json.loads(WORKFLOW.read_text())
    w['57']['inputs']['image']=start_rel
    w['6']['inputs']['text']=prompt
    w['7']['inputs']['text']=NEG
    w['55']['inputs']['width']=512
    w['55']['inputs']['height']=704
    w['55']['inputs']['length']=33
    w['55']['inputs']['batch_size']=1
    w['94']['inputs']['fps']=16
    w['3']['inputs']['seed']=seed
    w['3']['inputs']['steps']=16
    w['3']['inputs']['cfg']=4.5
    w['3']['inputs']['sampler_name']='uni_pc'
    w['3']['inputs']['scheduler']='simple'
    w['108']['inputs']['filename_prefix']=f'video/{prefix}'
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
def submit_wait(w,label):
    pid=post_json('/prompt',{'prompt':w,'client_id':str(uuid.uuid4())})['prompt_id']
    log(f'{label} submitted prompt_id={pid}')
    start=time.time(); last=-1
    while True:
        out,status=output_from_history(pid)
        if out:
            log(f'{label} completed output={out} status={status}')
            return out
        m=int((time.time()-start)//60)
        if m!=last:
            q=get_json('/queue'); log(f'{label} waiting {m}m running={len(q.get("queue_running",[]))} pending={len(q.get("queue_pending",[]))}')
            last=m
        time.sleep(10)
def ffprobe(p):
    return subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,avg_frame_rate,duration,nb_frames','-of','json',str(p)],text=True)
def extract_last(video,out):
    info=json.loads(ffprobe(video)); nb=int(info['streams'][0]['nb_frames']); idx=nb-1
    subprocess.check_call(['ffmpeg','-y','-i',str(video),'-vf',f'select=eq(n\\,{idx})','-fps_mode','passthrough','-frames:v','1',str(out)])
def make_contact(final):
    tmp=Path('/tmp/louise_5b_fair_splice_contact'); shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True)
    dur=float(json.loads(ffprobe(SEG1))['streams'][0]['duration'])
    times=[dur-0.36,dur-0.24,dur-0.12,dur-0.02,dur+0.02,dur+0.12,dur+0.24,dur+0.36]
    for i,t in enumerate(times,1):
        subprocess.call(['ffmpeg','-y','-ss',str(max(t,0)),'-i',str(final),'-frames:v','1',str(tmp/f'f{i:02d}.jpg')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.check_call(['ffmpeg','-y','-pattern_type','glob','-i',str(tmp/'*.jpg'),'-vf','scale=256:-1,tile=4x2:padding=8:margin=8','-frames:v','1',str(CONTACT)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def main():
    G.mkdir(parents=True,exist_ok=True)
    log('ComfyUI queue '+json.dumps(get_json('/queue'))[:300])
    rel1=stage(START,'start_512x704.png')
    out1=submit_wait(configure(rel1,PROMPT1,'louise_single_i2v_raise_hand_test_seg01_5b_fair_512x704_33f16fps',950001),'seg01')
    shutil.copy2(out1,SEG1); print('MEDIA:'+str(SEG1),flush=True)
    extract_last(SEG1,LAST); print('MEDIA:'+str(LAST),flush=True)
    rel2=stage(LAST,'seg01_actual_last_frame.png')
    out2=submit_wait(configure(rel2,PROMPT2,'louise_single_i2v_raise_hand_test_seg02_from_seg1_last_5b_fair_512x704_33f16fps',950002),'seg02')
    shutil.copy2(out2,SEG2); print('MEDIA:'+str(SEG2),flush=True)
    listfile=G/'louise_single_i2v_5b_fair_lastframe_concat_list.txt'
    listfile.write_text(f"file '{SEG1}'\nfile '{SEG2}'\n")
    subprocess.check_call(['ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','18','-preset','medium','-an',str(FINAL)])
    make_contact(FINAL)
    print('MEDIA:'+str(FINAL),flush=True); print('MEDIA:'+str(CONTACT),flush=True)
    for p in [SEG1,SEG2,FINAL]: log(str(p)); print(ffprobe(p),flush=True)
if __name__=='__main__': main()
