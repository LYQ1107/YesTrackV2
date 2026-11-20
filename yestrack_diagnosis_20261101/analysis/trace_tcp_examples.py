#!/usr/bin/env python3
"""Expose observed TCP amplification in saved error examples, without intervention."""
import csv
import json
from pathlib import Path

import numpy as np
from common import config,log_run,mot,save_json
from replay import load_observations,replay

c=config();t=Path(c['task_root']);out=t/'analysis/runs/R42_tcp_examples';out.mkdir(parents=True,exist_ok=True)
log_run(c,42,'实际保存FP的TCP逐帧机制核对',[
    "CUDA_VISIBLE_DEVICES='' "+c['reproduction_environment']+' analysis/trace_tcp_examples.py'],
    'CPU读取两个已经保存的H2误例，重放整个表达式且逐值验证原生6位输出，再展示对应ID最后15个可见帧的实际分数/原始判别。'
    '只解释观测到的历史加分，不改TCP/TRP或模型，不运行新推理，不估算移除启发式的HOTA。')
observed=load_observations(t/'analysis/runs/R17_h2/raw_scores')
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
cases=[('0019__persons-wearing-coat-and-pants',81,483),('0013__pedestrians-with-a-bike',136,269)]
result=[];table=[]
for name,oid,frame in cases:
    seq,expr=name.split('__',1);tr=mot(manifest['sequences'][seq]['track_file'])
    pred=mot(t/'analysis/runs/R17_h2/predictions'/seq/expr/'predict_with_conf.txt')
    exact=replay(tr,observed[name],serialize=False)
    native=np.fromiter((float(f'{p:.6f}') for p in exact),dtype=float,count=len(exact))
    assert np.array_equal(native,pred[:,6]),name
    ix=np.flatnonzero((tr[:,1]==oid)&(tr[:,0]<=frame))
    records=[]
    for k,i in enumerate(ix):
        f=int(tr[i,0]);raw=observed[name].get((f,oid));previous=ix[max(0,k-3):k]
        before=float(raw.get('video',raw['frame'])) if raw else float(exact[ix[k-1]])
        boosted=len(previous)==3 and all(exact[j]>=.4 for j in previous)
        record={'name':name,'id':oid,'frame':f,'fresh':raw is not None,
            'p_frame':raw['frame'] if raw else None,'p_video':raw.get('video') if raw else None,
            'p_before_TCP':before,'previous_3_final':list(map(float,exact[previous])),
            'TCP_boost_applied':bool(boosted),'p_final':float(pred[i,6])}
        if k>=len(ix)-15:records.append(record);table.append(record)
    result.append({'name':name,'id':oid,'target_frame':frame,'native_replay_max_difference':0.,'rows':records})
save_json(out/'result.json',{'reference':'相对本地基线','seed':c['seed'],'cases':result,
    'interpretation':'All probabilities are actual native observations or exact pre-serialization replay; no counterfactual inference.'})
with (out/'trace.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
