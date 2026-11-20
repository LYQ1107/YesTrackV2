#!/usr/bin/env python3
"""Separate official integer-box serialization loss from GT-candidate referring loss."""
import json
from pathlib import Path

import numpy as np
from common import config,log_run,mot,names,official_eval,run_logged,save_json,summary

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/runs/R20q_integer_gt';out.mkdir(parents=True,exist_ok=True)
log_run(c,'20q','H3 的官方整数框输出对照',[
 'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 '+c['reproduction_environment']+' analysis/quantization_sanity.py'],
 'CPU；原生推理llm_eval_from_mot.py:1023会int(x/y/w/h)，H2无法绕过。'
 '保留主要H3=原始GT框+GT referring≈100，另计算H3_int=完全相同int序列化+GT referring，量化H3−H2里坐标序列化混杂，不改变模型/推理。')
below=0
for name in names(c):
    seq,expr=name.split('__',1);gt=mot(Path(c['released_v2_gt'])/name/'gt/gt.txt')
    rows=np.column_stack([gt[:,:6].astype(int),np.ones(len(gt))]);below+=int((rows[:,4]*rows[:,5]<20).sum())
    file=out/'predictions'/seq/expr/'predict_with_conf.txt';file.parent.mkdir(parents=True,exist_ok=True)
    np.savetxt(file,rows,delimiter=',',fmt=['%d']*6+['%.6f'])
cmd=official_eval(c,out/'predictions',out/'evaluation',[b['gamma']])
save_json(out/'command.json',cmd);run_logged(cmd,t/c['upstream'],out/'trackeval.log')
tag=f"default_t{b['gamma']:.2f}".replace('.','p');metrics=summary(out/'evaluation/tracker'/tag/'pedestrian_summary.txt')
raw=json.loads((t/'analysis/runs/R20_oracles/result.json').read_text())['metrics']['h3']
save_json(out/'result.json',{'reference':'相对本地基线','metrics':metrics,'positive_integer_boxes_below_min_area':below,
    'H3_raw_minus_H3_integer':raw['HOTA']-metrics['HOTA'],
    'purpose':'Quantify integer-output localization confound in H3_raw-H2; actual Temp candidate-preserving oracle gains are unaffected.'})
print(json.dumps({'HOTA':metrics['HOTA'],'raw_minus_integer':raw['HOTA']-metrics['HOTA'],'below_min_area':below},indent=2),flush=True)
