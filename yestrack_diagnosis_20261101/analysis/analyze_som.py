#!/usr/bin/env python3
"""Report SoM candidate F1, none detection and empty-frame false alarms."""
import argparse
import gzip
import json
from pathlib import Path
import shlex

import numpy as np
from common import config,confusion,log_run,save_json

parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('analysis/runs/R25_som'))
parser.add_argument('--run-number',default='25-analysis');args=parser.parse_args()
c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
out=t/args.out
data=[]
with gzip.open(out/'frames.jsonl.gz','rt') as f:
    for line in f:data.append(json.loads(line))
methods=['crop_binary','full_marked_binary','SoM_frozen_gamma','SoM_argmax','SoM_next_token_gamma','always_first_order_control']
results={}
for group,subset in [('D',[r for r in data if r['group']=='D']),
                     ('G_empty_frame_control',[r for r in data if r['group']!='D']),
                     ('D_single_target',[r for r in data if r['group']=='D' and sum(r['y'])==1]),
                     ('D_multiple_targets',[r for r in data if r['group']=='D' and sum(r['y'])>1]),
                     ('D_single_token_options',[r for r in data if r['group']=='D' and r['single_token_option_probabilities'] is not None]),
                     ('G_single_token_options',[r for r in data if r['group']!='D' and r['single_token_option_probabilities'] is not None]),
                     ('all',data)]:
    group_result={}
    for method in methods:
        selected=[r for r in subset if method!='SoM_next_token_gamma' or r['single_token_option_probabilities'] is not None]
        ys=[];preds=[];y_none=[];pred_none=[];empty_alarm=empty_count=0
        for row in selected:
            y=np.array(row['y'],dtype=bool);n=len(y)
            if method=='crop_binary':pred=np.array(row['p_crop'])>=b['gamma']
            elif method=='full_marked_binary':pred=np.array(row['p_full_binary'])>=b['gamma']
            elif method=='SoM_frozen_gamma':pred=np.array(row['option_probabilities'][:-1])>=b['gamma']
            elif method=='SoM_next_token_gamma':pred=np.array(row['single_token_option_probabilities'][:-1])>=b['gamma']
            elif method=='always_first_order_control':
                pred=np.zeros(n,dtype=bool);pred[0]=True
            else:
                pred=np.zeros(n,dtype=bool)
                if row['selected'] is not None:pred[row['selected']-1]=True
            ys.extend(y);preds.extend(pred);y_none.append(not y.any());pred_none.append(not pred.any())
            if not y.any():empty_count+=1;empty_alarm+=bool(pred.any())
        candidate=confusion(ys,preds,.5);absent=confusion(y_none,pred_none,.5)
        group_result[method]={'candidate_referring':candidate,'none_detection':absent,
            'expression_frames':len(selected),'expressions':len({r['name'] for r in selected}),
            'empty_GT_frames':empty_count,'empty_GT_frames_with_false_alarm':empty_alarm,
            'empty_frame_false_alarm_rate':empty_alarm/empty_count if empty_count else None}
    results[group]=group_result
order_diagnostics={}
for group,subset in [('D',[r for r in data if r['group']=='D']),('G_empty_frame_control',[r for r in data if r['group']!='D'])]:
    positive=[r for r in subset if any(r['y'])]
    order_diagnostics[group]={'frames':len(subset),'argmax_selected_first_fraction':sum(r['selected']==1 for r in subset)/len(subset),
        'first_is_GT_target_among_positive_frames':sum(r['y'][0] for r in positive)/len(positive) if positive else None}
save_json(out/'result.json',{'reference':'相对本地基线','gamma':b['gamma'],'groups':results,
    'candidate_order_diagnostic':order_diagnostics,
    'candidate_ordering':json.loads((out/'coverage.json').read_text()).get('candidate_ordering','released_GT_order'),
    'G_whole_expression_count':0,'G_control_note':'Negative frames of real expressions, not invented globally absent expressions.',
    'primary_joint_decision':'candidate option probability>=same frozen gamma .6; reject if none passes',
    'argmax_is_secondary':True,'multiple_targets_note':'Single-choice simplex with gamma>.5 cannot select multiple targets; report this structural recall ceiling.',
    'numeric_token_note':'For multi-digit options, full answer+newline log likelihood softmax; exact single-next-token softmax shown separately on frames where all options are single tokens.'})
log_run(c,args.run_number,'Set-of-Mark 统计与空帧误报率',[
 'CUDA_VISIBLE_DEVICES=\'\' '+shlex.join([c['reproduction_environment'],'analysis/analyze_som.py','--out',str(args.out),'--run-number',args.run_number])],
 '同一γ=.6为主表；联合argmax另列；D单/多目标分开。无目标候选正类F1无定义时保留null，另报告none检测F1及空帧误报率。')
print(json.dumps(results,ensure_ascii=False,indent=2),flush=True)
