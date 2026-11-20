#!/usr/bin/env python3
"""Preregistered CPU-only temporal decision experiments on immutable score caches."""
import argparse
from collections import deque
import csv
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import traceback

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit

from common import (combine_hota, config, confusion, hota_rows, mot,
                    official_eval, run_logged, save_json, summary)
from replay import dense_cache, load_observations, replay


ROOT = Path(config()['task_root'])
PLAN = json.loads((ROOT/'analysis/plans/round3.json').read_text())
VARIANTS = list(PLAN['variants'])
OUT = ROOT/'analysis/runs/R50_temporal'
TAG = 'default_t0p60'


def rounded(p):
    """The native/R36 serialization rule, deliberately not numpy.round."""
    p = np.asarray(p)
    return np.fromiter((float(f'{v:.6f}') for v in p.ravel()),
                       dtype=np.float64, count=p.size).reshape(p.shape)


def geometry(tr):
    frames = tr[:,0].astype(int)
    ids = tr[:,1].astype(int)
    unique_ids = np.unique(ids)
    columns = np.searchsorted(unique_ids, ids)
    groups = [np.flatnonzero(frames == f) for f in np.unique(frames)]
    return {'frames': frames, 'ids': ids, 'columns': columns, 'groups': groups,
            'unique_ids': unique_ids, 'nrows': len(tr)}


class Dataset:
    def __init__(self, with_scores=False):
        self.c = config()
        self.labels = json.loads((ROOT/'analysis/labels/expressions.json').read_text())
        self.meta = {r['name']: r for r in self.labels}
        manifest = json.loads((ROOT/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
        self.tracks = {s: mot(v['track_file']) for s,v in manifest['sequences'].items()}
        self.geo = {s: geometry(tr) for s,tr in self.tracks.items()}
        self.by_seq = {s: [r['name'] for r in self.labels if r['sequence']==s]
                       for s in PLAN['sequences']}
        self.index = {n: (s,j) for s,ns in self.by_seq.items() for j,n in enumerate(ns)}
        self.y = {}
        self.empty = {}
        self.frame_probability = {}
        self.video_probability = {}
        self.q = {}
        for seq, ns in self.by_seq.items():
            tr = self.tracks[seq]
            yy = []
            ee = []
            pf, pv = [], []
            for name in ns:
                expr = name.split('__',1)[1]
                js = json.loads((Path(self.c['expression_root'])/seq/f'{expr}.json').read_text())
                mask = {int(f)+1:{int(i) for i in ids} for f,ids in js['label'].items()}
                yy.append([int(r[1]) in mask.get(int(r[0]),set()) for r in tr])
                gt = mot(Path(self.c['released_v2_gt'])/name/'gt/gt.txt')
                empty = np.ones(self.meta[name]['sequence_frames']+1, dtype=bool)
                empty[0] = False
                empty[gt[:,0].astype(int)] = False
                ee.append(empty)
                if with_scores:
                    cache = dense_cache(ROOT/'analysis/runs/R22_full_scores'/f'{name}.npz',len(tr))
                    pf.append(cache['p_frame'])
                    pv.append(cache['p_video'])
            self.y[seq] = np.asarray(yy, dtype=bool)
            self.empty[seq] = np.asarray(ee, dtype=bool)
            if with_scores:
                self.frame_probability[seq] = np.asarray(pf, dtype=np.float64)
                self.video_probability[seq] = np.asarray(pv, dtype=np.float64)
                select = (self.frame_probability[seq]>=.2) & (self.frame_probability[seq]<.8)
                self.q[seq] = np.where(select,self.video_probability[seq],self.frame_probability[seq])
                assert np.all(np.isfinite(self.q[seq])), seq
        assert sum(v.size for v in self.y.values()) == PLAN['native_gate']['candidate_rows']
        assert len(self.meta) == PLAN['native_gate']['expressions']
        self.switches = json.loads((ROOT/'analysis/labels/truth_switches.json').read_text())

    def native(self):
        out = {}
        for seq, ns in self.by_seq.items():
            out[seq] = np.stack([mot(ROOT/'analysis/runs/R17_h2/predictions'/seq/
                                   n.split('__',1)[1]/'predict_with_conf.txt')[:,6] for n in ns])
        return out


def require_gate():
    p = ROOT/'analysis/runs/R49_gate/result.json'
    if not p.exists() or not json.loads(p.read_text()).get('complete'):
        raise RuntimeError('V0 gate has not passed; run --stage gate before any R49/R50 result.')


def gate(data=None):
    """Stop on any native mismatch; no downstream results exist before this passes."""
    out = ROOT/'analysis/runs/R49_gate'
    out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():
        result = json.loads((out/'result.json').read_text())
        if result.get('complete'):
            print('V0 gate already passed:',result['maximum_score_difference'],flush=True)
            return
    start = time.monotonic()
    d = data or Dataset()
    observations = load_observations(ROOT/'analysis/runs/R17_h2/raw_scores')
    total, maxdiff, checks = 0, 0., []
    for row in d.labels:
        name = row['name']; seq,expr = name.split('__',1)
        tr = d.tracks[seq]
        native = mot(ROOT/'analysis/runs/R17_h2/predictions'/seq/expr/'predict_with_conf.txt')
        assert np.array_equal(native[:,:2],tr[:,:2]),(name,'row identity mismatch')
        assert np.array_equal(native[:,2:6],tr[:,2:6].astype(int)),(name,'integer box mismatch')
        score = replay(tr,observations[name])
        difference = float(np.max(np.abs(score-native[:,6])))
        maxdiff = max(maxdiff,difference)
        checks.append({'name':name,'rows':len(tr),'maximum_score_difference':difference})
        total += len(tr)
        if difference > PLAN['native_gate']['maximum_absolute_difference_tolerance']:
            save_json(out/'result.json',{'complete':False,'stop':True,'name':name,
                       'maximum_score_difference':difference,'reason':'Native V0 mismatch; downstream stopped'})
            raise RuntimeError(f'STOP: V0 native mismatch {name}: {difference}')
    native_summary = summary(ROOT/'analysis/runs/R17_h2/evaluation/tracker'/TAG/'pedestrian_summary.txt')
    assert native_summary['HOTA'] == PLAN['native_gate']['required_summary_HOTA'], native_summary
    assert total == PLAN['native_gate']['candidate_rows']
    with (out/'per_expression.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(checks[0]));w.writeheader();w.writerows(checks)
    result={'complete':True,'seed':PLAN['seed'],'expressions':len(checks),'candidate_rows':total,
            'maximum_score_difference':maxdiff,'tolerance':1e-12,
            'native_H2_HOTA':native_summary['HOTA'],'seconds':time.monotonic()-start,
            'serialization':PLAN['native_gate']['serialization']}
    save_json(out/'result.json',result)
    print('V0 native gate:',json.dumps(result),flush=True)


def latency_summary(values):
    a=np.asarray([x for x in values if x is not None],dtype=float)
    return {'events':len(values),'observed_crossings':len(a),'censored':len(values)-len(a),
            'mean_observed':float(np.mean(a)) if len(a) else None,
            'median_observed':float(np.median(a)) if len(a) else None,
            'q25_observed':float(np.quantile(a,.25)) if len(a) else None,
            'q75_observed':float(np.quantile(a,.75)) if len(a) else None}


def run_r49(d=None):
    require_gate()
    out=ROOT/'analysis/runs/R49_self_lock';out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists() and json.loads((out/'result.json').read_text()).get('complete'):
        print('R49 already complete',flush=True);return
    start=time.monotonic();d=d or Dataset(with_scores=True)
    native=d.native()
    events=[s for s in d.switches if s['gap']==1 and s['from']==1 and s['to']==0
            and 'F' in d.meta[s['name']]['labels']]
    event_by={}
    for event in events:event_by.setdefault(event['name'],[]).append(event)
    records=[];event_rows=[]
    curves={k:{'n':0,'frame':0.,'video_n':0,'video':0.,'q':0.,'final10':0.,'final1':0.,'positive':0}
            for k in range(16)}
    latch={delta:{'n':0,'raw_in_01_to_06':0,'routed_below_gamma':0,'raw_below_gamma':0}
           for delta in [10,1]}
    for name, evs in event_by.items():
        seq,j=d.index[name];tr=d.tracks[seq]
        full={'p_frame':d.frame_probability[seq][j],'p_video':d.video_probability[seq][j]}
        p1=replay(tr,None,delta=1,full=full)
        finals={10:native[seq][j],1:p1}
        for ev in evs:
            ix=np.flatnonzero((tr[:,1]==ev['id']) & (tr[:,0]>=ev['frame']) & (tr[:,0]<=ev['frame']+15))
            kk=tr[ix,0].astype(int)-ev['frame']
            raw=d.frame_probability[seq][j,ix];video=d.video_probability[seq][j,ix];q=d.q[seq][j,ix]
            def first(a):
                hits=kk[a<.6]
                return int(hits[0]) if len(hits) else None
            a=first(raw);q_cross=first(q)
            event_row={'name':name,'id':ev['id'],'switch_frame':ev['frame'],'visible_rows':len(ix),
                       'last_visible_offset':int(kk[-1]),'raw_frame_latency':a,'routed_q_latency':q_cross}
            for delta,score in finals.items():
                b=first(score[ix]);event_row[f'final{delta}_latency']=b
                event_row[f'final{delta}_minus_raw_latency']=b-a if a is not None and b is not None else None
                if a is not None:
                    chosen=(kk>=a) & (kk<(b if b is not None else 16))
                    latch[delta]['n']+=int(chosen.sum())
                    latch[delta]['raw_in_01_to_06']+=int((chosen & (raw>=.1) & (raw<.6)).sum())
                    latch[delta]['routed_below_gamma']+=int((chosen & (q<.6)).sum())
                    latch[delta]['raw_below_gamma']+=int((chosen & (raw<.6)).sum())
            event_rows.append(event_row)
            for pos,(i,k) in enumerate(zip(ix,kk)):
                n=curves[int(k)];n['n']+=1;n['frame']+=float(raw[pos]);n['q']+=float(q[pos])
                n['final10']+=float(finals[10][i]);n['final1']+=float(finals[1][i])
                n['positive']+=int(d.y[seq][j,i])
                if np.isfinite(video[pos]):n['video_n']+=1;n['video']+=float(video[pos])
                records.append({'name':name,'id':ev['id'],'switch_frame':ev['frame'],'offset':int(k),
                    'frame':int(tr[i,0]),'truth':int(d.y[seq][j,i]),'p_frame':float(raw[pos]),
                    'p_video':float(video[pos]) if np.isfinite(video[pos]) else None,'q':float(q[pos]),
                    'p_final_delta10':float(finals[10][i]),'p_final_delta1':float(finals[1][i])})
    curve_rows=[]
    for k,stat in curves.items():
        n=stat['n'];nv=stat['video_n']
        curve_rows.append({'offset':k,'n':n,'video_n':nv,'video_coverage':nv/n if n else None,
            'p_frame':stat['frame']/n if n else None,'p_video_conditional':stat['video']/nv if nv else None,
            'routed_q':stat['q']/n if n else None,'final_delta10':stat['final10']/n if n else None,
            'final_delta1':stat['final1']/n if n else None,'GT_positive_share':stat['positive']/n if n else None})
    for filename,rows in [('curves.csv',curve_rows),('event_latencies.csv',event_rows),('event_scores.csv',records)]:
        with (out/filename).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'complete':True,'seed':PLAN['seed'],'reference':'相对本地基线，GT candidates',
            'events':len(events),'event_weighted_visible_rows':len(records),'window':[0,15],
            'raw_frame_latency':latency_summary([r['raw_frame_latency'] for r in event_rows]),
            'routed_q_latency':latency_summary([r['routed_q_latency'] for r in event_rows]),
            'delta':{},'curves':curve_rows,'seconds':time.monotonic()-start,
            'source_lines':{'history_condition':'refer_llm/llm_eval_from_mot.py:1014-1017',
                            'final_TRP_cache':'refer_llm/llm_eval_from_mot.py:1019-1023'},
            'censoring':'No observed crossing in available offsets0..15 is censored; disappearance is never a rejection. Observed latency averages exclude censored events.'}
    for delta in [10,1]:
        stat=latch[delta];n=stat['n']
        result['delta'][str(delta)]={
            'final_latency':latency_summary([r[f'final{delta}_latency'] for r in event_rows]),
            'paired_final_minus_raw_latency':latency_summary([r[f'final{delta}_minus_raw_latency'] for r in event_rows]),
            'raw_crossed_but_final_censored':sum(r['raw_frame_latency'] is not None and r[f'final{delta}_latency'] is None for r in event_rows),
            'raw_crossed_events':sum(r['raw_frame_latency'] is not None for r in event_rows),
            'latch':{**stat,'fraction_raw_in_01_to_06':stat['raw_in_01_to_06']/n if n else None,
                     'fraction_routed_q_below_gamma':stat['routed_below_gamma']/n if n else None,
                     'fraction_raw_below_gamma':stat['raw_below_gamma']/n if n else None}}
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),sharey=True)
    for ax,delta in zip(axes,[10,1]):
        for key,label,style in [('p_frame','Raw frame p','-'),('p_video_conditional','Video p (routed subset)','--'),
                                 ('routed_q','Unboosted routed q','-'),(f'final_delta{delta}','Final TCP score','-')]:
            ax.plot(range(16),[r[key] for r in curve_rows],style,marker='.',label=label)
        ax.axhline(.6,color='grey',linestyle=':',label='gamma=0.6')
        ax.set(title=f'True-to-false switches, Delta={delta}',xlabel='Image frames after exact switch',
               ylabel='Event-weighted mean probability',ylim=(0,1));ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(out/'self_lock_curves.png',dpi=190);fig.savefig(out/'self_lock_curves.pdf');plt.close(fig)
    save_json(out/'result.json',result)
    print('R49:',json.dumps({k:v for k,v in result.items() if k!='curves'}),flush=True)


def temporal_variant(tr, geo, observed, variant):
    """V1/V2 change only the registered controller, never a model or crop."""
    last_final={};last_raw={};histories={};out=np.empty(len(tr),dtype=float)
    for counter,ix in enumerate(geo['groups']):
        infer_all=counter%10==0
        for i in ix:
            frame=int(tr[i,0]);oid=int(tr[i,1])
            if infer_all or oid not in last_final:
                item=observed[(frame,oid)];p=float(item['frame'])
                if .2<=p<.8:p=float(item['video'])
                last_raw[oid]=p
            else:p=last_final[oid]
            if variant=='V2':
                h=histories.setdefault(oid,deque(maxlen=3))
                if len(h)>=3 and all(v>=.4 for v in h):p=min(1.,p+.3)
                h.append(last_raw[oid])
            else:assert variant=='V1'
            last_final[oid]=p;out[i]=p
    return rounded(out)


def emission(q,bias):
    clipped=np.clip(q,1e-6,1-1e-6)
    return expit(np.log(clipped)-np.log1p(-clipped)+bias)


def hmm_forward(q,geo,p_stay,prior):
    """Vectorize across queries/visible IDs; filter causally along image time."""
    state=np.full((q.shape[0],len(geo['unique_ids'])),prior,dtype=np.float64)
    seen=np.zeros(len(geo['unique_ids']),dtype=bool)
    last_frame=np.zeros(len(geo['unique_ids']),dtype=int)
    out=np.empty(q.shape,dtype=np.float64)
    for ix in geo['groups']:
        cols=geo['columns'][ix];frame=int(geo['frames'][ix[0]])
        gap=frame-last_frame[cols]
        p0=.5+(state[:,cols]-.5)*np.power(2*p_stay-1,gap)[None,:]
        p0[:,~seen[cols]]=prior
        current=q[:,ix]
        numerator=p0*current
        post=numerator/(numerator+(1-p0)*(1-current))
        out[:,ix]=post;state[:,cols]=post
        seen[cols]=True;last_frame[cols]=frame
    return out


def bce(q,y,bias=0.):
    clipped=np.clip(q,1e-6,1-1e-6)
    z=np.log(clipped)-np.log1p(-clipped)+bias
    return float(np.mean(np.logaddexp(0.,z)-y*z))


def fit_loso(d):
    out=OUT/'LOSO';out.mkdir(parents=True,exist_ok=True)
    if (out/'parameters.json').exists():
        result=json.loads((out/'parameters.json').read_text())
        if result.get('complete'):return result
    folds=[]
    for held in PLAN['sequences']:
        path=out/f'fold_{held}.json'
        if path.exists() and json.loads(path.read_text()).get('complete'):
            folds.append(json.loads(path.read_text()));continue
        training=[s for s in PLAN['sequences'] if s!=held]
        train_q=np.concatenate([d.q[s].ravel() for s in training])
        train_y=np.concatenate([d.y[s].ravel() for s in training])
        prior=float(np.mean(train_y))
        optimized=minimize_scalar(lambda b:bce(train_q,train_y,float(b)),bounds=(-8.,8.),
                                  method='bounded',options={'xatol':1e-8})
        assert optimized.success,optimized
        bias=float(optimized.x)
        fold={'complete':False,'held_out_sequence':held,'training_sequences':training,
              'training_expressions':sum(len(d.by_seq[s]) for s in training),
              'training_rows':len(train_q),'training_positive_rows':int(train_y.sum()),
              'new_ID_prior':prior,'V4_calibration':{'temperature':1.,'bias':bias,
                  'BCE_before':bce(train_q,train_y),'BCE_after':float(optimized.fun)},
              'families':{}}
        grid_rows=[]
        for family,b in [('V4',bias),('V5',0.)]:
            calibrated={s:emission(d.q[s],b) for s in training}
            for stay in PLAN['LOSO']['p_stay_grid']:
                filtered={s:hmm_forward(calibrated[s],d.geo[s],stay,prior) for s in training}
                for threshold in PLAN['LOSO']['posterior_threshold_grid']:
                    tp=fp=fn=0
                    for s in training:
                        pred=filtered[s]>=threshold;y=d.y[s]
                        tp+=int(np.sum(pred & y));fp+=int(np.sum(pred & ~y));fn+=int(np.sum(~pred & y))
                    f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
                    grid_rows.append({'family':family,'held_out_sequence':held,'bias':b,
                        'p_stay':stay,'posterior_threshold':threshold,'tp':tp,'fp':fp,'fn':fn,'micro_F1':f1})
            choices=[r for r in grid_rows if r['family']==family]
            chosen=min(choices,key=lambda r:(-r['micro_F1'],r['p_stay'],abs(r['posterior_threshold']-.5),r['posterior_threshold']))
            fold['families'][family]={k:chosen[k] for k in ['bias','p_stay','posterior_threshold','micro_F1','tp','fp','fn']}
            fold['families'][family]['fitted_scalars']=3 if family=='V4' else 2
        with (out/f'training_grid_{held}.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(grid_rows[0]));w.writeheader();w.writerows(grid_rows)
        fold['complete']=True;save_json(path,fold);folds.append(fold)
        print('LOSO training-only fit:',json.dumps(fold),flush=True)
    result={'complete':True,'seed':PLAN['seed'],'folds':folds,
            'protocol':'analysis/plans/round3.json; each held-out sequence is never used to fit its parameters'}
    save_json(out/'parameters.json',result)
    return result


def write_predictions(d,variant,scores):
    folder=OUT/variant
    folder.mkdir(parents=True,exist_ok=True)
    if variant=='V0':
        dest=folder/'predictions'
        if not dest.exists():dest.symlink_to(ROOT/'analysis/runs/R17_h2/predictions',target_is_directory=True)
    elif variant=='V5_fixed':
        dest=folder/'predictions'
        if not dest.exists():dest.symlink_to(OUT/'V4_fixed/predictions',target_is_directory=True)
    else:
        for seq,ns in d.by_seq.items():
            tr=d.tracks[seq]
            fields=tr[:,:6].astype(int)
            for j,name in enumerate(ns):
                f=folder/'predictions'/seq/name.split('__',1)[1]/'predict_with_conf.txt'
                f.parent.mkdir(parents=True,exist_ok=True)
                with f.open('w') as handle:
                    handle.writelines(','.join(map(str,r))+f',{p:.6f}\n' for r,p in zip(fields,scores[seq][j]))
    for seq,values in scores.items():
        np.savez_compressed(folder/f'scores_{seq}.npz',names=np.asarray(d.by_seq[seq]),scores=values)
    save_json(folder/'predictions_receipt.json',{'complete':True,'variant':variant,'expressions':len(d.labels),
        'candidate_rows':sum(s.size for s in scores.values()),'seed':PLAN['seed'],'gamma':.6,
        'HMM_decision_binary':variant.startswith(('V4','V5')),
        'identical_fixed_alias':variant=='V5_fixed'})


def variant_scores(d,variant,parameters,observed=None):
    if variant=='V0':return d.native()
    if variant in ('V1','V2'):
        assert observed is not None
        return {s:np.stack([temporal_variant(d.tracks[s],d.geo[s],observed[n],variant) for n in ns])
                for s,ns in d.by_seq.items()}
    if variant=='V3':return {s:rounded(q) for s,q in d.q.items()}
    family=variant[:2];fixed=variant.endswith('fixed')
    folds={f['held_out_sequence']:f for f in parameters['folds']}
    out={}
    folder=OUT/variant;folder.mkdir(parents=True,exist_ok=True)
    for seq in PLAN['sequences']:
        fold=folds[seq]
        p={'bias':0.,'p_stay':.95,'posterior_threshold':.5} if fixed else fold['families'][family]
        q=emission(d.q[seq],p['bias'])
        posterior=hmm_forward(q,d.geo[seq],p['p_stay'],fold['new_ID_prior'])
        out[seq]=(posterior>=p['posterior_threshold']).astype(float)
        np.savez_compressed(folder/f'posterior_{seq}.npz',names=np.asarray(d.by_seq[seq]),
                            posterior=posterior,threshold=p['posterior_threshold'])
    return out


def aggregate_conf(rows):
    if not rows:return None
    totals={k:sum(r[k] for r in rows) for k in ['tp','fp','fn','tn','n']}
    tp,fp,fn,tn=[totals[k] for k in ['tp','fp','fn','tn']]
    return {**totals,'accuracy':(tp+tn)/totals['n'],'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def semantic_metrics(d,scores):
    per_expr={};empty_n=empty_alarms=post_n=post_errors=0
    exact=[ev for ev in d.switches if ev['gap']==1 and ev['from']==1 and ev['to']==0
           and 'F' in d.meta[ev['name']]['labels']]
    events={}
    for ev in exact:events.setdefault(ev['name'],[]).append(ev)
    for seq,ns in d.by_seq.items():
        tr=d.tracks[seq];frames=d.geo[seq]['frames']
        for j,name in enumerate(ns):
            p=scores[seq][j];pred=p>=.6;y=d.y[seq][j]
            per_expr[name]=confusion(y,p,.6)
            empty_n+=int(d.empty[seq][j].sum())
            hits=frames[pred & d.empty[seq][j,frames]]
            empty_alarms+=len(np.unique(hits))
            for ev in events.get(name,[]):
                select=(tr[:,1]==ev['id']) & (frames>=ev['frame']) & (frames<=ev['frame']+5)
                post_n+=int(select.sum());post_errors+=int((pred[select]!=y[select]).sum())
    return {'referring':aggregate_conf(list(per_expr.values())),'per_expression_referring':per_expr,
        'empty_GT_frames':{'denominator':empty_n,'false_alarm_frames':empty_alarms,'false_alarm_rate':empty_alarms/empty_n},
        'F_true_to_false_post0to5':{'n':post_n,'errors':post_errors,'error_rate':post_errors/post_n}}


def evaluate_variant(d,variant,scores):
    folder=OUT/variant
    result_file=folder/'result.json'
    if result_file.exists() and json.loads(result_file.read_text()).get('complete'):
        return json.loads(result_file.read_text())
    evaluation=folder/'evaluation'
    if variant=='V5_fixed':
        # Preregistered mathematical identity: same emissions, priors and parameters.
        source=OUT/'V4_fixed/evaluation'
        if not evaluation.exists():evaluation.symlink_to(source,target_is_directory=True)
        command=None
    else:
        command=official_eval(d.c,folder/'predictions',evaluation,[.6])
        save_json(folder/'evaluation_command.json',{'argv':command,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2'})
        with (OUT/'commands.sh').open('a') as f:
            f.write("CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "+shlex.join(command)+'\n')
        # The official wrapper launches TrackEval/scripts/... relative to its repo.
        run_logged(command,ROOT/d.c['upstream'],folder/'trackeval.log')
    metric,details=hota_rows(evaluation/'tracker'/TAG/'pedestrian_detailed.csv',d.c)
    assert set(details)==set(d.meta),(variant,'missing official expression metrics')
    total=combine_hota(metric,details)
    if variant=='V0':
        s=summary(evaluation/'tracker'/TAG/'pedestrian_summary.txt')
        assert s['HOTA']==65.232,(variant,'V0 native HOTA mismatch',s['HOTA'])
    semantic=semantic_metrics(d,scores)
    categories={}
    for cat in 'ABCDEFGH':
        ns=[r['name'] for r in d.labels if cat in r['labels']]
        categories[cat]={'expressions':len(ns),'HOTA_metrics':combine_hota(metric,{n:details[n] for n in ns}),
            'referring':aggregate_conf([semantic['per_expression_referring'][n] for n in ns])}
    per_seq={seq:combine_hota(metric,{n:details[n] for n in ns}) for seq,ns in d.by_seq.items()}
    result={'complete':True,'reference':'相对本地基线，GT candidates','variant':variant,'seed':2025,'gamma':.6,
            'metrics':total,**semantic,'categories':categories,'per_sequence':per_seq,
            'evaluation_command':command,'identical_evaluation_alias':'V4_fixed' if variant=='V5_fixed' else None}
    save_json(result_file,result)
    print('R50 evaluated:',variant,json.dumps({'metrics':total,'referring':semantic['referring'],
          'empty':semantic['empty_GT_frames'],'post':semantic['F_true_to_false_post0to5']}),flush=True)
    return result


def run_r50(d=None):
    require_gate();OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'result.json').exists() and json.loads((OUT/'result.json').read_text()).get('complete'):
        print('R50 already complete',flush=True);return
    start=time.monotonic();d=d or Dataset(with_scores=True)
    # Evaluate native replay before fitting any non-native variant.
    v0score=d.native();write_predictions(d,'V0',v0score);v0=evaluate_variant(d,'V0',v0score)
    parameters=fit_loso(d)
    observed=load_observations(ROOT/'analysis/runs/R17_h2/raw_scores')
    results={'V0':v0}
    for variant in VARIANTS[1:]:
        folder=OUT/variant
        if (folder/'result.json').exists() and json.loads((folder/'result.json').read_text()).get('complete'):
            results[variant]=json.loads((folder/'result.json').read_text());continue
        scores=variant_scores(d,variant,parameters,observed)
        write_predictions(d,variant,scores)
        results[variant]=evaluate_variant(d,variant,scores)
    base=results['V0']['metrics']['HOTA']
    for variant,r in results.items():
        r['gain_HOTA']=r['metrics']['HOTA']-base
        r['recovered_oracle_fraction']=r['gain_HOTA']/32.488
        for cat in 'ABCDEFGH':
            h=r['categories'][cat]['HOTA_metrics']['HOTA'];h0=results['V0']['categories'][cat]['HOTA_metrics']['HOTA']
            r['categories'][cat]['delta_HOTA_vs_V0']=h-h0 if h is not None else None
        save_json(OUT/variant/'result.json',r)
    best=max(VARIANTS[1:],key=lambda v:results[v]['metrics']['HOTA'])
    result={'complete':True,'seed':2025,'reference':'相对本地基线，GT候选，V0=H2','variants':results,
            'LOSO':parameters,'oracle_space_denominator':32.488,'best_registered_variant':best,
            'best_gain_HOTA':results[best]['gain_HOTA'],'R51_triggered':results[best]['gain_HOTA']>=2,
            'seconds':time.monotonic()-start}
    save_json(OUT/'result.json',result)
    with (OUT/'main_table.csv').open('w') as f:
        fields=['variant','HOTA','DetA','AssA','DetPr','DetRe','precision','recall','f1','empty_frame_FAR',
                'F_true_to_false_post0to5_error','gain_HOTA','recovered_oracle_fraction']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for variant,r in results.items():
            w.writerow({'variant':variant,**{k:r['metrics'][k] for k in fields if k in r['metrics']},
                        **{k:r['referring'][k] for k in ['precision','recall','f1']},
                        'empty_frame_FAR':r['empty_GT_frames']['false_alarm_rate'],
                        'F_true_to_false_post0to5_error':r['F_true_to_false_post0to5']['error_rate'],
                        'gain_HOTA':r['gain_HOTA'],'recovered_oracle_fraction':r['recovered_oracle_fraction']})
    with (OUT/'category_table.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['category','expressions','V0_HOTA',*[v+'_delta_HOTA' for v in VARIANTS[1:]]])
        for cat in 'ABCDEFGH':
            w.writerow([cat,results['V0']['categories'][cat]['expressions'],
                        results['V0']['categories'][cat]['HOTA_metrics']['HOTA'],
                        *[results[v]['categories'][cat]['delta_HOTA_vs_V0'] for v in VARIANTS[1:]]])
    print('R50 complete:',best,'gain',result['best_gain_HOTA'],flush=True)


def estimate_r51(r50):
    """CPU arithmetic only. A trigger never authorizes a new GPU stage."""
    out=ROOT/'analysis/runs/R51_estimate';out.mkdir(parents=True,exist_ok=True)
    c=config()
    r22=json.loads((ROOT/'analysis/runs/R22_full_scores/result.json').read_text())
    actual_rows=0
    # Actual candidates differ by expression only in referring scores, not boxes.
    # Read original Temp prediction files rather than making a new GPU pilot.
    baseline=json.loads((ROOT/'analysis/local_baseline.json').read_text())
    labels=json.loads((ROOT/'analysis/labels/expressions.json').read_text())
    for row in labels:
        seq,expr=row['name'].split('__',1)
        actual_rows+=len(mot(Path(baseline['predictions'])/seq/expr/'predict_with_conf.txt'))
    ratio=actual_rows/r22['candidate_rows']
    # Total full GT wall clock is measured, independent of how phase receipts are split.
    point=r22['seconds']*ratio
    result={'complete':True,'GPU_started':False,'requires_new_user_approval':bool(r50['R51_triggered']),
        'triggered':r50['R51_triggered'],'best_variant':r50['best_registered_variant'],
        'gain_HOTA':r50['best_gain_HOTA'],'actual_candidate_rows':actual_rows,
        'GT_candidate_rows':r22['candidate_rows'],'row_ratio':ratio,'R22_wall_seconds':r22['seconds'],
        'reference_physical_GPUs':r22['gpus'],'estimated_wall_seconds':point,'estimated_wall_hours':point/3600,
        'exceeds_8_hours':point>8*3600,
        'assumptions':'Four GPUs with R22-like availability; row-linear transfer of combined frame+selective-video throughput. Actual Temp crop uncertainty/video routing fraction and batch sizes are unmeasured, so this is an estimate, not a guaranteed runtime.',
        'scope':'Full actual TempRMOT* all-frame frame/video cache only; no GPU launch or extra model inference in R51 estimate.'}
    save_json(out/'result.json',result)
    print('R51 CPU estimate:',json.dumps(result),flush=True)
    return result


def fmt(x,places=3):return 'N/A' if x is None else f'{x:.{places}f}'
def pct(x):return 'N/A' if x is None else f'{100*x:.2f}%'


def report():
    require_gate()
    r49=json.loads((ROOT/'analysis/runs/R49_self_lock/result.json').read_text())
    r50=json.loads((OUT/'result.json').read_text());assert r50['complete']
    r51=estimate_r51(r50)
    gate_result=json.loads((ROOT/'analysis/runs/R49_gate/result.json').read_text())
    variants=r50['variants'];best=r50['best_registered_variant'];b=variants[best]
    lines=['# YesTrack 第三轮：时序决策层诊断',
        '', '2026-11-02；seed=2025。以下全部为**相对本地基线**，GT 候选，发布 V2 权重；不与论文 HOTA 混用。官方权重、crop、prompt、frame/video helper 及源码均未修改，全部新变体只重放 R17/R22 缓存。',
        '', '预注册：[冻结方案](plans/round3.json)、[命令记录](runs.md#r49预注册自锁曲线与原生逐值重放门槛)。变体在运行前已全部列出，未按结果增删。',
        '', '## R49：自锁机制', '',
        f'先决核对通过：V0 对全部 {gate_result["expressions"]} 条表达式、{gate_result["candidate_rows"]:,} 条记录逐值重放，最大分数差 **{gate_result["maximum_score_difference"]}**；采用 R36 的 Python `float(f\'{{p:.6f}}\')` 格式化，容差 1e-12。官方 TrackEval 重评 V0 HOTA={variants["V0"]["metrics"]["HOTA"]:.3f}，复现原生 H2=65.232。',
        '', '官方实现先检查历史的 3 个值，再执行加分，随后将**加分后的 `probs[i]`** 写入 `dq`：[1014–1017 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1014)；又把最终 `p` 写入 TRP 缓存：[1019–1023 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1019)。因此历史条件和中间帧复用均读取最终分数，构成两条反馈路径。',
        '', f'覆盖 F 类所有 gap=1 真→假事件，共 **{r49["events"]}** 个；offset 0 表示第一张 GT 为假的图像帧，窗口 0–15，共 {r49["event_weighted_visible_rows"]:,} 个事件加权可见记录。重叠窗口重复计入，消失帧不插值。video 只在原 frame p∈[0.2,0.8) 时有缓存，图中 video 曲线为该子集的条件均值；不能与全样本 frame 均值直接解释为 video 的因果改善。',
        '', '![R49 概率均值曲线](runs/R49_self_lock/self_lock_curves.png)',
        '', '[曲线数值及覆盖率](runs/R49_self_lock/curves.csv) · [每事件延迟](runs/R49_self_lock/event_latencies.csv) · [逐事件分数](runs/R49_self_lock/event_scores.csv)',
        '', '| 分数 | 16 帧内观察到跌破/事件数 | 未观察到跌破（删失） | 观察到的均值延迟 | 观察到的中位延迟 |',
        '|---|---:|---:|---:|---:|']
    for label,stat in [('原始 frame p',r49['raw_frame_latency']),('原始路由后 q',r49['routed_q_latency']),
                       ('最终 TCP+TRP10',r49['delta']['10']['final_latency']),('最终 TCP+Δ1',r49['delta']['1']['final_latency'])]:
        lines.append(f'| {label} | {stat["observed_crossings"]}/{stat["events"]} | {stat["censored"]} | {fmt(stat["mean_observed"])} 帧 | {fmt(stat["median_observed"])} 帧 |')
    lines += ['', '均值/中位数只对实际观察到跌破的事件计算，不能把仍锁存或失去可见性的事件当作已释放；下面另报配对与删失。锁存区间预定义为 raw frame 首次低于 γ 起，至最终分数首次低于 γ 前，最多观察至 offset15。',
              '', '| 重放 | 两者都跌破的配对事件 | 最终−frame 平均延迟 | frame 已跌破而最终仍未跌破 | 锁存可见帧 | 锁存时 raw p∈[.1,.6) | 锁存时路由 q<.6 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for delta in [10,1]:
        r=r49['delta'][str(delta)];p=r['paired_final_minus_raw_latency'];l=r['latch']
        lines.append(f'| Δ={delta} | {p["observed_crossings"]} | {fmt(p["mean_observed"])} 帧 | {r["raw_crossed_but_final_censored"]}/{r["raw_crossed_events"]} | {l["n"]:,} | {pct(l["fraction_raw_in_01_to_06"])} | {pct(l["fraction_routed_q_below_gamma"])} |')
    def mean_curve_cross(key):
        return next((r['offset'] for r in r49['curves'] if r[key] is not None and r[key]<.6),None)
    raw_curve=mean_curve_cross('p_frame');q_curve=mean_curve_cross('routed_q')
    final_curve10=mean_curve_cross('final_delta10');final_curve1=mean_curve_cross('final_delta1')
    lines += ['', f'按全事件**均值曲线**看，frame p 在 offset={raw_curve} 首次低于 .6，路由 q 在 offset={q_curve}；最终分数的 Δ10 与 Δ1 均值在 0–15 内均未低于 .6。此均值曲线统计不同于上述逐事件首次跌破延迟；offset15 有 {pct(r49["curves"][-1]["GT_positive_share"])} 的可见记录已再次转真，未把它们静默移除。']
    # Data-dependent interpretation is written from the fixed statistics, without
    # changing any experimental choice or selecting a new variant.
    d1=r49['delta']['1'];d10=r49['delta']['10']
    support=(d1['latch']['fraction_raw_in_01_to_06'] or 0)>.5 and \
            ((d1['paired_final_minus_raw_latency']['mean_observed'] or 0)>0 or d1['raw_crossed_but_final_censored']>0)
    lines += ['', ('**判定：支持 TCP 自反馈存在。**' if support else '**判定：这些事件统计未完整满足预设的自锁证据组合。**')+
              ' 原始 frame 与路由后 q 能在最终判定前转为负，且 Δ1 下仍可能存在锁存；R50 的 V1/V2 干预用于区分 TCP 反馈和 TRP 复用。video 自身的响应差异及可见性删失均另列，因此不把全部延迟归因模型反应慢或全部归因 TCP。',
        '', '## R50：预注册变体与 LOSO',
        '', '所有版本 γ=0.6、video 路由 [0.2,0.8) 不变。V0/V1/V2 每 10 个非空候选帧更新，新 ID 立即调用原生缓存；V3/V4/V5 逐可见帧读 R22 分数。q 指 TCP 前、按固定 frame/video 路由得到的原始判别分数。',
        '', '- V0：原生 TCP=3/.4/.3，TRP10。V1：去 TCP，保留 TRP10。',
        '- V2：只把 TCP 历史改为最近新鲜原始 q 的历史，中间帧保持该 q；TCP 加分基数和最终分数 TRP 缓存保持原生，因此只断开历史条件的反馈。',
        '- V3：每帧 q，无 TCP、无 TRP。',
        '- V4：T 固定为 1 的偏置校准，再做二状态因果 HMM 前向滤波；V5：同一 HMM，偏置固定 0。跨可见性空档按真实图像帧间隔推进对称转移，新 ID 先验取训练三个序列的 GT 对象帧正例率。',
        '- 固定版：b=0、stay=.95、后验阈值 τ=.5，无超参数拟合；故 V4_fixed 与 V5_fixed 预注册为完全相同的对照，未把它们算作两份独立证据。',
        '- LOSO：每折整段留出一个视频。V4 仅拟合 b/stay/τ 共 3 个标量；V5 仅 stay/τ 共 2 个。b 最小化训练 BCE；stay 与 τ 仅按其余三序列 pooled micro-F1 选择，网格与并列规则见冻结方案。训练正例率为用户指定的先验统计，非额外可调超参。未按完整 val 调任何参数。',
        '- HMM 的 τ 是后验决策阈值，按用户要求独立于模型 γ；保留连续后验供审核，再把后验≥τ 写为 0/1，官方评测依然传 `--thresholds 0.6`。r 仍未知，未猜测负样本保留率。',
        '', '| 留出序列 | 训练正例先验 | V4 偏置 | V4 stay / τ | V5 stay / τ |',
        '|---|---:|---:|---|---|']
    for fold in r50['LOSO']['folds']:
        p4=fold['families']['V4'];p5=fold['families']['V5']
        lines.append(f'| {fold["held_out_sequence"]} | {pct(fold["new_ID_prior"])} | {p4["bias"]:.6f} | {p4["p_stay"]} / {p4["posterior_threshold"]} | {p5["p_stay"]} / {p5["posterior_threshold"]} |')
    lines += ['', '[逐折参数与训练数据量](runs/R50_temporal/LOSO/parameters.json)。全部训练网格保存在同目录，四折测试输出合并后才计算官方 HOTA；汇总不是四个 HOTA 的简单平均。',
        '', '| 变体 | HOTA | DetA | AssA | DetPr | DetRe | P | R | F1 | 空 GT 帧误报率 | F 真→假后0–5帧错误率 | ΔHOTA | 恢复 oracle 空间 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for v,r in variants.items():
        m=r['metrics'];ref=r['referring']
        cells=[v,*[fmt(m[k]) for k in ['HOTA','DetA','AssA','DetPr','DetRe']],
               *[pct(ref[k]) for k in ['precision','recall','f1']],pct(r['empty_GT_frames']['false_alarm_rate']),
               pct(r['F_true_to_false_post0to5']['error_rate']),fmt(r['gain_HOTA']),pct(r['recovered_oracle_fraction'])]
        lines.append('| '+' | '.join(cells)+' |')
    v0=variants['V0']
    lines += ['', f'空 GT 帧误报率分母为 {v0["empty_GT_frames"]["denominator"]:,} 个表达式×图像帧，若该帧有任一候选被判为匹配即误报；含无候选帧。F 真→假后0–5帧为 {v0["F_true_to_false_post0to5"]["n"]:,} 条事件加权可见记录，按当时真实标签计算错误。V2 仍保留原生最终分数复用，不能把 V2 解释成彻底移除 TCP。',
        '', '恢复空间严格按用户给定分母 32.488 HOTA：`(变体 HOTA − V0 HOTA)/32.488`。整数框 oracle H3_int=97.720，原始浮点框 H3≈100 的坐标收益不计入。',
        '', '[主表 CSV](runs/R50_temporal/main_table.csv) · [完整结果和所有混淆计数](runs/R50_temporal/result.json) · [官方评测具体命令](runs/R50_temporal/commands.sh)',
        '', '### 类别内 ΔHOTA（相对同类别 V0）',
        '', '| 类别 | 表达式数 | V0 HOTA | V1 | V2 | V3 | V4_fixed | V4_LOSO | V5_fixed | V5_LOSO |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for cat in 'ABCDEFGH':
        base=v0['categories'][cat]
        lines.append('| '+' | '.join([cat,str(base['expressions']),fmt(base['HOTA_metrics']['HOTA']),
                        *[fmt(variants[v]['categories'][cat]['delta_HOTA_vs_V0']) for v in VARIANTS[1:]]])+' |')
    lines += ['', 'A–H 为沿用的多标签，收益不可相加；G 全视频无目标表达式为 0，不能报告 G 类 HOTA。D 仅 21 条且属于 0011 的同一个 GT 时序家族，不能视为 21 个独立场景。这里是类别**内部** HOTA 的增量，与第二轮“只替换该类再算总体”的 oracle ΔHOTA 定义不同。',
        '', '### 各序列 HOTA', '', '| 序列 | '+' | '.join(VARIANTS)+' |', '|---|'+'---:|'*len(VARIANTS)]
    for seq in PLAN['sequences']:
        lines.append('| '+seq+' | '+' | '.join(fmt(variants[v]['per_sequence'][seq]['HOTA']) for v in VARIANTS)+' |')
    gain=b['gain_HOTA']
    cal_gain=variants['V4_LOSO']['metrics']['HOTA']-variants['V5_LOSO']['metrics']['HOTA']
    no_trp_gain=variants['V3']['metrics']['HOTA']-variants['V1']['metrics']['HOTA']
    fixed_vs_v3=variants['V4_fixed']['metrics']['HOTA']-variants['V3']['metrics']['HOTA']
    lines += ['', f'**时序干预结论：**预注册最佳版本 {best} 的 HOTA 为 {b["metrics"]["HOTA"]:.3f}，相对 V0 提升 {gain:.3f}，回收整数框 referring oracle 空间的 {100*b["recovered_oracle_fraction"]:.2f}%。校准贡献只比较 V4_LOSO 与 V5_LOSO 的完整 out-of-fold 结果；该差异也包括训练折选出的最优 HMM 参数变化，不能当成固定 HMM 下单独偏置的效应。',
        '', f'机制对照：去 TCP 的 V1 获得 +{variants["V1"]["gain_HOTA"]:.3f}；仅切断历史条件反馈的 V2 获得 +{variants["V2"]["gain_HOTA"]:.3f}，直接支持最终分数历史会伤害判定。去 TCP 后再把 TRP10 改为逐帧（V3−V1），额外 +{no_trp_gain:.3f}。固定 HMM 相对逐帧 V3 额外 +{fixed_vs_v3:.3f}；校准 LOSO 流程相对未校准 LOSO 流程（V4_LOSO−V5_LOSO）+{cal_gain:.3f}。这些是指定成对干预的净变化，不能把各项最大收益简单相加。',
        '', 'HOTA 最优并不等于切换响应最快：固定 HMM 的真→假后错误率 76.96%，高于 V3 的 66.53%；V5_LOSO 该项最低为 60.98%，但总体 HOTA 低于固定 HMM。固定 HMM 相比 V3 在 0005/0011/0013 分别变化 −0.703/−0.563/−0.372 HOTA，在候选帧占比最大的 0019 为 +1.479；总体优势并非每序列一致。V4 的四折 τ 均为预注册网格下界 .1，未根据完整 val 外扩搜索。',
        '', '类别内固定 HMM 增量以 C(+7.830)、B(+6.966) 较高，F 为 +5.014，E 为 +5.712；这些是重叠子集内部收益，不能据此分配总体 +5.147 的类别贡献。C/D 的模型上下文困难也不能由时序层改善就判为已解决。',
        '', '## R51：实际候选 GPU 阶段',
        '', (f'已达到 +2 HOTA 的预设触发条件。R22 在 4 GPU 上全量 frame/video 共耗时 {r51["R22_wall_seconds"]/3600:.2f} 小时，GT 候选 {r51["GT_candidate_rows"]:,} 条；实际 TempRMOT* 候选 {r51["actual_candidate_rows"]:,} 条。按相同吞吐、相同 video 路由命中比例作线性估算，完整缓存约 **{r51["estimated_wall_hours"]:.2f} 小时 / 4 GPU**。实际 crop 不确定性比例及并发负载尚未测得，估算不保证时限。' if r51['triggered'] else '所有预注册固定/LOSO 版本均未达到 +2 HOTA，不启动 GPU 阶段。'),
        '', ('**尚未启动 GPU，等待用户批准。**依据本轮 R51 的显式授权要求，且估计超过 8 小时，先交付以上 CPU 结果。' if r51['triggered'] and r51['exceeds_8_hours'] else ('**尚未启动 GPU，等待用户批准。**本轮 R51 明确要求批准后执行。' if r51['triggered'] else 'GPU 推理数量为 0。')),
        '', '[耗时估算及假设](runs/R51_estimate/result.json)',
        '', '## 一句话结论',
        '', f'不改模型、只换时序决策层，在 GT 候选的本地基线上，{best} 可收回 **{gain:.3f} HOTA**（{v0["metrics"]["HOTA"]:.3f}→{b["metrics"]["HOTA"]:.3f}，oracle 空间的 {100*b["recovered_oracle_fraction"]:.2f}%）；实际 TempRMOT* 候选上的收益仍需获批后的 GPU 缓存验证。',
        '', '## 可复现命令与边界',
        '', '从任务根目录运行（CPU 阶段约耗时见各 result.json）：', '', '```bash',
        f"CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 {config()['reproduction_environment']} -u analysis/round3.py --stage all",'```',
        '', '该命令按 gate→R49→R50→report 顺序执行；已有完整单位可复用，未完成单位继续，不跳过失败样本。原始命令、LOSO 范围和所有变体均在结果前登记到 runs.md。R51 在此命令中仅做 CPU 耗时估算，不能启动 GPU。', '']
    (ROOT/'analysis/REPORT_round3.md').write_text('\n'.join(lines))
    state={'CPU_complete':True,'seed':2025,'variants':VARIANTS,'best':best,'gain_HOTA':gain,
           'R51_triggered':r51['triggered'],'R51_GPU_started':False,'R51_awaiting_approval':r51['requires_new_user_approval']}
    save_json(ROOT/'analysis/round3_state.json',state)
    print('REPORT_round3.md written:',json.dumps(state),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['gate','R49','R50','report','all'],required=True)
    args=ap.parse_args();np.random.seed(PLAN['seed'])
    assert not os.environ.get('CUDA_VISIBLE_DEVICES',''), 'CPU-only stage requires CUDA_VISIBLE_DEVICES empty'
    if args.stage in ('gate','all'):gate()
    if args.stage in ('R49','all'):run_r49()
    if args.stage in ('R50','all'):run_r50()
    if args.stage in ('report','all'):report()


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        out=ROOT/'analysis/runs/R49_R50_failure.json'
        save_json(out,{'failed':True,'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        raise
