#!/usr/bin/env python3
"""Execute the frozen R58 CPU analyses on a complete, unmodified score cache."""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit, logsumexp

from r58_metrics import (OUT, TASK, Data, ClusterSampler, basic, bin_indices, ece, nll,
                         paired_difference, probability, summary, temporal_events)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.floating, float)) and not np.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def macro_summary(data, p, attributes, mask=None):
    ix = np.isfinite(p)
    if mask is not None:
        ix &= mask
    ix &= np.isin(data.attr, attributes)
    if not ix.any():
        return {'N': 0}
    pp, yy, aa = p[ix], data.y[ix], data.attr[ix]
    tracks, seq = data.track[ix], data.seq[ix]
    attrs = [a for a in attributes if np.any(aa == a)]
    keys = ['accuracy', 'macro_F1_binary', 'F1_positive', 'NLL', 'Brier', 'ECE_mass15', 'ECE_width15']
    mm = [basic(pp[aa == a], yy[aa == a]) for a in attrs]
    result = {'N': len(pp), 'attributes': attrs, 'tracks': len(set(tracks)),
              **{k: float(np.mean([m[k] for m in mm])) for k in keys}}
    for kind in ['mass','width']:
        result['Brier_decomposition_'+kind] = {k:float(np.mean([m['Brier_decomposition_'+kind][k] for m in mm]))
            for k in mm[0]['Brier_decomposition_'+kind]}
    rng = np.random.default_rng(2025)
    sampler = ClusterSampler(tracks, seq)
    draws = {k: [] for k in keys}
    decomp_draws={kind:{k:[] for k in result['Brier_decomposition_'+kind]} for kind in ['mass','width']}
    for b in range(1000):
        jj = sampler.draw(rng)
        bb = [basic(pp[jj][aa[jj] == a], yy[jj][aa[jj] == a]) for a in attrs]
        if all(m['N'] for m in bb):
            for k in keys:
                draws[k].append(float(np.mean([m[k] for m in bb])))
            for kind in decomp_draws:
                for key in decomp_draws[kind]:
                    decomp_draws[kind][key].append(float(np.mean([m['Brier_decomposition_'+kind][key] for m in bb])))
    result['cluster_bootstrap95'] = {k: {'low': float(np.quantile(v, .025)),
                'high': float(np.quantile(v, .975)), 'valid_replicates': len(v)} for k, v in draws.items() if v}
    result['Brier_decomposition_bootstrap95']={kind:{k:{'low':float(np.quantile(v,.025)),
        'high':float(np.quantile(v,.975)),'valid_replicates':len(v)} for k,v in vv.items() if v}
        for kind,vv in decomp_draws.items()}
    # Independent labels for every proposition in the identical aggregate sample.
    bins = {(a, kind): [i for i in bin_indices(pp[aa == a], kind) if len(i)]
            for a in attrs for kind in ['mass', 'width']}
    noise = {kind: [] for kind in ['mass', 'width']}
    rng = np.random.default_rng(2025)
    for start in range(0, 1000, 50):
        ysim = (rng.random((50, len(pp))) < pp).astype(float)
        for kind in noise:
            values = []
            for a in attrs:
                p_a = pp[aa == a]
                y_a = ysim[:, aa == a]
                values.append(sum(len(i)/len(p_a)*abs(y_a[:, i].mean(1)-p_a[i].mean()) for i in bins[(a, kind)]))
            noise[kind].extend(np.mean(values, axis=0).tolist())
    for kind, values in noise.items():
        result[f'ECE_{kind}15_noise'] = {'mean': float(np.mean(values)),
            'low95': float(np.quantile(values, .025)), 'high95': float(np.quantile(values, .975))}
    return result


def reliability_figure(path, title, measures):
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), gridspec_kw={'height_ratios':[4,1]})
    for column, kind in enumerate(['mass', 'width']):
        ax=axes[0,column];hist=axes[1,column]
        ax.plot([0, 1], [0, 1], color='black', ls='--', lw=1)
        for label, metric in measures.items():
            bins = metric.get('reliability', {}).get(kind, [])
            if not bins:
                continue
            xx = np.array([r['mean_p'] for r in bins])
            yy = np.array([r['positive_rate'] for r in bins])
            low = np.maximum(yy-np.array([r['low95'] for r in bins]), 0)
            high = np.maximum(np.array([r['high95'] for r in bins])-yy, 0)
            ax.errorbar(xx, yy, yerr=[low, high], marker='o', ms=3, label=label, capsize=2)
            area = np.array([r['N'] for r in bins], float)
            widths=np.array([max(r['max_p']-r['min_p'],.005) for r in bins])
            hist.bar(xx,area/area.sum(),width=widths,alpha=.3,label=label)
        ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='Predicted P(value)', ylabel='Observed positive frequency',
               title=f'15 {"equal-mass" if kind == "mass" else "equal-width"} bins')
        ax.legend(fontsize=8)
        hist.set(xlim=(0,1),xlabel='Predicted P(value)',ylabel='Bin mass')
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(exist_ok=True, parents=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def analyze_primary(data, dest):
    p_raw = probability(data.z, data.selected)
    p_global, temperatures = data.oof()
    p_attr, attribute_temperatures = data.oof(attribute_specific=True)
    info = next(x for x in data.plan['models'] if x['repo'].replace('/', '__') in str(dest)
                or (x['repo'] == 'vllm-sr/d3-turbo' and 'd3-turbo' in str(dest)))
    native_temperature = info['public_temperature']
    p_native = probability(data.z, data.selected, native_temperature)
    states = {'native': p_native, 'global_T_LOSO': p_global, 'attribute_T_LOSO': p_attr}
    if native_temperature != 1:
        states['raw_readout_T1'] = p_raw
    result = {'attributes': {}, 'temperatures': [{'held_out': s, 'T': t} for (s, a), t in temperatures.items()],
              'attribute_temperatures': [{'held_out': s, 'attribute': a, 'T': t} for (s, a), t in attribute_temperatures.items()]}
    tt = np.array([t for t in temperatures.values() if t is not None])
    result['T_cv'] = float(tt.std(ddof=1)/tt.mean()) if len(tt)>1 else None
    main_attrs = data.plan['samples']['main_attributes']
    for state, p in states.items():
        print(json.dumps({'analysis': 'P1_P2', 'state': state, 'rows': data.n}), flush=True)
        metrics = {}
        for a in sorted(set(data.attr)):
            m = data.subset_summary(p, data.attr == a)
            metrics[a] = m
        finite = np.isfinite(p)
        result['attributes'][state] = metrics
        result[state] = {'main_attribute_macro': macro_summary(data, p, main_attrs),
                         'all_attribute_macro': macro_summary(data, p, sorted(set(data.attr))),
                         'pooled': data.subset_summary(p, finite),
                         'unestimable_rows': int((~finite).sum())}
    for a in sorted(set(data.attr)):
        reliability_figure(dest/'figures'/f'reliability_{a}.png', a,
            {state: result['attributes'][state][a] for state in ['native','global_T_LOSO']})
    save(dest/'P1_P2.json', clean(result))
    np.savez_compressed(dest/'OOF.npz', y=data.y, z=data.z, selected=data.selected,
                        p_native=p_native, p_global=p_global, p_attribute=p_attr,
                        sequence=data.seq, track=data.track, attribute=data.attr)
    save(dest/'rows.json', data.rows)
    return p_global, temperatures, p_native, result


def analyze_groups(data, p, dest):
    sample = [data.sample_index[r['sample_id']] for r in data.rows]
    groups = []
    height = np.array([s['box_xywh'][3] for s in sample])
    for label, ix in [('<40',height<40), ('40-100',(height>=40)&(height<=100)), ('>100',height>100)]:
        groups.append(('height',label,ix))
    for field in ['occlusion','category','sequence']:
        values = [s.get(field) for s in sample]
        for value in sorted(set(values), key=str):
            groups.append((field,str(value),np.array([v==value for v in values])))
    tr = np.array([s['truncation'] if s['truncation'] is not None else np.nan for s in sample])
    for label, ix in [('0',tr==0), ('(0,.5]',(tr>0)&(tr<=.5)), ('>.5',tr>.5), ('unknown',~np.isfinite(tr))]:
        if ix.any():
            groups.append(('truncation',label,ix))
    result = []
    for field, value, ix in groups:
        by_attr = {}
        for a in sorted(set(data.attr)):
            mask = ix & (data.attr==a) & np.isfinite(p)
            by_attr[a] = summary(p[mask],data.y[mask],data.track[mask],data.seq[mask],reliability=False)
        result.append({'group':field,'value':value,'attributes':by_attr,
                       'main_attribute_macro':macro_summary(data,p,data.plan['samples']['main_attributes'],ix)})
        print(json.dumps({'analysis':'P3','group':field,'value':value}),flush=True)
    save(dest/'P3.json',clean(result))


def distribution(record, q, T):
    keys = [o['id'] for o in q['options']]
    z = np.log(np.maximum([record['probabilities'][q['id']][k] for k in keys],1e-12))/T
    return np.exp(z-logsumexp(z))


def js(p,q):
    m=(p+q)/2
    return float(.5*np.sum(np.where(p>0,p*np.log(np.maximum(p,1e-12)/np.maximum(m,1e-12)),0))+
                 .5*np.sum(np.where(q>0,q*np.log(np.maximum(q,1e-12)/np.maximum(m,1e-12)),0)))


def scalar_summary(rows, key):
    if not rows:
        return {'N':0}
    values = [r[key] for r in rows]
    result = paired_difference(values,np.zeros(len(values)),[r['track'] for r in rows],[r['sequence'] for r in rows])
    result['mean']=result.pop('difference')
    return result


def analyze_wording(data, temperatures, dest):
    rows=[]
    eligible_by_sample=defaultdict(set)
    for r in data.rows:
        eligible_by_sample[r['sample_id']].add(r['qid'])
    for sample in data.samples:
        T=temperatures[(sample['sequence'],'global')]
        eligible=eligible_by_sample[sample['id']]
        for qid in sorted(eligible):
            q=data.questions[qid]
            ds=[distribution(data.pred[setting][sample['id']],q,T) for setting in ['main','wording_1','wording_2']]
            divergences=[js(ds[i],ds[j]) for i,j in [(0,1),(0,2),(1,2)]]
            flips=[int(np.argmax(ds[i])!=np.argmax(ds[j])) for i,j in [(0,1),(0,2),(1,2)]]
            row={'sample_id':sample['id'],'track':sample['track'],'sequence':sample['sequence'],
                 'attribute':q['attribute'],'qid':qid,'JS':float(np.mean(divergences)),
                 'wording_flip':float(np.mean(flips)),**{f'flip_{i}':v for i,v in enumerate(flips)}}
            if q['type']=='choice':
                orders=[distribution(data.pred[s][sample['id']],q,T) for s in ['order_1','order_2']]
                row['order_flip']=float(np.mean([np.argmax(d)!=np.argmax(ds[0]) for d in orders]))
                row['order_flip_1']=float(np.argmax(orders[0])!=np.argmax(ds[0]))
                row['order_flip_2']=float(np.argmax(orders[1])!=np.argmax(ds[0]))
            rows.append(row)
    result={}
    for attr in ['ALL']+sorted(set(r['attribute'] for r in rows)):
        rr=[r for r in rows if attr=='ALL' or r['attribute']==attr]
        result[attr]={k:scalar_summary(rr,k) for k in ['JS','wording_flip','flip_0','flip_1','flip_2']}
        result[attr]['worst_wording_pair_flip']=max(result[attr][f'flip_{i}'].get('mean',0) for i in range(3))
        choice_rows=[r for r in rr if 'order_flip' in r]
        result[attr].update({k:scalar_summary(choice_rows,k) for k in ['order_flip','order_flip_1','order_flip_2']})
    save(dest/'P4_rows.json',clean(rows))
    save(dest/'P4.json',clean(result))


def analyze_composition(data,p,temperatures,dest):
    events={(r['sample_id'],r['attribute'],r['value']):(i,r['y']) for i,r in enumerate(data.rows)}
    rows=[]
    for sample in data.samples:
        T=temperatures[(sample['sequence'],'global')]
        for q in data.questions.values():
            if q['attribute']!='conjunction':
                continue
            components=[events.get((sample['id'],a,v)) for a,v in q['events']]
            if any(x is None for x in components):
                continue
            indexes=[x[0] for x in components]
            direct=distribution(data.pred['main'][sample['id']],q,T)[1]
            rows.append({'sample_id':sample['id'],'track':sample['track'],'sequence':sample['sequence'],
                         'qid':q['id'],'order':len(components),'y':int(all(x[1] for x in components)),
                         'product':float(np.prod(p[indexes])),'direct':float(direct)})
    result={}
    groups=['ALL','pairs','triples']+[q['id'] for q in data.questions.values() if q['attribute']=='conjunction']
    for group in groups:
        rr=[r for r in rows if group=='ALL' or group=='pairs' and r['order']==2 or
            group=='triples' and r['order']==3 or r['qid']==group]
        if not rr:
            result[group]={'N':0}
            continue
        yy=np.array([r['y'] for r in rr]);tt=[r['track'] for r in rr];ss=[r['sequence'] for r in rr]
        result[group]={mode:summary(np.array([r[mode] for r in rr]),yy,tt,ss) for mode in ['product','direct']}
        a=np.clip([r['product'] for r in rr],1e-12,1-1e-12)
        b=np.clip([r['direct'] for r in rr],1e-12,1-1e-12)
        la=-yy*np.log(a)-(1-yy)*np.log1p(-a);lb=-yy*np.log(b)-(1-yy)*np.log1p(-b)
        result[group]['NLL_product_minus_direct']=paired_difference(la,lb,tt,ss)
        if group in ['ALL','pairs','triples']:
            reliability_figure(dest/'figures'/f'P5_{group}.png',f'Conjunction: {group}',
                {mode:result[group][mode] for mode in ['product','direct']})
    save(dest/'P5_rows.json',clean(rows))
    save(dest/'P5.json',clean(result))
    # Pairwise binary correctness across distinct attributes, with labels/value identities preserved.
    by_sample=defaultdict(list)
    for i,r in enumerate(data.rows):
        by_sample[r['sample_id']].append((r,int((p[i]>=.5)==r['y'])))
    pairs=defaultdict(list)
    for sid,rs in by_sample.items():
        for (a,ca),(b,cb) in itertools.combinations(rs,2):
            if a['attribute']==b['attribute']:
                continue
            if (a['attribute'],a['value'])>(b['attribute'],b['value']):
                a,b,ca,cb=b,a,cb,ca
            key=(a['attribute'],a['value'],b['attribute'],b['value'])
            pairs[key].append((ca,cb,a['track'],a['sequence']))
    correlations=[]
    for key,rr in pairs.items():
        aa=np.array([r[0] for r in rr]);bb=np.array([r[1] for r in rr])
        corr=float(np.corrcoef(aa,bb)[0,1]) if aa.std()>0 and bb.std()>0 else None
        sampler=ClusterSampler([r[2] for r in rr],[r[3] for r in rr]);rng=np.random.default_rng(2025);draws=[]
        if corr is not None:
            for k in range(1000):
                ii=sampler.draw(rng)
                if aa[ii].std()>0 and bb[ii].std()>0:
                    draws.append(float(np.corrcoef(aa[ii],bb[ii])[0,1]))
        correlations.append({'attribute_a':key[0],'value_a':key[1],'attribute_b':key[2],'value_b':key[3],
                             'N':len(rr),'phi':corr,'low95':float(np.quantile(draws,.025)) if draws else None,
                             'high95':float(np.quantile(draws,.975)) if draws else None,'valid_bootstraps':len(draws)})
    save(dest/'P5_correctness_correlations.json',clean(correlations))


def analyze_temporal(data,p,inner,dest):
    events=temporal_events(data,p)
    alpha={}
    for held_out in data.plan['sequences']:
        train=temporal_events(data,inner[held_out])
        if not train:
            alpha[held_out]=None
            continue
        z=np.array([r['sum'] for r in train]);yy=np.array([r['y'] for r in train])
        fitted=minimize_scalar(lambda a:nll(expit(a*z),yy),bounds=(0,4),method='bounded',options={'xatol':1e-6})
        assert fitted.success
        alpha[held_out]=float(fitted.x)
    for r in events:
        r['sum_p']=float(expit(r['sum']));r['mean_p']=float(expit(r['mean']))
        a=alpha[r['sequence']]
        r['scaled_sum_p']=float(expit(a*r['sum'])) if a is not None else None
    result={'alpha_LOSO':alpha,'K':{}}
    for cohort in ['each_K','common_K8']:
        result['K'][cohort]={}
        for K in [1,2,4,8]:
            rr=[r for r in events if r['K']==K and (cohort=='each_K' or r['available_frames']>=8)]
            entry={}
            for a in ['ALL']+sorted(set(data.attr)):
                rs=[r for r in rr if a=='ALL' or r['attribute']==a]
                if not rs:
                    entry[a]={'N':0};continue
                yy=np.array([r['y'] for r in rs]);tt=[r['track'] for r in rs];ss=[r['sequence'] for r in rs]
                entry[a]={}
                for rule in ['p1','sum_p','mean_p','scaled_sum_p']:
                    known=[r for r in rs if r[rule] is not None]
                    entry[a][rule]=summary(np.array([r[rule] for r in known]),np.array([r['y'] for r in known]),
                        [r['track'] for r in known],[r['sequence'] for r in known],reliability=False) if known else {'N':0}
            entry['MAIN_MACRO']={}
            if rr:
                event_data=SimpleNamespace(attr=np.array([r['attribute'] for r in rr]),y=np.array([r['y'] for r in rr]),
                    track=np.array([r['track'] for r in rr]),seq=np.array([r['sequence'] for r in rr]))
                for rule in ['p1','sum_p','mean_p','scaled_sum_p']:
                    pp=np.array([r[rule] if r[rule] is not None else np.nan for r in rr])
                    entry['MAIN_MACRO'][rule]=macro_summary(event_data,pp,data.plan['samples']['main_attributes'])
            result['K'][cohort][str(K)]=entry
    save(dest/'P6_rows.json',clean(events));save(dest/'P6.json',clean(result))
    common=result['K']['common_K8']
    if common['8'].get('MAIN_MACRO',{}):
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for rule in ['sum_p','mean_p','scaled_sum_p']:
            ms=[common[str(K)]['MAIN_MACRO'].get(rule,{}) for K in [1,2,4,8]]
            if not all(m.get('N') for m in ms):continue
            axes[0].plot([1,2,4,8],[m['accuracy'] for m in ms],marker='o',label=rule)
            axes[1].plot([1,2,4,8],[m['ECE_mass15'] for m in ms],marker='o',label=rule+' ECE')
            axes[1].plot([1,2,4,8],[m['ECE_mass15_noise']['mean'] for m in ms],ls='--',alpha=.6,label=rule+' noise')
        axes[0].set(xlabel='K',ylabel='Accuracy');axes[1].set(xlabel='K',ylabel='Binary equal-mass ECE')
        axes[1].axhline(.05,color='black',ls=':',lw=1)
        for ax in axes:ax.set_xticks([1,2,4,8]);ax.legend(fontsize=7)
        fig.suptitle('Same K=8-eligible track/event cohort; main-attribute macro')
        fig.tight_layout();(dest/'figures').mkdir(exist_ok=True)
        fig.savefig(dest/'figures/P6_common_K8.png',dpi=160);plt.close(fig)
    return result


def analyze_utility(data,p,inner,dest):
    thresholds={};pred=np.zeros(data.n,bool)
    for seq in data.plan['sequences']:
        nested=inner[seq]
        for a in sorted(set(data.attr)):
            tr=(data.seq!=seq)&(data.attr==a)&np.isfinite(nested)
            if not tr.any():
                thresholds[(seq,a)]=None
                continue
            candidates=[]
            for threshold in data.plan['decision_utility']['threshold_grid']:
                h=nested[tr]>=threshold;y=data.y[tr]
                tp=int((h&(y==1)).sum());fp=int((h&(y==0)).sum());fn=int((~h&(y==1)).sum())
                candidates.append((2*tp/max(2*tp+fp+fn,1),-abs(threshold-.5),-threshold,threshold))
            t=max(candidates)[-1];thresholds[(seq,a)]=t
            ix=(data.seq==seq)&(data.attr==a);pred[ix]=p[ix]>=t
    result={'thresholds':[{'held_out':s,'attribute':a,'threshold':t} for (s,a),t in thresholds.items()], 'attributes':{}}
    for a in sorted(set(data.attr)):
        mask=(data.attr==a)&np.array([thresholds.get((s,a)) is not None for s in data.seq])
        if not mask.any():
            result['attributes'][a]={'N':0};continue
        # p=.75/.25 encodes the selected binary decisions without masquerading as calibrated probabilities.
        fixed=summary(p[mask],data.y[mask],data.track[mask],data.seq[mask],reliability=False)
        tuned=basic(np.where(pred[mask],.75,.25),data.y[mask])
        sampler=ClusterSampler(data.track[mask],data.seq[mask]);rng=np.random.default_rng(2025);diff=[]
        for b in range(1000):
            jj=sampler.draw(rng)
            f0=basic(p[mask][jj],data.y[mask][jj])['F1_positive']
            f1=basic(np.where(pred[mask][jj],.75,.25),data.y[mask][jj])['F1_positive'];diff.append(f1-f0)
        result['attributes'][a]={'N':int(mask.sum()),'F1_fixed_0p5':fixed['F1_positive'],
            'F1_LOSO_threshold':tuned['F1_positive'],'F1_gap':tuned['F1_positive']-fixed['F1_positive'],
            'gap_low95':float(np.quantile(diff,.025)),'gap_high95':float(np.quantile(diff,.975))}
    save(dest/'decision_utility.json',clean(result))


def load_main_checkpoint(data,dest):
    with np.load(dest/'OOF.npz') as saved:
        for name,current in [('z',data.z),('selected',data.selected),('y',data.y),
                             ('sequence',data.seq),('track',data.track),('attribute',data.attr)]:
            assert np.array_equal(saved[name],current),('Main input changed since CPU checkpoint',name)
        p=saved['p_global']
    primary=json.loads((dest/'P1_P2.json').read_text())
    temperatures={(r['held_out'],'global'):r['T'] for r in primary['temperatures']}
    return p,temperatures


def analyze_one(data,dest,main_only=False):
    dest.mkdir(parents=True,exist_ok=True)
    marker=dest/'main_completion.json'
    if marker.exists() and json.loads(marker.read_text()).get('complete'):
        p,temperatures=load_main_checkpoint(data,dest)
        print(json.dumps({'analysis':'reuse_main_CPU_checkpoint','destination':str(dest)}),flush=True)
    else:
        p,temperatures,p_native,primary=analyze_primary(data,dest)
        analyze_groups(data,p,dest)
        analyze_composition(data,p,temperatures,dest)
        print(json.dumps({'analysis':'nested_LOSO','destination':str(dest)}),flush=True)
        inner={s:data.nested_oof(s) for s in data.plan['sequences']}
        analyze_temporal(data,p,inner,dest)
        analyze_utility(data,p,inner,dest)
        save(marker,{'complete':True,'scope':'full main setting only; P4/crop remain',
            'seed':2025,'samples':len({r['sample_id'] for r in data.rows}),'binary_rows':data.n,'bootstrap':1000})
    if main_only:
        return
    analyze_wording(data,temperatures,dest)
    analyze_crop(data,temperatures,dest)
    save(dest/'completion.json',{'complete':True,'seed':2025,
                               'samples':len({r['sample_id'] for r in data.rows}),'binary_rows':data.n,'bootstrap':1000})


def analyze_crop(data,temperatures,dest):
    values=[]
    for r in data.rows:
        q=data.questions[r['qid']]
        T=temperatures[(r['sequence'],'global')]
        d=distribution(data.pred['crop_only'][r['sample_id']],q,T)
        selected=[o['id'] in q['value_options'][r['value']] for o in q['options']]
        values.append(float(d[selected].sum()))
    pp=np.array(values)
    result={'temperature':'reuse main-input outer-fold global T; no new fitted scalar',
            'attributes':{},'main_attribute_macro':macro_summary(data,pp,data.plan['samples']['main_attributes'])}
    for a in sorted(set(data.attr)):
        result['attributes'][a]=data.subset_summary(pp,data.attr==a)
    save(dest/'crop_ablation.json',clean(result))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model-key',required=True)
    ap.add_argument('--main-only',action='store_true');args=ap.parse_args()
    data=Data(args.model_key,require_full=True,main_only=args.main_only)
    dest=OUT/'metrics'/args.model_key
    analyze_one(data,dest,args.main_only)
    # Requested sensitivity experiment: refit the same one-scalar LOSO procedure on the strict row subset.
    # The native checkpoint cache, prompts, folds and seeds stay exactly the same.
    analyze_one(data.restrict_two_values(),dest/'sensitivity_two_values',args.main_only)


if __name__=='__main__':
    main()
