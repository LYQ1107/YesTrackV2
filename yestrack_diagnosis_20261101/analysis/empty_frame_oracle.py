#!/usr/bin/env python3
"""Quantify absence at individual frames without inventing globally empty expressions."""
import json
from pathlib import Path

import numpy as np
from common import combine_hota,config,hota_rows,log_run,mot,names,official_eval,run_logged,save_json,summary

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/'analysis/runs/R37_empty_frames';out.mkdir(parents=True,exist_ok=True)
log_run(c,37,'空GT帧的候选保持 oracle（与G全空表达式分开）',[
 'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 '+c['reproduction_environment']+' -u analysis/empty_frame_oracle.py'],
 'CPU；G全视频空表达式为0，不造新语言样本。只在真实表达式的GT集合为空的帧把全部候选score置0，'
 '其余帧、所有框/ID/种子/γ/TrackEval协议保持原样。全862表达式重算，量化时变无目标帧的实际HOTA空间；与F类收益重叠，不能相加。')
counts={'expressions':0,'expressions_with_empty_GT_frames':0,'all_expression_frames':0,'empty_GT_expression_frames':0,
        'empty_GT_frames_with_baseline_false_alarm':0,'candidate_rows':0,'candidate_rows_on_empty_frames':0,
        'positive_predictions_removed':0}
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
for name in names(c):
    seq,expr=name.split('__',1);pred=mot(Path(b['predictions'])/seq/expr/'predict_with_conf.txt')
    gt=mot(Path(c['released_v2_gt'])/name/'gt/gt.txt')
    length=manifest['sequences'][seq]['frames']
    empty=set(range(1,length+1))-set(gt[:,0].astype(int));select=np.isin(pred[:,0],list(empty))
    removed=select & (pred[:,6]>=b['gamma'])
    counts['expressions']+=1;counts['expressions_with_empty_GT_frames']+=bool(empty)
    counts['all_expression_frames']+=length;counts['empty_GT_expression_frames']+=len(empty)
    counts['empty_GT_frames_with_baseline_false_alarm']+=len(np.unique(pred[removed,0]))
    counts['candidate_rows']+=len(pred);counts['candidate_rows_on_empty_frames']+=int(select.sum())
    counts['positive_predictions_removed']+=int(removed.sum())
    pred[select,6]=0
    file=out/'predictions'/seq/expr/'predict_with_conf.txt';file.parent.mkdir(parents=True,exist_ok=True)
    np.savetxt(file,pred,delimiter=',',fmt=['%d']*6+['%.6f'])
command=official_eval(c,out/'predictions',out/'evaluation',[b['gamma']]);save_json(out/'command.json',command)
run_logged(command,t/c['upstream'],out/'trackeval.log')
tag=f"default_t{b['gamma']:.2f}".replace('.','p')
metrics=summary(out/'evaluation/tracker'/tag/'pedestrian_summary.txt')
metric,new=hota_rows(out/'evaluation/tracker'/tag/'pedestrian_detailed.csv',c)
_,base=hota_rows(Path(b['evaluation'])/'tracker'/tag/'pedestrian_detailed.csv',c)
gain=combine_hota(metric,new)['HOTA']-combine_hota(metric,base)['HOTA']
save_json(out/'result.json',{'reference':'相对本地基线','gamma':b['gamma'],'metrics':metrics,'delta_HOTA':gain,
    'counts':counts,'empty_frame_false_alarm_rate':counts['empty_GT_frames_with_baseline_false_alarm']/counts['empty_GT_expression_frames'],
    'scope':'GT-empty expression-frame units, not globally empty expressions or a replacement of categoryG definition.'})
print(json.dumps({'metrics':{k:metrics[k] for k in ('HOTA','DetA','AssA')},'delta_HOTA':gain,'counts':counts},indent=2),flush=True)
