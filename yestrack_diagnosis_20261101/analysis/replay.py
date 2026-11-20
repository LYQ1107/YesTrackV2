"""Exact causal TCP/TRP replay from unmodified-helper score observations."""
from collections import deque
import gzip
import json
from pathlib import Path

import numpy as np


def load_observations(root):
    by_name={}
    for file in sorted(Path(root).glob('rank*.jsonl.gz')):
        with gzip.open(file,'rt') as f:
            for line in f:
                r=json.loads(line)
                current=by_name.setdefault(r['name'],{})
                for oid,p in zip(r['ids'],r['p']):
                    item=current.setdefault((r['frame'],oid),{})
                    assert r['mode'] not in item
                    item[r['mode']]=p
    return by_name


def replay(tr, observed, delta=10, lower=.2, upper=.8, full=None, births=None, serialize=True):
    """Return continuous final scores; gamma is evaluation-only and never used here."""
    result=np.zeros(len(tr),dtype=np.float64)
    last={};history={}
    for counter,frame in enumerate(np.unique(tr[:,0]).astype(int)):
        ix=np.flatnonzero(tr[:,0]==frame)
        infer_all=counter%delta==0
        for i in ix:
            oid=int(tr[i,1]);key=(frame,oid)
            if infer_all or oid not in last:
                if full is None:
                    item=observed[key]
                    p=float(item['frame'])
                    if lower<=p<upper:p=float(item['video'])
                else:
                    source=full if infer_all else births
                    p=float(source['p_frame'][i])
                    assert np.isfinite(p),(frame,oid)
                    if lower<=p<upper:
                        p=float(source['p_video'][i])
                        assert np.isfinite(p),(frame,oid,'video')
            else:
                p=last[oid]
            dq=history.setdefault(oid,deque(maxlen=3))
            if len(dq)>=3 and all(v>=.4 for v in dq):p=min(1.,p+.3)
            dq.append(p);last[oid]=p;result[i]=p
    if not serialize:return result
    # Match the official f"{p:.6f}" writer exactly; np.round can differ by1e-6
    # on binary values close to a decimal half-way point.
    return np.fromiter((float(f'{p:.6f}') for p in result),dtype=np.float64,count=len(result))


def dense_cache(file,n):
    cache=np.load(file)
    out={key:np.full(n,np.nan) for key in ('p_frame','p_video')}
    for key in out:out[key][cache['row_index']]=cache[key]
    return out
