#!/usr/bin/env python3
"""Numerical delivery checks only; no new variants, tuning, or model inference."""
import json
from pathlib import Path
import subprocess
import numpy as np
from common import config,save_json,summary
from round3 import PLAN,VARIANTS,ROOT,OUT,TAG

c=config()
gate=json.loads((ROOT/'analysis/runs/R49_gate/result.json').read_text())
r49=json.loads((ROOT/'analysis/runs/R49_self_lock/result.json').read_text())
r50=json.loads((OUT/'result.json').read_text())
assert gate['complete'] and gate['maximum_score_difference']==0
assert list(r50['variants'])==VARIANTS
assert r49['events']==605
checks={}
for variant in VARIANTS:
    r=r50['variants'][variant]
    assert r['complete'] and r['referring']['n']==2860484
    assert r['empty_GT_frames']['denominator']==237085
    assert r['F_true_to_false_post0to5']['n']==3529
    path=OUT/variant/'evaluation/tracker'/TAG/'pedestrian_summary.txt'
    official=summary(path)
    assert abs(official['HOTA']-r['metrics']['HOTA'])<=.00050001
    rows=0
    for seq in PLAN['sequences']:
        cache=np.load(OUT/variant/f'scores_{seq}.npz')
        names=cache['names'];score=cache['scores'];rows+=score.size
        assert len(names)==len(set(names)) and all(n.startswith(seq+'__') for n in names)
        if variant.startswith(('V4','V5')):
            posterior=np.load(OUT/variant/f'posterior_{seq}.npz')
            assert np.array_equal(score,(posterior['posterior']>=float(posterior['threshold'])).astype(float))
        if variant=='V5_fixed':
            other=np.load(OUT/'V4_fixed'/f'scores_{seq}.npz')
            assert np.array_equal(score,other['scores'])
    assert rows==2860484
    assert abs(r['gain_HOTA']/32.488-r['recovered_oracle_fraction'])<1e-12
    checks[variant]={'rows':rows,'official_HOTA':official['HOTA'],'posterior_decision_checked':variant.startswith(('V4','V5'))}
for fold in r50['LOSO']['folds']:
    held=fold['held_out_sequence'];train=fold['training_sequences']
    assert held not in train and set(train)==set(PLAN['sequences'])-{held}
    assert fold['families']['V4']['fitted_scalars']==3 and fold['families']['V5']['fitted_scalars']==2
    assert fold['V4_calibration']['BCE_after']<=fold['V4_calibration']['BCE_before']
    assert abs(fold['new_ID_prior']-fold['training_positive_rows']/fold['training_rows'])<1e-15
upstream=ROOT/c['upstream']
diff=subprocess.run(['git','diff','--exit-code'],cwd=upstream,capture_output=True,text=True,check=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
assert commit==c['upstream_commit']
assert (ROOT/'analysis/REPORT_round3.md').exists()
state=json.loads((ROOT/'analysis/round3_state.json').read_text())
assert state['CPU_complete'] and state['R51_GPU_started'] is False
result={'complete':True,'seed':2025,'V0_maximum_difference':0.,'variants':checks,'LOSO_folds':4,
        'max_fitted_scalars':3,'upstream_tracked_diff_empty':True,'upstream_commit':commit,
        'all_registered_variants_retained':True,'R51_GPU_started':False,
        'R51_pending_user_approval':state['R51_awaiting_approval'],
        'known_failure':'First report render had an unescaped literal f-string; fixed template and resumed report only. Experiment results unchanged.'}
save_json(ROOT/'analysis/runs/R50_validation/result.json',result)
print(json.dumps(result,ensure_ascii=False,indent=2))
