import json
from pathlib import Path
for name in ('download_state.json','sd35_download_state.json'):
    p=Path('/Users/tf00185088/Desktop/ai-drawing/model_benchmarks/20260711')/name
    d=json.loads(p.read_text())
    for rec in d.get('resources',{}).values():
        if rec.get('status')=='verified':
            rec.pop('error',None)
            if rec.get('size'):
                rec['expected_size']=rec['size']
                rec['bytes']=rec['size']
    tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(p)
    print(p)
