#!/usr/bin/env python3
"""Full GT frame calibration and source-selected threshold/refinement transfer."""
import csv
import json
from pathlib import Path
import shlex

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from common import config,confusion,log_run,mot,official_eval,run_logged,save_json,summary
from replay import load_observations,replay
from calibration_scan import scan

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/runs/R27_calibration';out.mkdir(parents=True,exist_ok=True)
if (out/'result.json').exists():
    existing=json.loads((out/'result.json').read_text())
    assert existing['frame_calibration']['n']==2860484 and existing['gamma_frozen_baseline']==b['gamma']
    print('Reuse complete validated calibration result; full frame cache and protocol unchanged.',flush=True)
    raise SystemExit(0)
log_run(c,27,'全量 frame-mode 校准、ECE 与 V1→V2 阈值迁移',[
 'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 '+shlex.join([c['reproduction_environment'],'-u','analysis/calibration.py'])],
 'CPU；V2全部GT候选原始frame概率，15个等宽概率箱，报告ECE/Brier；不使用TCP后分数代替frame概率。'
 '实际发布权重负样本保留率r未知，训练CLI默认.5不是该checkpoint的训练记录，不估计、不执行先验修正。'
 'V1用V1发布权重的完整158表达式；V2用V2发布权重；此迁移包含权重版本变化且三个视频重叠，不是独立新视频泛化。'
 '用官方原始观察值精确重放TCP/TRP10。γ=.1:.1:.9，pl∈{.2,.3,.4}、ph∈{.6,.7,.8}；区间均在已执行video范围内，仅收窄，无缺失video推断。'
 '按V1 micro referential F1选一次配置，再在V2评估；V2网格最优仅作为诊断对照，绝不改变冻结γ=.6基线。')
rows=json.loads((t/'analysis/labels/expressions.json').read_text())
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={seq:mot(r['track_file']) for seq,r in manifest['sequences'].items()}
ys={};p_all=[];y_all=[]
for r in rows:
    seq,expr=r['name'].split('__',1);tr=tracks[seq]
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(x) for x in ids} for f,ids in js['label'].items()}
    y=np.array([int(row[1]) in mask.get(int(row[0]),set()) for row in tr])
    cache=np.load(t/'analysis/runs/R22_full_scores'/(r['name']+'.npz'))
    assert len(cache['p_frame'])==len(tr)
    assert np.array_equal(cache['row_index'],np.arange(len(tr)))
    ys[r['name']]=y;p_all.append(cache['p_frame']);y_all.append(y)
p=np.concatenate(p_all).astype(float);y=np.concatenate(y_all)
bins=np.minimum((p*15).astype(int),14)
reliability=[];ece=0.
for i in range(15):
    ix=bins==i;n=int(ix.sum())
    mean=float(p[ix].mean()) if n else None;freq=float(y[ix].mean()) if n else None
    if n:ece+=n/len(p)*abs(mean-freq)
    reliability.append({'bin':i,'lower':i/15,'upper':(i+1)/15,'n':n,'mean_p':mean,'positive_frequency':freq})
with (out/'reliability.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(reliability[0]));w.writeheader();w.writerows(reliability)
fig,ax=plt.subplots(figsize=(5,5));ax.plot([0,1],[0,1],'--',color='gray')
valid=[r for r in reliability if r['n']]
ax.plot([r['mean_p'] for r in valid],[r['positive_frequency'] for r in valid],marker='o')
ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean frame-mode Yes probability',ylabel='Observed positive fraction',
       title=f'V2 complete GT tracks: ECE={100*ece:.2f}% (n={len(p):,})')
fig.tight_layout();fig.savefig(out/'reliability.png',dpi=180);fig.savefig(out/'reliability.pdf');plt.close(fig)
save_json(out/'frame_calibration.json',{'n':len(p),'ECE':ece,'Brier':float(np.mean((p-y)**2)),
    'mean_p':float(p.mean()),'positive_prior':float(y.mean()),'bins':reliability,
    'negative_retention_r':None,'prior_correction':'skipped: released-checkpoint actual rate unknown',
    'repository_training_default_r':.5,'default_is_not_checkpoint_evidence':True})
source_plan=json.loads((t/'analysis/plans/calibration_v1_full.json').read_text())
source_manifest=json.loads((t/'analysis/resources/gt_candidates_v1/manifest.json').read_text())
source_tracks={seq:mot(r['track_file']) for seq,r in source_manifest['sequences'].items()}
source_rows=source_plan['tasks']
source_y={}
for r in source_rows:
    seq,expr=r['name'].split('__',1);tr=source_tracks[seq]
    js=json.loads((Path(source_manifest['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(x) for x in ids} for f,ids in js['label'].items()}
    source_y[r['name']]=np.array([int(row[1]) in mask.get(int(row[0]),set()) for row in tr])
observed_v1=load_observations(t/'analysis/runs/R24_v1_calibration/raw_scores')
observed_v2=load_observations(t/'analysis/runs/R17_h2/raw_scores')


source_frozen=t/'analysis/runs/R35_v1_grid/result.json'
if source_frozen.exists():
    frozen=json.loads(source_frozen.read_text());assert frozen['complete'] and frozen['seed']==c['seed']
    v1,diff1=frozen['grid'],frozen['native_max_difference']
else:
    v1,diff1=scan('V1',source_rows,source_tracks,source_y,observed_v1,t/'analysis/runs/R24_v1_calibration/predictions')
v2,diff2=scan('V2',rows,tracks,ys,observed_v2,t/'analysis/runs/R17_h2/predictions')
best1=max(v1,key=lambda x:x['f1']);best2=max(v2,key=lambda x:x['f1'])
transferred=next(x for x in v2 if all(x[k]==best1[k] for k in ('gamma','lower','upper')))
native=next(x for x in v2 if x['gamma']==b['gamma'] and x['lower']==.2 and x['upper']==.8)
save_json(out/'threshold_grid.json',{'V1':v1,'V2':v2})
with (out/'threshold_grid.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(v1[0]));writer.writeheader();writer.writerows(v1+v2)
for row in rows:
    name=row['name'];seq,expr=name.split('__',1);tr=tracks[seq]
    scores=replay(tr,observed_v2[name],lower=best1['lower'],upper=best1['upper'])
    prediction=np.column_stack([tr[:,:2],tr[:,2:6].astype(int),scores])
    path=out/'transferred_predictions'/seq/expr/'predict_with_conf.txt';path.parent.mkdir(parents=True,exist_ok=True)
    np.savetxt(path,prediction,delimiter=',',fmt=['%d']*6+['%.6f'])
cmd=official_eval(c,out/'transferred_predictions',out/'transfer_evaluation',[best1['gamma']])
save_json(out/'trackeval_command.json',cmd);run_logged(cmd,t/c['upstream'],out/'transfer_trackeval.log')
tag=f"default_t{best1['gamma']:.2f}".replace('.','p')
transfer_hota=summary(out/'transfer_evaluation/tracker'/tag/'pedestrian_summary.txt')
save_json(out/'result.json',{'reference':'相对本地基线','gamma_frozen_baseline':b['gamma'],
    'frame_calibration':json.loads((out/'frame_calibration.json').read_text()),
    'V1_best':best1,'V2_grid_best_diagnostic_only':best2,'V2_at_V1_configuration':transferred,
    'V2_frozen_baseline':native,'transfer_F1_drop_vs_V2_oracle':best2['f1']-transferred['f1'],
    'transfer_F1_change_vs_frozen_baseline':transferred['f1']-native['f1'],
    'transfer_HOTA':transfer_hota,
    'transfer_HOTA_change_vs_H2_baseline':transfer_hota['HOTA']-json.loads((t/'analysis/runs/R17_h2/result.json').read_text())['metrics']['HOTA'],
    'replay_native_max_score_difference':{'V1':diff1,'V2':diff2},
    'limitations':'Source V1 adapter differs from target V2 adapter, and V1 validation videos overlap target; this diagnoses deployment calibration transfer, not independent data-domain causality.'})
print(json.dumps({'ECE':ece,'V1_best':best1,'V2_transfer':transferred,'transfer_HOTA':transfer_hota['HOTA']},indent=2),flush=True)
import subprocess
subprocess.run([c['reproduction_environment'],'analysis/render_report.py'],cwd=t,check=True)
