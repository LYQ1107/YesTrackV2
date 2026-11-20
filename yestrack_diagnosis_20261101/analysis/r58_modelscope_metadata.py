#!/usr/bin/env python3
"""Reproduce publisher-mirror file listings; HF frozen identities still govern downloads."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.request
TASK=Path(__file__).resolve().parents[1];OUT=TASK/'analysis/runs/R58_calibration'
REPOS=['vllm-sr/d3-mini','vllm-sr/d3-flash','vllm-sr/d3-turbo',
       'OmniJev/OneJev1.5-9B','Qwen/Qwen3-VL-8B-Instruct']
def probe(repo):
    start=time.monotonic();row={'repo':repo}
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'https://modelscope.cn/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true',timeout=15) as response:
            data=json.load(response)
        row.update(seconds=time.monotonic()-start,code=data.get('Code'),data=data)
    except Exception as e:row.update(exception=repr(e),seconds=time.monotonic()-start)
    return row
if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(probe,REPOS))
    dest=OUT/'modelscope_transport_metadata.json'
    if dest.exists():
        history=OUT/'transport_metadata_history';history.mkdir(exist_ok=True)
        (history/f'before_refresh_{time.time_ns()}.json').write_text(dest.read_text())
    dest.write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({'repos':len(rows),'successful':sum(r.get('code')==200 for r in rows)}),flush=True)
