#!/usr/bin/env python3
import json
from pathlib import Path
p=Path(__file__).resolve().parent/'state.json'
s=json.loads(p.read_text(encoding='utf-8')); stages=s['stages']; counts={}
for x in stages: counts[x['status']]=counts.get(x['status'],0)+1
print(f"pipeline health: goal={s['goal']['id']} status={s['goal']['status']} stages={len(stages)} committed={counts.get('COMMITTED',0)} active={sum(counts.get(k,0) for k in ('READY','DISPATCHED','RUNNING','AWAITING_REVIEW','REVIEWING','ACCEPTED'))} updated={s['updated_at']}")
