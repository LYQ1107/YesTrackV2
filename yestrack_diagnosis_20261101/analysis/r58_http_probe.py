#!/usr/bin/env python3
"""Small ranged transfer from a pinned real shard through the official HTTP client."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,'/home/user/.cache/r58_calibration/extra310')
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import hf_hub_url
from huggingface_hub.utils import get_session

root=Path(__file__).resolve().parents[1];out=root/'analysis/runs/R58_calibration'
plan=json.loads((root/'analysis/plans/r58.json').read_text())
m=next(x for x in plan['models'] if x['repo']=='vllm-sr/d3-mini')
url=hf_hub_url(m['repo'],'model-00001-of-00002.safetensors',revision=m['revision'])
data=bytearray()
with get_session().stream('GET',url,headers={'Range':'bytes=0-65535'},follow_redirects=True,timeout=30) as r:
    r.raise_for_status()
    status=r.status_code
    for chunk in r.iter_bytes(chunk_size=65536):
        data.extend(chunk)
        if len(data)>=65536:break
assert len(data)>=65536
(out/'network_shard_prefix.bin').write_bytes(data[:65536])
result={'status':'passed','transport':'official HF HTTP, Xet disabled','repo':m['repo'],
        'revision':m['revision'],'file':'model-00001-of-00002.safetensors',
        'HTTP_status':status,'prefix_bytes':65536,'model_inference':False}
(out/'network_http_shard_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
