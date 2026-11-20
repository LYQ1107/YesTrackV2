#!/usr/bin/env python3
"""Reconnect one blocking observer to an existing durable R58 CPU owner."""
import argparse
import json
from pathlib import Path
import time

TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model-key',required=True)
    ap.add_argument('--main-only',action='store_true');args=ap.parse_args()
    stage='cpu-main' if args.main_only else 'cpu-model'
    launch=json.loads((OUT/(stage+'_'+args.model_key+'_pipeline_launch.json')).read_text())
    process=Path('/proc')/str(launch['pid'])
    result=OUT/('cpu_'+args.model_key+('_main' if args.main_only else '')+'_result.json')

    def alive():
        try:argv=(process/'cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:return False
        return (b'analysis/r58_cpu_owner.py' in argv and args.model_key.encode() in argv
                and (b'--main-only' in argv)==args.main_only)

    print(json.dumps({'event':'CPU_observer_attached','owner_pid':launch['pid'],
        'model':args.model_key,'main_only':args.main_only,'owner_live':alive()}),flush=True)
    with Path(launch['log']).open() as stream:
        while True:
            chunk=stream.read()
            if chunk:print(chunk,end='',flush=True)
            if not alive():
                chunk=stream.read()
                if chunk:print(chunk,end='',flush=True)
                break
            time.sleep(5)
    if not result.exists():
        raise RuntimeError('CPU owner is no longer live but no terminal result was written; inspect its analysis worker/log before resuming')
    rows=json.loads(result.read_text())
    print(json.dumps({'event':'CPU_observer_terminal','result':rows}),flush=True)
    if any(r['status']!='complete' for r in rows):
        raise RuntimeError('The CPU owner recorded an analysis failure; inspect its log')


if __name__=='__main__':main()
