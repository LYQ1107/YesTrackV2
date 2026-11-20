#!/usr/bin/env python3
"""Compare a corrected official KV path against immutable full-option pilot scores."""
import json
import os
from pathlib import Path
import random
import sys
import time
import traceback
TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
from r58_owner import select_gpu
visible=select_gpu(12)
os.environ['CUDA_VISIBLE_DEVICES']=str(visible)
os.environ['OMP_NUM_THREADS']='4'
os.environ['TOKENIZERS_PARALLELISM']='false'
sys.path.insert(0,'/home/user/.cache/r58_calibration/extra310')
import numpy as np
import torch
from r58_gpu import Qwen,PLAN
random.seed(2025);np.random.seed(2025);torch.manual_seed(2025);torch.cuda.manual_seed_all(2025);torch.set_num_threads(4)
repo='Qwen/Qwen3-VL-2B-Instruct';key=repo.replace('/','__')
with (TASK/'analysis/runs.md').open('a') as f:f.write(f'\nR58 Qwen共享前缀工程修复回归：物理GPU{visible}，启动前预估3–15分钟；对同一试跑250条请求逐值比较，冻结容差仍为0.005，不覆盖任何已存概率。使用TF5.17官方_prepare_position_ids_for_generation及prepare_inputs_for_generation，修正suffix-only输入的M-RoPE切片；模型、完整选项条件似然、批次大小和题库均不变。\n\n```bash\npython3 -u analysis/r58_qwen_cache_regression.py\n```\n')
start=time.monotonic();rows=[]
try:
 model=Qwen(repo,OUT/'models'/key)
 torch.cuda.synchronize();load=time.monotonic()-start
 samples={r['id']:r for r in json.loads((OUT/'samples.json').read_text())}
 maximum=0.;flips=0
 for setting in PLAN['questions']['settings']:
  source=OUT/'predictions'/key/(setting['id']+'.jsonl')
  reference=[json.loads(line) for line in source.read_text().splitlines()]
  for i,ref in enumerate(reference):
   before=time.monotonic()
   with torch.inference_mode():
    inputs,mapping=model.inputs(samples[ref['sample_id']],setting)
    probs=model.cached(inputs,mapping)
   torch.cuda.synchronize();seconds=time.monotonic()-before
   delta=max(abs(p-ref['probabilities'][q][k]) for q,pp in probs.items() for k,p in pp.items())
   maximum=max(maximum,delta)
   flips+=sum(max(pp,key=pp.get)!=max(ref['probabilities'][q],key=ref['probabilities'][q].get) for q,pp in probs.items())
   rows.append({'sample_id':ref['sample_id'],'setting':setting['id'],'seconds':seconds,'max_abs_probability_error':delta})
   assert delta<=.005,(ref['sample_id'],setting['id'],delta)
   if i==0 or (i+1)%20==0:print(json.dumps({'event':'cache_regression','setting':setting['id'],'completed':i+1,'max_abs_probability_error':maximum,'last_seconds':seconds}),flush=True)
 result={'status':'passed','repo':repo,'seed':2025,'physical_gpu':visible,'load_seconds':load,
  'wall_seconds':time.monotonic()-start,'probability_max_abs_error':maximum,'tolerance':.005,
  'argmax_flips_among_compared_questions':flips,'reference':'immutable full-option pilot probabilities',
  'probabilities_overwritten':False,'requests':rows}
except Exception as e:
 result={'status':'failed','repo':repo,'exception':repr(e),'traceback':traceback.format_exc(),
  'wall_seconds':time.monotonic()-start,'requests':rows}
 traceback.print_exc()
(OUT/'qwen_cache_regression.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['requests','traceback']}),flush=True)
if result['status']!='passed':raise SystemExit(1)
