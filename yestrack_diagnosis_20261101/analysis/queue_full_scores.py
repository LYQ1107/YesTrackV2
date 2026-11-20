#!/usr/bin/env python3
"""A single blocking owner waits for earlier stages, then runs the authorized full cache."""
import json
from pathlib import Path
import subprocess
import time

from common import config,log_run,save_json

c=config();t=Path(c['task_root'])
budget=t/'analysis/plans/R22_budget_request.json'
plan=json.loads(budget.read_text())
assert plan['status']=='user_approved_full_stage'
out=t/'analysis/runs/R22_full_scores';out.mkdir(parents=True,exist_ok=True)
dependencies=[t/'analysis/runs/R17_h2/result.json',t/'analysis/runs/R23_context/result.json',
              t/'analysis/runs/R24_v1_calibration/result.json']
log_run(c,'22-queue','获批全量阶段的阻塞队列',[
    'CUDA_VISIBLE_DEVICES=3,4,5,6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+c['reproduction_environment']+' -u analysis/queue_full_scores.py'],
    '用户已于本轮明确回复“批准全量运行（推荐，完成全部校准和 TRP 扫描）”。'
    'GPU 阶段预计11.5–16小时，点估计11.49小时，预算13小时；先等待R17/R23/R24完成释放同一组GPU。'
    '只在此单一阻塞命令内部等待依赖，模型端不轮询进程/日志；不停止其他项目进程。')
print('[R22] User authorization recorded; waiting inside owner for R17, R23 and R24.',flush=True)
while not all(p.exists() for p in dependencies):
    time.sleep(20)
for path in dependencies:
    receipt=json.loads(path.read_text())
    if 'complete' in receipt:assert receipt['complete'],str(path)
resource=subprocess.run(['nvidia-smi','-i','3,4,5,6','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],
                        check=True,text=True,capture_output=True)
(out/'resource_start.csv').write_text(resource.stdout)
assert all(int(line.split(',')[1])>=16000 for line in resource.stdout.splitlines()),resource.stdout
print('[R22] Dependencies complete and resources checked; launching all 862 expressions.',flush=True)
command=[c['reproduction_environment'],'-u','analysis/run_score_cache.py',
    '--plan','analysis/plans/calibration_full.json','--out','analysis/runs/R22_full_scores',
    '--gpus','3,4,5,6','--run-number','22','--estimated-hours','13','--video','--over8-authorized']
subprocess.run(command,cwd=t,check=True)
print('[R22] Full score cache complete and validated.',flush=True)
