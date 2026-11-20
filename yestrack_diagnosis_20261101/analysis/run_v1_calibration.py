#!/usr/bin/env python3
"""Complete V1 GT referring with its published verifier; source for threshold transfer."""
import json
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import time

import numpy as np
from common import config,log_run,mot,save_json

p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');options=p.parse_args()
c=config();t=Path(c['task_root']);assert os.environ.get('CUDA_VISIBLE_DEVICES')=='5'
out=t/'analysis/runs/R24_v1_calibration';out.mkdir(parents=True,exist_ok=True)
official=t/c['upstream']
template=json.loads((t/'analysis/runs/R17_h2/commands.json').read_text())['inference']
args=template[template.index('--')+1:]
changes={'--lora_path':str(t/'analysis/resources/release/yestrack/v1bestweight'),
         '--data_root':str(t/'analysis/resources/dataset_v1'),
         '--results_root':str(t/'analysis/resources/gt_candidates_v1/results'),
         '--output_root':str(out/'predictions')}
for key,value in changes.items():args[args.index(key)+1]=value
if options.resume:args+=['--resume']
cmd=[c['reproduction_environment'],'-u',str(t/'analysis/observed_inference.py'),
     '--seed',str(c['seed']),'--script',str(official/'refer_llm/llm_eval_from_mot.py'),
     '--trace-root',str(out/'raw_scores'),'--',*args]
log_run(c,24,'V1 完整 GT tracks referring，供校准阈值迁移',[
    'CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join(
        [c['reproduction_environment'],'-u','analysis/run_v1_calibration.py',*(['--resume'] if options.resume else [])]),
    '# 官方子命令：'+shlex.join(cmd)],
    'GPU 阶段启动前预计 0.7–1.5 小时，参考 R09 2.2小时×328330/1850576×2GPU/1GPU≈0.78小时；低于8小时。'
    '完整158表达式、328330候选，V1发布权重、同一TCP/TRP；GPU5启动前余量超过30GiB，保留其他项目进程。'
    'V1最优阈值迁移到V2使用各自发布权重，所以效应包含权重校准版本变化，不能单归为数据集变化。')
save_json(out/'commands.json',{'inference':cmd,'cwd':str(official),'seed':c['seed'],'physical_gpu':5,
          'configuration':changes,'source_dataset':'V1','source_adapter':'V1 published'})
start=time.monotonic();errs=[]
with (out/'inference.log').open('w') as f:
    child=subprocess.Popen(cmd,cwd=official,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    for line in child.stdout:
        f.write(line)
        if '[ERR]' in line:errs.append(line.strip())
    rc=child.wait()
assert not rc and not errs,(rc,errs[:1])
plan=json.loads((t/'analysis/plans/calibration_v1_full.json').read_text())
for task in plan['tasks']:
    seq,expr=task['name'].split('__',1)
    rows=mot(out/'predictions'/seq/expr/'predict_with_conf.txt')
    assert len(rows)==task['candidate_rows'] and np.isfinite(rows[:,6]).all(),task['name']
save_json(out/'result.json',{'complete':True,'seed':c['seed'],'expressions':len(plan['tasks']),
          'candidate_rows':sum(x['candidate_rows'] for x in plan['tasks']),'seconds':time.monotonic()-start})
print((out/'result.json').read_text(),flush=True)
