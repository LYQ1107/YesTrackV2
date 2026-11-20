#!/usr/bin/env python3
"""Supplement real empty-GT-frame FP examples without creating G expressions."""
import csv
import json
from pathlib import Path
import textwrap

import numpy as np
from PIL import Image,ImageDraw,ImageFont
from common import config,log_run,mot,names,save_json

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/errors/G_empty_frame_control';out.mkdir(parents=True,exist_ok=True)
log_run(c,38,'真实空GT帧的30个FP补充样例',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/empty_frame_examples.py'],
 'CPU；原G全空表达式类别仍为0。另从本地TempRMOT*基线的空GT帧误报中抽30个不同(expression,track)组，再组内随机帧，seed2025。'
 '保留独立目录/索引，不与主GT候选错误样例混用。GT为空时目标检测FN总体不存在，补充集FN记0。p为实际final输出。')
rng=np.random.default_rng(c['seed']);pool={};predictions={}
for name in names(c):
    seq,expr=name.split('__',1);p=mot(Path(b['predictions'])/seq/expr/'predict_with_conf.txt')
    gt=mot(Path(c['released_v2_gt'])/name/'gt/gt.txt');active=set(gt[:,0].astype(int))
    ix=np.flatnonzero((p[:,6]>=b['gamma']) & ~np.isin(p[:,0],list(active)))
    for i in ix:pool.setdefault((name,int(p[i,1])),[]).append(int(i))
    predictions[name]=p
keys=list(pool);selected=rng.choice(len(keys),min(30,len(keys)),replace=False)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
records=[];thumbs=[]
for j,k in enumerate(selected,1):
    name,oid=keys[k];seq,expr=name.split('__',1);i=int(rng.choice(pool[(name,oid)]));row=predictions[name][i]
    frame=int(row[0]);x,y,w,h=row[2:6];prob=float(row[6])
    image=Image.open(Path(c['image_root'])/seq/f'{frame-1:06d}.png').convert('RGB')
    draw=ImageDraw.Draw(image);draw.rectangle((x,y,x+w,y+h),outline='red',width=4)
    text=[f'G_empty_frame_control FP | TempRMOT* | sequence={seq} frame={frame} track={oid}',
          f'GT referring set empty; p_final={prob:.6f}; gamma={b["gamma"]}',
          *textwrap.wrap(expr.replace('-',' ').replace('_',' '),110)]
    canvas=Image.new('RGB',(image.width,image.height+28*len(text)+14),'white');canvas.paste(image,(0,0));d=ImageDraw.Draw(canvas)
    for n,line in enumerate(text):d.text((10,image.height+7+28*n),line,font=font,fill='black')
    file=out/f'FP_{j:02d}_{seq}_{frame:06d}_{oid}.png';canvas.save(file)
    records.append({'name':name,'frame':frame,'id':oid,'p_final':prob,'file':str(file),'GT_target_rows':0})
    if j<=12:
        thumb=canvas.copy();thumb.thumbnail((500,230));thumbs.append(thumb)
if thumbs:
    sheet=Image.new('RGB',(1000,230*((len(thumbs)+1)//2)),'#dddddd')
    for i,thumb in enumerate(thumbs):sheet.paste(thumb,((i%2)*500,(i//2)*230))
    sheet.save(out/'overview.jpg',quality=92)
with (out/'index.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
save_json(out/'manifest.json',{'reference':'相对本地基线','seed':c['seed'],'candidate_type':'TempRMOT_star',
    'FP_saved':len(records),'FN_saved':0,'distinct_expression_tracks_available':len(keys),
    'note':'Supplement for framewise absence; G globally empty expression class still has zero examples.'})
print(json.dumps({'FP_saved':len(records),'FN_saved':0,'available_groups':len(keys)},ensure_ascii=False),flush=True)
