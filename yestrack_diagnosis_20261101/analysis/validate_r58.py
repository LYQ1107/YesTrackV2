#!/usr/bin/env python3
"""Necessary R58 sanity checks: positive completeness, sampling and known metric values."""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit

from r58_data import (C, OUT, ATTRIBUTES, align_boxes, original_labels, annotate_expressions,
                      build_labels, write)
from r58_metrics import basic, noise_floor, probability, nll, ClusterSampler


def main():
    samples=json.loads((OUT/'samples.json').read_text())
    plan=json.loads((OUT.parents[1]/'plans/r58.json').read_text())
    assert plan['samples']['images']==len(samples)
    eligible,_=annotate_expressions()
    frames,tracks,alignment=align_boxes(original_labels())
    dataset,exclusions,values,unknown,bad=build_labels(frames,eligible)
    sample_index={(s['sequence'],s['track_id'],s['frame']):s for s in samples}
    positive_checks=0
    for q,gt in eligible:
        attr,value=q['attribute'],q['value']
        if attr=='base_category':continue
        if attr=='upper_colour':value=q['garment']+':'+value
        for frame,ids in gt.items():
            for tid in ids:
                sample=sample_index.get((q['sequence'],tid,frame))
                if sample is None or (q['sequence'],tid,attr) in bad:continue
                labels={(l['attribute'],l['value']):l['y'] for l in sample['labels']}
                assert labels.get((attr,value))==1,('GT positive incorrectly discarded',q['file'],sample['id'],attr,value)
                positive_checks+=1
    for sample in samples:
        assert sample['sequence'] in C['train_sequences']
        expected={(l['attribute'],l['value']):l['y'] for l in dataset[sample['id']]['labels']}
        actual={(l['attribute'],l['value']):l['y'] for l in sample['labels']}
        assert actual==expected
        for lab in sample['labels']:
            if lab['attribute']=='category':continue
            for source in lab['source']:
                expression=json.loads((Path(C['expression_root'])/sample['sequence']/source).read_text())
                assert str(sample['frame']) in expression['label']
                assert int(sample['track_id'] in expression['label'][str(sample['frame'])])==lab['y']
    grouped={}
    for sample in samples:grouped.setdefault(sample['track'],[]).append(sample['frame'])
    for track,fs in grouped.items():
        assert len(fs)<=8
        assert all(b-a>=10 for a,b in zip(sorted(fs),sorted(fs)[1:]))
    # Independent closed-form known values, no dataset/model results are used here.
    p=np.array([.2]*5+[.8]*5);y=np.array([1,0,0,0,0,1,1,1,1,0])
    m=basic(p,y)
    assert abs(m['Brier']-.16)<1e-12
    assert abs(m['Brier_decomposition_width']['calibration_reliability'])<1e-12
    assert abs(m['Brier_decomposition_width']['resolution']-.09)<1e-12
    assert abs(basic(np.array([.1,.4,.35,.8]),np.array([0,0,1,1]))['AUROC']-.75)<1e-12
    assert abs(basic(np.array([.5,.5]),np.array([0,1]))['AUROC']-.5)<1e-12
    n=noise_floor(np.array([0.,1.,0.,1.]),1000)
    assert n['ECE_mass15_noise']['mean']==0 and n['ECE_width15_noise']['mean']==0
    rng=np.random.default_rng(2025);z=rng.normal(size=20000)
    yy=(rng.random(len(z))<expit(z)).astype(int)
    logits=np.column_stack([np.zeros_like(z),2*z]);selected=np.column_stack([np.zeros(len(z),bool),np.ones(len(z),bool)])
    fit=minimize_scalar(lambda logT:nll(probability(logits,selected,np.exp(logT)),yy),
                        bounds=(np.log(.05),np.log(50)),method='bounded')
    assert fit.success and 1.8<np.exp(fit.x)<2.2
    write(OUT/'excluded_tracks.json',[{'sequence':s,'track_id':t,'attribute':a} for s,t,a in sorted(bad)])
    result={'status':'passed','seed':2025,'samples':len(samples),'tracks':len(grouped),
            'visible_GT_positive_source_checks':positive_checks,'missing_GT_positives':0,
            'source_label_frame_and_truth_mismatches':0,'sample_spacing_and_max8':'passed',
            'binary_metric_known_values':'passed','synthetic_temperature_true':2.,
            'synthetic_temperature_fitted':float(np.exp(fit.x)),
            'synthetic_note':'implementation sanity only, not a model or R58 calibration result',
            'model_inference_performed':False}
    write(OUT/'validation_pre_inference.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
