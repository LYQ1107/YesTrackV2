#!/usr/bin/env python3
"""Explain the measured 1e-6 replay discrepancy without changing acceptance tolerance."""
import json
from pathlib import Path

import numpy as np
from common import config,log_run,mot,save_json
from replay import load_observations,replay

c=config();t=Path(c['task_root']);name='0005__black-cars-in-the-left';seq,expr=name.split('__',1)
manifest=json.loads((t/'analysis/resources/gt_candidates_v1/manifest.json').read_text())
tr=mot(manifest['sequences'][seq]['track_file'])
native=mot(t/'analysis/runs/R24_v1_calibration/predictions'/seq/expr/'predict_with_conf.txt')[:,6]
observed=load_observations(t/'analysis/runs/R24_v1_calibration/raw_scores')[name]
raw=replay(tr,observed,serialize=False);old=np.round(raw,6);fixed=replay(tr,observed)
indices=np.flatnonzero(old!=native)
examples=[{'frame':int(tr[i,0]),'id':int(tr[i,1]),'raw':float(raw[i]),'numpy_round':float(old[i]),
            'official_format':float(fixed[i]),'native':float(native[i])} for i in indices[:10]]
result={'seed':c['seed'],'expression':name,'old_max_difference':float(np.max(np.abs(old-native))),
    'fixed_max_difference':float(np.max(np.abs(fixed-native))),'different_numpy_round_rows':len(indices),
    'examples':examples,'acceptance_tolerance_unchanged':1e-12,
    'fix':'Use exactly the official Python decimal f-string formatting, rather than numpy.round.'}
save_json(t/'analysis/runs/R36_rounding/result.json',result)
log_run(c,36,'离线重放第6位舍入差异的定向修复',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/diagnose_replay_rounding.py',
 'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 '+c['reproduction_environment']+' -u analysis/calibration_source.py'],
 'R35首次CPU回放在0005__black-cars-in-the-left失败：最大差1e-6，未放宽1e-12验收标准。'
 '原生入口以f-string写6位小数，np.round在二进制临界值上不同；分析脚本改为完全相同的Python格式化。'
 '不改官方推理或分数，只修复离线序列化。先验证触发样本，再重跑完整158表达式源网格。')
assert result['fixed_max_difference']<1e-12,result
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
