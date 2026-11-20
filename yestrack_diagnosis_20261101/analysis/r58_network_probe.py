#!/usr/bin/env python3
"""Targeted regression for the actual HF client's SOCKS dependency, with a small pinned file."""
import json
from pathlib import Path
import sys
sys.path.insert(0,'/home/user/.cache/r58_calibration/extra310')
from huggingface_hub import HfApi,hf_hub_download

root=Path(__file__).resolve().parents[1]
out=root/'analysis/runs/R58_calibration'
plan=json.loads((root/'analysis/plans/r58.json').read_text())
m=next(x for x in plan['models'] if x['repo']=='vllm-sr/d3-mini')
info=HfApi().model_info(m['repo'],revision=m['revision'])
assert info.sha==m['revision']
path=hf_hub_download(m['repo'],'config.json',revision=m['revision'],
                     cache_dir='/home/user/.cache/r58_calibration/network_probe')
config=json.loads(Path(path).read_text())
assert config['model_type']=='qwen3_5'
result={'status':'passed','client':'official huggingface_hub','repo':m['repo'],'revision':info.sha,
        'small_pinned_file':'config.json','model_inference_performed':False}
(out/'network_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
