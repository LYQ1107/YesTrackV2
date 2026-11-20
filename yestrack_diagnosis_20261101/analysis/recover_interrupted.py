#!/usr/bin/env python3
"""Preserve completed units after SIGTERM and resume under one persistent shell owner."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zlib

import numpy as np
from common import config,log_run,mot,save_json

p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true');a=p.parse_args()
c=config();t=Path(c['task_root']);out=t/'analysis/runs/R32_sigterm_recovery';out.mkdir(parents=True,exist_ok=True)


def archive(file,root):
    if file.exists():
        target=root/file.name;target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists(),str(target)
        shutil.move(str(file),str(target))


if a.prepare:
    context=t/'analysis/runs/R23_context';context_plan=json.loads((t/'analysis/plans/context.json').read_text())
    valid_context=0;invalid_context=[]
    for task in context_plan['tasks']:
        file=context/(task['name']+'.npz')
        if not file.exists():continue
        try:
            with np.load(file) as data:
                assert len(data['row_index'])==len(data['y'])==task['candidate_rows']
                for mode in ('original','expand1p5','expand2p5','full_frame_box'):
                    assert len(data[mode])==task['candidate_rows'] and np.isfinite(data[mode]).all()
            valid_context+=1
        except Exception as e:
            invalid_context.append({'name':task['name'],'error':str(e)})
            archive(file,context/'interrupted_attempt1')
    archive(t/'analysis/runs/R23_context.log',out/'attempt1_logs')
    v1=t/'analysis/runs/R24_v1_calibration'
    trace=v1/'raw_scores/rank0.jsonl.gz'
    records=[];decoder=zlib.decompressobj(16+zlib.MAX_WBITS);buffer=b''
    with trace.open('rb') as f:
        while chunk:=f.read(1024*1024):buffer+=decoder.decompress(chunk)
    complete_lines=buffer.split(b'\n')
    if complete_lines[-1]:complete_lines=complete_lines[:-1]
    for line in complete_lines:
        if line:records.append(json.loads(line))
    raw={}
    for r in records:
        current=raw.setdefault(r['name'],{})
        for oid,prob in zip(r['ids'],r['p']):
            item=current.setdefault((r['frame'],oid),{});assert r['mode'] not in item
            item[r['mode']]=prob
    plan=json.loads((t/'analysis/plans/calibration_v1_full.json').read_text())
    manifest=json.loads((t/'analysis/resources/gt_candidates_v1/manifest.json').read_text())
    tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
    valid=set();invalid=[]
    for task in plan['tasks']:
        name=task['name'];seq,expr=name.split('__',1);file=v1/'predictions'/seq/expr/'predict_with_conf.txt'
        if not file.exists():continue
        try:
            pred=mot(file);tr=tracks[seq]
            assert len(pred)==len(tr)==task['candidate_rows']
            assert np.array_equal(pred[:,:2],tr[:,:2]) and np.array_equal(pred[:,2:6],tr[:,2:6].astype(int))
            assert np.isfinite(pred[:,6]).all() and ((pred[:,6]>=0)&(pred[:,6]<=1)).all()
            seen=set();required=set()
            for k,frame in enumerate(np.unique(tr[:,0]).astype(int)):
                ids=tr[tr[:,0]==frame,1].astype(int)
                for oid in ids:
                    if k%10==0 or oid not in seen:required.add((int(frame),int(oid)))
                seen.update(ids)
            observed=raw.get(name,{})
            assert set(observed)==required,(len(observed),len(required))
            for key,item in observed.items():
                assert 'frame' in item
                assert ('video' in item)==(.2<=item['frame']<.8),key
            valid.add(name)
        except Exception as e:
            invalid.append({'name':name,'error':str(e)})
            dest=v1/'interrupted_attempt1/predictions'/seq/expr
            archive(file,dest)
    archive(trace,v1/'raw_scores/interrupted_attempt1')
    with gzip.open(v1/'raw_scores/rank0_recovered.jsonl.gz','wt') as f:
        for record in records:
            if record['name'] in valid:f.write(json.dumps(record)+'\n')
    for file in (v1/'inference.log',v1/'commands.json',t/'analysis/runs/R24_v1_calibration.log'):
        archive(file,out/'attempt1_logs')
    save_json(out/'recovery.json',{'seed':c['seed'],'exit_codes':{'R23':143,'R24':143,'R22_queue':143},
        'root_cause_evidence':'External SIGTERM, no model traceback in completed-unit logs; multiple execution-session cleanup is suspected, not established.',
        'valid_context_tasks':valid_context,'expected_context_tasks':len(context_plan['tasks']),
        'invalid_context_units_preserved':invalid_context,'valid_v1_tasks':len(valid),
        'expected_v1_tasks':len(plan['tasks']),'v1_units_requiring_recompute':invalid,
        'salvaged_raw_json_records':len(records),'partial_gzip_trailer':not decoder.eof,
        'protocol_unchanged':True,'new_owner':'one shell owner, child subprocesses start_new_session=True'})
    log_run(c,32,'SIGTERM 中断恢复（不跳过样本）',[
        'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/recover_interrupted.py --prepare',
        'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+c['reproduction_environment']+' -u analysis/recover_interrupted.py --run'],
        f'R23/R24/等待队列均退出143（SIGTERM），日志无模型异常；不宣称已确定发送者。'
        f'保留R23完整{valid_context}/{len(context_plan["tasks"])}个表达式；'
        f'R24仅保留预测及全部frame/video观察同时完整的{len(valid)}/{len(plan["tasks"])}个表达式。'
        '截断gzip只恢复完整JSON行，缺少所需观察的表达式完整重推；原文件全部存档。'
        '固定seed/权重/参数/指标不变。GPU恢复前预计上下文剩余<2小时，V1剩余<1.5小时；R22已获13小时全量授权。')
    print((out/'recovery.json').read_text(),flush=True)
if a.run:
    assert (out/'recovery.json').exists()
    jobs=[('context',['analysis/context_probe.py','--resume'],'6'),
          ('v1',['analysis/run_v1_calibration.py','--resume'],'5'),
          ('queue',['analysis/queue_full_scores.py'],'3,4,5,6')]
    children=[];logs=[]
    for name,arguments,gpus in jobs:
        env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=gpus
        log=(out/f'{name}_resumed.log').open('w');logs.append(log)
        child=subprocess.Popen([c['reproduction_environment'],'-u',*arguments],cwd=t,env=env,
                               stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        children.append((name,child))
    save_json(out/'child_pids.json',{name:p.pid for name,p in children})
    for name,child in children:
        status=child.wait()
        print(f'[recovery] {name} finished with {status}',flush=True)
        assert status==0,f'{name} failed; inspect {out/(name+"_resumed.log")}'
    for f in logs:f.close()
    save_json(out/'result.json',{'complete':True,'seed':c['seed'],'protocol_unchanged':True})
