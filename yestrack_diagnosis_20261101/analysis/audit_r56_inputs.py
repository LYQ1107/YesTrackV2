#!/usr/bin/env python3
"""Read-only R14/released-candidate field audit; write only new R56 artifacts."""
import json
import os
from pathlib import Path

import numpy as np
from common import config,log_run,mot,names,save_json


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    c=config();root=Path(c['task_root']);out=root/'analysis/runs/R56';out.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((root/'analysis/local_baseline.json').read_text())
    log_run(c,'56-inputs','候选字段与R14坐标对齐核查',[
        "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "+c['reproduction_environment']+' -u analysis/audit_r56_inputs.py'],
        '只读R14和发布候选，全862表达式；本步骤仅核查字段、轨迹元数据及行对齐，不计算任何新HOTA或选择规则阈值。')
    canonical={};features={};columns={};total=0;file_count=0
    for name in names(c):
        seq,expr=name.split('__',1)
        raw=mot(Path(c['temprmot_star_candidates'])/seq/expr/'predict.txt')
        base=mot(Path(baseline['predictions'])/seq/expr/'predict_with_conf.txt')
        assert np.array_equal(np.trunc(raw[:,:6]),base[:,:6]),(name,'candidate/R14 row mismatch')
        assert len(set(map(tuple,raw[:,:2].astype(int))))==len(raw),(name,'duplicate frame/ID')
        if seq not in canonical:
            canonical[seq]=raw[:,:6].copy()
            ids,inverse,count=np.unique(raw[:,1].astype(int),return_inverse=True,return_counts=True)
            features[seq]={'frames':raw[:,0].astype(int),'ids':raw[:,1].astype(int),
                'geometry':base[:,:6],'track_length':count[inverse],
                'box_area':raw[:,4]*raw[:,5]}
        else:assert np.array_equal(raw[:,:6],canonical[seq]),(name,'features differ by expression')
        for j in range(6,raw.shape[1]):
            stat=columns.setdefault(str(j+1),{'unique_values':set(),'rows':0,'files':0})
            stat['unique_values'].update(np.unique(raw[:,j]).tolist());stat['rows']+=len(raw);stat['files']+=1
        total+=len(raw);file_count+=1
    assert file_count==862 and total==1850576
    for stat in columns.values():stat['unique_values']=sorted(stat['unique_values'])
    informative=bool(len(columns['7']['unique_values'])>1)
    result={'complete':True,'seed':2025,'expressions':file_count,'candidate_rows':total,
        'candidate_columns':6+len(columns),'columns_after_geometry':columns,
        'informative_detection_confidence_present':informative,
        'confidence_interpretation':'MOT column7 exists but is a constant placeholder; no varying detector confidence is released' if not informative else 'column7 varies; inspect meaning before use',
        'features_expression_independent':True,'R14_integer_geometry_exact':True,
        'feature_definitions':{'track_length':'total observed rows for this sequence-local tracker ID; one row per visible frame, offline including future observations',
            'box_area':'per-row original tracker float width*height, before YesTrack integer serialization'},
        'sequences':{}}
    for seq,values in features.items():
        p=out/'features'/f'{seq}.npz';p.parent.mkdir(exist_ok=True)
        np.savez_compressed(p,**values)
        result['sequences'][seq]={'candidate_rows_per_expression':len(values['ids']),
            'tracks':len(np.unique(values['ids'])),'track_length_range':[int(values['track_length'].min()),int(values['track_length'].max())],
            'area_range':[float(values['box_area'].min()),float(values['box_area'].max())]}
    save_json(out/'input_audit.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
