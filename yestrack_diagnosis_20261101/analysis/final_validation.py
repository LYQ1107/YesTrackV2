#!/usr/bin/env python3
"""Verify delivered data coverage and the new paired-number control once complete."""
import csv
import gzip
import json
from pathlib import Path
import subprocess

import numpy as np
from common import config,log_run,save_json

c=config();t=Path(c['task_root']);a=t/'analysis'
log_run(c,48,'最终交付核对：覆盖、同输入对照、人工审核表及官方源码',[
    "CUDA_VISIBLE_DEVICES='' "+c['reproduction_environment']+' analysis/final_validation.py'],
    'CPU；只做结果可信和交付完整所需核对，不重跑已通过的GPU推理/全量TrackEval。'
    '原生重放须差0；SoM softmax归一化按FP32累计误差检查1e-6，二者为不同条件。'
    '随机编号前后按GT ID逐值核对crop概率/标签和候选集合，不能只比较汇总F1。')


def read(path):return json.loads((a/path).read_text())


baseline=read('local_baseline.json');status=read('round2_status.json')
assert c['seed']==baseline['seed']==2025 and baseline['gamma']==.6
assert status['complete'] and all(status['completed'].values())
checks=[('runs/R17_h2/coverage.json',{'complete':True,'expressions':862,'candidate_rows':2860484}),
        ('runs/R22_full_scores/result.json',{'complete':True,'seed':2025,'tasks':862,'candidate_rows':2860484}),
        ('runs/R26_birth_scores/result.json',{'complete':True,'seed':2025,'tasks':532,'candidate_rows':28676}),
        ('runs/R25_som/coverage.json',{'complete':True,'seed':2025,'expression_frames':1704}),
        ('runs/R47_shuffled_som/coverage.json',{'complete':True,'seed':2025,'expression_frames':1704}),
        ('runs/R47_shuffled_som/controller_complete.json',{'complete':True,'seed':2025,'expression_frames':1704})]
for path,expected in checks:
    r=read(path)
    for key,value in expected.items():assert r[key]==value,(path,key,r[key],value)
trp=read('runs/R28_trp/result.json');cal=read('runs/R27_calibration/result.json')
assert trp['expressions']==532 and trp['candidate_rows']==2150942 and trp['gamma']==.6
assert trp['native_delta10_max_score_difference']==0
assert cal['replay_native_max_score_difference']=={'V1':0.0,'V2':0.0}
assert cal['frame_calibration']['n']==2860484 and cal['gamma_frozen_baseline']==.6
labels=read('labels/expressions.json');names={r['name'] for r in labels}
assert len(labels)==len(names)==862
with (a/'label_audit.csv').open() as f:audit=list(csv.DictReader(f))
assert len(audit)==len({r['name'] for r in audit})==100
assert {r['name'] for r in audit}<=names
images=read('errors/manifest.json')
with (a/'errors/index.csv').open() as f:main_images=list(csv.DictReader(f))
with (a/'errors/G_empty_frame_control/index.csv').open() as f:empty_images=list(csv.DictReader(f))
assert len(main_images)==images['images']==404 and len(empty_images)==30
for row in main_images+empty_images:assert Path(row['file']).is_file(),row['file']
for value in images['counts'].values():
    for kind in ('FP','FN'):assert value[kind]['saved']==min(30,value[kind]['available_errors'])
plan=read('plans/som.json');expected_units={(r['name'],f,r['group']) for r in plan['tasks'] for f in r['frames']}
assert len(expected_units)==1704
records={};max_normalization_error=0.
for stage in ('R25_som','R47_shuffled_som'):
    rows={}
    with gzip.open(a/'runs'/stage/'frames.jsonl.gz','rt') as f:
        for line in f:
            r=json.loads(line);key=(r['name'],r['frame'],r['group']);assert key not in rows;rows[key]=r
            assert len(r['ids'])==len(set(r['ids']))==r['n']
            for field in ('p_crop','p_full_binary','option_probabilities','single_token_option_probabilities'):
                if r[field] is None:continue
                p=np.asarray(r[field]);assert np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),(key,field)
                if 'option_probabilities' in field:
                    error=abs(float(p.sum())-1);max_normalization_error=max(max_normalization_error,error)
                    assert len(p)==r['n']+1 and error<1e-6,(key,field,error)
    assert set(rows)==expected_units,stage
    records[stage]=rows
for key,random in records['R47_shuffled_som'].items():
    original=records['R25_som'][key];seq=key[0].split('__',1)[0]
    perm=np.random.default_rng(c['seed']+100000*int(seq)+key[1]).permutation(original['n'])
    assert random['candidate_permutation_from_original']==perm.tolist()
    assert random['ids']==np.array(original['ids'])[perm].tolist()
    assert random['y']==np.array(original['y'])[perm].tolist()
    assert random['p_crop']==np.array(original['p_crop'])[perm].tolist()
context=read('runs/R23_context/result.json')['groups']['D']['original']
for stage in ('R25_som','R47_shuffled_som'):
    r=read('runs/'+stage+'/result.json');assert r['gamma']==.6
    for key in ('tp','fp','fn','tn','n'):assert r['groups']['D']['crop_binary']['candidate_referring'][key]==context[key]
for path in ('REPORT.md','runs.md','error_patterns.md','runs/R27_calibration/reliability.png',
             'runs/R27_calibration/reliability.pdf','runs/R28_trp/switch_error.png','runs/R28_trp/switch_error.pdf',
             'runs/R21_decomposition/category_gains.png','runs/R21_decomposition/category_gains.pdf'):
    assert (a/path).is_file(),path
source=subprocess.run(['git','diff','--exit-code'],cwd=t/c['upstream'],capture_output=True,text=True)
assert source.returncode==0,source.stdout
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=t/c['upstream'],text=True).strip()
assert head==c['upstream_commit']
save_json(a/'runs/R48_final_validation/result.json',{'complete':True,'seed':2025,'gamma':.6,
    'full_GT_rows':2860484,'expressions':862,'audit_rows':100,'error_images':434,
    'ordered_SoM_frames':1704,'randomized_SoM_frames':1704,'SOM_crop_and_GT_ID_parity_exact':True,
    'D_crop_confusion_matches_R23_in_both_runs':True,'native_replay_max_difference':0.,
    'max_FP32_option_normalization_error':max_normalization_error,'upstream_tracked_diff_empty':True,'upstream_commit':head})
print((a/'runs/R48_final_validation/result.json').read_text(),flush=True)
