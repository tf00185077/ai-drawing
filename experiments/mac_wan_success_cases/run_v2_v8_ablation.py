#!/usr/bin/env python3
import json, urllib.request, urllib.error, time, uuid, subprocess, copy, sys
from pathlib import Path

BASE = Path('/Users/tf00185088/Desktop/ai-drawing/experiments/mac_wan_success_cases')
OUT = Path('/Users/tf00185088/comfyui/output')
TEMP = Path('/Users/tf00185088/comfyui/temp')
BASELINE = json.loads((BASE/'video_wan2_2_14B_i2v_mac_api_baseline.json').read_text())
V1 = json.loads((BASE/'video_wan2_2_14B_i2v_mac_api_v1_no_lightning_lora.json').read_text())
RESULT_JSON = BASE/'ablation_v2_v8_results.json'
REPORT_MD = BASE/'ABLATION_RESULTS_V2_V8.md'

HOST='http://127.0.0.1:8188'

def jget(path, timeout=30):
    with urllib.request.urlopen(HOST+path, timeout=timeout) as r:
        return json.load(r)

def jpost(path, obj, timeout=60):
    req=urllib.request.Request(HOST+path, data=json.dumps(obj).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or '{}')

def free_memory():
    try:
        jpost('/free', {'unload_models': True, 'free_memory': True}, timeout=30)
    except Exception as e:
        print('WARN free_memory', type(e).__name__, e, flush=True)

def queue_empty():
    q=jget('/queue', 20)
    return not q.get('queue_running') and not q.get('queue_pending')

def wait_terminal(pid, label, poll=60):
    start=time.time()
    while True:
        try:
            h=jget(f'/history/{pid}', 30)
        except Exception as e:
            print(f'{label}: history poll error {type(e).__name__}: {e}', flush=True)
            time.sleep(poll); continue
        if pid in h:
            return h[pid], time.time()-start
        try:
            q=jget('/queue', 20)
            running=[x[1] for x in q.get('queue_running', [])]
            pending=[x[1] for x in q.get('queue_pending', [])]
            print(f'{label}: still running/pending elapsed={int(time.time()-start)}s running={running} pending={pending}', flush=True)
        except Exception as e:
            print(f'{label}: queue poll error {type(e).__name__}: {e}', flush=True)
        time.sleep(poll)

def set_save_prefix(prompt, prefix):
    for node in prompt.values():
        if node['class_type']=='SaveVideo':
            node['inputs']['filename_prefix']=prefix

def collect_outputs(item, prefix, label):
    videos=[]
    for out in (item.get('outputs') or {}).values():
        for key in ['images','gifs','videos']:
            for v in out.get(key) or []:
                if not isinstance(v,dict) or 'filename' not in v: continue
                base=OUT if (v.get('type') or 'output')=='output' else TEMP
                p=base / str(v.get('subfolder') or '') / str(v.get('filename'))
                if p.exists() and p.suffix.lower() in ['.mp4','.mov','.webm','.mkv','.gif']:
                    videos.append(p)
    if not videos:
        videos=sorted(OUT.rglob(Path(prefix).name+'*.mp4'), key=lambda p:p.stat().st_mtime, reverse=True)[:3]
    artifacts=[]
    for p in videos[:3]:
        ff=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration,size:stream=width,height,nb_frames,r_frame_rate,codec_name','-of','json',str(p)], capture_output=True, text=True, timeout=60)
        ffj={}
        try: ffj=json.loads(ff.stdout)
        except Exception: ffj={'raw': ff.stdout, 'err': ff.stderr}
        contact=Path('/tmp')/f'{label}_{p.stem[-18:]}_contact.jpg'
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-i',str(p),'-vf',"select='not(mod(n,8))',scale=160:-1,tile=12x1",'-frames:v','1',str(contact)], capture_output=True, text=True, timeout=180)
        artifacts.append({'video': str(p), 'contact': str(contact) if contact.exists() else None, 'ffprobe': ffj})
    return artifacts

def error_summary(item):
    status=item.get('status', {})
    for msg,payload in status.get('messages', []):
        if msg=='execution_error':
            return {k:payload.get(k) for k in ['node_id','node_type','exception_type','exception_message','executed']}
    return {}

def submit(prompt, label):
    resp=jpost('/prompt', {'prompt': prompt, 'client_id': label+'-'+str(uuid.uuid4())}, 60)
    return resp['prompt_id'], resp

def save_api(prompt, name):
    p=BASE/name
    p.write_text(json.dumps(prompt, ensure_ascii=False, indent=2))
    return str(p)

def make_v2():
    p=copy.deepcopy(BASELINE)
    for n in p.values():
        if n['class_type']=='LoraLoaderModelOnly':
            n['inputs']['strength_model']=0.5
    set_save_prefix(p, 'video/mac_i2v_v2_lora_half_asuka')
    return p

def make_v3():
    p=copy.deepcopy(V1)
    for n in p.values():
        if n['class_type']=='KSamplerAdvanced':
            n['inputs']['steps']=12
            if n['inputs']['start_at_step']==0:
                n['inputs']['end_at_step']=6
            else:
                n['inputs']['start_at_step']=6
                n['inputs']['end_at_step']=12
    set_save_prefix(p, 'video/mac_i2v_v3_no_lora_steps12_asuka')
    return p

def make_v4():
    p=copy.deepcopy(BASELINE)
    for n in p.values():
        if n['class_type']=='KSamplerAdvanced':
            n['inputs']['steps']=10
            if n['inputs']['start_at_step']==0:
                n['inputs']['end_at_step']=5
            else:
                n['inputs']['start_at_step']=5
                n['inputs']['end_at_step']=10
    set_save_prefix(p, 'video/mac_i2v_v4_lora_steps10_asuka')
    return p

def make_v5():
    p=copy.deepcopy(BASELINE)
    for n in p.values():
        if n['class_type']=='KSamplerAdvanced':
            n['inputs']['cfg']=1.5
    set_save_prefix(p, 'video/mac_i2v_v5_cfg15_asuka')
    return p

def make_v6():
    p=copy.deepcopy(BASELINE)
    for n in p.values():
        if n['class_type']=='WanImageToVideo':
            n['inputs']['width']=512
            n['inputs']['height']=512
    set_save_prefix(p, 'video/mac_i2v_v6_512x512_asuka')
    return p

def make_v7():
    p=copy.deepcopy(BASELINE)
    for n in p.values():
        if n['class_type']=='WanImageToVideo':
            n['inputs']['length']=41
    set_save_prefix(p, 'video/mac_i2v_v7_41frames_asuka')
    return p

def make_v8():
    p=copy.deepcopy(BASELINE)
    for n in p.values():
        if n['class_type']=='UnetLoaderGGUF':
            old=n['inputs']['unet_name']
            if 'HighNoise' in old:
                n['inputs']['unet_name']='Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf'
            elif 'LowNoise' in old:
                n['inputs']['unet_name']='Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf'
    set_save_prefix(p, 'video/mac_i2v_v8_q4km_asuka')
    return p

TESTS=[
    {'id':'V2','desc':'Lightning LoRA strength 1.0 → 0.5', 'make':make_v2, 'api':'video_wan2_2_14B_i2v_mac_api_v2_lora_half_strength.json', 'prefix':'video/mac_i2v_v2_lora_half_asuka', 'existing_pid':'1cee9c3a-717f-4de5-904d-d35ac0e54020'},
    {'id':'V3','desc':'no-Lightning LoRA + steps 6 → 12', 'make':make_v3, 'api':'video_wan2_2_14B_i2v_mac_api_v3_no_lora_steps12.json', 'prefix':'video/mac_i2v_v3_no_lora_steps12_asuka'},
    {'id':'V4','desc':'baseline Lightning + steps 6 → 10', 'make':make_v4, 'api':'video_wan2_2_14B_i2v_mac_api_v4_lora_steps10.json', 'prefix':'video/mac_i2v_v4_lora_steps10_asuka'},
    {'id':'V5','desc':'baseline Lightning + CFG 1.0 → 1.5', 'make':make_v5, 'api':'video_wan2_2_14B_i2v_mac_api_v5_cfg15.json', 'prefix':'video/mac_i2v_v5_cfg15_asuka'},
    {'id':'V6','desc':'baseline Lightning + resolution 480×480 → 512×512', 'make':make_v6, 'api':'video_wan2_2_14B_i2v_mac_api_v6_512x512.json', 'prefix':'video/mac_i2v_v6_512x512_asuka'},
    {'id':'V7','desc':'baseline Lightning + length 81 → 41 frames', 'make':make_v7, 'api':'video_wan2_2_14B_i2v_mac_api_v7_41frames.json', 'prefix':'video/mac_i2v_v7_41frames_asuka'},
    {'id':'V8','desc':'baseline Lightning + GGUF Q4_K_S → Q4_K_M', 'make':make_v8, 'api':'video_wan2_2_14B_i2v_mac_api_v8_q4km.json', 'prefix':'video/mac_i2v_v8_q4km_asuka'},
]

def main():
    print('Starting V2-V8 sequential ablation. Final report only after all terminal states.', flush=True)
    # verify server
    print('system', jget('/system_stats', 20)['devices'][0]['name'], flush=True)
    results=[]
    for t in TESTS:
        label=t['id']
        prompt=t['make']()
        api_path=save_api(prompt, t['api'])
        pid=t.get('existing_pid')
        resp=None
        if pid:
            print(f'{label}: adopting existing prompt_id={pid}', flush=True)
        else:
            while not queue_empty():
                print(f'{label}: waiting for queue to empty before submit', flush=True)
                time.sleep(30)
            pid, resp = submit(prompt, f'mac-i2v-{label.lower()}')
            print(f'{label}: submitted prompt_id={pid} resp={resp}', flush=True)
        item, elapsed=wait_terminal(pid, label, poll=60)
        status=item.get('status',{}).get('status_str')
        print(f'{label}: terminal status={status} elapsed={int(elapsed)}s', flush=True)
        rec={'id':label,'description':t['desc'],'prompt_id':pid,'api_path':api_path,'status':status,'elapsed_seconds':round(elapsed,1),'artifacts':[],'error':None}
        if status=='success':
            rec['artifacts']=collect_outputs(item, t['prefix'], label.lower())
        else:
            rec['error']=error_summary(item)
        results.append(rec)
        RESULT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        free_memory()
        time.sleep(20)
    write_report(results)
    print_report(results)

def write_report(results):
    lines=['# Mac Wan2.2 I2V V2–V8 ablation results','']
    lines.append('Baseline: `mac_i2v_baseline_asuka_faithful_00001_.mp4` — Lightning LoRA strength 1.0, 480×480, 81 frames, 6 steps, CFG 1.0, Q4_K_S.')
    lines.append('')
    lines.append('| ID | Change | Status | Duration | Output |')
    lines.append('|---|---|---|---:|---|')
    for r in results:
        art=r['artifacts'][0] if r.get('artifacts') else {}
        dur=''
        try: dur=art['ffprobe']['format']['duration']
        except Exception: pass
        out=art.get('video','') or (str(r.get('error'))[:80] if r.get('error') else '')
        lines.append(f"| {r['id']} | {r['description']} | {r['status']} | {dur} | `{out}` |")
    lines.append('')
    for r in results:
        lines.append(f"## {r['id']} — {r['description']}")
        lines.append(f"- prompt_id: `{r['prompt_id']}`")
        lines.append(f"- status: `{r['status']}`")
        lines.append(f"- api: `{r['api_path']}`")
        if r.get('error'):
            lines.append('- error:')
            lines.append('```json')
            lines.append(json.dumps(r['error'], ensure_ascii=False, indent=2))
            lines.append('```')
        for a in r.get('artifacts') or []:
            lines.append(f"- video: `{a['video']}`")
            lines.append(f"- contact: `{a.get('contact')}`")
            lines.append('- ffprobe:')
            lines.append('```json')
            lines.append(json.dumps(a.get('ffprobe'), ensure_ascii=False, indent=2)[:2000])
            lines.append('```')
        lines.append('')
    REPORT_MD.write_text('\n'.join(lines))

def print_report(results):
    print('\n=== FINAL V2-V8 ABLATION REPORT ===')
    print(f'Report file: {REPORT_MD}')
    print(f'JSON file: {RESULT_JSON}')
    print('Baseline reference: MEDIA:/Users/tf00185088/comfyui/output/video/mac_i2v_baseline_asuka_faithful_00001_.mp4')
    print('V1 reference no-Lightning: MEDIA:/Users/tf00185088/comfyui/output/video/mac_i2v_v1_no_lightning_lora_asuka_00001_.mp4')
    for r in results:
        print(f"\n{r['id']} — {r['description']} — {r['status']} — prompt_id={r['prompt_id']}")
        if r.get('error'):
            print('ERROR', json.dumps(r['error'], ensure_ascii=False)[:1000])
        for a in r.get('artifacts') or []:
            print('MEDIA:'+a['video'])
            if a.get('contact'):
                print('MEDIA:'+a['contact'])
            try:
                s=a['ffprobe']['streams'][0]; f=a['ffprobe']['format']
                print(f"ffprobe: {s.get('width')}x{s.get('height')} {s.get('nb_frames')} frames {s.get('r_frame_rate')} duration={f.get('duration')} size={f.get('size')}")
            except Exception:
                print('ffprobe:', json.dumps(a.get('ffprobe'), ensure_ascii=False)[:500])
    print('\nNotes: visual ranking/interpretation should be done after reviewing the attached videos/contact sheets. No further tests were submitted after V8.')

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print('FATAL', type(e).__name__, e, flush=True)
        raise
