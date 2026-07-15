#!/usr/bin/env python3
"""One-time migration from review/retry benchmark semantics to one-pass collection."""
import json
from datetime import datetime
from pathlib import Path
p=Path(__file__).with_name('benchmark_state.json')
d=json.loads(p.read_text())
d['mode']='one_pass_collect_no_visual_review'
d['status']='benchmarking'
d['rules']={
 'images_per_model':3,
 'generation_attempts_per_slot':1,
 'retry_only_on_technical_submission_failure':False,
 'review_required':False,
 'visual_analysis_forbidden':True,
 'seed_policy':'random, recorded',
 'output_root':'/Users/tf00185088/Desktop/ai-drawing/outputs/review/mio-10-model-benchmark-20260711',
 'finished_root':'/Volumes/AI-Drawing-16T/finished-works/images/starfall-night/model-benchmark-20260711',
 'complete_marker':'/Users/tf00185088/Desktop/ai-drawing/model_benchmarks/20260711/benchmark_complete.json'
}
for m in d['models']:
    gens=m.setdefault('generations',{})
    for pose,g in list(gens.items()):
        if not isinstance(g,dict): continue
        latest=g.get('retry') if isinstance(g.get('retry'),dict) and g['retry'].get('image_path') else g
        if latest.get('image_path'):
            history=g.copy()
            gens[pose]={k:latest.get(k) for k in ('job_id','image_id','image_path','resource','seed','steps','cfg','sampler','scheduler','denoise','reference','workflow_type','submitted_via') if latest.get(k) is not None}
            gens[pose]['status']='completed'
            gens[pose]['legacy_review_history']=history
    completed=sum(1 for pose in ('standing','seated_reading','telescope') if gens.get(pose,{}).get('status')=='completed')
    m['status']='completed' if completed==3 else ('in_progress' if completed else 'pending')
d['updated_at']=datetime.now().astimezone().isoformat(timespec='seconds')
t=p.with_suffix('.json.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(p)
print('migrated',sum(1 for m in d['models'] for g in m.get('generations',{}).values() if g.get('status')=='completed'),'completed slots')
