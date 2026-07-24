#!/usr/bin/env python3
"""Package and verify the historical initial 7-condition/21-image matrix.

This script operates on the pre-Epoch-2 intermediate manifest. The authoritative
final 8-condition/24-image packages and manifest remain on the external volume
under ``shampoohatslime-anima-v1-comparison-by-condition-8`` and
``style_shampoohatslime-first50-anima-v1-matrix-jobs-final-8-conditions.json``.
"""
import hashlib, json, shutil, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, PngImagePlugin

ROOT=Path('/Volumes/AI-Drawing-16T/ai-drawing')
OUTROOT=ROOT/'training/lora/output'
JOBS=OUTROOT/'style_shampoohatslime-first50-anima-v1-matrix-jobs.json'
MASTER=OUTROOT/'style_shampoohatslime-first50-anima-v1-matrix-manifest.json'
ZIPDIR=OUTROOT/'shampoohatslime-anima-v1-comparison-by-condition'
GALLERY=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery').resolve()
BASE='http://127.0.0.1:8001'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def get(path):
 with opener.open(BASE+path,timeout=30) as r: return json.loads(r.read())
def pixel_info(path):
 with Image.open(path) as im:
  im.load(); return {'mode':im.mode,'dimensions':list(im.size),'pixel_sha256':hashlib.sha256(im.tobytes()).hexdigest()}
def optimized_copy(src,dst):
 with Image.open(src) as im:
  im.load(); before={'mode':im.mode,'dimensions':list(im.size),'pixel_sha256':hashlib.sha256(im.tobytes()).hexdigest()}
  pnginfo=PngImagePlugin.PngInfo()
  preserved=[]
  for k,v in im.info.items():
   if isinstance(k,str) and isinstance(v,str): pnginfo.add_text(k,v); preserved.append(k)
  im.save(dst,format='PNG',optimize=True,compress_level=9,pnginfo=pnginfo)
 after=pixel_info(dst)
 if before!=after: raise RuntimeError(f'pixel mismatch {src} {before} {after}')
 return {'source':str(src),'archive_copy':str(dst),'source_file_sha256':sha(src),'archive_file_sha256':sha(dst),
         **after,'text_metadata_preserved':sorted(preserved),'lossless_pixel_equivalent':True}

def training_artifact(name):
 p=OUTROOT/name
 return {'name':name,'path':str(p),'realpath':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p)}

if not ROOT.is_dir() or not ROOT.exists(): raise RuntimeError('external volume unavailable')
probe=ROOT/'.anima_matrix_write_probe'; probe.write_text('ok'); probe.unlink()
if not str(GALLERY).startswith(str(ROOT.resolve())+'/'): raise RuntimeError(f'gallery is not on external volume: {GALLERY}')
raw=json.loads(JOBS.read_text())
if raw.get('summary')!={'completed':21}: raise RuntimeError(f'jobs not all complete: {raw.get("summary")}')

train=[training_artifact('style_shampoohatslime-first50-anima-v1-000004.safetensors'),training_artifact('style_shampoohatslime-first50-anima-v1-000006.safetensors'),training_artifact('style_shampoohatslime-first50-anima-v1.safetensors')]
master={
 'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),
 'training':{'status':'completed','log':str(OUTROOT/'style_shampoohatslime-first50-anima-v1.train.log'),'total_steps':1600,'epochs':8,
             'terminal_evidence':'model saved; progress 1600/1600; no live trainer process','artifacts':train},
 'base_components':{'diffusion_model':'anima_baseV10.safetensors','text_encoder':'anima_baseV10_txt.safetensors','vae':'qwen_image_vae.safetensors','inference_loras_excluded':['Moonlit recipe LoRAs']},
 'trigger':'connexion','fixed_settings':raw['settings'],'architecture_adaptation':raw['settings']['architecture_adaptation'],
 'source_comparison':{'illustrious_manifest':str(OUTROOT/'style_shampoohatslime-first50-v2-matrix-jobs.json'),'seed':3174638636},
 'conditions':{},'images':{},'zip_archives':{}
}

for label,jid in raw['jobs'].items():
 res=raw['results'][label]
 if res.get('status')!='completed': raise RuntimeError(f'{label} not complete')
 artifacts=[a for a in res.get('artifacts',[]) if a.get('source_node_type')=='SaveImage' and a.get('mime_type')=='image/png']
 if len(artifacts)!=1: raise RuntimeError(f'{label}: expected exactly one SaveImage PNG, got {artifacts}')
 image_id=res['image_id']; detail=get(f'/api/gallery/{image_id}'); art=get(f'/api/gallery/artifacts/{artifacts[0]["id"]}')
 src=(GALLERY/detail['image_path']).resolve()
 if not src.is_file() or not str(src).startswith(str(ROOT.resolve())+'/'): raise RuntimeError(f'bad permanent path {src}')
 tech=pixel_info(src)
 eff=raw['effective'][label]
 expected=raw['settings']
 checks={
  'seed':detail.get('seed')==expected['seed'],'steps':detail.get('steps')==expected['steps'],'cfg':detail.get('cfg')==expected['cfg'],
  'prompt':detail.get('prompt')==eff['prompt'],'negative_prompt':detail.get('negative_prompt')==expected['negative_prompt'],
  'dimensions':tech['dimensions']==[expected['width'],expected['height']],
  'diffusion_model':detail.get('diffusion_model')==expected['diffusion_model'],'text_encoder':detail.get('text_encoder')==expected['text_encoder'],'vae':detail.get('vae')==expected['vae'],
  'artifact_dimensions':art.get('width') in (None,expected['width']) and art.get('height') in (None,expected['height'])
 }
 if not all(checks.values()): raise RuntimeError(f'{label} metadata mismatch {checks} detail={detail}')
 rec={'label':label,'condition':eff['condition'],'character':eff['character'],'job_id':jid,'image_id':image_id,'artifact_id':artifacts[0]['id'],
      'gallery_path':detail['image_path'],'permanent_path':str(src),'bytes':src.stat().st_size,'file_sha256':sha(src),**tech,
      'prompt':detail['prompt'],'negative_prompt':detail['negative_prompt'],'seed':detail['seed'],'steps':detail['steps'],'cfg':detail['cfg'],
      'sampler_name':expected['sampler_name'],'scheduler':expected['scheduler'],'denoise':expected['denoise'],
      'width':expected['width'],'height':expected['height'],'template':detail.get('template'),'diffusion_model':detail.get('diffusion_model'),
      'text_encoder':detail.get('text_encoder'),'vae':detail.get('vae'),'lora':eff['lora'],'lora_strength':eff['lora_strength'],'trigger':eff['trigger'],
      'technical_checks':checks,'workflow_json':art.get('workflow_json')}
 master['images'][label]=rec
 master['conditions'].setdefault(eff['condition'],{'trigger':eff['trigger'],'lora':eff['lora'],'lora_strength':eff['lora_strength'],'images':[]})['images'].append(label)

ZIPDIR.mkdir(parents=True,exist_ok=True)
for old in ZIPDIR.glob('*.zip'): old.unlink()
for cond,cdata in sorted(master['conditions'].items()):
 stage=ZIPDIR/(cond+'.stage')
 if stage.exists(): shutil.rmtree(stage)
 stage.mkdir()
 copy_records=[]
 labels=sorted(cdata['images'],key=lambda x:['emma','karin','kanata'].index(master['images'][x]['character']))
 for label in labels:
  rec=master['images'][label]; dst=stage/(rec['character']+'.png')
  copy_records.append(optimized_copy(Path(rec['permanent_path']),dst))
 cond_manifest={'condition':cond,'trigger':cdata['trigger'],'lora':cdata['lora'],'lora_strength':cdata['lora_strength'],
                'base_components':master['base_components'],'settings':raw['settings'],'images':[master['images'][x] for x in labels],
                'archive_copies':copy_records}
 (stage/'MANIFEST.json').write_text(json.dumps(cond_manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=[f'Condition: {cond}',f'Trigger: {cdata["trigger"] or "(none)"}',f'LoRA: {cdata["lora"] or "(none)"}',f'LoRA strength: {cdata["lora_strength"]}',
        'Characters: emma.png, karin.png, kanata.png','All PNG archive copies are losslessly recompressed; decoded mode, dimensions, and pixel-byte SHA-256 match Gallery originals.']
 (stage/'INDEX.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 zpath=ZIPDIR/(cond+'.zip')
 with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(stage.iterdir()): z.write(p,p.name)
 with zipfile.ZipFile(zpath) as z:
  bad=z.testzip(); names=sorted(z.namelist())
 if bad or names!=['INDEX.txt','MANIFEST.json','emma.png','kanata.png','karin.png']: raise RuntimeError(f'bad zip {zpath} {bad} {names}')
 if zpath.stat().st_size>=10*1024*1024: raise RuntimeError(f'zip exceeds 10 MiB: {zpath} {zpath.stat().st_size}')
 master['zip_archives'][cond]={'path':str(zpath),'bytes':zpath.stat().st_size,'sha256':sha(zpath),'testzip':'ok','entries':names,'lossless_recompression':True}
 shutil.rmtree(stage)

MASTER.write_text(json.dumps(master,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'master_manifest':str(MASTER),'images':len(master['images']),'conditions':len(master['conditions']),'zips':master['zip_archives']},ensure_ascii=False,indent=2))
