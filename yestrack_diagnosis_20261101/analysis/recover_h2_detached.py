#!/usr/bin/env python3
"""Recover complete two-rank H2 observations, then detach H2 and completion owners."""
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import zlib

import numpy as np
from common import config,log_run,mot,save_json

c=config();t=Path(c['task_root']);out=t/'analysis/runs/R34_h2_recovery';out.mkdir(parents=True,exist_ok=True)
h2=t/'analysis/runs/R17_h2';manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
records=[];truncated=[];files=list((h2/'raw_scores').glob('rank*.jsonl.gz'))
for file in files:
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS);buffer=b''
    with file.open('rb') as f:
        while chunk:=f.read(1024*1024):buffer+=decoder.decompress(chunk)
    parts=buffer.split(b'\n')
    if parts[-1]:parts=parts[:-1]
    records.extend(json.loads(line) for line in parts if line)
    if not decoder.eof:truncated.append(file.name)
raw={}
for record in records:
    obs=raw.setdefault(record['name'],{})
    for oid,p in zip(record['ids'],record['p']):
        item=obs.setdefault((record['frame'],oid),{});assert record['mode'] not in item
        item[record['mode']]=p
valid=set();invalid=[]
for task in manifest['expressions']:
    name=task['name'];seq,expr=name.split('__',1);file=h2/'predictions'/seq/expr/'predict_with_conf.txt'
    if not file.exists():continue
    try:
        p=mot(file);tr=tracks[seq]
        assert len(p)==len(tr)==task['candidate_rows']
        assert np.array_equal(p[:,:2],tr[:,:2]) and np.array_equal(p[:,2:6],tr[:,2:6].astype(int))
        assert np.isfinite(p[:,6]).all() and ((p[:,6]>=0)&(p[:,6]<=1)).all()
        seen=set();required=set()
        for k,frame in enumerate(np.unique(tr[:,0]).astype(int)):
            ids=tr[tr[:,0]==frame,1].astype(int)
            required.update((int(frame),int(oid)) for oid in ids if k%10==0 or oid not in seen)
            seen.update(ids)
        obs=raw.get(name,{})
        assert set(obs)==required,(len(obs),len(required))
        for key,item in obs.items():
            assert 'frame' in item
            assert ('video' in item)==(.2<=item['frame']<.8),key
        valid.add(name)
    except Exception as e:
        invalid.append({'name':name,'reason':str(e)})
        dest=out/'interrupted_predictions'/seq/expr/'predict_with_conf.txt';dest.parent.mkdir(parents=True,exist_ok=True)
        assert not dest.exists();shutil.move(str(file),str(dest))
archive=out/'interrupted_raw';archive.mkdir(parents=True,exist_ok=True)
for file in files:
    assert not (archive/file.name).exists();shutil.move(str(file),str(archive/file.name))
with gzip.open(h2/'raw_scores/rank0_recovered_attempt1.jsonl.gz','wt') as f:
    for r in records:
        if r['name'] in valid:f.write(json.dumps(r)+'\n')
for file in (h2/'inference.log',h2/'commands.json'):
    if file.exists():shutil.move(str(file),str(out/('attempt1_'+file.name)))
save_json(out/'recovery.json',{'seed':c['seed'],'valid_complete_tasks':len(valid),'expected_tasks':862,
    'candidate_rows_preserved':sum(x['candidate_rows'] for x in manifest['expressions'] if x['name'] in valid),
    'invalid_units_preserved':invalid,'truncated_gzip_files':truncated,
    'cause_evidence':'Execution-attached owners terminated without model traceback; detached context/V1/queue children survived under PID1. Recreate parent owners with start_new_session=True.',
    'protocol_unchanged':True})
log_run(c,34,'H2 工具会话中断后的独立进程恢复',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/recover_h2_detached.py'],
    f'H2保留{len(valid)}/862个预测和全部raw观察同时完整的表达式；其余完整重推，旧数据存档。'
    '固定seed/权重/TCP/TRP/γ/指标均不变。GPU阶段预计剩余1–3小时，参考R09 2.2h及已保留候选数；低于8小时。'
    'H2及CPU完成owner均通过start_new_session=True脱离工具会话，已运行的R23/R24/R22队列不重复启动。')
owners={}
for name,script,args,gpus in [('H2','analysis/run_h2.py',['--resume'],'3,4'),
                              ('completion_owner','analysis/finish_round2.py',[],'')]:
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=gpus
    log=(out/(name+'.log')).open('w')
    child=subprocess.Popen([c['reproduction_environment'],'-u',script,*args],cwd=t,env=env,
                           stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    owners[name]=child.pid
owners['R22_queue']=2520228
save_json(t/'analysis/process_owners.json',owners)
print(json.dumps({'recovery':json.loads((out/'recovery.json').read_text()),'owners':owners},ensure_ascii=False,indent=2),flush=True)
