#!/usr/bin/env python3
"""R58 binary calibration metrics, track-cluster bootstrap, and sequence-LOSO scalars."""
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit, logsumexp, xlogy
from scipy.stats import rankdata

TASK = Path(__file__).resolve().parents[1]
OUT = TASK / 'analysis/runs/R58_calibration'
EPS = 1e-12


def probability(z, selected, T=1.):
    zz = z / T
    p = np.exp(zz - logsumexp(zz, axis=-1, keepdims=True))
    return np.sum(p * selected, axis=-1)


def bin_indices(p, kind):
    n = len(p)
    if kind == 'width':
        idx = np.minimum((p * 15).astype(int), 14)
        return [np.flatnonzero(idx == i) for i in range(15)]
    return np.array_split(np.argsort(p, kind='stable'), 15)


def ece(p, y, kind='mass'):
    if not len(p):
        return float('nan')
    return float(sum(len(i) * abs(np.mean(p[i]) - np.mean(y[i]))
                     for i in bin_indices(p, kind) if len(i)) / len(p))


def nll(p, y):
    pp = np.clip(p, EPS, 1 - EPS)
    return float(np.mean(-y*np.log(pp) - (1-y)*np.log1p(-pp)))


def basic(p, y):
    p, y = np.asarray(p), np.asarray(y)
    if not len(p):
        return {'N': 0}
    h = p >= .5
    tp, fp, fn, tn = ((h & (y == 1)).sum(), (h & (y == 0)).sum(),
                       (~h & (y == 1)).sum(), (~h & (y == 0)).sum())
    f_pos = 2*tp / max(2*tp+fp+fn, 1)
    f_neg = 2*tn / max(2*tn+fp+fn, 1)
    result = {'N': len(p), 'positive': int(y.sum()), 'accuracy': float((h == y).mean()),
              'macro_F1_binary': float((f_pos+f_neg)/2), 'F1_positive': float(f_pos),
              'NLL': nll(p, y), 'Brier': float(np.mean((p-y)**2)),
              'ECE_mass15': ece(p, y, 'mass'), 'ECE_width15': ece(p, y, 'width'),
              'AUROC': float((rankdata(p)[y == 1].sum()-y.sum()*(y.sum()+1)/2) /
                             (y.sum()*(len(y)-y.sum()))) if len(np.unique(y)) == 2 else None}
    for kind in ['mass', 'width']:
        bins = [i for i in bin_indices(p, kind) if len(i)]
        mean_y = y.mean()
        rel = sum(len(i)/len(p)*(p[i].mean()-y[i].mean())**2 for i in bins)
        res = sum(len(i)/len(p)*(y[i].mean()-mean_y)**2 for i in bins)
        unc = mean_y*(1-mean_y)
        result['Brier_decomposition_' + kind] = {'calibration_reliability': float(rel),
            'resolution': float(res), 'uncertainty': float(unc),
            'discretization_residual': float(result['Brier']-(unc-res+rel))}
    return result


def noise_floor(p, repetitions=1000, seed=2025):
    if not len(p):
        return {}
    rng = np.random.default_rng(seed)
    # Probability bins are fixed when only calibrated labels are drawn.
    bins = {kind: [idx for idx in bin_indices(p, kind) if len(idx)] for kind in ['mass', 'width']}
    results = {kind: [] for kind in bins}
    for start in range(0, repetitions, 50):
        yy = (rng.random((min(50, repetitions-start), len(p))) < p).astype(np.float32)
        for kind, ix in bins.items():
            v = sum(len(i)/len(p)*abs(yy[:, i].mean(1)-p[i].mean()) for i in ix)
            results[kind].extend(v.tolist())
    return {f'ECE_{kind}15_noise': {'mean': float(np.mean(v)),
                'low95': float(np.quantile(v, .025)), 'high95': float(np.quantile(v, .975))}
            for kind, v in results.items()}


class ClusterSampler:
    def __init__(self, tracks, sequences):
        groups = defaultdict(list)
        for i, (t, s) in enumerate(zip(tracks, sequences)):
            groups[(s, t)].append(i)
        self.by_seq = defaultdict(list)
        for (s, t), indices in groups.items():
            self.by_seq[s].append(np.asarray(indices))

    def draw(self, rng):
        return np.concatenate([units[i] for units in self.by_seq.values()
                               for i in rng.integers(0, len(units), len(units))])


def bootstrap_indices(tracks, sequences, rng):
    yield ClusterSampler(tracks, sequences).draw(rng)


def summary(p, y, tracks, sequences, repetitions=1000, seed=2025, reliability=True):
    p, y = np.asarray(p, float), np.asarray(y, int)
    result = basic(p, y)
    if not len(p):
        return result
    result.update(noise_floor(p, repetitions, seed))
    result['tracks'] = len(set(tracks))
    rng = np.random.default_rng(seed)
    measures = ['accuracy', 'macro_F1_binary', 'F1_positive', 'NLL', 'Brier', 'ECE_mass15', 'ECE_width15']
    values = {key: [] for key in measures}
    # Bootstrap AUROC by the same track units; undefined resamples remain unavailable, never set to 0.
    values['AUROC'] = []
    sampler = ClusterSampler(tracks, sequences)
    decomposition_values = {kind: {k: [] for k in result['Brier_decomposition_'+kind]} for kind in ['mass','width']}
    for b in range(repetitions):
        ix = sampler.draw(rng)
        m = basic(p[ix], y[ix])
        for key in values:
            if m[key] is not None:
                values[key].append(m[key])
        for kind in decomposition_values:
            for key in decomposition_values[kind]:
                decomposition_values[kind][key].append(m['Brier_decomposition_'+kind][key])
    result['cluster_bootstrap95'] = {key: {'low': float(np.quantile(v, .025)),
                'high': float(np.quantile(v, .975)), 'valid_replicates': len(v)}
                for key, v in values.items() if v}
    result['Brier_decomposition_bootstrap95'] = {kind: {key: [float(np.quantile(v,.025)),float(np.quantile(v,.975))]
                for key,v in vv.items()} for kind,vv in decomposition_values.items()}
    result['reliability'] = {}
    if not reliability:
        return result
    for kind in ['mass', 'width']:
        rows = []
        for idx in bin_indices(p, kind):
            if not len(idx):
                continue
            # Retain track clustering for each reliability-bin confidence interval.
            bt, bs = np.asarray(tracks)[idx], np.asarray(sequences)[idx]
            yy = y[idx]
            sampler_bin = ClusterSampler(bt,bs)
            brng = np.random.default_rng(seed)
            means = []
            for b in range(repetitions):
                bi = sampler_bin.draw(brng)
                means.append(float(yy[bi].mean()))
            rows.append({'N': len(idx), 'mean_p': float(p[idx].mean()), 'positive_rate': float(yy.mean()),
                         'min_p':float(p[idx].min()),'max_p':float(p[idx].max()),
                         'low95': float(np.quantile(means, .025)), 'high95': float(np.quantile(means, .975))})
        result['reliability'][kind] = rows
    return result


class Data:
    def __init__(self, model_key, require_full=True, main_only=False):
        self.plan = json.loads((TASK / 'analysis/plans/r58.json').read_text())
        self.samples = json.loads((OUT / 'samples.json').read_text())
        self.sample_index = {r['id']: r for r in self.samples}
        self.questions = {q['id']: q for q in self.plan['questions']['bank']}
        self.qlookup = {(q['attribute'], value): q['id'] for q in self.questions.values()
                        if q['attribute'] != 'conjunction' for value in q['value_options']}
        self.pred = {}
        for setting in self.plan['questions']['settings']:
            if main_only and setting['id']!='main':
                continue
            p = OUT / 'predictions' / model_key / (setting['id'] + '.jsonl')
            rows = [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []
            assert len({r['sample_id'] for r in rows}) == len(rows)
            self.pred[setting['id']] = {r['sample_id']: r for r in rows}
            if require_full:
                assert set(self.pred[setting['id']]) == set(self.sample_index), (model_key, setting['id'], len(rows))
        self.rows = []
        zz = []
        selected = []
        for sample in self.samples:
            record = self.pred['main'].get(sample['id'])
            if record is None:
                continue
            for lab in sample['labels']:
                qid = self.qlookup[(lab['attribute'], lab['value'])]
                question = self.questions[qid]
                keys = [o['id'] for o in question['options']]
                p = record['probabilities'][qid]
                z = np.full(9, -np.inf)
                z[:len(keys)] = np.log(np.maximum([p[k] for k in keys], EPS))
                sel = np.zeros(9, bool)
                sel[:len(keys)] = [k in question['value_options'][lab['value']] for k in keys]
                self.rows.append({'sample_id': sample['id'], 'sequence': sample['sequence'],
                                  'track': sample['track'], 'attribute': lab['attribute'],
                                  'value': lab['value'], 'y': lab['y'], 'qid': qid,
                                  'sensitivity': lab['sensitivity_two_values']})
                zz.append(z)
                selected.append(sel)
        self.z, self.selected = np.asarray(zz), np.asarray(selected)
        self.y = np.array([r['y'] for r in self.rows])
        self.seq = np.array([r['sequence'] for r in self.rows])
        self.track = np.array([r['track'] for r in self.rows])
        self.attr = np.array([r['attribute'] for r in self.rows])
        self.n = len(self.rows)

    def restrict_two_values(self):
        """Same frozen binary rows, stricter source-expression availability; no GPU recomputation."""
        import copy
        result = copy.copy(self)
        ix = np.array([r['sensitivity'] for r in self.rows])
        result.rows = [r for r, keep in zip(self.rows, ix) if keep]
        for key in ['z','selected','y','seq','track','attr']:
            setattr(result,key,getattr(self,key)[ix])
        result.n = len(result.rows)
        return result

    def fit_T(self, mask):
        if not mask.any():
            return None
        y, z, selected = self.y[mask], self.z[mask], self.selected[mask]
        result = minimize_scalar(lambda logT: nll(probability(z, selected, np.exp(logT)), y),
            bounds=(np.log(.05), np.log(50.)), method='bounded', options={'xatol': 1e-6})
        assert result.success
        return float(np.exp(result.x))

    def oof(self, attribute_specific=False):
        p = np.full(self.n, np.nan)
        fitted = {}
        for seq in self.plan['sequences']:
            test = self.seq == seq
            if not test.any():
                continue
            attrs = sorted(set(self.attr)) if attribute_specific else ['global']
            for a in attrs:
                amask = self.attr == a if attribute_specific else np.ones(self.n, bool)
                T = self.fit_T(~test & amask)
                fitted[(seq, a)] = T
                if T is not None:
                    ix = test & amask
                    p[ix] = probability(self.z[ix], self.selected[ix], T)
        return p, fitted

    def subset_summary(self, p, mask):
        mask = mask & np.isfinite(p)
        return summary(p[mask], self.y[mask], self.track[mask], self.seq[mask])

    def nested_oof(self, outer):
        # One T for each inner training split; outer sequence labels never enter the inner fit.
        p = np.full(self.n, np.nan)
        for seq in self.plan['sequences']:
            if seq == outer:
                continue
            train = (self.seq != outer) & (self.seq != seq)
            T = self.fit_T(train)
            ix = self.seq == seq
            if T is not None:
                p[ix] = probability(self.z[ix], self.selected[ix], T)
        return p


def logodds(p):
    q = np.clip(p, EPS, 1-EPS)
    return np.log(q) - np.log1p(-q)


def temporal_events(data, p):
    groups = defaultdict(list)
    for i, row in enumerate(data.rows):
        if np.isfinite(p[i]):
            groups[(row['track'], row['attribute'], row['value'])].append(i)
    events = []
    for (track, attr, value), ix in groups.items():
        ix.sort(key=lambda i: data.sample_index[data.rows[i]['sample_id']]['frame'])
        assert len(set(data.y[ix])) == 1, (track, attr, value)
        for K in [1, 2, 4, 8]:
            if len(ix) >= K:
                indexes = ix[:K]
                events.append({'track': track, 'sequence': data.seq[ix[0]], 'attribute': attr,
                    'value': value, 'K': K, 'available_frames': len(ix), 'y': int(data.y[ix[0]]),
                    'sum': float(logodds(p[indexes]).sum()), 'mean': float(logodds(p[indexes]).mean()),
                    'p1': float(p[ix[0]])})
    return events


def paired_difference(values_a, values_b, tracks, seq, seed=2025):
    delta = np.asarray(values_a) - np.asarray(values_b)
    if not len(delta):
        return {'N': 0}
    rng = np.random.default_rng(seed)
    means = []
    sampler = ClusterSampler(tracks,seq)
    for b in range(1000):
        ix = sampler.draw(rng)
        means.append(float(delta[ix].mean()))
    return {'N': len(delta), 'difference': float(delta.mean()),
            'low95': float(np.quantile(means, .025)), 'high95': float(np.quantile(means, .975))}
