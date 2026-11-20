#!/usr/bin/env python3
"""Bounded byte-range diagnostics for pinned checkpoint transport, without model inference."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,'/home/user/.cache/r58_calibration/extra310')
import httpx

TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
plan=json.loads((TASK/'analysis/plans/r58.json').read_text())
m=next(x for x in plan['models'] if x['repo']=='vllm-sr/d3-mini')
relative=f"/{m['repo']}/resolve/{m['revision']}/model-00001-of-00002.safetensors"
def probe(item):
    host,env=item;t=time.monotonic();n=0
    result={'host':host,'proxy_environment':env,'bytes_requested':1048576}
    try:
        with httpx.Client(trust_env=env,timeout=8,follow_redirects=True) as client:
            with client.stream('GET','https://'+host+relative,headers={'Range':'bytes=0-1048575'}) as r:
                r.raise_for_status()
                result.update(http_status=r.status_code,content_range=r.headers.get('content-range'))
                for chunk in r.iter_bytes(chunk_size=65536):
                    n+=len(chunk)
                    if n>=1048576 or time.monotonic()-t>25:break
        result['status']='passed' if n>=1048576 else 'partial'
    except Exception as e:result.update(status='failed',exception=repr(e))
    result.update(bytes_received=n,seconds=time.monotonic()-t)
    return result
with ThreadPoolExecutor(max_workers=4) as pool:
    result=list(pool.map(probe,[(h,p) for h in ['huggingface.co','hf-mirror.com'] for p in [True,False]]))
(OUT/'network_transport_benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
for row in result:print(json.dumps(row),flush=True)
