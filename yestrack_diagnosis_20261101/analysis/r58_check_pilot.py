#!/usr/bin/env python3
"""Check the frozen complete pilot cohorts without evaluating calibration quality."""
import json
import math
from pathlib import Path
TASK=Path(__file__).resolve().parents[1];OUT=TASK/'analysis/runs/R58_calibration'
plan=json.loads((TASK/'analysis/plans/r58.json').read_text())
owner=json.loads((OUT/'pilot_owner_result.json').read_text());checked=0
for family in owner['models']:
 if family['status']!='complete':continue
 key=family['checkpoint_repo'].replace('/','__')
 status=json.loads((OUT/'status'/(key+'_pilot.json')).read_text())
 info=next(m for m in plan['models'] if m['repo']==family['model'])
 expected_info=info if family['checkpoint_repo']==family['model'] else next(m for m in info['memory_fallbacks'] if m['repo']==family['checkpoint_repo'])
 assert status['revision']==expected_info['revision']
 for setting in plan['questions']['settings']:
  expected=plan['pilot']['sample_ids'] if setting['id']=='main' else plan['pilot']['sample_ids'][:10]
  keep=set(expected)
  records=[json.loads(l) for l in (OUT/'predictions'/key/(setting['id']+'.jsonl')).read_text().splitlines()]
  records=[r for r in records if r['sample_id'] in keep]
  assert [r['sample_id'] for r in records]==expected
  for r in records:
   assert r['seed']==2025 and set(r['probabilities'])=={q['id'] for q in plan['questions']['bank']}
   for probs in r['probabilities'].values():
    assert all(math.isfinite(v) and 0<=v<=1 for v in probs.values())
    assert abs(sum(probs.values())-1)<1e-5
   checked+=1
state=json.loads((OUT/'protocol_status.json').read_text())
result={'status':'passed','models':sum(r['status']=='complete' for r in owner['models']),
 'requests_checked':checked,'typed_questions':checked*len(plan['questions']['bank']),
 'seed':2025,'formal_inference_started':state.get('full_inference_started',False),
 'budget_gate':json.loads((OUT/'budget.json').read_text())['gate'],
 'definition':'original frozen pilot IDs, including when later full results are appended'}
(OUT/'pilot_integrity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
