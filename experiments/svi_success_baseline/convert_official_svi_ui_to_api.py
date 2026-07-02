#!/usr/bin/env python3
import json, urllib.request
from pathlib import Path
from collections import defaultdict, deque

UI=Path('official_svi_wan22_10clips.json')
OUT=Path('official_svi_wan22_2clip_baseline_api.json')
OBJ=json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info',timeout=30))
w=json.loads(UI.read_text())
nodes={str(n['id']):n for n in w['nodes']}
links={int(l[0]):l for l in w['links']}
# Build input link by target node/slot and output link by source node/slot
input_link={}
for l in w['links']:
    lid,src,src_slot,dst,dst_slot,typ=l
    input_link[(str(dst), int(dst_slot))]=int(lid)

set_source={}
for nid,n in nodes.items():
    if n['type']=='SetNode':
        name=(n.get('widgets_values') or [''])[0]
        # SetNode should have one input socket; find its linked source.
        src=None
        for i,inp in enumerate(n.get('inputs') or []):
            lid=inp.get('link')
            if lid is not None:
                src=links[int(lid)]
                break
        set_source[name]=src

def resolve_link(lid, seen=None):
    if seen is None: seen=set()
    if lid is None: return None
    lid=int(lid)
    if lid in seen: raise RuntimeError('link cycle')
    seen.add(lid)
    link=links[lid]
    _,src,src_slot,dst,dst_slot,typ=link
    sn=nodes[str(src)]
    if sn['type']=='Reroute':
        # reroute source is whatever feeds input slot 0
        in_lid=None
        for inp in sn.get('inputs') or []:
            if inp.get('link') is not None:
                in_lid=inp.get('link'); break
        return resolve_link(in_lid, seen)
    if sn['type']=='GetNode':
        name=(sn.get('widgets_values') or [''])[0]
        src_link=set_source.get(name)
        if src_link is None: raise RuntimeError(f'GetNode {src} name {name} has no Set source')
        # Use the SetNode's linked input source.
        return resolve_link(src_link[0], seen)
    if sn['type']=='SetNode':
        # SetNode can itself be the source of a link; bypass it to the linked input.
        in_lid=None
        for inp in sn.get('inputs') or []:
            if inp.get('link') is not None:
                in_lid=inp.get('link'); break
        return resolve_link(in_lid, seen)
    return (str(src), int(src_slot))

def primitive_input_names(cls):
    info=OBJ.get(cls)
    if not info: return []
    out=[]
    for section in ['required','optional']:
        for name,spec in (info.get('input',{}).get(section,{}) or {}).items():
            # node inputs are strings like LATENT/WANVIDEOMODEL/IMAGE; widgets are INT/FLOAT/BOOLEAN/STRING or combo list
            typ=spec[0] if isinstance(spec,(list,tuple)) and spec else spec
            if isinstance(typ, list) or typ in ['INT','FLOAT','BOOLEAN','STRING']:
                out.append(name)
    return out

def all_input_names(cls):
    info=OBJ.get(cls)
    if not info: return []
    out=[]
    for section in ['required','optional']:
        out += list((info.get('input',{}).get(section,{}) or {}).keys())
    return out

def widgets_to_values(node):
    vals=node.get('widgets_values')
    if vals is None: return {}
    cls=node['type']
    if isinstance(vals, dict):
        # VHS_VideoCombine stores named widget dict
        return {k:v for k,v in vals.items() if k in all_input_names(cls) or k in primitive_input_names(cls)}
    if not isinstance(vals, list): vals=[vals]
    # Kijai WanVideoSampler workflow JSON predates the current schema and has
    # an extra seed_mode widget after seed. Map it explicitly to avoid shifting
    # force_offload/scheduler/rope/etc.
    if cls=='WanVideoSampler':
        names=['steps','cfg','shift','seed','_seed_mode_removed','force_offload','scheduler','riflex_freq_index','denoise_strength','batched_cfg','rope_function','start_step','end_step','_unused']
        raw={name: vals[i] for i,name in enumerate(names) if i < len(vals) and not name.startswith('_')}
        linked={inp.get('name') for inp in (node.get('inputs') or []) if inp.get('link') is not None}
        return {k:v for k,v in raw.items() if k not in linked}
    result={}
    i=0
    # IMPORTANT: for UI workflows, widgets_values are ordered by the UI node's
    # input list entries that carry a `widget`, not by current object_info
    # schema order. Linked widget inputs still consume a widget value, but the
    # link wins and no literal value is emitted for that input.
    for inp in (node.get('inputs') or []):
        if 'widget' not in inp:
            continue
        name=inp.get('name')
        if i >= len(vals):
            break
        val=vals[i]
        i += 1
        if name and inp.get('link') is None:
            result[name]=val
    return result

# Choose official second saved output node for a two-clip baseline.
TARGET='210'  # VHS_VideoCombine, save_output True, second visible output in official workflow
# ancestor traversal through inputs, resolving Get/Set/Reroute to real sources
needed=set()
def visit(nid):
    nid=str(nid)
    if nid in needed: return
    n=nodes[nid]
    if n['type'] in ['Reroute','SetNode','GetNode']:
        return
    needed.add(nid)
    for idx,inp in enumerate(n.get('inputs') or []):
        lid=inp.get('link')
        if lid is None: continue
        src=resolve_link(lid)
        if src: visit(src[0])
visit(TARGET)
print('needed nodes',len(needed))
print('types')
from collections import Counter
c=Counter(nodes[n]['type'] for n in needed)
for t,k in c.most_common(): print(k,t)

api={}
for nid in sorted(needed, key=lambda x:int(x)):
    node=nodes[nid]
    cls=node['type']
    if cls not in OBJ:
        raise RuntimeError(f'missing class {cls} node {nid}')
    inputs={}
    for idx,inp in enumerate(node.get('inputs') or []):
        name=inp.get('name')
        lid=inp.get('link')
        if name and lid is not None:
            src=resolve_link(lid)
            if src:
                inputs[name]=[src[0], src[1]]
    inputs.update(widgets_to_values(node))
    # Local resource substitutions preserving official route as much as possible.
    if cls=='WanVideoModelLoader':
        if 'HIGH' in inputs.get('model',''):
            inputs['model']='Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
        elif 'LOW' in inputs.get('model',''):
            inputs['model']='Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
        inputs['attention_mode']='sdpa'  # Mac-safe; official used sageattn (CUDA-oriented)
    if cls=='LoadWanVideoT5TextEncoder':
        inputs['model_name']='umt5-xxl-enc-bf16.safetensors'
        inputs['load_device']='offload_device'
    if cls=='WanVideoVAELoader':
        inputs['model_name']='Wan2_1_VAE_bf16.safetensors'
    if cls=='LoadImage':
        # will stage woman.jpg in ComfyUI input
        inputs['image']='svi_success_baseline/woman.jpg'
    if cls=='VHS_VideoCombine':
        inputs['filename_prefix']='svi_success_baseline_official_2clip'
        inputs['save_output']=True
        inputs['format']='video/h264-mp4'
        inputs['frame_rate']=16
    api[nid]={'class_type':cls,'inputs':inputs}
OUT.write_text(json.dumps(api,ensure_ascii=False,indent=2))
print('wrote',OUT)
