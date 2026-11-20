#!/usr/bin/env python3
"""Run the paired candidate-number permutation control in a detached owner."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

import numpy as np
from common import config,log_run,save_json

p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');args=p.parse_args()
c=config();t=Path(c['task_root']);out=t/'analysis/runs/R47_shuffled_som';out.mkdir(parents=True,exist_ok=True)
gpu_command=[c['reproduction_environment'],'-u','analysis/som_probe.py','--shuffle-candidates',
    '--out','analysis/runs/R47_shuffled_som']
analysis_command=[c['reproduction_environment'],'analysis/analyze_som.py','--out',
    'analysis/runs/R47_shuffled_som','--run-number','47-analysis']
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='6',OMP_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false')
if not args.worker:
    if (out/'controller_complete.json').exists():
        receipt=json.loads((out/'controller_complete.json').read_text())
        assert receipt['complete'] and receipt['seed']==c['seed'] and receipt['expression_frames']==1704
        print('Reuse complete paired shuffled-number control.',flush=True)
        raise SystemExit(0)
    log_run(c,'47-launch','随机编号配对对照的预算、输入核对与独立owner',[
        "CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 "+c['reproduction_environment']+' analysis/launch_shuffled_som.py',
        "CUDA_VISIBLE_DEVICES='' "+c['reproduction_environment']+' -u analysis/wait_round2.py --next --shuffle'],
        '新GPU阶段启动前预计1–2小时/单GPU6，依据原完全相同1704帧实际3373.536秒；小于8小时。'
        'R25发现D阳性目标100%为编号1，always-first F1=.71264超过联合.50456，需消除实际排序混杂。'
        '相同21D/100空帧表达式、相同1704帧和gamma=.6；只随机编号，不调模型/阈值/采样。'
        'crop分数按GT ID原样复用，重新计算相同随机标号整帧的独立/联合分数。'+shlex.join(gpu_command))
    records=[]
    with gzip.open(t/'analysis/runs/R25_som/frames.jsonl.gz','rt') as f:
        for line in f:records.append(json.loads(line))
    assert len(records)==1704
    names=set();positive=first_after=0
    for row in records:
        key=(row['name'],row['frame'],row['group']);assert key not in names;names.add(key)
        seq=row['name'].split('__',1)[0]
        perm=np.random.default_rng(c['seed']+100000*int(seq)+row['frame']).permutation(row['n'])
        assert sorted(perm.tolist())==list(range(row['n']))
        assert sorted(zip(np.array(row['ids'])[perm].tolist(),np.array(row['p_crop'])[perm].tolist()))==sorted(zip(row['ids'],row['p_crop']))
        if row['group']=='D' and any(row['y']):positive+=1;first_after+=int(np.array(row['y'])[perm][0])
    save_json(out/'mapping_sanity.json',{'complete':True,'expression_frames':len(records),
        'unique_units':len(names),'GT_ID_and_crop_probability_pairs_preserved':True,
        'D_positive_frames':positive,'D_positive_frames_target_first_after_permutation':first_after})
    save_json(t/'analysis/plans/R47_shuffled_som.json',{'seed':c['seed'],'reference_plan':'analysis/plans/som.json',
        'expression_frames':1704,'estimated_gpu_hours':2,'physical_gpus':[6],
        'permutation_seed':'2025+100000*int(sequence)+frame','scope':'same frozen inputs; labels and crop probabilities permuted by GT ID',
        'purpose':'Resolve observed always-first ordering confound, without reselecting samples or tuning gamma.'})
    resource=subprocess.run(['nvidia-smi','-i','6','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],
        text=True,capture_output=True,check=True)
    (out/'resource_start.csv').write_text(resource.stdout)
    assert int(resource.stdout.split(',')[1])>=16000,resource.stdout
    with (out/'controller.log').open('w') as f:
        child=subprocess.Popen([c['reproduction_environment'],'-u','analysis/launch_shuffled_som.py','--worker'],
            cwd=t,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    save_json(out/'owner.json',{'pid':child.pid,'gpu_command':gpu_command,'analysis_command':analysis_command,'seed':c['seed']})
    owners=json.loads((t/'analysis/process_owners.json').read_text());owners['R47_order_control']=child.pid
    save_json(t/'analysis/process_owners.json',owners)
    subprocess.run([c['reproduction_environment'],'analysis/render_report.py'],cwd=t,env={**env,'CUDA_VISIBLE_DEVICES':''},check=True)
    print(json.dumps({'launched':True,'pid':child.pid,'physical_gpu':6,'estimated_hours':[1,2]}),flush=True)
    raise SystemExit(0)
started=time.monotonic()
try:
    with (out/'inference.log').open('w') as f:
        subprocess.run(gpu_command,cwd=t,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,start_new_session=True)
    cpu_env={**env,'CUDA_VISIBLE_DEVICES':''}
    with (out/'analysis.log').open('w') as f:
        subprocess.run(analysis_command,cwd=t,env=cpu_env,stdout=f,stderr=subprocess.STDOUT,check=True)
    subprocess.run([c['reproduction_environment'],'analysis/render_report.py'],cwd=t,env=cpu_env,check=True)
    source=subprocess.run(['git','diff','--exit-code'],cwd=t/c['upstream'],capture_output=True,text=True)
    assert source.returncode==0,source.stdout
    save_json(out/'controller_complete.json',{'complete':True,'seconds':time.monotonic()-started,
        'expression_frames':1704,'seed':c['seed'],'physical_gpu':6,'upstream_tracked_diff_empty':True})
except Exception as e:
    save_json(out/'failure.json',{'error':str(e),'elapsed_seconds':time.monotonic()-started})
    raise
