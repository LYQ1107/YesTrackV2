#!/usr/bin/env python3
"""Paired context intervention on all C/D expressions and sequence-matched A controls."""
import json
import argparse
import os
from pathlib import Path
import random
import shlex
import sys
import time

import numpy as np
from PIL import Image,ImageDraw
import torch
from common import config,confusion,log_run,mot,save_json

p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');args=p.parse_args()
c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='6'
plan=json.loads((t/'analysis/plans/context.json').read_text())
out=t/'analysis/runs/R23_context';out.mkdir(parents=True,exist_ok=True)
log_run(c,23,'成对上下文探针（全部 C/D 表达式）',[
    'CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join(
        [c['reproduction_environment'],'-u','analysis/context_probe.py',*(['--resume'] if args.resume else [])])],
    'GPU 阶段开始前预计 1–2 小时；依据 R19b 约39.7条frame样本/秒/GPU（R09完整基线2.2小时）。'
    '全部107条 C/D 表达式 + 同视频等量随机A对照（排除C/D，允许B/E共同标签），每表达式均匀随机24帧、全部GT候选；四种输入使用完全相同单位。'
    '原crop为官方margin=.2（未截断宽高1.4bbox），1.5/2.5倍指原crop未截断尺寸，margin分别.55/1.25；'
    '整帧逐候选画红框，所有输入均缩放320x320，保持视觉token预算一致；相同官方prompt、发布V2权重、γ=.6，比较纯frame-mode，不混入TCP/TRP。')
random.seed(c['seed']);np.random.seed(c['seed']);torch.manual_seed(c['seed']);torch.cuda.manual_seed_all(c['seed'])
sys.path.insert(0,str(t/c['upstream']))
from refer_llm import llm_eval_from_mot as off
from transformers.utils.logging import disable_progress_bar
disable_progress_bar()
device=torch.device('cuda:0');torch.cuda.set_device(device)
model,processor,ids=off.build_model_and_processor_for_eval(c['base_model'],bf16=True,lora_path=c['official_v2_adapter'])
model.to(device);model.eval()
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={seq:mot(r['track_file']) for seq,r in manifest['sequences'].items()}
labels={r['name']:r for r in json.loads((t/'analysis/labels/expressions.json').read_text())}
tpl='The normalized position of the car or person in the picture is <{coord}>.Determine whether this description matches this image: {sentence}. Answer Yes or No.'
modes=['original','expand1p5','expand2p5','full_frame_box']
all_counts={};per_expr={};started=time.monotonic()
with torch.inference_mode():
    for task in plan['tasks']:
        cachefile=out/(task['name']+'.npz')
        if args.resume and cachefile.exists():
            saved=np.load(cachefile)
            assert len(saved['y'])==task['candidate_rows']
            per_expr[task['name']]={m:confusion(saved['y'],saved[m],b['gamma']) for m in modes}
            continue
        seq,expr=task['name'].split('__',1); tr=tracks[seq]
        js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
        mask={int(f)+1:{int(i) for i in v} for f,v in js['label'].items()}
        y=[];p_by={m:[] for m in modes};indices=[]
        for frame in task['frames']:
            ix=np.flatnonzero(tr[:,0]==frame)
            if not len(ix):continue
            image=Image.open(Path(c['image_root'])/seq/f'{frame-1:06d}.png').convert('RGB')
            w,h=image.size
            coords=[f'{np.clip((x+.5*bw)/w,0,1):.3f} {np.clip((y+.5*bh)/h,0,1):.3f}' for x,y,bw,bh in tr[ix,2:6]]
            prompts=[tpl.format(coord=co,sentence=off._natural_sentence_from_dirname(expr)) for co in coords]
            for mode,margin in zip(modes,[.2,.55,1.25,None]):
                patches=[]
                for x,y0,bw,bh in tr[ix,2:6]:
                    if margin is None:
                        patch=image.copy();draw=ImageDraw.Draw(patch)
                        draw.rectangle((x,y0,x+bw,y0+bh),outline='red',width=4)
                    else:
                        patch=off.crop_with_margin(image,(x,y0,bw,bh),margin_ratio=margin,min_side=8)
                        assert patch is not None
                    patches.append(patch.resize((320,320)))
                p_by[mode].extend(off._forward_probs_for_patches(model,processor,device,patches,prompts,
                    ids[0],ids[1],context=f'{task["name"]} {frame} {mode}'))
            y.extend(int(r[1]) in mask.get(frame,set()) for r in tr[ix]);indices.extend(ix)
        assert len(indices)==task['candidate_rows']
        temporary=cachefile.with_suffix('.tmp.npz')
        np.savez_compressed(temporary,row_index=np.asarray(indices,dtype=np.int32),
                            y=np.asarray(y),**{m:np.asarray(p_by[m],dtype=np.float32) for m in modes})
        temporary.replace(cachefile)
        per_expr[task['name']]={m:confusion(y,p_by[m],b['gamma']) for m in modes}
groups={'C':[x['name'] for x in plan['tasks'] if 'C' in labels[x['name']]['labels']],
        'D':[x['name'] for x in plan['tasks'] if 'D' in labels[x['name']]['labels']],
        'A_control':[x['name'] for x in plan['tasks'] if x['group']=='A_control']}
for group,ns in groups.items():
    all_counts[group]={}
    for mode in modes:
        counts={k:sum(per_expr[n][mode][k] for n in ns) for k in ('tp','fp','fn','tn','n')}
        tp,fp,fn=[counts[k] for k in ('tp','fp','fn')]
        all_counts[group][mode]={**counts,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
save_json(out/'per_expression.json',per_expr)
save_json(out/'result.json',{'reference':'相对本地基线','gamma':b['gamma'],'groups':all_counts,
    'scope':plan['scope'],'expressions':{g:len(n) for g,n in groups.items()},
    'frame_sampling':'24 uniform random GT-visible frames/expression; all candidates; seed2025',
    'image_size':[320,320],'margins':[.2,.55,1.25], 'seconds':time.monotonic()-started})
print((out/'result.json').read_text(),flush=True)
