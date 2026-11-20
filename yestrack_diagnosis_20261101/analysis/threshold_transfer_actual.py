#!/usr/bin/env python3
"""Apply the source-frozen threshold to existing actual Temp V2 predictions."""
import json
from pathlib import Path

from common import config,log_run,save_json

c=config();t=Path(c['task_root']);b=json.loads((t/'analysis/local_baseline.json').read_text())
source=json.loads((t/'analysis/runs/R35_v1_grid/result.json').read_text())['best']
r14=json.loads((t/'analysis/runs/R14/result.json').read_text())
assert (source['lower'],source['upper'])==(.2,.8),'Changed refinement interval requires new actual-candidate scores.'
key=str(source['gamma']);metrics=r14['sensitivity_appendix_only'][key]
result={'reference':'相对本地基线','source_configuration':{k:source[k] for k in ('gamma','lower','upper')},
    'source_selection_objective':'V1 GT-track micro referring F1; frozen before target full calibration',
    'target_candidates':'actual TempRMOT_star','target_adapter':'published V2',
    'V2_metrics_at_source_threshold':metrics,'V2_local_baseline_gamma':b['gamma'],
    'HOTA_change_vs_local_baseline':metrics['HOTA']-b['metrics']['HOTA'],
    'new_inference':False,'reason_existing_scores_are_exact':'Source-selected refine interval equals original .2/.8; gamma is evaluation-only.',
    'not_used_to_change_baseline':True}
save_json(t/'analysis/runs/R39_threshold_transfer_actual/result.json',result)
log_run(c,39,'V1最优γ迁移到实际Temp候选的V2 HOTA',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/threshold_transfer_actual.py'],
 'CPU读取已有完整评测；源R35选择(.4,.2,.8)，没有根据V2网格选择。区间未变且γ只在评测生效，因此R14的γ=.4结果即精确迁移结果，无需新推理。'
 '以冻结本地γ=.6为对照，所有其他主实验仍γ=.6。此源/目标使用各自发布权重，效应包含权重版本变化。')
print(json.dumps({'source_configuration':result['source_configuration'],'target_HOTA':metrics['HOTA'],
                  'HOTA_change_vs_local_baseline':result['HOTA_change_vs_local_baseline']},ensure_ascii=False,indent=2))
