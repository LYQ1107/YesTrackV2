#!/usr/bin/env python3
"""Reuse the existing base Qwen checkpoint only when every pinned HF metadata entry agrees."""
import json
from pathlib import Path
import shutil

TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
repo='Qwen/Qwen3-VL-2B-Instruct'
plan=json.loads((TASK/'analysis/plans/r58.json').read_text())
info=next(m for m in plan['models'] if m['repo']==repo)
source=Path('/data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct')
dest=Path('/home/user/.cache/r58_calibration/models')/repo.replace('/','__')/info['revision']
dest.mkdir(parents=True,exist_ok=True)
files=[]
for p in source.iterdir():
    if not p.is_file():continue
    meta=source/'.cache/huggingface/download'/(p.name+'.metadata')
    assert meta.exists(),p
    assert meta.read_text().splitlines()[0]==info['revision'],p
    target=dest/p.name
    if not target.exists():target.symlink_to(p)
    cache=dest/'.cache/huggingface/download'
    cache.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(meta,cache/meta.name)
    files.append({'file':p.name,'bytes':p.stat().st_size})
assert any(x['file']=='model.safetensors' for x in files)
target=OUT/'models'/repo.replace('/','__')
target.parent.mkdir(exist_ok=True)
if not target.exists():target.symlink_to(dest,target_is_directory=True)
result={'repo':repo,'revision':info['revision'],'path':str(dest),'status':'downloaded',
        'source':'existing unmodified base checkpoint with matching official per-file revision metadata',
        'source_path':str(source),'files':files,'seconds':0}
(OUT/'download_status').mkdir(exist_ok=True)
(OUT/'download_status'/(repo.replace('/','__')+'.json')).write_text(json.dumps(result,indent=2)+'\n')
(OUT/'local_checkpoint_reuse.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'reused_pinned_local_checkpoint','repo':repo,'revision':info['revision']}),flush=True)
