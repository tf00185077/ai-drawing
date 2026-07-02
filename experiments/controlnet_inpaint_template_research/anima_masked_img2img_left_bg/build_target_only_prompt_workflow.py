#!/usr/bin/env python3
import copy, json
from pathlib import Path
ROOT=Path('/Users/tf00185088/Desktop/ai-drawing')
BASE=json.loads((ROOT/'experiments/controlnet_inpaint_template_research/anima_masked_img2img_left_bg/masked_left_bg_moonlit_api.json').read_text())
EXP=ROOT/'experiments/controlnet_inpaint_template_research/anima_masked_img2img_left_bg'
wf=copy.deepcopy(BASE)
# Target-only prompt: no character identity / preserve language.
wf['5']['inputs']['text'] = (
    'deep moonlit blue cinematic background, dark navy gradient, glowing cyan rim light, '
    'misty atmosphere, luminous blue fog, distant soft city lights, high contrast glossy moonlit lighting, '
    'visible blue light beams, dramatic night ambience, rich cool shadows, polished semi-real niji rendering'
)
wf['6']['inputs']['text'] = (
    'flat pastel background, bright daytime, white empty background, washed out, low contrast, muddy colors, text, watermark, logo'
)
wf['7']['inputs']['seed'] = 2606268202
wf['9']['inputs']['filename_prefix'] = 'anima_masked_img2img_left_bg_target_only'
out=EXP/'masked_left_bg_target_only_prompt_api.json'
out.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
print(out)
print(json.dumps(wf, ensure_ascii=False))
