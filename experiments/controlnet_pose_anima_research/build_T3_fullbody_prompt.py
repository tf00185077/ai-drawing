#!/usr/bin/env python3
import json, copy
from pathlib import Path
EXP=Path('/Users/tf00185088/Desktop/ai-drawing/experiments/controlnet_pose_anima_research')
base=json.loads((EXP/'T2_pose_s14.json').read_text())
wf=copy.deepcopy(base)
wf['5']['inputs']['text'] = (
    '1girl, solo, full body, complete head-to-toe character, entire body visible, feet visible, shoes visible, '
    'zoomed out camera, long shot, standing on ground, centered full-body composition, lots of empty space around character, '
    'orange hair, blue eyes, red futuristic plugsuit, dynamic asymmetrical standing pose, one arm raised high, one arm lowered, legs apart, '
    'clean anime illustration, detailed character, plain white background'
)
wf['6']['inputs']['text'] = (
    'half body, upper body, close-up, portrait, bust shot, cropped body, cropped legs, cropped feet, feet out of frame, '
    'head cut off, out of frame, low quality, worst quality, bad anatomy, extra limbs, extra fingers, distorted hands, multiple people, text, watermark, logo'
)
wf['7']['inputs']['seed']=2606269302
wf['15']['inputs']['strength']=1.4
wf['9']['inputs']['filename_prefix']='anima_lllite_pose_T3_fullbody_prompt_s14'
out=EXP/'T3_fullbody_prompt_s14.json'
out.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
print(out)
