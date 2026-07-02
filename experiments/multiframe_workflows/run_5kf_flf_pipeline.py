#!/usr/bin/env python3
import json, urllib.request, time, uuid, subprocess, copy, shutil
from pathlib import Path

HOST='http://127.0.0.1:8188'
EXP=Path('/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows/5kf_flf_run')
ROOT=Path('/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows')
INPUT=Path('/Users/tf00185088/comfyui/input')
APPROVED=INPUT/'asuka_approved_5kf_v1'
OUT=Path('/Users/tf00185088/comfyui/output')
TEMP=Path('/Users/tf00185088/comfyui/temp')
BASE=json.loads((ROOT/'flf_mac_gguf_2kf_test_api.json').read_text())
FILM=Path('/Users/tf00185088/Desktop/ai-drawing/experiments/frame_interpolation_tests/film_interpolate_multi.py')
EXP.mkdir(parents=True, exist_ok=True)
RESULT_JSON=EXP/'5kf_flf_results.json'
REPORT=EXP/'README_RESULTS.md'

PROMPT_TEXT = "anime girl in a red plugsuit inside a futuristic cockpit, smooth cinematic transition between the supplied keyframes, maintain the same character identity, detailed face, detailed hair, coherent body, coherent background, cinematic lighting, sharp focus, stable composition, natural motion"
NEG_TEXT = "blurry, low quality, deformed face, bad hands, extra fingers, distorted body, duplicated limbs, messy background, flicker, sudden cut, text, watermark, jpeg artifacts"

def jget(path, timeout=30):
    with urllib.request.urlopen(HOST+path,timeout=timeout) as r: return json.load(r)
def jpost(path, obj, timeout=60):
    req=urllib.request.Request(HOST+path,data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode() or '{}')
def queue_empty():
    q=jget('/queue',20); return not q.get('queue_running') and not q.get('queue_pending')
def wait_terminal(pid, label, poll=60):
    start=time.time()
    while True:
        h=jget(f'/history/{pid}',30)
        if pid in h: return h[pid], time.time()-start
        q=jget('/queue',20)
        print(f'{label}: elapsed={int(time.time()-start)}s running={[x[1] for x in q.get("queue_running",[])]} pending={[x[1] for x in q.get("queue_pending",[])]}', flush=True)
        time.sleep(poll)
def free():
    try: jpost('/free', {'unload_models':True,'free_memory':True}, 30)
    except Exception as e: print('free warn',type(e).__name__,e,flush=True)
def submit(prompt, label):
    while not queue_empty():
        print(label,'waiting for queue empty',flush=True); time.sleep(30)
    resp=jpost('/prompt', {'prompt':prompt,'client_id':label+'-'+str(uuid.uuid4())}, 60)
    return resp['prompt_id'], resp

def collect_video(item, prefix):
    videos=[]
    for out in (item.get('outputs') or {}).values():
        for key in ['images','gifs','videos']:
            for v in out.get(key) or []:
                if not isinstance(v,dict) or 'filename' not in v: continue
                base=OUT if (v.get('type') or 'output')=='output' else TEMP
                p=base/str(v.get('subfolder') or '')/str(v.get('filename'))
                if p.exists() and p.suffix.lower() in ['.mp4','.mov','.webm','.mkv','.gif']: videos.append(p)
    if not videos:
        videos=sorted(OUT.rglob(Path(prefix).name+'*.mp4'), key=lambda p:p.stat().st_mtime, reverse=True)[:1]
    return videos[0] if videos else None

def ffprobe(path):
    p=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration,size:stream=width,height,nb_frames,r_frame_rate,codec_name','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=60)
    return json.loads(p.stdout)
def contact(path, out, every=8):
    subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-i',str(path),'-vf',f"select='not(mod(n,{every}))',scale=160:-1,tile=16x1",'-frames:v','1',str(out)],capture_output=True,text=True,timeout=180)
    return str(out) if out.exists() else None

def make_prompt(seg_idx, start_name, end_name):
    p=copy.deepcopy(BASE)
    p['2']['inputs']['text']=PROMPT_TEXT
    p['3']['inputs']['text']=NEG_TEXT
    p['5']['inputs']['image']=start_name
    p['6']['inputs']['image']=end_name
    p['13']['inputs']['width']=512
    p['13']['inputs']['height']=512
    p['13']['inputs']['length']=81
    p['14']['inputs']['steps']=10; p['14']['inputs']['cfg']=1.5; p['14']['inputs']['start_at_step']=0; p['14']['inputs']['end_at_step']=5
    p['15']['inputs']['steps']=10; p['15']['inputs']['cfg']=1.5; p['15']['inputs']['start_at_step']=5; p['15']['inputs']['end_at_step']=10
    p['14']['inputs']['noise_seed']=52025000+seg_idx
    p['18']['inputs']['filename_prefix']=f'video/5kf_flf_seg{seg_idx:02d}_{start_name[:-4]}_to_{end_name[:-4]}'
    return p

def err(item):
    st=item.get('status',{})
    for msg,payload in st.get('messages',[]):
        if msg=='execution_error': return {k:payload.get(k) for k in ['node_id','node_type','exception_type','exception_message','executed']}
    return {}

def stitch(paths):
    listfile=EXP/'concat_list.txt'
    listfile.write_text('\n'.join(["file '"+str(p).replace("'","'\\''")+"'" for p in paths])+"\n")
    out=EXP/'asuka_5kf_flf_stitched_16fps.mp4'
    cmd=['/opt/homebrew/bin/ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c','copy',str(out)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
    if r.returncode!=0:
        cmd=['/opt/homebrew/bin/ffmpeg','-y','-f','concat','-safe','0','-i',str(listfile),'-c:v','libx264','-pix_fmt','yuv420p','-crf','18',str(out)]
        subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=600)
    return out

def film_x4(src):
    out=EXP/'asuka_5kf_flf_stitched_FILM_x4_62fps.mp4'
    subprocess.run(['/opt/homebrew/bin/python3.11', str(FILM), '--input', str(src), '--multiplier', '4', '--outputs', f'{out}:62'], check=True, timeout=3600)
    return out

def main():
    # copy keyframes to root input with deterministic names
    names=[]
    for i in range(1,6):
        src=APPROVED/f'keyframe_{i:02d}.png'
        dst=INPUT/f'flf5_keyframe_{i:02d}.png'
        shutil.copy2(src,dst)
        names.append(dst.name)
    segments=[]; results=[]
    for idx in range(1,5):
        label=f'seg{idx:02d}_{idx:02d}_to_{idx+1:02d}'
        prompt=make_prompt(idx,names[idx-1],names[idx])
        api=EXP/f'{label}_api.json'; api.write_text(json.dumps(prompt,ensure_ascii=False,indent=2))
        pid, resp=submit(prompt,label)
        print(label,'submitted',pid,resp,flush=True)
        item,elapsed=wait_terminal(pid,label)
        status=item.get('status',{}).get('status_str')
        rec={'segment':idx,'label':label,'prompt_id':pid,'api':str(api),'status':status,'elapsed_seconds':round(elapsed,1),'video':None,'contact':None,'ffprobe':None,'error':None}
        if status=='success':
            v=collect_video(item, prompt['18']['inputs']['filename_prefix'])
            if v:
                rec['video']=str(v); rec['ffprobe']=ffprobe(v); rec['contact']=contact(v, EXP/f'{label}_contact.jpg', every=8); segments.append(v)
        else:
            rec['error']=err(item)
        results.append(rec); RESULT_JSON.write_text(json.dumps(results,ensure_ascii=False,indent=2)); free(); time.sleep(20)
        if status!='success':
            write_report(results, None, None); print_report(results, None, None); return
    stitched=stitch(segments)
    stitched_contact=contact(stitched, EXP/'asuka_5kf_flf_stitched_16fps_contact.jpg', every=16)
    film=film_x4(stitched)
    film_contact=contact(film, EXP/'asuka_5kf_flf_stitched_FILM_x4_62fps_contact.jpg', every=64)
    final={'stitched':str(stitched),'stitched_ffprobe':ffprobe(stitched),'stitched_contact':stitched_contact,'film_x4_62':str(film),'film_x4_62_ffprobe':ffprobe(film),'film_x4_62_contact':film_contact}
    (EXP/'5kf_final_outputs.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
    write_report(results, final, segments); print_report(results, final, segments)

def write_report(results, final, segments):
    lines=['# 5-keyframe FLF segmented pipeline results','', 'Route: 4 FLF segments using local Mac/MPS GGUF Wan2.2 route, then ffmpeg stitch, then direct FILM x4/62fps.', '']
    lines += ['## Segments','']
    for r in results:
        lines += [f"### {r['label']} — {r['status']}", f"- prompt_id: `{r['prompt_id']}`", f"- elapsed_seconds: `{r['elapsed_seconds']}`"]
        if r.get('video'): lines += [f"- video: `{r['video']}`", f"- contact: `{r['contact']}`", '- ffprobe:', '```json', json.dumps(r['ffprobe'],ensure_ascii=False,indent=2)[:2000], '```']
        if r.get('error'): lines += ['- error:', '```json', json.dumps(r['error'],ensure_ascii=False,indent=2), '```']
    if final:
        lines += ['', '## Final stitched outputs', f"- stitched_16fps: `{final['stitched']}`", f"- stitched_contact: `{final['stitched_contact']}`", f"- FILM_x4_62fps: `{final['film_x4_62']}`", f"- FILM_contact: `{final['film_x4_62_contact']}`", '', '### final ffprobe', '```json', json.dumps(final,ensure_ascii=False,indent=2)[:4000], '```']
    REPORT.write_text('\n'.join(lines))

def print_report(results, final, segments):
    print('\n=== 5KF FLF PIPELINE REPORT ===')
    print('REPORT',REPORT)
    print('RESULT_JSON',RESULT_JSON)
    for r in results:
        print(f"\n{r['label']} {r['status']} prompt_id={r['prompt_id']} elapsed={r['elapsed_seconds']}")
        if r.get('video'): print('MEDIA:'+r['video'])
        if r.get('contact'): print('MEDIA:'+r['contact'])
        if r.get('error'): print('ERROR',json.dumps(r['error'],ensure_ascii=False)[:1000])
    if final:
        print('\nFINAL STITCHED')
        print('MEDIA:'+final['stitched'])
        print('MEDIA:'+final['stitched_contact'])
        print('FINAL FILM X4 62FPS')
        print('MEDIA:'+final['film_x4_62'])
        print('MEDIA:'+final['film_x4_62_contact'])
        print('ffprobe stitched', json.dumps(final['stitched_ffprobe'],ensure_ascii=False)[:1000])
        print('ffprobe film', json.dumps(final['film_x4_62_ffprobe'],ensure_ascii=False)[:1000])

if __name__=='__main__':
    main()
