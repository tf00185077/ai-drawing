#!/usr/bin/env python3
import json, urllib.request, urllib.error, time, uuid, subprocess, copy
from pathlib import Path

HOST='http://127.0.0.1:8188'
EXP=Path('/Users/tf00185088/Desktop/ai-drawing/experiments/multiframe_workflows')
OUT=Path('/Users/tf00185088/comfyui/output')
TEMP=Path('/Users/tf00185088/comfyui/temp')
BASE_PROMPT=json.loads((EXP/'flf_mac_gguf_2kf_test_api.json').read_text())
BASE_PID='ac6d2ba6-a32a-4e39-ad39-fe391edbdedf'
RESULT_JSON=EXP/'flf_mac_gguf_ablation_results.json'
REPORT=EXP/'FLF_MAC_GGUF_ABLATION_RESULTS.md'

def jget(path, timeout=30):
    with urllib.request.urlopen(HOST+path,timeout=timeout) as r: return json.load(r)
def jpost(path, obj, timeout=60):
    req=urllib.request.Request(HOST+path,data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode() or '{}')
def wait_terminal(pid, label, poll=60):
    start=time.time()
    while True:
        h=jget(f'/history/{pid}',30)
        if pid in h: return h[pid], time.time()-start
        q=jget('/queue',20)
        print(f'{label}: elapsed={int(time.time()-start)}s running={[x[1] for x in q.get("queue_running",[])]} pending={[x[1] for x in q.get("queue_pending",[])]}', flush=True)
        time.sleep(poll)
def queue_empty():
    q=jget('/queue',20); return not q.get('queue_running') and not q.get('queue_pending')
def free():
    try: jpost('/free', {'unload_models':True,'free_memory':True}, 30)
    except Exception as e: print('free warn',type(e).__name__,e,flush=True)
def submit(prompt, label):
    while not queue_empty():
        print(label,'waiting queue empty',flush=True); time.sleep(30)
    return jpost('/prompt', {'prompt':prompt,'client_id':label+'-'+str(uuid.uuid4())},60)['prompt_id']
def collect(item, prefix, label):
    videos=[]
    for out in (item.get('outputs') or {}).values():
        for key in ['images','gifs','videos']:
            for v in out.get(key) or []:
                if not isinstance(v,dict) or 'filename' not in v: continue
                base=OUT if (v.get('type') or 'output')=='output' else TEMP
                p=base/str(v.get('subfolder') or '')/str(v.get('filename'))
                if p.exists() and p.suffix.lower() in ['.mp4','.mov','.webm','.mkv','.gif']: videos.append(p)
    if not videos:
        videos=sorted(OUT.rglob(Path(prefix).name+'*.mp4'), key=lambda p:p.stat().st_mtime, reverse=True)[:3]
    arts=[]
    for p in videos[:3]:
        ff=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration,size:stream=width,height,nb_frames,r_frame_rate,codec_name','-of','json',str(p)],capture_output=True,text=True,timeout=60)
        try: ffj=json.loads(ff.stdout)
        except Exception: ffj={'raw':ff.stdout,'err':ff.stderr}
        contact=Path('/tmp')/f'{label}_{p.stem[-18:]}_contact.jpg'
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-i',str(p),'-vf',"select='not(mod(n,4))',scale=160:-1,tile=12x1",'-frames:v','1',str(contact)],capture_output=True,text=True,timeout=180)
        arts.append({'video':str(p),'contact':str(contact) if contact.exists() else None,'ffprobe':ffj})
    return arts
def err(item):
    st=item.get('status',{})
    for msg,payload in st.get('messages',[]):
        if msg=='execution_error': return {k:payload.get(k) for k in ['node_id','node_type','exception_type','exception_message','executed']}
    return {}
def save_prompt(prompt, name):
    p=EXP/name; p.write_text(json.dumps(prompt,ensure_ascii=False,indent=2)); return str(p)
def set_prefix(prompt, prefix): prompt['18']['inputs']['filename_prefix']=prefix

def make_length81():
    p=copy.deepcopy(BASE_PROMPT); p['13']['inputs']['length']=81; set_prefix(p,'video/flf_mac_gguf_v1_len81_512'); return p
def make_steps6():
    p=copy.deepcopy(BASE_PROMPT)
    p['14']['inputs']['steps']=6; p['14']['inputs']['end_at_step']=3
    p['15']['inputs']['steps']=6; p['15']['inputs']['start_at_step']=3; p['15']['inputs']['end_at_step']=6
    set_prefix(p,'video/flf_mac_gguf_v2_steps6_41f'); return p
def make_cfg10():
    p=copy.deepcopy(BASE_PROMPT); p['14']['inputs']['cfg']=1.0; p['15']['inputs']['cfg']=1.0; set_prefix(p,'video/flf_mac_gguf_v3_cfg10_41f'); return p

TESTS=[
 {'id':'B0','desc':'baseline FLF Mac GGUF: 512² length41 steps10 CFG1.5, keyframe_01→02','pid':BASE_PID,'prompt':BASE_PROMPT,'api':'flf_mac_gguf_2kf_test_api.json','prefix':'video/flf_mac_gguf_2kf_test_512_41f'},
 {'id':'V1','desc':'length 41→81, other settings unchanged','make':make_length81,'api':'flf_mac_gguf_v1_len81_api.json','prefix':'video/flf_mac_gguf_v1_len81_512'},
 {'id':'V2','desc':'steps 10→6, length41 unchanged','make':make_steps6,'api':'flf_mac_gguf_v2_steps6_api.json','prefix':'video/flf_mac_gguf_v2_steps6_41f'},
 {'id':'V3','desc':'CFG 1.5→1.0, length41 unchanged','make':make_cfg10,'api':'flf_mac_gguf_v3_cfg10_api.json','prefix':'video/flf_mac_gguf_v3_cfg10_41f'},
]

def main():
    results=[]
    for t in TESTS:
        if t['id']=='B0':
            pid=t['pid']; api_path=str(EXP/t['api']); print('adopting baseline',pid,flush=True)
        else:
            prompt=t['make'](); api_path=save_prompt(prompt,t['api']); pid=submit(prompt,'flf-'+t['id'].lower()); print(t['id'],'submitted',pid,flush=True)
        item,elapsed=wait_terminal(pid,t['id'])
        status=item.get('status',{}).get('status_str')
        rec={'id':t['id'],'description':t['desc'],'prompt_id':pid,'api_path':api_path,'status':status,'elapsed_seconds':round(elapsed,1),'artifacts':[],'error':None}
        print(t['id'],'terminal',status,'elapsed',int(elapsed),flush=True)
        if status=='success': rec['artifacts']=collect(item,t['prefix'],t['id'].lower())
        else: rec['error']=err(item)
        results.append(rec); RESULT_JSON.write_text(json.dumps(results,ensure_ascii=False,indent=2)); free(); time.sleep(20)
        if status!='success':
            print('Stopping ablation after failed baseline/variant',flush=True); break
    write_report(results); print_report(results)

def write_report(results):
    lines=['# FLF Mac GGUF 2-keyframe ablation results','', 'Source: official Comfy Wan2.2 FLF structure adapted to local Apple/MPS-safe GGUF route.', 'Inputs: `flf_start_keyframe_01.png` → `flf_end_keyframe_02.png`.', '']
    lines += ['| ID | Change | Status | Output |','|---|---|---|---|']
    for r in results:
        out=(r['artifacts'][0]['video'] if r.get('artifacts') else json.dumps(r.get('error'),ensure_ascii=False)[:80])
        lines.append(f"| {r['id']} | {r['description']} | {r['status']} | `{out}` |")
    for r in results:
        lines += ['', f"## {r['id']} — {r['description']}", f"- prompt_id: `{r['prompt_id']}`", f"- status: `{r['status']}`", f"- api: `{r['api_path']}`"]
        if r.get('error'):
            lines += ['- error:', '```json', json.dumps(r['error'],ensure_ascii=False,indent=2), '```']
        for a in r.get('artifacts') or []:
            lines += [f"- video: `{a['video']}`", f"- contact: `{a['contact']}`", '- ffprobe:', '```json', json.dumps(a['ffprobe'],ensure_ascii=False,indent=2)[:2000], '```']
    REPORT.write_text('\n'.join(lines))

def print_report(results):
    print('\n=== FLF MAC GGUF REPORT ===')
    print('REPORT',REPORT)
    print('JSON',RESULT_JSON)
    for r in results:
        print(f"\n{r['id']} {r['status']} {r['description']} prompt_id={r['prompt_id']}")
        if r.get('error'): print('ERROR',json.dumps(r['error'],ensure_ascii=False)[:1000])
        for a in r.get('artifacts') or []:
            print('MEDIA:'+a['video'])
            if a.get('contact'): print('MEDIA:'+a['contact'])
            try:
                s=a['ffprobe']['streams'][0]; f=a['ffprobe']['format']; print(f"ffprobe: {s.get('width')}x{s.get('height')} {s.get('nb_frames')} frames {s.get('r_frame_rate')} duration={f.get('duration')} size={f.get('size')}")
            except Exception: pass

if __name__=='__main__': main()
