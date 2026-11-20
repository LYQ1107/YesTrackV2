#!/usr/bin/env python3
"""Check an alternate official publisher endpoint against the frozen HF weight identity."""
import json
from pathlib import Path
import time
import urllib.request
from urllib.parse import urlencode
TASK=Path(__file__).resolve().parents[1];OUT=TASK/'analysis/runs/R58_calibration'
rows=json.loads((OUT/'modelscope_transport_metadata.json').read_text())
mini=next(x for x in rows if x['repo']=='vllm-sr/d3-mini')
file=next(f for f in mini['data']['Data']['Files'] if f['Path']=='model-00001-of-00002.safetensors')
manifest=json.loads((OUT/'model_cards/vllm-sr__d3-mini/MODEL_MANIFEST.json').read_text())
expected=manifest['identity']['files_sha256'][file['Path']]
assert file['Sha256']==expected,(file['Sha256'],expected)
url='https://modelscope.cn/api/v1/models/vllm-sr/d3-mini/repo?'+urlencode({'Revision':file['Revision'],'FilePath':file['Path']})
request=urllib.request.Request(url,headers={'Range':'bytes=0-1048575'})
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
start=time.monotonic();data=bytearray()
try:
 with opener.open(request,timeout=15) as r:
  code=r.status;content_range=r.headers.get('Content-Range')
  while len(data)<1048576:
   chunk=r.read(min(65536,1048576-len(data)))
   if not chunk:break
   data.extend(chunk)
 result={'status':'passed' if len(data)==1048576 else 'partial','repo':mini['repo'],
   'pinned_HF_SHA256':expected,'modelscope_file_revision':file['Revision'],'HTTP_status':code,
   'content_range':content_range,'bytes':len(data),'seconds':time.monotonic()-start,
   'matches_known_HF_prefix':data[:65536]==(OUT/'network_shard_prefix.bin').read_bytes()}
except Exception as e:result={'status':'failed','exception':repr(e),'seconds':time.monotonic()-start}
(OUT/'modelscope_transport_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
