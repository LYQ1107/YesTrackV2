#!/usr/bin/env python3
"""Prepare the released V1 protocol for frozen-V2-verifier calibration transfer."""
import configparser
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
from common import config, mot, save_json

c=config()
t=Path(c["task_root"])
gt_root=t/"analysis/resources/release/yestrack/refer_kitti_motc_gt"
data=Path('/data2/user/LocateMOT/data/refer_kitti_v1')
spec=importlib.util.spec_from_file_location('official_gt_parser',t/c['upstream']/'tools/prepare_refer_kitti_motc_gt.py')
off=importlib.util.module_from_spec(spec);spec.loader.exec_module(off)
with (gt_root/'seqmaps/val.txt').open() as f:
    ns=[','.join(row) for row in list(csv.reader(f))[1:] if row]
assert len(ns)==158
out=t/'analysis/resources/gt_candidates_v1'
out.mkdir(parents=True,exist_ok=True)
sequences={}; tasks=[]
for name in ns:
    seq,expr=name.split('__',1)
    if seq not in sequences:
        info=configparser.ConfigParser();info.read(gt_root/name/'seqinfo.ini')
        w,h=info.getint('Sequence','imWidth'),info.getint('Sequence','imHeight')
        frames=off.read_labels_with_ids_boxes(str(data/'labels_with_ids/image_02'),seq,w,h)
        tr=np.array([(f+1,oid,x,y,bw,bh,1.) for f,rs in sorted(frames.items()) for oid,x,y,bw,bh in rs])
        target=out/f'{seq}.txt'
        np.savetxt(target,tr,delimiter=',',fmt=['%d','%d']+['%.3f']*4+['%.6f'])
        sequences[seq]={'track_file':str(target),'width':w,'height':h,
                        'frames':info.getint('Sequence','seqLength'),'candidate_rows':len(tr)}
    tr=mot(sequences[seq]['track_file'])
    js=json.loads((data/'expression'/seq/f'{expr}.json').read_text())
    masks={int(f)+1:{int(i) for i in v} for f,v in js['label'].items()}
    positive=tr[[int(r[1]) in masks.get(int(r[0]),set()) for r in tr],:6]
    gt=mot(gt_root/name/'gt/gt.txt')
    assert np.array_equal(positive,gt[:,:6]),name
    tasks.append({'name':name,'frames':sorted(map(int,np.unique(tr[:,0]))),
                  'candidate_rows':len(tr)})
save_json(out/'manifest.json',{'sequences':sequences,'seed':c['seed'],
    'expression_root':str(data/'expression'),'released_gt':str(gt_root)})
save_json(t/'analysis/plans/calibration_v1_full.json',{'seed':c['seed'],'tasks':tasks,
    'tracks_manifest':str(out/'manifest.json'),
    'scope':'All 158 released V1 val expressions, frozen same V2 verifier for threshold transfer.'})
view=t/'analysis/resources/dataset_v1'
for source,target in [(Path(c['image_root']),view/'KITTI/training/image_02'),
                      (data/'labels_with_ids/image_02',view/'KITTI/labels_with_ids/image_02'),
                      (data/'expression',view/'expression')]:
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.is_symlink():target.symlink_to(source)
for task in tasks:
    seq,expr=task['name'].split('__',1)
    target=out/'results'/seq/expr/'predict.txt';target.parent.mkdir(parents=True,exist_ok=True)
    if not target.is_symlink():target.symlink_to(sequences[seq]['track_file'])
print(json.dumps({'expressions':len(tasks),'candidate_rows':sum(r['candidate_rows'] for r in tasks)},indent=2))
