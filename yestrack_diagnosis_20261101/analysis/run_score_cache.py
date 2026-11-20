#!/usr/bin/env python3
"""One blocking multi-GPU owner for a fully specified official-helper score cache."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import shutil

import numpy as np
from common import config,log_run,save_json

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--plan',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--gpus',required=True)
p.add_argument('--run-number',required=True)
p.add_argument('--estimated-hours',type=float,required=True)
p.add_argument('--over8-authorized',action='store_true')
p.add_argument('--video',action='store_true')
p.add_argument('--resume',action='store_true')
a=p.parse_args();c=config();t=Path(c['task_root'])
gpus=list(map(int,a.gpus.split(',')))
resources=json.loads((Path(c['project_root'])/'configs/groundjev/resources.json').read_text())
assert len(gpus)<=4 and set(gpus)<=set(resources['physical_gpu_allowlist'])
if a.estimated_hours>8 and not a.over8_authorized:
    raise SystemExit('User rule: stage exceeds 8 hours; obtain explicit approval before passing --over8-authorized.')
plan=json.loads(a.plan.read_text())
a.out.mkdir(parents=True,exist_ok=True)
controller=[c['reproduction_environment'],'-u','analysis/run_score_cache.py','--plan',str(a.plan),
    '--out',str(a.out),'--gpus',a.gpus,'--run-number',a.run_number,'--estimated-hours',str(a.estimated_hours)]
if a.video:controller+=['--video']
if a.resume:controller+=['--resume']
if a.over8_authorized:controller+=['--over8-authorized']
log_run(c,a.run_number,'GT frame/video 全量概率缓存',[
    'CUDA_VISIBLE_DEVICES='+a.gpus+' OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join(controller)],
    f'GPU 阶段开始前预计 {a.estimated_hours:g} 小时；R09 为2.2小时，另依据 R19/R19b 实测吞吐。'
    f'物理 GPU={a.gpus}；全量 {len(plan["tasks"])} 表达式、{sum(x["candidate_rows"] for x in plan["tasks"])} 候选。'
    '使用官方 crop、prompt、模型与 forward helper，保持每帧原批次；只缓存分数供分析，未改官方控制器。'
    '多GPU按完整表达式原子领取任务，以免共享GPU成为固定分片的长尾；每帧批次/权重/种子不变，完整任务归属写入各rank receipt。'
    +('用户已显式批准超过8小时。' if a.over8_authorized else '估计低于8小时。'))
started=time.monotonic();commands=[]
split=a.run_number=='22' and a.video
if split:
    regression=t/'analysis/runs/R19c_split_regression';regression.mkdir(parents=True,exist_ok=True)
    pilot=json.loads((t/'analysis/plans/R19_timing.json').read_text())
    for task in pilot['tasks']:
        shutil.copyfile(t/'analysis/runs/R19b_frame_timing'/(task['name']+'.npz'),regression/(task['name']+'.npz'))
    cmd=[c['reproduction_environment'],'-u',str(t/'analysis/cache_scores.py'),
         '--plan',str(t/'analysis/plans/R19_timing.json'),'--out',str(regression),'--video','--video-only']
    log_run(c,'19c','frame/video分两遍执行的真实输入数值回归',[ 
        'CUDA_VISIBLE_DEVICES='+str(gpus[0])+' OMP_NUM_THREADS=2 '+shlex.join(cmd)],
        'GPU阶段启动前预计1–3分钟；复用R19全部827个真实GT样本的frame缓存，只重推344个uncertain视频样本；'
        '逐值验证与R19原联合执行完全相等，必要数值检查通过才启动获批全量两遍缓存。')
    reg_env=os.environ.copy();reg_env['CUDA_VISIBLE_DEVICES']=str(gpus[0])
    with (regression/'video_only.log').open('w') as f:subprocess.run(cmd,cwd=t,env=reg_env,stdout=f,stderr=subprocess.STDOUT,check=True)
    maximum=0.
    for task in pilot['tasks']:
        ref=np.load(t/'analysis/runs/R19_timing'/(task['name']+'.npz'))
        actual=np.load(regression/(task['name']+'.npz'))
        for key in ('p_frame','p_video'):
            assert np.array_equal(ref[key],actual[key],equal_nan=True),(task['name'],key)
    save_json(regression/'result.json',{'complete':True,'seed':c['seed'],'max_score_difference':maximum})
    print('[cache] Split-pass numerical regression passed exactly.',flush=True)
phases=[('frame',[]),('video',['--video','--video-only'])] if split else [('joint',['--video'] if a.video else [])]
calibration=None;calibration_log=None
for phase,flags in phases:
    children=[];logs=[]
    if len(gpus)>1:
        claim_phase='video' if '--video-only' in flags else ('joint' if '--video' in flags else 'frame')
        shutil.rmtree(a.out/('claims_'+claim_phase),ignore_errors=True)
    for rank,gpu in enumerate(gpus):
        cmd=[c['reproduction_environment'],'-u',str(t/'analysis/cache_scores.py'),'--plan',str(a.plan.resolve()),
             '--out',str(a.out.resolve()),'--rank',str(rank),'--world-size',str(len(gpus)),*flags]
        if a.resume:cmd+=['--resume']
        if len(gpus)>1:cmd+=['--dynamic-shards']
        env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=str(gpu)
        log=(a.out/f'{phase}_worker{rank}.log').open('w');logs.append(log)
        children.append(subprocess.Popen(cmd,cwd=t,env=env,stdout=log,stderr=subprocess.STDOUT))
        commands.append({'phase':phase,'gpu':gpu,'command':cmd})
    save_json(a.out/'commands.json',commands)
    codes=[p.wait() for p in children]
    for f in logs:f.close()
    assert not any(codes),(phase,codes)
    assigned=[]
    for rank in range(len(gpus)):
        assigned.extend(json.loads((a.out/f'receipt_rank{rank}.json').read_text())['assigned_expression_names'])
        shutil.copyfile(a.out/f'receipt_rank{rank}.json',a.out/f'{phase}_receipt_rank{rank}.json')
    assert len(assigned)==len(set(assigned))==len(plan['tasks'])
    assert set(assigned)=={x['name'] for x in plan['tasks']}
    print(f'[cache] {phase} phase complete.',flush=True)
    if split and phase=='frame':
        for task in plan['tasks']:
            data=np.load(a.out/(task['name']+'.npz'))
            assert len(data['row_index'])==task['candidate_rows'] and np.isfinite(data['p_frame']).all()
        save_json(a.out/'frame_complete.json',{'complete':True,'candidate_rows':sum(x['candidate_rows'] for x in plan['tasks']),
                  'elapsed_seconds':time.monotonic()-started})
        calibration_log=(a.out/'priority_calibration.log').open('w')
        cpu_env=os.environ.copy();cpu_env['CUDA_VISIBLE_DEVICES']=''
        calibration=subprocess.Popen([c['reproduction_environment'],'-u','analysis/calibration.py'],
            cwd=t,env=cpu_env,stdout=calibration_log,stderr=subprocess.STDOUT)
        print('[cache] Full frame reliability/threshold analysis started on CPU while selective video scores run.',flush=True)
if calibration is not None:
    rc=calibration.wait();calibration_log.close()
    assert not rc,f'Priority calibration failed; inspect {a.out/"priority_calibration.log"}'
for task in plan['tasks']:
    cached=np.load(a.out/(task['name']+'.npz'))
    assert len(cached['row_index'])==task['candidate_rows'],task['name']
    assert np.isfinite(cached['p_frame']).all()
    if a.video:
        eligible=(cached['p_frame']>=.2)&(cached['p_frame']<.8)
        assert np.isfinite(cached['p_video'][eligible]).all()
save_json(a.out/'result.json',{'complete':True,'seed':c['seed'],'tasks':len(plan['tasks']),
    'candidate_rows':sum(x['candidate_rows'] for x in plan['tasks']),
    'seconds':time.monotonic()-started,'gpus':gpus,'video':a.video})
print((a.out/'result.json').read_text(),flush=True)
