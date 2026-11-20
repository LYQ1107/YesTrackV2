"""Shared fixed threshold grid and exact native-controller score validation."""
import numpy as np
from common import confusion,mot
from replay import replay


def scan(dataset,rows,tracks,truth,observed,native_root):
    records=[];native_max_diff=0.
    for lo in [.2,.3,.4]:
     for hi in [.6,.7,.8]:
        counts={gamma:{'tp':0,'fp':0,'fn':0,'tn':0,'n':0} for gamma in [.1,.2,.3,.4,.5,.6,.7,.8,.9]}
        for row in rows:
            name=row['name'];seq,expr=name.split('__',1);tr=tracks[seq]
            score=replay(tr,observed[name],lower=lo,upper=hi)
            if lo==.2 and hi==.8:
                native=mot(native_root/seq/expr/'predict_with_conf.txt')[:,6]
                diff=float(np.max(np.abs(native-score)));native_max_diff=max(native_max_diff,diff)
                assert diff<1e-12,(dataset,name,diff)
            for gamma,value in counts.items():
                result=confusion(truth[name],score,gamma)
                for key in value:value[key]+=result[key]
        for gamma,value in counts.items():
            tp,fp,fn=value['tp'],value['fp'],value['fn']
            records.append({'dataset':dataset,'gamma':gamma,'lower':lo,'upper':hi,**value,
                'precision':tp/(tp+fp),'recall':tp/(tp+fn),'f1':2*tp/(2*tp+fp+fn)})
    return records,native_max_diff
