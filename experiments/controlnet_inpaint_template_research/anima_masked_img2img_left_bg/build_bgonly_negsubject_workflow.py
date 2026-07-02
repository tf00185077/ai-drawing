#!/usr/bin/env python3
import copy, json
from pathlib import Path
ROOT=Path('/Users/tf00185088/Desktop/ai-drawing')
BASE=json.loads((ROOT/'experiments/controlnet_inpaint_template_research/anima_masked_img2img_left_bg/masked_left_bg_moonlit_api.json').read_text())
EXP=ROOT/'experiments/controlnet_inpaint_template_research/anima_masked_img2img_left_bg'
wf=copy.deepcopy(BASE)
wf['5']['inputs']['text'] = (
    'background only, no subject, no character, no person, '
    'deep moonlit blue abstract cinematic background, dark navy gradient, glowing cyan rim light, '
    'misty atmosphere, luminous blue fog, distant soft city lights, visible blue light beams, '
    'dramatic night ambience, rich cool shadows, glossy high contrast moonlit lighting, '
    'empty atmospheric background, polished semi-real niji rendering'
)
wf['6']['inputs']['text'] = (
    'person, face, head, eyes, body, character, portrait, girl, woman, human, skin, hair, '
    'extra person, duplicate character, cropped face, close-up face, facial features, body parts, '
    'flat pastel background, bright daytime, white empty background, washed out, low contrast, muddy colors, text, watermark, logo'
)
wf['7']['inputs']['seed'] = 2606268203
wf['7']['inputs']['denoise'] = 0.88
wf['7']['inputs']['cfg'] = 6.0
wf['9']['inputs']['filename_prefix'] = 'anima_masked_img2img_left_bg_bgonly_negsubject'
out=EXP/'masked_left_bg_bgonly_negsubject_api.json'
out.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
print(out)
print(json.dumps(wf, ensure_ascii=False))
