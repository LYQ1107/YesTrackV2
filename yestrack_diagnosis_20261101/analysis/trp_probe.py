#!/usr/bin/env python3
"""Full F-class TRP delta sweep, using exact official per-frame and newborn batches."""
import csv
import json
from pathlib import Path
import shlex

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from common import config,confusion,log_run,mot,save_json
from replay import dense_cache,replay

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/runs/R28_trp';out.mkdir(parents=True,exist_ok=True)
log_run(c,28,'F 类全量 TRP Δ=1/5/10/20 与切换窗口',[
 'CUDA_VISIBLE_DEVICES=\'\' '+shlex.join([c['reproduction_environment'],'-u','analysis/trp_probe.py'])],
 'CPU重放全532条F表达式、2150942个可见GT候选；所有δ共用同一官方helper分数、γ=.6及TCP=3/.4/.3。'
 '复用分数的中间帧仍按官方逻辑再执行TCP，绝不简化为恒定输出。新ID立即判别，使用单独的原始newborn批次缓存。'
 'δ10须逐样本与原生H2输出完全一致后才报告。±5窗口只定位gap=1的精确真值切换，跨可见性空档另记，不伪造切换时刻。')
rows=[r for r in json.loads((t/'analysis/labels/expressions.json').read_text()) if 'F' in r['labels']]
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
switches=json.loads((t/'analysis/labels/truth_switches.json').read_text())
switch_by={}
for s in switches:
    switch_by.setdefault((s['name'],s['id']),[]).append(s)
deltas=[1,5,10,20]
stats={d:{region:{'n':0,'errors':0,'positive':0,'fp':0,'fn':0} for region in ('overall','near','far')}
       for d in deltas}
offsets={d:{sign:{k:{'n':0,'errors':0} for k in range(-5,6)} for sign in ('0to1','1to0')}
         for d in deltas}
per_expr={};maximum_diff=0.;gap_switches=sum(s['gap']!=1 for s in switches)
for row in rows:
    name=row['name'];seq,expr=name.split('__',1);tr=tracks[seq]
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(i) for i in v} for f,v in js['label'].items()}
    y=np.array([int(r[1]) in mask.get(int(r[0]),set()) for r in tr])
    full=dense_cache(t/'analysis/runs/R22_full_scores'/(name+'.npz'),len(tr))
    births=dense_cache(t/'analysis/runs/R26_birth_scores'/(name+'.npz'),len(tr))
    near=np.zeros(len(tr),dtype=bool)
    events=[]
    for oid in np.unique(tr[:,1]).astype(int):
        ix=np.flatnonzero(tr[:,1]==oid)
        exact=[s for s in switch_by.get((name,oid),[]) if s['gap']==1]
        for s in exact:
            difference=tr[ix,0].astype(int)-s['frame']
            near[ix[np.abs(difference)<=5]]=True
            for offset in range(-5,6):
                match=ix[difference==offset]
                if len(match):events.append((s['from'],s['to'],offset,int(match[0])))
    per_expr[name]={}
    for delta in deltas:
        score=replay(tr,None,delta=delta,full=full,births=births)
        if delta==10:
            native=mot(t/'analysis/runs/R17_h2/predictions'/seq/expr/'predict_with_conf.txt')[:,6]
            diff=float(np.max(np.abs(native-score)));maximum_diff=max(maximum_diff,diff)
            assert diff<1e-12,(name,'cache/native mismatch',diff)
        pred=score>=b['gamma'];error=pred!=y
        for region,select in [('overall',np.ones(len(y),dtype=bool)),('near',near),('far',~near)]:
            stat=stats[delta][region]
            stat['n']+=int(select.sum());stat['errors']+=int(error[select].sum())
            stat['positive']+=int(y[select].sum())
            stat['fp']+=int((select & pred & ~y).sum());stat['fn']+=int((select & ~pred & y).sum())
        for old,new,k,i in events:
            stat=offsets[delta][f'{old}to{new}'][k];stat['n']+=1;stat['errors']+=int(error[i])
        per_expr[name][delta]=confusion(y,score,b['gamma'])
for delta in deltas:
    for region,stat in stats[delta].items():
        stat['error_rate']=stat['errors']/stat['n'] if stat['n'] else None
        stat['positive_prior']=stat['positive']/stat['n'] if stat['n'] else None
    stats[delta]['near_minus_far_error']=stats[delta]['near']['error_rate']-stats[delta]['far']['error_rate']
    for sign in offsets[delta]:
        for stat in offsets[delta][sign].values():stat['error_rate']=stat['errors']/stat['n'] if stat['n'] else None
with (out/'delta_error_rates.csv').open('w') as f:
    writer=csv.writer(f);writer.writerow(['delta','region','n','errors','error_rate','fp','fn','positive_prior'])
    for delta in deltas:
        for region in ('overall','near','far'):
            stat=stats[delta][region];writer.writerow([delta,region,stat['n'],stat['errors'],stat['error_rate'],stat['fp'],stat['fn'],stat['positive_prior']])
fig,axs=plt.subplots(1,2,figsize=(10,4),sharey=True)
for ax,sign in zip(axs,['0to1','1to0']):
    for delta in deltas:
        xx=list(range(-5,6));ax.plot(xx,[offsets[delta][sign][x]['error_rate'] for x in xx],marker='.',label=f'Delta={delta}')
    ax.axvline(0,color='gray',linestyle='--');ax.set(title=sign,xlabel='Frames from GT truth switch',ylabel='Error rate');ax.legend()
fig.tight_layout();fig.savefig(out/'switch_error.png',dpi=180);fig.savefig(out/'switch_error.pdf');plt.close(fig)
save_json(out/'per_expression.json',per_expr)
transition_windows={}
for delta in deltas:
    transition_windows[delta]={}
    for sign in ('0to1','1to0'):
        transition_windows[delta][sign]={}
        for region,ks in [('before',range(-5,0)),('after',range(0,6))]:
            n=sum(offsets[delta][sign][k]['n'] for k in ks)
            errors=sum(offsets[delta][sign][k]['errors'] for k in ks)
            transition_windows[delta][sign][region]={'n':n,'errors':errors,'error_rate':errors/n if n else None}
near_penalty=stats[10]['near']['error_rate']-stats[1]['near']['error_rate']
far_penalty=stats[10]['far']['error_rate']-stats[1]['far']['error_rate']
save_json(out/'result.json',{'reference':'相对本地基线','candidate_type':'GT tracks, all F expressions',
    'gamma':b['gamma'],'expressions':len(rows),'candidate_rows':sum(r['candidate_rows_gt'] for r in rows),
    'switches_total':len(switches),'switches_contiguous':len(switches)-gap_switches,
    'switches_across_visibility_gap':gap_switches,'delta':stats,'offsets':offsets,
    'native_delta10_max_score_difference':maximum_diff,
    'delta10_minus_delta1_near_error':near_penalty,
    'delta10_minus_delta1_far_error':far_penalty,
    'additional_switch_window_penalty':near_penalty-far_penalty,'transition_windows':transition_windows})
print(json.dumps({'delta':stats,'native_max_difference':maximum_diff},indent=2),flush=True)
