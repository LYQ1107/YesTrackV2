#!/usr/bin/env python3
"""Freeze the SoM sample and exact newborn batches required for causal TRP replay."""
import json
from pathlib import Path

import numpy as np
from common import config,mot,save_json

c=config();t=Path(c['task_root']);rng=np.random.default_rng(c['seed'])
rows=json.loads((t/'analysis/labels/expressions.json').read_text())
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
context=json.loads((t/'analysis/plans/context.json').read_text())
context_by={x['name']:x for x in context['tasks']}
tasks=[];empty_pool=[];birth_tasks=[]
for row in rows:
    seq,expr=row['name'].split('__',1);tr=tracks[seq]
    fs=np.unique(tr[:,0]).astype(int)
    if 'D' in row['labels']:
        tasks.append({**context_by[row['name']],'group':'D'})
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    positive=mot(Path(c['released_v2_gt'])/row['name']/'gt/gt.txt')
    positive_frames=set(positive[:,0].astype(int))
    empty=[int(f) for f in fs if int(f) not in positive_frames]
    if empty:empty_pool.append((row['name'],empty))
    if 'F' in row['labels']:
        births=[int(np.min(tr[tr[:,1]==oid,0])) for oid in np.unique(tr[:,1])]
        birth_tasks.append({'name':row['name'],'frames':sorted(set(births)),
                            'candidate_rows':len(births)})
for i in rng.choice(len(empty_pool),min(100,len(empty_pool)),replace=False):
    name,fs=empty_pool[i]
    tasks.append({'name':name,'frames':sorted(map(int,rng.choice(fs,min(12,len(fs)),replace=False))),
                  'group':'G_empty_frame_control'})
save_json(t/'analysis/plans/som.json',{'seed':c['seed'],'tasks':tasks,
    'scope':'All 21 D expressions, same 24 frames as context probe; 100 random expressions with up to12 empty-GT frames each. G has zero globally empty expressions; empty-frame control is explicitly distinct.',
    'candidates':'complete GT tracks to isolate referring; no tracker detection noise',
    'scoring':'softmax of complete answer log likelihood for numeric options1..N and none, including a newline terminator; multi-digit numbers are multiple Qwen tokens'})
save_json(t/'analysis/plans/trp_births.json',{'seed':c['seed'],'tasks':birth_tasks,'births_only':True,
    'scope':'All F expressions; only GT IDs at their first observed frame, in the original per-frame newborn batch; enables exact TRP new-ID handling.'})
print(json.dumps({'D_expressions':sum(x['group']=='D' for x in tasks),
 'empty_frame_control_expressions':sum(x['group']!='D' for x in tasks),
 'SoM_expression_frames':sum(len(x['frames']) for x in tasks),
 'F_newborn_rows':sum(x['candidate_rows'] for x in birth_tasks)},indent=2))
