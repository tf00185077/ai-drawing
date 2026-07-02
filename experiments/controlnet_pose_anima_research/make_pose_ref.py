#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw
W,H=832,1216
img=Image.new('RGB',(W,H),(0,0,0))
d=ImageDraw.Draw(img)
# COCO-ish/OpenPose-ish colored stick figure, intentionally asymmetrical full-body pose.
pts={
 'head':(416,170),'neck':(416,285),'mid':(416,555),'pelvis':(416,690),
 'l_shoulder':(315,325),'l_elbow':(220,455),'l_wrist':(165,610),
 'r_shoulder':(515,325),'r_elbow':(625,250),'r_wrist':(710,175),
 'l_hip':(355,705),'l_knee':(305,910),'l_ankle':(245,1110),
 'r_hip':(475,705),'r_knee':(555,910),'r_ankle':(635,1110),
}
# colors loosely inspired by OpenPose limb palette
limbs=[
 ('neck','head',(255,255,255)),
 ('neck','l_shoulder',(255,0,0)),('l_shoulder','l_elbow',(255,85,0)),('l_elbow','l_wrist',(255,170,0)),
 ('neck','r_shoulder',(0,255,0)),('r_shoulder','r_elbow',(0,255,85)),('r_elbow','r_wrist',(0,255,170)),
 ('neck','mid',(0,170,255)),('mid','pelvis',(0,85,255)),
 ('pelvis','l_hip',(170,0,255)),('l_hip','l_knee',(255,0,255)),('l_knee','l_ankle',(255,0,170)),
 ('pelvis','r_hip',(85,255,255)),('r_hip','r_knee',(0,255,255)),('r_knee','r_ankle',(0,170,255)),
]
for a,b,c in limbs:
    d.line([pts[a],pts[b]], fill=c, width=14)
for name,p in pts.items():
    r=12 if name!='head' else 18
    d.ellipse([p[0]-r,p[1]-r,p[0]+r,p[1]+r], fill=(255,255,255), outline=(0,0,0), width=2)
# simple face/hand keypoint hints
for p in [(392,160),(440,160),(416,185),(402,198),(430,198), pts['l_wrist'], pts['r_wrist']]:
    d.ellipse([p[0]-5,p[1]-5,p[0]+5,p[1]+5], fill=(255,255,0))
out=Path('/Users/tf00185088/Desktop/ai-drawing/outputs/gallery/2026-06-26/anima_lllite_pose_ref_asym_832x1216.png')
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out)
print(out)
