#!/usr/bin/env python3
"""Separate positive prevalence from conditional classification error rates."""
import csv
import json
from pathlib import Path

import numpy as np
from common import config,confusion,log_run,mot,save_json

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/runs/R46_class_base_rates';out.mkdir(parents=True,exist_ok=True)
log_run(c,46,'类别正例率及同序列A对照的条件错误率',[
    "CUDA_VISIBLE_DEVICES='' "+c['reproduction_environment']+' analysis/class_base_rates.py'],
    'CPU；P/F1受正例率影响，补充TPR/FPR/均衡准确率，避免把低基率直接归因比较/关系推理。'
    'D全21条只出现在0011；A对照直接沿用R23冻结的0011中51条A表达式，未按结果重抽。'
    '两组使用该序列全部可见GT候选帧；主γ=.6不变。类别/GT时序家族不独立，不声明显著性或架构因果。')
dec=json.loads((t/'analysis/runs/R21_decomposition/result.json').read_text())
raw=json.loads((t/'analysis/runs/R45_frame_scores/result.json').read_text())


def enrich(v):
    v=dict(v);pos=v['tp']+v['fn'];neg=v['fp']+v['tn'];n=v['n']
    tpr=v['tp']/pos if pos else None;fpr=v['fp']/neg if neg else None
    v.update(positive_prior=pos/n if n else None,TPR=tpr,FPR=fpr,
        balanced_accuracy=(tpr+1-fpr)/2 if tpr is not None and fpr is not None else None)
    return v


final={k:enrich(v['gt_track_referring']) for k,v in dec['categories'].items() if v['gt_track_referring']}
for k,v in dec['additional_subsets'].items():final[k]=enrich(v['gt_track_referring'])
frame={k:enrich(v) for k,v in raw['categories'].items() if v['n']}
plan=json.loads((t/'analysis/plans/context.json').read_text())
controls=[r['name'] for r in plan['tasks'] if r['group']=='A_control' and r['name'].startswith('0011__')]
assert len(controls)==51 and len(set(controls))==51
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tr=mot(manifest['sequences']['0011']['track_file'])
counts={mode:{k:0 for k in ('tp','fp','fn','tn','n')} for mode in ('H2_final','raw_frame')}
for name in controls:
    seq,expr=name.split('__',1)
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(i) for i in ids} for f,ids in js['label'].items()}
    y=np.array([int(r[1]) in mask.get(int(r[0]),set()) for r in tr])
    pred=mot(t/'analysis/runs/R17_h2/predictions'/seq/expr/'predict_with_conf.txt')[:,6]
    pf=np.load(t/'analysis/runs/R22_full_scores'/(name+'.npz'))['p_frame']
    for mode,p in [('H2_final',pred),('raw_frame',pf)]:
        value=confusion(y,p,b['gamma'])
        for k in counts[mode]:counts[mode][k]+=value[k]
control={}
for mode,v in counts.items():
    tp,fp,fn,tn,n=(v[k] for k in ('tp','fp','fn','tn','n'))
    v.update(precision=tp/(tp+fp),recall=tp/(tp+fn),f1=2*tp/(2*tp+fp+fn),accuracy=(tp+tn)/n)
    control[mode]=enrich(v)
paired={'H2_final':{'D':final['D'],'A_control_same_video':control['H2_final']},
        'raw_frame':{'D':frame['D'],'A_control_same_video':control['raw_frame']}}
save_json(out/'result.json',{'seed':c['seed'],'reference':'相对本地基线','gamma':b['gamma'],
    'H2_final_categories':final,'raw_frame_categories':frame,'D_matched_video_control':paired,
    'control_expression_names':controls,'D_expressions':21,'control_expressions':len(controls),
    'scope':'Descriptive conditional rates; frozen controls match video/candidate universe, not semantic negative difficulty.'})
table=[]
for mode,groups in [('H2_final',final),('raw_frame',frame)]:
    for group,v in groups.items():table.append({'mode':mode,'group':group,**v})
for mode,v in control.items():table.append({'mode':mode,'group':'A_control_same_video',**v})
with (out/'rates.csv').open('w') as f:
    fields=list(dict.fromkeys(k for r in table for k in r))
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(table)
print(json.dumps(paired,ensure_ascii=False,indent=2),flush=True)
