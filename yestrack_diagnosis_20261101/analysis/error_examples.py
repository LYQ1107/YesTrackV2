#!/usr/bin/env python3
"""Draw seeded FP/FN examples from GT-candidate referring, with factual score metadata."""
import csv
import json
from pathlib import Path
import textwrap

import numpy as np
from PIL import Image,ImageDraw,ImageFont
from common import config,log_run,mot,save_json
from replay import load_observations

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/errors';out.mkdir(parents=True,exist_ok=True)
log_run(c,29,'每类别30FP/30FN的完整帧错误可视化',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/error_examples.py'],
 'CPU；GT候选+官方H2 referring，以隔离跟踪漏检。seed2025，优先不同(expression,track)错误组，组内随机选帧；不足时从剩余错误帧补足。'
 '图中 p_final 是含video/TCP/TRP的实际输出，另标最近一次frame模式原始概率和实际判别帧；不混淆两者。G没有全视频空表达式，无法抽造30FP/30FN；实际数量如实记录。')
rows=json.loads((t/'analysis/labels/expressions.json').read_text());rng=np.random.default_rng(c['seed'])
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
observed=load_observations(t/'analysis/runs/R17_h2/raw_scores')
switches=json.loads((t/'analysis/labels/truth_switches.json').read_text());switch_by={}
for s in switches:
    if s['gap']==1:switch_by.setdefault((s['name'],s['id']),[]).append(s['frame'])
pools={cat:{kind:[] for kind in ('FP','FN')} for cat in 'ABCDEFGH'}
predictions={};truths={}
for row in rows:
    name=row['name'];seq,expr=name.split('__',1);tr=tracks[seq]
    p=mot(t/'analysis/runs/R17_h2/predictions'/seq/expr/'predict_with_conf.txt')
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(x) for x in v} for f,v in js['label'].items()}
    y=np.array([int(r[1]) in mask.get(int(r[0]),set()) for r in tr]);pred=p[:,6]>=b['gamma']
    predictions[name]=p;truths[name]=y
    for kind,select in [('FP',pred & ~y),('FN',~pred & y)]:
        for cat in row['labels']:
            pools[cat][kind].extend((name,int(i)) for i in np.flatnonzero(select))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
smallfont=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
index=[];counts={};patterns={}
for cat in 'ABCDEFGH':
    folder=out/cat;folder.mkdir(parents=True,exist_ok=True)
    counts[cat]={};thumbs=[];patterns[cat]={}
    for kind in ('FP','FN'):
        pool=pools[cat][kind];groups={}
        for name,i in pool:
            oid=int(predictions[name][i,1]);groups.setdefault((name,oid),[]).append(i)
        keys=list(groups)
        selected=[]
        if keys:
            order=rng.permutation(len(keys))[:30]
            for k in order:
                name,oid=keys[k];i=int(rng.choice(groups[(name,oid)]));selected.append((name,i))
        if len(selected)<min(30,len(pool)):
            used=set(selected);remaining=[x for x in pool if x not in used]
            for k in rng.choice(len(remaining),min(30-len(selected),len(remaining)),replace=False):selected.append(remaining[k])
        counts[cat][kind]={'available_errors':len(pool),'distinct_expression_tracks':len(groups),'saved':len(selected)}
        saturated=small=near=0
        for j,(name,i) in enumerate(selected,1):
            seq,expr=name.split('__',1);p=predictions[name];tr=tracks[seq]
            frame,oid=map(int,p[i,:2]);x,y0,w,h=p[i,2:6];prob=float(p[i,6]);y_true=int(truths[name][i])
            previous=[(f,v) for (f,tid),v in observed[name].items() if tid==oid and f<=frame]
            last_frame,raw=max(previous,key=lambda x:x[0])
            nearest=min((abs(frame-f) for f in switch_by.get((name,oid),[])),default=None)
            image=Image.open(Path(c['image_root'])/seq/f'{frame-1:06d}.png').convert('RGB')
            draw=ImageDraw.Draw(image)
            pos=np.flatnonzero((tr[:,0]==frame) & truths[name])
            for gi in pos:
                gx,gy,gw,gh=tr[gi,2:6];draw.rectangle((gx,gy,gx+gw,gy+gh),outline='lime',width=2)
            draw.rectangle((x,y0,x+w,y0+h),outline='red' if kind=='FP' else 'orange',width=4)
            draw.text((max(0,x),max(0,y0-22)),f'id={oid}',font=font,fill='red' if kind=='FP' else 'orange')
            sentence=expr.replace('-',' ').replace('_',' ')
            text=[f'{cat} {kind} | sequence={seq} frame={frame} track={oid} | GT={y_true} | gamma={b["gamma"]}',
                  f'p_final={prob:.6f}; latest verification frame={last_frame}; p_frame={raw["frame"]:.6f}'
                  +(f'; p_video={raw["video"]:.6f}' if 'video' in raw else ''),
                  *textwrap.wrap(sentence,width=110)]
            canvas=Image.new('RGB',(image.width,image.height+28*len(text)+14),'white');canvas.paste(image,(0,0))
            d=ImageDraw.Draw(canvas)
            for line_no,line in enumerate(text):d.text((10,image.height+7+28*line_no),line,font=font,fill='black')
            filename=f'{kind}_{j:02d}_{seq}_{frame:06d}_{oid}.png';canvas.save(folder/filename)
            meta={'category':cat,'kind':kind,'file':str(folder/filename),'name':name,'frame':frame,'id':oid,
                'p_final':prob,'truth':y_true,'last_verification_frame':last_frame,'last_p_frame':raw['frame'],
                'last_p_video':raw.get('video'),'bbox_area':float(w*h),'nearest_contiguous_truth_switch':nearest}
            index.append(meta)
            saturated+=prob>=.99;small+=w*h<1024;near+=nearest is not None and nearest<=5
            if j<=6:
                thumb=canvas.copy();thumb.thumbnail((500,230));thumbs.append(thumb)
        patterns[cat][kind]={'sampled':len(selected),'p_final_ge_0p99':int(saturated),'area_lt_1024':int(small),'near_truth_switch_pm5':int(near)}
    if thumbs:
        sheet=Image.new('RGB',(1000,230*((len(thumbs)+1)//2)),'#dddddd')
        for i,thumb in enumerate(thumbs):sheet.paste(thumb,((i%2)*500,(i//2)*230))
        sheet.save(folder/'overview.jpg',quality=92)
with (out/'index.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(index[0]));writer.writeheader();writer.writerows(index)
save_json(out/'manifest.json',{'seed':c['seed'],'reference':'相对本地基线','candidate_type':'GT tracks',
    'counts':counts,'sample_statistics':patterns,'images':len(index),
    'G_note':'No globally empty expression exists; G has zero FP/FN population and cannot supply artificial samples.'})
print(json.dumps({'images':len(index),'counts':counts},ensure_ascii=False,indent=2),flush=True)
