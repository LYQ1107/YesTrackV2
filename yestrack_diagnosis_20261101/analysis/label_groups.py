#!/usr/bin/env python3
"""Count annotation-equivalent query families without changing the official weighting."""
import json
from pathlib import Path

import numpy as np
from common import config,log_run,mot,save_json

c=config();t=Path(c['task_root']);rows=json.loads((t/'analysis/labels/expressions.json').read_text())
by_signature={};groups={};by_name={}
for row in rows:
    gt=mot(Path(c['released_v2_gt'])/row['name']/'gt/gt.txt')
    signature=(row['sequence'],gt[:,:2].astype(np.int64).tobytes())
    if signature not in by_signature:by_signature[signature]=f'gtfamily{len(by_signature):03d}'
    group=by_signature[signature];groups.setdefault(group,[]).append(row['name']);by_name[row['name']]=group
counts={cat:len({by_name[r['name']] for r in rows if cat in r['labels']}) for cat in 'ABCDEFGH'}
save_json(t/'analysis/labels/annotation_equivalent_groups.json',{'by_name':by_name,'groups':groups,
    'category_distinct_GT_membership_families':counts,
    'definition':'same sequence and exactly same positive (frame,GT ID) pairs; this is an annotation-equivalence count, not a claim of textual synonymy',
    'official_weighting_unchanged':True})
log_run(c,'18-groups','表达式依赖性核对',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/build_labels.py',
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/freeze_semantic_review.py',
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/build_labels.py --review analysis/labels/llm_review.json',
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/label_groups.py',
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/plan_probes.py',
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' analysis/plan_som_and_births.py'],
 '记录完整规则→LLM冻结审核→标注F/G→抽100条→冻结探针采样的命令链。相同GT成员时序的表达式属于同一标注等价组；只用于界定证据范围，不合并官方评测条目。')
print(json.dumps({'annotation_equivalent_families':len(groups),'by_category':counts},indent=2))
