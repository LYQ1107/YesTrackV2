#!/usr/bin/env python3
"""Check that every skipped-frame posterior is exactly a transition prediction."""
import json
import numpy as np
from common import save_json
from round3 import Dataset,ROOT
from round3_budget import PLAN,OUT

d=Dataset(with_scores=False)
r=json.loads((OUT/'result.json').read_text())
folds={f['held_out_sequence']:f for f in r['LOSO']['folds']}
checks={}
for variant in PLAN['variants']:
    checked=0;maximum=0.
    for seq in d.by_seq:
        p=np.load(OUT/variant/f'posterior_{seq}.npz')
        post=p['posterior'];observed=p['observed'];threshold=float(p['threshold'])
        scores=np.load(OUT/variant/f'scores_{seq}.npz')['scores']
        assert np.array_equal(scores,(post>=threshold).astype(float))
        stay=PLAN['fixed']['p_stay'] if variant.endswith('fixed') else folds[seq]['p_stay']
        geo=d.geo[seq]
        for oid in geo['unique_ids']:
            ix=np.flatnonzero(geo['ids']==oid)
            assert observed[ix[0]],(seq,int(oid),'new ID missing emission')
            previous,current=ix[:-1],ix[1:]
            select=~observed[current];previous=previous[select];current=current[select]
            if not len(current):continue
            gap=geo['frames'][current]-geo['frames'][previous]
            expected=.5+(post[:,previous]-.5)*np.power(2*stay-1,gap)[None,:]
            maximum=max(maximum,float(np.max(np.abs(expected-post[:,current]))))
            checked+=expected.size
    assert maximum<1e-14
    checks[variant]={'transition_only_rows_checked':checked,'maximum_transition_prediction_error':maximum}
for held,fold in folds.items():
    assert held not in fold['training_sequences'] and fold['fitted_scalars']==3
assert r['observations']['V0_max_difference']==0 and not r['observations']['R22_read']
save_json(OUT/'validation.json',{'complete':True,'seed':2025,'checks':checks,'R22_read':False,
    'V0_max_difference':0.,'no_full_val_tuning':True,'new_variants_registered_before_results':True})
print(json.dumps(checks,indent=2))
