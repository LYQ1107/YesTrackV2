#!/usr/bin/env python3
"""Detached CPU experiment owner and one blocking completion wait, no GPU launch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import config,save_json

c=config();root=Path(c['task_root']);folder=root/'analysis/runs/R49_R50_owner'
folder.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['launch','run','wait']);a=ap.parse_args()
env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
if a.action=='launch':
    receipt=folder/'owner.json'
    if receipt.exists() and not (folder/'result.json').exists():
        raise RuntimeError('Existing owner not complete; wait or diagnose instead of duplicate launch')
    with (folder/'owner.log').open('a') as handle:
        p=subprocess.Popen([c['reproduction_environment'],'-u',str(Path(__file__).resolve()),'run'],
            cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
    save_json(receipt,{'pid':p.pid,'started_unix':time.time(),'GPU_allowed':False,'seed':2025})
    print(json.dumps({'owner_pid':p.pid,'log':str(folder/'owner.log'),'GPU_allowed':False}),flush=True)
elif a.action=='run':
    start=time.monotonic()
    command=[c['reproduction_environment'],'-u','analysis/round3.py','--stage','all']
    with (folder/'experiment.log').open('a') as handle:
        r=subprocess.run(command,cwd=root,env=env,stdout=handle,stderr=subprocess.STDOUT)
    save_json(folder/'result.json',{'complete':r.returncode==0,'returncode':r.returncode,
                                  'seconds':time.monotonic()-start,'command':command,'GPU_started':False})
    sys.exit(r.returncode)
else:
    owner=json.loads((folder/'owner.json').read_text());announced=set()
    stages={'V0 exact gate':root/'analysis/runs/R49_gate/result.json',
            'R49 curves':root/'analysis/runs/R49_self_lock/result.json',
            **{f'LOSO heldout {s}':root/f'analysis/runs/R50_temporal/LOSO/fold_{s}.json' for s in c['val_sequences']},
            **{v:root/f'analysis/runs/R50_temporal/{v}/result.json' for v in
               ['V0','V1','V2','V3','V4_fixed','V4_LOSO','V5_fixed','V5_LOSO']}}
    while not (folder/'result.json').exists():
        os.kill(owner['pid'],0)
        for stage,path in stages.items():
            if stage not in announced and path.exists():
                r=json.loads(path.read_text())
                if r.get('complete'):
                    concise={k:r[k] for k in ['maximum_score_difference','events','held_out_sequence','variant','metrics'] if k in r}
                    print(stage,json.dumps(concise),flush=True);announced.add(stage)
        time.sleep(10)
    result=json.loads((folder/'result.json').read_text());print('CPU owner completed:',json.dumps(result),flush=True)
    if not result['complete']:
        print((folder/'experiment.log').read_text()[-12000:],flush=True)
    sys.exit(result['returncode'])
