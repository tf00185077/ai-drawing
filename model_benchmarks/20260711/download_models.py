#!/usr/bin/env python3
import concurrent.futures
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MANIFEST = Path('/Users/tf00185088/Desktop/ai-drawing/model_benchmarks/20260711/download_manifest.json')
STATE = MANIFEST.with_name('download_state.json')
CIVITAI_TOKEN_PATH = Path.home()/'.config/civitai/token.txt'
HF_TOKEN_PATH = Path.home()/'.cache/huggingface/token'
CHUNK = 8 * 1024 * 1024
lock = threading.Lock()
manifest = json.loads(MANIFEST.read_text())
root = Path(manifest['model_root'])
civitai_token = CIVITAI_TOKEN_PATH.read_text().strip() if CIVITAI_TOKEN_PATH.exists() else None
hf_token = HF_TOKEN_PATH.read_text().strip() if HF_TOKEN_PATH.exists() else None
state = {'campaign': manifest['campaign'], 'updated_at': None, 'resources': {}}
if STATE.exists():
    try: state = json.loads(STATE.read_text())
    except Exception: pass
state.setdefault('resources', {})

def save_state():
    state['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    os.replace(tmp, STATE)

def headers_for(r, range_start=None):
    h = {'User-Agent': 'Hermes-Model-Benchmark/1.0'}
    if 'huggingface.co' in r['url'] and hf_token:
        h['Authorization'] = 'Bearer ' + hf_token
    if range_start:
        h['Range'] = f'bytes={range_start}-'
    return h

def effective_url(r):
    if r.get('auth') == 'civitai' and civitai_token:
        separator = '&' if '?' in r['url'] else '?'
        return r['url'] + separator + urllib.parse.urlencode({'token': civitai_token})
    return r['url']

def discover_sha(r):
    if r.get('sha256'): return r['sha256'].lower()
    try:
        req = urllib.request.Request(effective_url(r), headers=headers_for(r), method='HEAD')
        with urllib.request.urlopen(req, timeout=60) as resp:
            for key in ('x-linked-etag', 'etag'):
                value = (resp.headers.get(key) or '').strip('"')
                if re.fullmatch(r'[0-9a-fA-F]{64}', value):
                    return value.lower()
    except Exception:
        pass
    return None

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b=f.read(CHUNK)
            if not b: break
            h.update(b)
    return h.hexdigest()

def download(r):
    dest = root/r['dest']; part=dest.with_suffix(dest.suffix+'.part')
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected_sha=discover_sha(r)
    rec=state['resources'].setdefault(r['dest'], {'model':r['model'],'url':r['url']})
    if dest.exists():
        actual=sha256(dest)
        if expected_sha and actual != expected_sha:
            dest.rename(part)
        else:
            rec.update(status='verified',size=dest.stat().st_size,sha256=actual,expected_sha256=expected_sha)
            with lock: save_state()
            return f"VERIFIED existing {r['model']}"
    start=part.stat().st_size if part.exists() else 0
    if start and expected_sha and start == r.get('size'):
        actual=sha256(part)
        if actual == expected_sha:
            os.replace(part,dest)
            rec.update(status='verified',size=dest.stat().st_size,sha256=actual,expected_sha256=expected_sha)
            with lock: save_state()
            return f"VERIFIED completed part {r['model']} {dest.stat().st_size/1024**3:.2f} GiB"
    rec.update(status='downloading',bytes=start,expected_size=r.get('size'),expected_sha256=expected_sha)
    with lock: save_state()
    req=urllib.request.Request(effective_url(r),headers=headers_for(r,start if start else None))
    try:
        resp=urllib.request.urlopen(req,timeout=120)
    except urllib.error.HTTPError as e:
        rec.update(status='blocked' if e.code in (401,403) else 'failed',error=f'HTTP {e.code}')
        with lock: save_state()
        return f"FAILED {r['model']}: HTTP {e.code}"
    mode='ab' if start and getattr(resp,'status',200)==206 else 'wb'
    if mode=='wb': start=0
    last=time.time();done=start
    with resp, part.open(mode) as f:
        while True:
            b=resp.read(CHUNK)
            if not b: break
            f.write(b);done+=len(b)
            if time.time()-last>=20:
                rec.update(bytes=done,status='downloading')
                with lock: save_state()
                print(f"PROGRESS {r['model']} {done/1024**3:.2f} GiB",flush=True);last=time.time()
    actual=sha256(part)
    if expected_sha and actual != expected_sha:
        rec.update(status='failed',bytes=part.stat().st_size,sha256=actual,error='sha256 mismatch')
        with lock: save_state()
        return f"FAILED {r['model']}: sha256 mismatch"
    os.replace(part,dest)
    rec.update(status='verified',size=dest.stat().st_size,sha256=actual,expected_sha256=expected_sha)
    with lock: save_state()
    return f"VERIFIED {r['model']} {dest.stat().st_size/1024**3:.2f} GiB"

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    futures=[ex.submit(download,r) for r in manifest['resources']]
    for f in concurrent.futures.as_completed(futures):
        try: print(f.result(),flush=True)
        except Exception as e: print('WORKER_ERROR',repr(e),flush=True)
save_state()
print('DOWNLOAD_CAMPAIGN_FINISHED',flush=True)
