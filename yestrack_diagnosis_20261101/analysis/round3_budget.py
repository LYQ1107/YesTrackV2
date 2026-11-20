#!/usr/bin/env python3
"""User-requested budget-matched HMM: R17 observations, transition-only skipped frames."""
import csv
import json
import os
from pathlib import Path
import time
import traceback

import numpy as np
from scipy.optimize import minimize_scalar

import round3 as native
from common import config,save_json
from replay import load_observations,replay

ROOT=native.ROOT
OUT=ROOT/'analysis/runs/R52_budget'
PLAN=json.loads((ROOT/'analysis/plans/round3_budget.json').read_text())


def observation_mask(geo):
    seen=set();mask=np.zeros(geo['nrows'],dtype=bool)
    for counter,ix in enumerate(geo['groups']):
        for i in ix:
            oid=int(geo['ids'][i]);mask[i]=(counter%10==0 or oid not in seen);seen.add(oid)
    return mask


def sparse_forward(q,geo,observed,p_stay,prior):
    """At an unobserved row q is NaN and must never enter the emission update."""
    state=np.full((q.shape[0],len(geo['unique_ids'])),prior,dtype=float)
    seen=np.zeros(len(geo['unique_ids']),dtype=bool)
    last_frame=np.zeros(len(geo['unique_ids']),dtype=int)
    out=np.empty(q.shape,dtype=float)
    for ix in geo['groups']:
        cols=geo['columns'][ix];frame=int(geo['frames'][ix[0]])
        gap=frame-last_frame[cols]
        post=.5+(state[:,cols]-.5)*np.power(2*p_stay-1,gap)[None,:]
        post[:,~seen[cols]]=prior
        update=observed[ix]
        if np.any(update):
            p0=post[:,update];current=q[:,ix[update]]
            numerator=p0*current
            post[:,update]=numerator/(numerator+(1-p0)*(1-current))
        out[:,ix]=post;state[:,cols]=post
        seen[cols]=True;last_frame[cols]=frame
    return out


def load_sparse(d):
    obs=load_observations(ROOT/'analysis/runs/R17_h2/raw_scores')
    q={};masks={};frame_samples=video_samples=0;maxdiff=0.
    native_scores=d.native()
    for seq,ns in d.by_seq.items():
        tr=d.tracks[seq];g=d.geo[seq];mask=observation_mask(g);masks[seq]=mask
        keys=[(int(tr[i,0]),int(tr[i,1])) for i in np.flatnonzero(mask)]
        qq=np.full(d.y[seq].shape,np.nan,dtype=float)
        for j,name in enumerate(ns):
            observed=obs[name]
            assert set(observed)==set(keys),(name,'native observation schedule mismatch')
            baseline=replay(tr,observed)
            diff=float(np.max(np.abs(baseline-native_scores[seq][j])))
            maxdiff=max(maxdiff,diff)
            if diff>1e-12:raise RuntimeError(f'STOP: V0 mismatch {name}: {diff}')
            for i,key in zip(np.flatnonzero(mask),keys):
                p=float(observed[key]['frame']);frame_samples+=1
                if .2<=p<.8:
                    p=float(observed[key]['video']);video_samples+=1
                qq[j,i]=p
        assert np.all(np.isfinite(qq[:,mask])) and np.all(np.isnan(qq[:,~mask]))
        q[seq]=qq
    receipt={'complete':True,'V0_max_difference':maxdiff,'frame_candidate_observations':frame_samples,
             'video_candidate_observations':video_samples,'R22_read':False,
             'rows_total':sum(x.size for x in d.y.values()),
             'observations_per_sequence':{s:int(masks[s].sum())*len(d.by_seq[s]) for s in masks}}
    save_json(OUT/'observation_receipt.json',receipt)
    print('Sparse observation gate:',json.dumps(receipt),flush=True)
    return q,masks,receipt


def fit_loso(d,q,masks):
    folder=OUT/'LOSO';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'parameters.json'
    if path.exists() and json.loads(path.read_text()).get('complete'):return json.loads(path.read_text())
    folds=[]
    for held in PLAN['sequences'] if 'sequences' in PLAN else native.PLAN['sequences']:
        dest=folder/f'fold_{held}.json'
        if dest.exists() and json.loads(dest.read_text()).get('complete'):
            folds.append(json.loads(dest.read_text()));continue
        training=[s for s in d.by_seq if s!=held]
        observed_q=np.concatenate([q[s][:,masks[s]].ravel() for s in training])
        observed_y=np.concatenate([d.y[s][:,masks[s]].ravel() for s in training])
        train_rows=sum(d.y[s].size for s in training)
        train_pos=sum(int(d.y[s].sum()) for s in training)
        prior=train_pos/train_rows
        fit=minimize_scalar(lambda b:native.bce(observed_q,observed_y,float(b)),bounds=(-8.,8.),
                            method='bounded',options={'xatol':1e-8})
        assert fit.success,fit
        bias=float(fit.x)
        calibrated={s:native.emission(q[s],bias) for s in training}
        grid=[]
        for stay in PLAN['LOSO']['p_stay_grid']:
            pp={s:sparse_forward(calibrated[s],d.geo[s],masks[s],stay,prior) for s in training}
            for threshold in PLAN['LOSO']['posterior_threshold_grid']:
                tp=fp=fn=0
                for s in training:
                    pred=pp[s]>=threshold;y=d.y[s]
                    tp+=int(np.sum(pred & y));fp+=int(np.sum(pred & ~y));fn+=int(np.sum(~pred & y))
                grid.append({'held_out':held,'bias':bias,'p_stay':stay,'posterior_threshold':threshold,
                             'tp':tp,'fp':fp,'fn':fn,'micro_F1':2*tp/(2*tp+fp+fn)})
        chosen=min(grid,key=lambda r:(-r['micro_F1'],r['p_stay'],abs(r['posterior_threshold']-.5),r['posterior_threshold']))
        result={'complete':True,'held_out_sequence':held,'training_sequences':training,
                'training_rows':train_rows,'training_positive_rows':train_pos,
                'calibration_observed_rows':len(observed_q),'new_ID_prior':prior,
                'fitted_scalars':3,'temperature':1.,'bias':bias,'p_stay':chosen['p_stay'],
                'posterior_threshold':chosen['posterior_threshold'],'training_micro_F1':chosen['micro_F1'],
                'training_BCE_before':native.bce(observed_q,observed_y),'training_BCE_after':float(fit.fun)}
        with (folder/f'training_grid_{held}.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(grid[0]));w.writeheader();w.writerows(grid)
        save_json(dest,result);folds.append(result)
        print('Delta10 LOSO fold:',json.dumps(result),flush=True)
    result={'complete':True,'seed':2025,'folds':folds,'fit_on_full_val':False,'max_fitted_scalars':3}
    save_json(path,result);return result


def build_scores(d,q,masks,folds,variant):
    fixed=variant.endswith('_fixed');scores={}
    out=OUT/variant;out.mkdir(parents=True,exist_ok=True)
    by_held={r['held_out_sequence']:r for r in folds['folds']}
    for seq in d.by_seq:
        fold=by_held[seq]
        p=PLAN['fixed'] if fixed else fold
        qq=native.emission(q[seq],p['bias'])
        post=sparse_forward(qq,d.geo[seq],masks[seq],p['p_stay'],fold['new_ID_prior'])
        scores[seq]=(post>=p['posterior_threshold']).astype(float)
        np.savez_compressed(out/f'posterior_{seq}.npz',names=np.asarray(d.by_seq[seq]),posterior=post,
                            threshold=p['posterior_threshold'],observed=masks[seq])
    return scores


def tables_and_report(d,result):
    previous=json.loads((ROOT/'analysis/runs/R50_temporal/result.json').read_text())
    old=previous['variants'];new=result['variants']
    records=[]
    ordered=[('V0',10),('V1',10),('V2',10),('V3',1),('V4_fixed',1),('V4_LOSO',1),
             ('V5_fixed',1),('V5_LOSO',1),('V4_D10_fixed',10),('V4_D10_LOSO',10)]
    for variant,delta in ordered:
        r=(old if variant in old else new)[variant]
        records.append({'variant':variant,'observation_delta':delta,
            **{k:r['metrics'][k] for k in ['HOTA','DetA','AssA','DetPr','DetRe']},
            'gain_HOTA_vs_V0':r['metrics']['HOTA']-old['V0']['metrics']['HOTA']})
    with (OUT/'budget_comparison.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    robustness=[]
    for variant in ['V4_fixed','V4_LOSO','V4_D10_fixed','V4_D10_LOSO']:
        r=(old if variant in old else new)[variant]
        for seq in d.by_seq:
            h=r['per_sequence'][seq]['HOTA'];base=old['V0']['per_sequence'][seq]['HOTA']
            robustness.append({'variant':variant,'sequence':seq,'V0_HOTA':base,'HMM_HOTA':h,'delta_HOTA':h-base})
    with (OUT/'sequence_gains.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(robustness[0]));w.writeheader();w.writerows(robustness)
    r49=json.loads((ROOT/'analysis/runs/R49_self_lock/result.json').read_text())
    rc=result['observations']
    best=max(new,key=lambda v:new[v]['gain_HOTA'])
    gain=new[best]['gain_HOTA'];trigger=gain>=2
    decision={'best_sparse_variant':best,'sparse_gain_HOTA':gain,'sparse_HMM_reaches_plus2':trigger,
              'full_frame_cache_authorized':False,'GPU_started':False,
              'next_step':'estimate_native_Delta10_trace_runtime; auto-run only if<8h' if trigger else 'ask_user_before_fullframe_cache'}
    save_json(OUT/'GPU_decision.json',decision)
    lines=['## R52：用户续补——观测预算对齐、稳健性和机制核对','',
        '本节按用户新指令追加；保留原 R50 的全部冻结版本和结果。本节新变体在结果前登记于 [round3_budget.json](plans/round3_budget.json)，只读 R17 的真实 Δ10 观测，未读取 R22 的跳过帧概率。此前 R51 的“完整缓存等待批准”是历史方案；当前后续行动以本节的新条件授权为准。','',
        '### 1. 推理预算对齐','',
        '原 R50 的 V0/V1/V2 用 **Δ10**；V3、V4_fixed/V4_LOSO、V5_fixed/V5_LOSO 均用 **Δ1**。因此 +5.147 是逐帧观测下的改善，不能当作同推理预算的收益。原生 Δ10 按非空候选帧计数，每 10 帧验证全部候选，新 ID 额外即时验证。','',
        f'Δ10 版本共使用 **{rc["frame_candidate_observations"]:,}** 条 frame 候选观测、其中 **{rc["video_candidate_observations"]:,}** 条调用 video；Δ1 对照使用 2,860,484 条 frame、801,329 条 video。这里计数的是候选观测，非 GPU batch 数。读取本轮 R17 后重新检查 V0，最大差仍为 **{rc["V0_max_difference"]}**。','',
        '新增 HMM：只有实际推理行才施加发射似然；中间帧只做状态转移预测，禁止把上次发射分数反复当作新证据。跨可见性间隔用实际图像帧数的转移矩阵幂。固定版 b=0/T=1/stay=.95/τ=.5 不调参；LOSO 版在每个训练三序列上重新拟合 b/stay/τ（≤3 标量），b 的 BCE 仅用真实观测，HMM 选择目标仍是训练三序列全部可见候选帧的 micro-F1，未用完整 val 选参。','',
        '| 版本 | 观测 Δ | HOTA | DetA | AssA | DetPr | DetRe | 相对 V0 ΔHOTA |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in records:
        lines.append('| '+' | '.join([r['variant'],str(r['observation_delta']),
            *[f'{r[k]:.3f}' for k in ['HOTA','DetA','AssA','DetPr','DetRe','gain_HOTA_vs_V0']]])+' |')
    lines+=['','[预算对齐主表](runs/R52_budget/budget_comparison.csv) · [全部结果](runs/R52_budget/result.json) · [真实观测及 V0 校验](runs/R52_budget/observation_receipt.json)','',
        '| 留出序列 | 训练先验 | 稀疏观测校准偏置 | stay | τ |',
        '|---|---:|---:|---:|---:|']
    for f in result['LOSO']['folds']:
        lines.append(f'| {f["held_out_sequence"]} | {100*f["new_ID_prior"]:.2f}% | {f["bias"]:.6f} | {f["p_stay"]} | {f["posterior_threshold"]} |')
    lines+=['','### 2. 四序列稳健性','',
        '| 序列 | V0 HOTA | Δ1 固定 HMM ΔHOTA | Δ1 LOSO HMM ΔHOTA | Δ10 固定 HMM ΔHOTA | Δ10 LOSO HMM ΔHOTA |',
        '|---|---:|---:|---:|---:|---:|']
    for seq in d.by_seq:
        by_variant={r['variant']:r for r in robustness if r['sequence']==seq}
        lines.append('| '+' | '.join([seq,f'{old["V0"]["per_sequence"][seq]["HOTA"]:.3f}',
            *[f'{by_variant[v]["delta_HOTA"]:.3f}' for v in ['V4_fixed','V4_LOSO','V4_D10_fixed','V4_D10_LOSO']]])+' |')
    lines+=['',f'四折未见序列输出按官方 HOTA.combine_sequences 合并：**Δ10 LOSO HOTA={new["V4_D10_LOSO"]["metrics"]["HOTA"]:.3f}，ΔHOTA={new["V4_D10_LOSO"]["gain_HOTA"]:+.3f}**；原 Δ1 LOSO 为 70.210（+4.979）。这不是四序列 HOTA 的简单平均。逐序列变化全部保留，不因下降而删除序列。','',
        '[四序列增量 CSV](runs/R52_budget/sequence_gains.csv) · [Δ10 逐折参数](runs/R52_budget/LOSO/parameters.json)','',
        '### 3. 自锁机制核对','',
        f'R49 共 {r49["events"]} 个精确真→假事件。按**均值曲线**，原始 frame p 在 **offset6** 首次跌破 γ=.6；最终分数无论 Δ10 还是 Δ1，在 0–15 帧内的均值均未跌破。不能把“未跌破”写成有限延迟。','',
        '| 逐事件首次跌破 | 实际观察到跌破/事件数 | 平均延迟（仅观察到者） | 中位延迟（仅观察到者） |',
        '|---|---:|---:|---:|']
    for label,stat in [('原始 frame p',r49['raw_frame_latency']),('最终TCP+TRP10',r49['delta']['10']['final_latency']),
                       ('最终TCP+Δ1',r49['delta']['1']['final_latency'])]:
        lines.append(f'| {label} | {stat["observed_crossings"]}/{stat["events"]} | {stat["mean_observed"]:.3f}帧 | {stat["median_observed"]:.3f}帧 |')
    lines+=['','两者均观察到跌破的配对事件中，最终−原始的平均延迟为 Δ10 **4.179 帧**、Δ1 **2.154 帧**；原始已跌破但最终在可见随访内仍未跌破分别为 302/498、153/498。锁存期原始 p∈[.1,.6) 的比例分别 67.42%、61.77%。删失和 video 条件观测均已显式保留，支持自反馈存在，但不将所有响应延迟归因 TCP。','',
        f'两个同 Δ10 观测的直接干预：**V1（去 TCP）HOTA={old["V1"]["metrics"]["HOTA"]:.3f}（+{old["V1"]["gain_HOTA"]:.3f}）；V2（历史改读原始 q）HOTA={old["V2"]["metrics"]["HOTA"]:.3f}（+{old["V2"]["gain_HOTA"]:.3f}）**。官方代码 [1014–1017 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1014) 把最终加分写回历史，[1019–1023 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1019) 又写回 TRP 缓存。','',
        '### R51 新决策','',
        (f'预算对齐后最佳 {best} 获得 **+{gain:.3f} HOTA**，达到用户规定的 +2 门槛。下一步仅估算实际 TempRMOT* 的 **Δ10 原生带 trace 推理一次**，低于8小时则按用户本次明确授权执行；不启动8.41小时全帧缓存。' if trigger else
         f'预算对齐后最佳 {best} 仅 **+{gain:.3f} HOTA**，未达+2；按用户规则不启动 GPU，需另行询问完整8.41小时全帧缓存。'),
        '',f'**预算对齐结论：**只改时序层且保持 Δ10 原生观测，{best} 可回收 {gain:.3f} HOTA；Δ1 的原 +5.147 结果另列，不能混作同预算结论。','']
    text='\n'.join(lines)
    (ROOT/'analysis/REPORT_round3_budget.md').write_text(text)
    report=ROOT/'analysis/REPORT_round3.md'
    base=report.read_text().split('\n## R52：用户续补')[0]
    base=base.replace('**尚未启动 GPU，等待用户批准。**依据本轮 R51 的显式授权要求，且估计超过 8 小时，先交付以上 CPU 结果。',
        '**历史状态：完整全帧缓存未启动。用户随后要求先做 R52 预算复查，并给出新的条件授权，当前决策见末尾 R52。**')
    report.write_text(base.rstrip()+'\n\n'+text)
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R52_CPU_complete':True,'R52_best_sparse_variant':best,'R52_sparse_gain_HOTA':gain,
                  'R51_next_action':decision['next_step'],'R51_fullframe_cache_authorized':False})
    save_json(ROOT/'analysis/round3_state.json',state)
    print('R52 decision:',json.dumps(decision),flush=True)


def main():
    assert not os.environ.get('CUDA_VISIBLE_DEVICES',''),'CPU only'
    OUT.mkdir(parents=True,exist_ok=True);np.random.seed(2025)
    native.require_gate();start=time.monotonic()
    d=native.Dataset(with_scores=False)
    q,masks,receipt=load_sparse(d)
    folds=fit_loso(d,q,masks)
    original=json.loads((ROOT/'analysis/runs/R50_temporal/result.json').read_text())
    v0=original['variants']['V0'];variants={}
    native.OUT=OUT
    for variant in PLAN['variants']:
        path=OUT/variant/'result.json'
        if path.exists() and json.loads(path.read_text()).get('complete'):
            result=json.loads(path.read_text())
        else:
            scores=build_scores(d,q,masks,folds,variant)
            native.write_predictions(d,variant,scores)
            result=native.evaluate_variant(d,variant,scores)
        result['observation_delta']=10
        result['non_observation_update']='transition only; no emission'
        result['gain_HOTA']=result['metrics']['HOTA']-v0['metrics']['HOTA']
        result['recovered_oracle_fraction']=result['gain_HOTA']/32.488
        for cat in 'ABCDEFGH':
            h=result['categories'][cat]['HOTA_metrics']['HOTA'];h0=v0['categories'][cat]['HOTA_metrics']['HOTA']
            result['categories'][cat]['delta_HOTA_vs_V0']=h-h0 if h is not None else None
        save_json(path,result);variants[variant]=result
    result={'complete':True,'seed':2025,'reference':'relative_local_GT_candidates',
            'observations':receipt,'LOSO':folds,'variants':variants,'seconds':time.monotonic()-start,
            'frozen_plan':'analysis/plans/round3_budget.json','GPU_started':False}
    save_json(OUT/'result.json',result)
    tables_and_report(d,result)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        save_json(OUT/'failure.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        raise
