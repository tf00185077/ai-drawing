#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import dispatch
p=argparse.ArgumentParser(description='Resume a paused/blocked pipeline stage')
p.add_argument('stage_id');p.add_argument('owner_input');a=p.parse_args()
l=dispatch.lock()
if not l: raise SystemExit('dispatcher lock held')
try:
 s=dispatch.load_state(); st=dispatch.stage(s,a.stage_id)
 if not st: raise SystemExit('unknown stage')
 if s['goal']['status'] not in ('PAUSED','ACTIVE') or st['status'] not in ('BLOCKED','FAILED','READY'): raise SystemExit('stage is not resumable')
 st['owner_input']=a.owner_input;st['blocked_reason']=None;st['status']='READY';s['goal']['status']='ACTIVE';dispatch.save(s)
finally: dispatch.unlock(l)
