#!/usr/bin/env python3
"""Launch one budget-gated R58 owner in a durable process group and block on its log."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
TASK=Path(__file__).resolve().parents[1];OUT=TASK/'analysis/runs/R58_calibration'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['pilot','full','cpu','cpu-model','cpu-main'],required=True)
 ap.add_argument('--model-key');args=ap.parse_args()
 if args.stage=='full':
  assert (OUT/'full_budget_approval.json').exists(),'R58 full budget requires user approval above four hours'
 commands={'pilot':[sys.executable,'-u','analysis/r58_owner.py'],
           'full':[sys.executable,'-u','analysis/r58_pipeline.py'],
           'cpu':[str(TASK/'analysis/.venv-yestrack/bin/python'),'-u','analysis/r58_cpu_owner.py']}
 label=args.stage
 if args.stage in ['cpu-model','cpu-main']:
  assert args.model_key,'--model-key is required for model CPU stages'
  suffix='_pilot.json' if args.stage=='cpu-main' else '_full.json'
  status=json.loads((OUT/'status'/(args.model_key+suffix)).read_text())
  assert status['status']=='complete','Frozen inference stage required before CPU analysis'
  commands[args.stage]=commands['cpu']+['--model-key',args.model_key]+(['--main-only'] if args.stage=='cpu-main' else [])
  label+='_'+args.model_key
 log=OUT/f'{label}_pipeline_stream.log';record=OUT/f'{label}_pipeline_launch.json'
 if record.exists():
  old=json.loads(record.read_text());p=Path('/proc')/str(old['pid'])
  if p.exists():
   try:
    assert commands[args.stage][2].encode() not in (p/'cmdline').read_bytes().split(b'\0'),'The same R58 owner is already running; use analysis/r58_wait.py to reconnect'
   except FileNotFoundError:pass
 offset=log.stat().st_size if log.exists() else 0
 env=dict(os.environ)
 if args.stage in ['cpu','cpu-model','cpu-main']:
  env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
 with log.open('a') as f:
  child=subprocess.Popen(commands[args.stage],cwd=TASK,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)
 record.write_text(json.dumps({'pid':child.pid,'stage':args.stage,'command':commands[args.stage],
   'log':str(log),'terminal_signal_isolated':True},indent=2)+'\n')
 print(json.dumps({'event':'durable_R58_launch','stage':args.stage,'pid':child.pid}),flush=True)
 with log.open() as f:
  f.seek(offset)
  while True:
   chunk=f.read()
   if chunk:print(chunk,end='',flush=True)
   code=child.poll()
   if code is not None:
    chunk=f.read()
    if chunk:print(chunk,end='',flush=True)
    raise SystemExit(code)
   time.sleep(5)
if __name__=='__main__':main()
