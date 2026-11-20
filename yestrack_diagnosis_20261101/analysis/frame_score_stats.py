#!/usr/bin/env python3
"""Describe complete raw frame scores at the frozen gamma; no new inference."""
import json
from pathlib import Path

import numpy as np
from common import config,confusion,log_run,mot,save_json

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/runs/R45_frame_scores';out.mkdir(parents=True,exist_ok=True)
log_run(c,45,'全量原始frame判别及分序列校准',[
    "CUDA_VISIBLE_DEVICES='' "+c['reproduction_environment']+' analysis/frame_score_stats.py'],
    'CPU读取完成的2860484条frame概率，固定主基线gamma=.6，给出总体/类别P/R/F1和分序列ECE。'
    '与H2最终输出的差异同时包含video/TCP/TRP，属于描述性联合对照，不能单独当作移除某一启发式的因果收益。'
    '不改原生逻辑，不跑新推理，不改变基线，不选择阈值。')
assert json.loads((t/'analysis/runs/R22_full_scores/frame_complete.json').read_text())['candidate_rows']==2860484
rows=json.loads((t/'analysis/labels/expressions.json').read_text())
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
counts={k:{f:0 for f in ('tp','fp','fn','tn','n')} for k in ['overall',*'ABCDEFGH']}
sequences={s:{'p':[],'y':[]} for s in tracks}
for row in rows:
    name=row['name'];seq,expr=name.split('__',1);tr=tracks[seq]
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(i) for i in ids} for f,ids in js['label'].items()}
    y=np.array([int(r[1]) in mask.get(int(r[0]),set()) for r in tr])
    cached=np.load(t/'analysis/runs/R22_full_scores'/(name+'.npz'))
    assert np.array_equal(cached['row_index'],np.arange(len(tr)))
    p=cached['p_frame'].astype(float);assert np.isfinite(p).all()
    value=confusion(y,p,b['gamma'])
    for cat in ['overall',*row['labels']]:
        for f in counts[cat]:counts[cat][f]+=value[f]
    sequences[seq]['p'].append(p);sequences[seq]['y'].append(y)
for value in counts.values():
    tp,fp,fn,tn,n=(value[k] for k in ('tp','fp','fn','tn','n'))
    value.update(accuracy=(tp+tn)/n if n else None,precision=tp/(tp+fp) if tp+fp else None,
        recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
by_sequence={}
for seq,parts in sequences.items():
    p=np.concatenate(parts['p']);y=np.concatenate(parts['y']);bins=np.minimum((p*15).astype(int),14)
    ece=0.
    for k in range(15):
        select=bins==k
        if select.any():ece+=float(select.mean())*abs(float(p[select].mean())-float(y[select].mean()))
    by_sequence[seq]={**confusion(y,p,b['gamma']),'ECE':ece,'mean_p':float(p.mean()),
        'positive_prior':float(y.mean()),'Brier':float(np.mean((p-y)**2))}
assert counts['overall']['n']==2860484
assert counts['overall']['tp']+counts['overall']['fn']==491286
h2=json.loads((t/'analysis/runs/R21_decomposition/result.json').read_text())['categories']['overall']['gt_track_referring']
save_json(out/'result.json',{'reference':'相对本地基线','seed':c['seed'],'gamma':b['gamma'],
    'mode':'raw frame only, every GT-visible frame; not final H2 controller',
    'categories':counts,'sequences':by_sequence,'H2_final_referring':h2,
    'frame_F1_minus_H2_final':counts['overall']['f1']-h2['f1'],
    'interpretation':'Descriptive joint contrast: changes include video, TCP and TRP; no isolated heuristic intervention was run.'})
print(json.dumps({'overall':counts['overall'],'sequences':by_sequence,
    'frame_F1_minus_H2_final':counts['overall']['f1']-h2['f1']},ensure_ascii=False,indent=2),flush=True)
