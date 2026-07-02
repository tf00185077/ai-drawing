#!/usr/bin/env python3
import copy, json
from pathlib import Path
ROOT=Path('/Users/tf00185088/Desktop/ai-drawing')
BASE=json.loads((ROOT/'experiments/controlnet_inpaint_template_research/anima_img2img_niji_moonlit_style/niji_moonlit_img2img_d065_api.json').read_text())
EXP=ROOT/'experiments/controlnet_inpaint_template_research/anima_masked_img2img_left_bg'
EXP.mkdir(parents=True, exist_ok=True)
wf=copy.deepcopy(BASE)
# LoadImage will be replaced by MCP image=...
wf['14']['inputs']['image']='anima_masked_input_placeholder.png'
# Add mask loader; MCP mask=... should replace this LoadImageMask image.
wf['16']={
  'class_type':'LoadImageMask',
  'inputs':{'image':'mask_left_background_soft_832x1216.png','channel':'red'},
  '_meta':{'title':'Load repaint mask (white=repaint)'}
}
# Apply mask to encoded latent.
wf['17']={
  'class_type':'SetLatentNoiseMask',
  'inputs':{'samples':['15',0],'mask':['16',0]},
  '_meta':{'title':'Set latent noise mask'}
}
wf['7']['inputs']['latent_image']=['17',0]
wf['7']['inputs']['denoise']=0.82
wf['7']['inputs']['steps']=24
wf['7']['inputs']['cfg']=5.5
wf['7']['inputs']['seed']=2606268201
# Prompt focuses on changing only background zone.
wf['5']['inputs']['text']=(
    'masterpiece, best quality, high-quality Anima illustration, semi-realistic niji anime rendering, '
    'Asuka Langley Soryu from Evangelion, full body, head-to-toe, red plugsuit, orange hair, blue eyes, '
    'preserve character body and face outside mask, preserve full-body framing, '
    'localized background repaint inside mask only, deep moonlit blue cinematic background, cool blue rim light, '
    'glowing mist, glossy dark gradient, subtle star-like bokeh particles, high-contrast moonlit atmosphere, '
    'clean edge transition, refined semi-real rendering'
)
wf['6']['inputs']['text']=(
    'worst quality, low quality, cropped body, cropped head, cropped feet, feet out of frame, close-up, portrait crop, '
    'bad anatomy, deformed hands, extra limbs, distorted face, character changed outside mask, redrawn face, redrawn body, '
    'text, watermark, logo, muddy colors, bright daytime, flat pastel coloring'
)
# Composite decoded repaint back onto original so non-mask region stays original.
wf['18']={
  'class_type':'ImageCompositeMasked',
  'inputs':{'destination':['14',0],'source':['8',0],'x':0,'y':0,'resize_source':False,'mask':['16',0]},
  '_meta':{'title':'Composite masked repaint onto original'}
}
wf['9']['inputs']['filename_prefix']='anima_masked_img2img_left_bg_moonlit'
wf['9']['inputs']['images']=['18',0]
wf['13']['inputs']['images']=['18',0]
out=EXP/'masked_left_bg_moonlit_api.json'
out.write_text(json.dumps(wf,ensure_ascii=False,indent=2))
print(out)
print(json.dumps(wf,ensure_ascii=False))
