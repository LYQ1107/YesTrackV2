#!/usr/bin/env python3
"""Single blocking R58 wait; progress/process checks stay inside this shell-owned job."""
import json
import os
from pathlib import Path
import time

TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
CACHE=Path('/home/user/.cache/r58_calibration/models')
SCRIPTS={b'analysis/r58_owner.py',b'analysis/r58_download.py',b'analysis/r58_fast_download.py',
         b'analysis/r58_gpu.py',b'analysis/r58_pipeline.py',b'analysis/r58_cpu_owner.py',
         b'analysis/r58_analyze.py',b'analysis/r58_report.py'}


def jobs():
    result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0')
            if SCRIPTS.intersection(args) and (p/'cwd').resolve()==TASK:
                result.append({'pid':int(p.name),'script':next(a.decode() for a in args if a in SCRIPTS)})
        except (FileNotFoundError,PermissionError):
            continue
    return result


def progress():
    result=[]
    for m in json.loads((TASK/'analysis/plans/r58.json').read_text())['models']:
        repo=m['repo'];key=repo.replace('/','__');folder=CACHE/key/m['revision']
        complete=partial=0
        for p in folder.glob('*.safetensors'):
            try:complete+=p.stat().st_size
            except FileNotFoundError:pass
        for p in (folder/'.cache/huggingface/download').glob('*.incomplete'):
            try:partial+=p.stat().st_blocks*512
            except FileNotFoundError:pass
        status=OUT/'download_status'/(key+'.json')
        phase=json.loads(status.read_text())['status'] if status.exists() else 'preparing'
        records=0
        for p in (OUT/'predictions'/key).glob('*.jsonl'):
            with p.open('rb') as f:
                while chunk:=f.read(1024*1024):records+=chunk.count(b'\n')
        result.append({'model':repo,'weights_complete_GB':round(complete/1e9,3),
                       'partial_allocated_GB':round(partial/1e9,3),'download':phase,'requests_cached':records})
    return {'active_jobs':jobs(),'models':result}


def main():
    start=time.monotonic();last=None
    with (OUT/'wait_progress.jsonl').open('a') as log:
        while True:
            state=progress();payload=json.dumps(state,sort_keys=True)
            if payload!=last:
                state['wait_elapsed_seconds']=round(time.monotonic()-start)
                line=json.dumps(state);print(line,flush=True);log.write(line+'\n');log.flush();last=payload
            if not state['active_jobs']:
                result={'wait_finished':True,'owner_result_exists':(OUT/'pilot_owner_result.json').exists(),
                        'budget_exists':(OUT/'budget.json').exists()}
                (OUT/'wait_completion.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps(result),flush=True)
                return
            time.sleep(30)


if __name__=='__main__':main()
