#!/usr/bin/env python3
"""Attribute observed confidence crossings to native TCP on fresh versus reused scores."""
import json
from pathlib import Path

import numpy as np
from common import config,log_run,mot,save_json
from replay import load_observations

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
observed=load_observations(t/'analysis/runs/R17_h2/raw_scores')
rows=json.loads((t/'analysis/labels/expressions.json').read_text())
out=t/'analysis/runs/R31_heuristics';out.mkdir(parents=True,exist_ok=True)
stats={cat:{k:0 for k in ('n','fp','fn','fp_reused','fp_saturated','fp_last_raw_refined_below_gamma',
    'fp_last_frame_above_refine_upper','fn_last_frame_below_refine_lower',
    'TCP_crossed_gamma','TCP_crossed_gamma_FP','TCP_crossed_gamma_FP_on_reuse')} for cat in ['overall',*'ABCDEFGH']}
for row in rows:
    name=row['name'];seq,expr=name.split('__',1)
    p=mot(t/'analysis/runs/R17_h2/predictions'/seq/expr/'predict_with_conf.txt')
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(v) for v in vs} for f,vs in js['label'].items()}
    last={};raw_last={};frame_last={}
    for r in p:
        frame,oid=int(r[0]),int(r[1]);prob=float(r[6]);truth=oid in mask.get(frame,set())
        fresh=(frame,oid) in observed[name]
        if fresh:
            obs=observed[name][(frame,oid)];pre=float(obs.get('video',obs['frame']));raw_last[oid]=pre
            frame_last[oid]=obs['frame']
        else:pre=last[oid]
        fp=prob>=b['gamma'] and not truth;fn=prob<b['gamma'] and truth
        cross=pre<b['gamma']<=prob
        for cat in ['overall',*row['labels']]:
            s=stats[cat];s['n']+=1;s['fp']+=fp;s['fn']+=fn
            s['fp_reused']+=fp and not fresh;s['fp_saturated']+=fp and prob>=.99
            s['fp_last_raw_refined_below_gamma']+=fp and raw_last[oid]<b['gamma']
            s['fp_last_frame_above_refine_upper']+=fp and frame_last[oid]>=.8
            s['fn_last_frame_below_refine_lower']+=fn and frame_last[oid]<.2
            s['TCP_crossed_gamma']+=cross;s['TCP_crossed_gamma_FP']+=cross and fp
            s['TCP_crossed_gamma_FP_on_reuse']+=cross and fp and not fresh
        last[oid]=prob
for s in stats.values():
    s['fp_reused_fraction']=s['fp_reused']/s['fp'] if s['fp'] else None
    s['fp_saturated_fraction']=s['fp_saturated']/s['fp'] if s['fp'] else None
    s['fp_last_raw_refined_below_gamma_fraction']=s['fp_last_raw_refined_below_gamma']/s['fp'] if s['fp'] else None
save_json(out/'result.json',{'reference':'相对本地基线','gamma':b['gamma'],'categories':stats,
    'interpretation':'Descriptive exact native trace: a threshold crossing without a new model call is caused by TCP on a reused score. This is not a separate model or heuristic intervention.'})
log_run(c,31,'原生推理中TCP/复用分数的阈值越界诊断',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/heuristic_diagnostics.py'],
 '只分析实际H2原始观察与最终分数，不修改TCP/TRP，不做新推理。统计无新模型调用但分数由γ下升至γ上的次数，及其中真实FP。')
print(json.dumps(stats,ensure_ascii=False,indent=2),flush=True)
