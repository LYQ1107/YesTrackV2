#!/usr/bin/env python3
"""Freeze the complete V1 optimum before target calibration, and verify trace recovery."""
import json
from pathlib import Path

import numpy as np
from common import config,log_run,mot,save_json
from replay import load_observations
from calibration_scan import scan

c=config();t=Path(c['task_root']);assert json.loads((t/'analysis/runs/R24_v1_calibration/result.json').read_text())['complete']
out=t/'analysis/runs/R35_v1_grid';out.mkdir(parents=True,exist_ok=True)
log_run(c,35,'先冻结 V1 阈值/精炼区间最优，并校验原生重放',[
 'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 '+c['reproduction_environment']+' -u analysis/calibration_source.py'],
 '纯CPU；完整158表达式328330个GT候选。γ=.1:.1:.9、pl∈{.2,.3,.4}、ph∈{.6,.7,.8}，按源V1 micro-F1选择；'
 '目标V2全量校准尚未产生，用此冻结源配置作迁移。原始TCP/TRP10区间必须逐值重放原生分数，最大差阈值1e-12。'
 '后续R27复用本源网格，不为选择源配置查看V2网格。')
plan=json.loads((t/'analysis/plans/calibration_v1_full.json').read_text())
manifest=json.loads((t/'analysis/resources/gt_candidates_v1/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
truth={}
for row in plan['tasks']:
    seq,expr=row['name'].split('__',1);tr=tracks[seq]
    js=json.loads((Path(manifest['expression_root'])/seq/f'{expr}.json').read_text())
    mask={int(f)+1:{int(i) for i in ids} for f,ids in js['label'].items()}
    truth[row['name']]=np.array([int(r[1]) in mask.get(int(r[0]),set()) for r in tr])
observed=load_observations(t/'analysis/runs/R24_v1_calibration/raw_scores')
grid,diff=scan('V1',plan['tasks'],tracks,truth,observed,t/'analysis/runs/R24_v1_calibration/predictions')
best=max(grid,key=lambda r:r['f1'])
save_json(out/'result.json',{'complete':True,'seed':c['seed'],'grid':grid,'best':best,'native_max_difference':diff,
    'source':'V1 released adapter and all158 official val expressions','selection_objective':'micro GT referring F1',
    'frozen_before_V2_full_calibration':True})
print(json.dumps({'best':best,'native_max_difference':diff},ensure_ascii=False,indent=2),flush=True)
