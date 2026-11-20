#!/usr/bin/env python3
"""Pinned HF downloads with resumable parallel HTTP byte ranges for large weights."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlencode
sys.path.insert(0,'/home/user/.cache/r58_calibration/extra310')
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='120'
from huggingface_hub import snapshot_download,hf_hub_download,hf_hub_url,get_hf_file_metadata
from huggingface_hub._local_folder import get_local_download_paths,write_download_metadata

TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
CACHE=Path('/home/user/.cache/r58_calibration/models')

def shard(info,name,dest):
    url=hf_hub_url(info['repo'],name,revision=info['revision'])
    meta=get_hf_file_metadata(url,timeout=30)
    assert meta.commit_hash==info['revision']
    if meta.size<64*1024*1024:
        return hf_hub_download(info['repo'],name,revision=info['revision'],local_dir=dest)
    target=dest/name
    paths=get_local_download_paths(dest,name)
    if target.exists() and target.stat().st_size==meta.size:
        if paths.metadata_path.exists() and paths.metadata_path.read_text().splitlines()[0]==info['revision']:
            return str(target)
    temporary=target.with_name(target.name+'.http-ranges')
    if not temporary.exists():
        partials=[p for p in (dest/'.cache/huggingface/download').glob('*.incomplete') if name in p.name and meta.etag in p.name]
        if partials:
            assert len(partials)==1
            partials[0].rename(temporary)
    assert len(meta.etag)==64,'Expected official LFS SHA256 for weight file'
    # Only use the publisher mirror when its content identity equals the frozen HF object.
    transport='pinned HF HTTP'
    metadata_path=OUT/'modelscope_transport_metadata.json'
    mirrors=json.loads(metadata_path.read_text())
    mirror=next((m for m in mirrors if m['repo']==info['repo'] and m.get('code')==200),None)
    if mirror is not None:
        alternate=next((f for f in mirror['data']['Data']['Files'] if f['Path']==name),None)
        if alternate is not None and alternate['Sha256']==meta.etag and alternate['Size']==meta.size:
            url='https://modelscope.cn/api/v1/models/'+info['repo']+'/repo?'+urlencode(
                {'Revision':alternate['Revision'],'FilePath':name})
            transport='publisher ModelScope, exact pinned HF SHA256'
            with (OUT/'modelscope_weight_identity.jsonl').open('a') as f:
                f.write(json.dumps({'repo':info['repo'],'HF_revision':info['revision'],'file':name,
                    'sha256':meta.etag,'bytes':meta.size,'modelscope_file_revision':alternate['Revision']})+'\n')
    command=['aria2c','--no-conf=true','--show-console-readout=false',
        '--continue=true','--auto-file-renaming=false','--allow-overwrite=true',
        '--file-allocation=none','--max-connection-per-server=16','--split=16','--min-split-size=8M',
        '--timeout=60','--connect-timeout=20','--retry-wait=5','--max-tries=5',
        '--summary-interval=60','--console-log-level=warn','--download-result=hide',
        '--check-integrity=true','--checksum=sha-256='+meta.etag,
        '--dir='+str(dest),'--out='+temporary.name,url]
    # Keep the process environment (including the existing local HTTP proxy) task-local.
    key=info['repo'].replace('/','__')
    with (OUT/'logs'/(key+'_'+name+'_transfer.log')).open('a') as log:
        env=dict(os.environ)
        if transport.startswith('publisher ModelScope'):
            env={k:v for k,v in env.items() if 'proxy' not in k.lower()}
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
    if result.returncode:
        raise RuntimeError(f'aria2 returned {result.returncode} for pinned {key}/{name}; raw transfer log preserved')
    assert temporary.stat().st_size==meta.size
    temporary.rename(target)
    write_download_metadata(dest,name,info['revision'],meta.etag)
    print(json.dumps({'event':'verified_weight','repo':info['repo'],'file':name,'bytes':meta.size,'transport':transport}),flush=True)
    return str(target)

def download(info):
    repo=info['repo'];key=repo.replace('/','__');dest=CACHE/key/info['revision'];start=time.monotonic()
    print(json.dumps({'event':'parallel_http_start','repo':repo,'revision':info['revision']}),flush=True)
    try:
        snapshot_download(repo,revision=info['revision'],local_dir=dest,max_workers=4,ignore_patterns=['*.safetensors'])
        names=[n for n in info['files'] if n.endswith('.safetensors')]
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda name:shard(info,name,dest),names))
        link=OUT/'models'/key
        if not link.exists():link.symlink_to(dest,target_is_directory=True)
        result={'repo':repo,'revision':info['revision'],'path':str(dest),'status':'downloaded',
            'transport':'parallel publisher mirror or HF HTTP, all weights verified against frozen HF LFS SHA256','seconds':time.monotonic()-start}
    except Exception as e:
        result={'repo':repo,'revision':info['revision'],'status':'download_failed','exception':repr(e),'seconds':time.monotonic()-start}
    path=OUT/'download_status'/(key+'.json')
    if path.exists():
        h=OUT/'download_status_history';h.mkdir(exist_ok=True)
        (h/(key+'_'+str(time.time_ns())+'.json')).write_text(path.read_text())
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repos',nargs='*');a=ap.parse_args()
    inv=json.loads((OUT/'model_inventory.json').read_text())
    repos=a.repos or ['vllm-sr/d3-mini','vllm-sr/d3-flash','OmniJev/OneJev1.5-9B','Qwen/Qwen3-VL-8B-Instruct','vllm-sr/d3-turbo']
    infos=[next(m for m in inv if m['repo']==r) for r in repos]
    (OUT/'logs').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(download,infos))
    raise SystemExit(int(any(r['status']!='downloaded' for r in results)))
