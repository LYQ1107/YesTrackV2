#!/usr/bin/env python3
"""Compare paired context changes with annotation-family dependence acknowledged."""
import json
from pathlib import Path

import numpy as np
from common import config,log_run,save_json

c=config();t=Path(c['task_root']);out=t/'analysis/runs/R23_context'
result=json.loads((out/'result.json').read_text());per=json.loads((out/'per_expression.json').read_text())
if (out/'analysis.json').exists():
    cached=json.loads((out/'analysis.json').read_text())
    if cached.get('analysis_version')==2:
        print('Reuse complete paired-context analysis (unchanged214-expression inputs).',flush=True)
        raise SystemExit(0)
plan=json.loads((t/'analysis/plans/context.json').read_text());labels={r['name']:r for r in json.loads((t/'analysis/labels/expressions.json').read_text())}
grouping=json.loads((t/'analysis/labels/annotation_equivalent_groups.json').read_text())['by_name']
groups={'C':[x['name'] for x in plan['tasks'] if 'C' in labels[x['name']]['labels']],
        'D':[x['name'] for x in plan['tasks'] if 'D' in labels[x['name']]['labels']],
        'A_control':[x['name'] for x in plan['tasks'] if x['group']=='A_control']}
groups['A_control_D_video']=[n for n in groups['A_control'] if n[:4]=='0011']
groups['C_scene']=[n for n in groups['C'] if any(w in labels[n]['sentence'] for w in ('bike','bicycle'))]
groups['C_viewpoint']=[n for n in groups['C'] if n not in set(groups['C_scene'])]


def f1(ns,mode):
    tp=sum(per[n][mode]['tp'] for n in ns);fp=sum(per[n][mode]['fp'] for n in ns);fn=sum(per[n][mode]['fn'] for n in ns)
    return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None


changes={}
for group,ns in groups.items():
    base=f1(ns,'original')
    changes[group]={'expressions':len(ns),'distinct_GT_membership_families':len({grouping[n] for n in ns}),
        'original_F1':base,'F1':{mode:f1(ns,mode) for mode in ('original','expand1p5','expand2p5','full_frame_box')},
        'delta_F1':{mode:f1(ns,mode)-base for mode in ('expand1p5','expand2p5','full_frame_box')}}
contrasts={}
for cat,control in [('C','A_control'),('D','A_control_D_video')]:
    difference=changes[cat]['delta_F1']['full_frame_box']-changes[control]['delta_F1']['full_frame_box']
    contrasts[cat]={'control':control,'full_frame_gain_minus_control_gain':difference,
        'gain_minus_control_by_mode':{m:changes[cat]['delta_F1'][m]-changes[control]['delta_F1'][m]
            for m in ('expand1p5','expand2p5','full_frame_box')},
        'direction':'supports differential context benefit' if difference>0 else 'does not support differential context benefit',
        'scope_note':'No independent-expression significance claim: annotation-equivalent paraphrases are dependent; D has few independent query families.'}
save_json(out/'analysis.json',{'analysis_version':2,'groups':changes,'contrasts':contrasts,'reference':'相对本地基线',
    'limitations':'All variants use320x320; full frame reduces target pixel size. A negative result does not establish that native-resolution context cannot help. Text categories and videos are not randomized.'})
log_run(c,'23-analysis','上下文收益与 A 对照的差值',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/analyze_context.py'],
 'C按全部A对照比较，D使用同视频0011的A对照；分列C_scene/C_viewpoint。依赖于同GT成员序列的回译表达不当作独立统计重复，不虚报显著性。')
print(json.dumps({'groups':changes,'contrasts':contrasts},indent=2),flush=True)
