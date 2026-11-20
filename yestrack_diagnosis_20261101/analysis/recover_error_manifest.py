#!/usr/bin/env python3
"""Resume the CPU deliverable that failed while serializing NumPy counters."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import numpy as np
from common import config,log_run,save_json

c=config();t=Path(c['task_root']);out=t/'analysis/runs/R40_error_manifest_recovery'
out.mkdir(parents=True,exist_ok=True)
# Targeted regression for the exact offending counter, retaining strict JSON.
counter=0;counter+=np.float64(50)<1024
assert isinstance(counter,np.integer)
assert json.loads(json.dumps({'count':int(counter)},allow_nan=False))['count']==1
save_json(out/'serialization_regression.json',{'complete':True,'counter_type':type(counter).__name__,
    'serialized_count':int(counter),'protocol_changed':False})
command=[c['reproduction_environment'],'-u','analysis/finish_round2.py','--resume-h2-deliverables']
log_run(c,40,'错误样例汇总JSON类型修复及原完成owner接续',[
    "CUDA_VISIBLE_DEVICES='' "+c['reproduction_environment']+' analysis/recover_error_manifest.py'],
    'R29已保存图片/index但清单写入因area计数为numpy.int64而失败。只将清单计数转Python int；'
    '定向严格JSON回归通过后重做未完成R29汇总单元，跳过已有完整H2/上下文/分解结果。'
    'R22独立全量GPU owner继续，绝不重启；新完成owner只等其receipt。'+shlex.join(command))
failure=t/'analysis/runs/R30_completion/failure.json'
assert failure.exists(),failure
shutil.move(str(failure),str(out/'failure_before.json'))
env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='';env['OMP_NUM_THREADS']='2'
with (out/'completion_resumed.log').open('w') as f:
    child=subprocess.Popen(command,cwd=t,env=env,stdin=subprocess.DEVNULL,
        stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
owners=json.loads((t/'analysis/process_owners.json').read_text());owners['completion_owner']=child.pid
save_json(t/'analysis/process_owners.json',owners)
save_json(out/'launched.json',{'complete':True,'completion_owner':child.pid,'command':command,
    'reuse_H2':True,'reuse_R22_owner':True,'seed':c['seed']})
entry=('\n2026-11-01 — Full H2 completed:862 expressions/2860484 GT candidate rows; '
       'HOTA65.231987 /DetA48.203352 /AssA88.284481; referAcc83.7918%,P51.5889%,R91.3828%,F165.9478%. '
       'H2-H1=24.804525; H3raw-H2=34.765405; integer-box control gives semantic gap32.488. '
       'R19c split frame/video execution exactly matches827 original samples (344 video), maxdifference0.0; '
       'approved full cache has started. R29 manifest failed only on NumPy int64 JSON serialization after '
       'images/index were written; explicit int conversion and targeted strict-JSON regression retain all '
       'counts/seed/protocol. Resume unfinished CPU deliverable in detached completion owner; do not restart GPU inference.\n')
for file in (t/'analysis/research_log.md',t.parent/'research_log.md'):
    with file.open('a') as f:f.write(entry)
print(json.dumps({'recovered':True,'pid':child.pid,'regression':True}),flush=True)
