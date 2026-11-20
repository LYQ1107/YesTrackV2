#!/usr/bin/env python3
"""Replay preregistered temporal rules on one native TempRMOT* Delta10 trace."""
import csv
import json
import os
from pathlib import Path
import time
import traceback

import numpy as np

import round3 as temporal
from round3_budget import observation_mask,sparse_forward
from replay import load_observations,replay
from common import (combine_hota,config,confusion,hota_rows,mot,official_eval,
                    run_logged,save_json,summary)

c=config();ROOT=Path(c['task_root']);OUT=ROOT/'analysis/runs/R53_actual_temporal'
NATIVE=ROOT/'analysis/runs/R53_native_trace'
PLAN=json.loads((ROOT/'analysis/plans/round3_actual_native_trace.json').read_text())
TAG='default_t0p60'


class ActualData:
    def __init__(self):
        self.labels=json.loads((ROOT/'analysis/labels/expressions.json').read_text())
        self.meta={r['name']:r for r in self.labels}
        self.by_seq={s:[r['name'] for r in self.labels if r['sequence']==s] for s in c['val_sequences']}
        self.tracks={};self.geo={};self.native={};self.y={};self.empty={}
        baseline=json.loads((ROOT/'analysis/local_baseline.json').read_text())
        self.old_native={};self.row_total=0
        for seq,ns in self.by_seq.items():
            native_scores=[];old_scores=[];ys=[];empty=[];canonical=None
            for name in ns:
                expr=name.split('__',1)[1]
                p=mot(NATIVE/'predictions'/seq/expr/'predict_with_conf.txt')
                old=mot(Path(baseline['predictions'])/seq/expr/'predict_with_conf.txt')
                assert np.array_equal(p[:,:6],old[:,:6]),(name,'candidate geometry differs from frozenR09')
                if canonical is None:canonical=p.copy()
                assert np.array_equal(p[:,:6],canonical[:,:6]),(name,'candidate geometry differs by expression')
                labels=np.load(ROOT/'analysis/runs/R20_oracles/candidate_labels'/seq/f'{expr}.npz')
                assert len(labels['y'])==len(p)
                ys.append(labels['y']);native_scores.append(p[:,6]);old_scores.append(old[:,6])
                e=np.ones(self.meta[name]['sequence_frames']+1,dtype=bool);e[0]=False
                gt=mot(Path(c['released_v2_gt'])/name/'gt/gt.txt');e[gt[:,0].astype(int)]=False
                empty.append(e);self.row_total+=len(p)
            self.tracks[seq]=canonical;self.geo[seq]=temporal.geometry(canonical)
            self.native[seq]=np.stack(native_scores);self.old_native[seq]=np.stack(old_scores)
            self.y[seq]=np.stack(ys).astype(bool);self.empty[seq]=np.stack(empty)
        assert self.row_total==PLAN['candidate_rows'] and len(self.labels)==PLAN['expressions']


def load_and_gate(d):
    observed=load_observations(NATIVE/'raw_scores')
    assert set(observed)==set(d.meta),'incomplete trace expression coverage'
    q={};masks={};maxdiff=old_diff=0.;changed=frame_n=video_n=0;checks=[]
    for seq,ns in d.by_seq.items():
        tr=d.tracks[seq];mask=observation_mask(d.geo[seq]);masks[seq]=mask
        rows=np.flatnonzero(mask);keys=[(int(tr[i,0]),int(tr[i,1])) for i in rows]
        scores=np.full(d.native[seq].shape,np.nan)
        for j,name in enumerate(ns):
            obs=observed[name];assert set(obs)==set(keys),(name,'native observation schedule mismatch')
            reconstructed=replay(tr,obs)
            diff=float(np.max(np.abs(reconstructed-d.native[seq][j])))
            maxdiff=max(maxdiff,diff)
            if diff>1e-12:
                save_json(OUT/'gate.json',{'complete':False,'stop':True,'name':name,'difference':diff})
                raise RuntimeError(f'STOP: actual native V0 trace replay mismatch {name}: {diff}')
            old_difference=float(np.max(np.abs(d.native[seq][j]-d.old_native[seq][j])))
            old_diff=max(old_diff,old_difference)
            changed+=int(np.sum((d.native[seq][j]>=.6)!=(d.old_native[seq][j]>=.6)))
            for i,key in zip(rows,keys):
                p=float(obs[key]['frame']);frame_n+=1
                if .2<=p<.8:p=float(obs[key]['video']);video_n+=1
                scores[j,i]=p
            checks.append({'name':name,'rows':len(tr),'native_replay_max_difference':diff,
                           'R09_max_difference':old_difference})
        assert np.isfinite(scores[:,mask]).all() and np.isnan(scores[:,~mask]).all()
        q[seq]=scores
        np.savez_compressed(OUT/f'sparse_observations_{seq}.npz',names=np.asarray(ns),row_index=rows,q=scores[:,mask])
    with (OUT/'gate_per_expression.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(checks[0]));w.writeheader();w.writerows(checks)
    receipt={'complete':True,'expressions':len(checks),'candidate_rows':d.row_total,'native_max_difference':maxdiff,
             'R09_max_difference':old_diff,'R09_gamma06_changed_decisions':changed,
             'frame_candidate_observations':frame_n,'video_candidate_observations':video_n,
             'formatting':'R36 Python float(f\'{p:.6f}\')','R22_full_cache_used':False}
    save_json(OUT/'gate.json',receipt)
    print('Actual native gate:',json.dumps(receipt),flush=True)
    return observed,q,masks,receipt


def scores_for(d,observed,q,masks,variant):
    if variant=='Actual_V0':return d.native
    if variant in ['Actual_V1','Actual_V2']:
        return {s:np.stack([temporal.temporal_variant(d.tracks[s],d.geo[s],observed[n],variant[-2:]) for n in ns])
                for s,ns in d.by_seq.items()}
    folds={r['held_out_sequence']:r for r in json.loads((ROOT/'analysis/runs/R52_budget/LOSO/parameters.json').read_text())['folds']}
    fixed=variant.endswith('fixed');out={};folder=OUT/variant;folder.mkdir(parents=True,exist_ok=True)
    for seq in d.by_seq:
        fold=folds[seq];p=PLAN['fixed_HMM'] if fixed else fold
        post=sparse_forward(temporal.emission(q[seq],p['bias']),d.geo[seq],masks[seq],
                            p['p_stay'],fold['new_ID_prior'])
        out[seq]=(post>=p['posterior_threshold']).astype(float)
        np.savez_compressed(folder/f'posterior_{seq}.npz',names=np.asarray(d.by_seq[seq]),posterior=post,
                            threshold=p['posterior_threshold'],observed=masks[seq])
    return out


def evaluate(d,variant,scores,native_predictions=None):
    folder=OUT/variant;folder.mkdir(parents=True,exist_ok=True)
    p=folder/'result.json'
    if p.exists() and json.loads(p.read_text()).get('complete'):return json.loads(p.read_text())
    if variant=='Actual_V0' or native_predictions is not None:
        dest=folder/'predictions'
        if not dest.exists():dest.symlink_to(native_predictions or NATIVE/'predictions',target_is_directory=True)
    else:
        for seq,ns in d.by_seq.items():
            fields=d.tracks[seq][:,:6].astype(int)
            for j,name in enumerate(ns):
                file=folder/'predictions'/seq/name.split('__',1)[1]/'predict_with_conf.txt'
                file.parent.mkdir(parents=True,exist_ok=True)
                with file.open('w') as f:
                    f.writelines(','.join(map(str,row))+f',{score:.6f}\n' for row,score in zip(fields,scores[seq][j]))
    for seq,score in scores.items():np.savez_compressed(folder/f'scores_{seq}.npz',names=np.asarray(d.by_seq[seq]),scores=score)
    command=official_eval(c,folder/'predictions',folder/'evaluation',[.6])
    save_json(folder/'evaluation_command.json',{'argv':command,'cwd':str(ROOT/c['upstream']),
              'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2'})
    run_logged(command,ROOT/c['upstream'],folder/'trackeval.log')
    metric,details=hota_rows(folder/'evaluation/tracker'/TAG/'pedestrian_detailed.csv',c)
    assert set(details)==set(d.meta)
    total=combine_hota(metric,details);conf={};empty_n=empty_alarm=0
    for seq,ns in d.by_seq.items():
        frames=d.geo[seq]['frames']
        for j,name in enumerate(ns):
            pred=scores[seq][j]>=.6
            conf[name]=confusion(d.y[seq][j],scores[seq][j],.6)
            empty_n+=int(d.empty[seq][j].sum())
            empty_alarm+=len(np.unique(frames[pred & d.empty[seq][j,frames]]))
    perseq={s:combine_hota(metric,{n:details[n] for n in ns}) for s,ns in d.by_seq.items()}
    categories={cat:{'expressions':sum(cat in r['labels'] for r in d.labels),
        'metrics':combine_hota(metric,{r['name']:details[r['name']] for r in d.labels if cat in r['labels']})}
        for cat in 'ABCDEFGH'}
    result={'complete':True,'seed':2025,'variant':variant,'candidate_type':'actual TempRMOT*',
            'reference':'relative paired native TempRMOT* Delta10 baseline, not GT-candidate H2',
            'observation_delta':10,'gamma':.6,'metrics':total,'per_sequence':perseq,'categories':categories,
            'conditional_referring':temporal.aggregate_conf(list(conf.values())),
            'conditional_referring_definition':'R20 fixed Hungarian-IoU>=.5 GT assignments; unmatched candidates are negative; misses with no candidate enter HOTA, not this conditional P/R',
            'empty_GT_frame_false_alarm':{'denominator':empty_n,'false_alarm_frames':empty_alarm,'rate':empty_alarm/empty_n},
            'evaluation_command':command,'actual_candidate_parameter_fits':0,
            'frozen_parameter_source':'analysis/runs/R52_budget/LOSO/parameters.json' if variant.endswith('LOSO') else None}
    save_json(p,result)
    print('Actual evaluation:',variant,json.dumps({'metrics':total,'conditional_referring':result['conditional_referring']}),flush=True)
    return result


def report(result):
    variants=result['variants'];v0=variants['Actual_V0'];gate=result['native_gate']
    rows=[]
    for v,r in variants.items():
        rows.append({'variant':v,**{k:r['metrics'][k] for k in ['HOTA','DetA','AssA','DetPr','DetRe']},
                     'gain_HOTA':r['gain_HOTA'],**{k:r['conditional_referring'][k] for k in ['precision','recall','f1']},
                     'empty_frame_FAR':r['empty_GT_frame_false_alarm']['rate']})
    with (OUT/'main_table.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (OUT/'sequence_gains.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['sequence',*[v+'_HOTA' for v in variants],*[v+'_gain' for v in variants]])
        for s in c['val_sequences']:
            w.writerow([s,*[r['per_sequence'][s]['HOTA'] for r in variants.values()],
                        *[r['per_sequence'][s]['HOTA']-v0['per_sequence'][s]['HOTA'] for r in variants.values()]])
    with (OUT/'category_gains.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['category','expressions',*[v+'_gain' for v in variants]])
        for cat in 'ABCDEFGH':
            h0=v0['categories'][cat]['metrics']['HOTA']
            w.writerow([cat,v0['categories'][cat]['expressions'],
                *[r['categories'][cat]['metrics']['HOTA']-h0 if h0 is not None else None for r in variants.values()]])
    inference=json.loads((NATIVE/'inference_result.json').read_text())
    h=variants['Actual_HMM10_LOSO'];fixed=variants['Actual_HMM10_fixed']
    lines=['## R53：实际 TempRMOT* 的 Δ10 原生 trace 与离线决策','',
        '用户在 R52 后给出条件授权：若 Δ10 HMM≥+2 且估计低于8小时，可直接执行。R52 LOSO 已+4.250，因此只运行一次原生 Δ10 推理并被动记录 frame/video，未运行逐帧 GPU 缓存。运行前冻结 [R53 方案](plans/round3_actual_native_trace.json)；官方源码、权重、TCP/TRP 和种子不改，模型推理只产生原生输出，所有替代决策均在 GPU 推理完成后离线执行。','',
        f'资源为物理 GPU5/7 两张；启动前按 R09 同候选实测2.209小时及 R22 共享GPU实测最慢阶段放大3.247倍，估计7.172小时，低于8小时。实际原生推理耗时 **{inference["seconds"]/3600:.3f}小时**。','',
        f'完整覆盖862条表达式、{gate["candidate_rows"]:,}行；trace 记录 frame 候选观测 {gate["frame_candidate_observations"]:,} 条、video {gate["video_candidate_observations"]:,} 条。新原生 V0 逐值重放最大差 **{gate["native_max_difference"]}**。与 R09 历史输出最大分数差 {gate["R09_max_difference"]:.6f}，γ=.6 判定变化 {gate["R09_gamma06_changed_decisions"]:,} 行；下表增量全部以本次配对 V0 为准，历史本地 HOTA40.427仅作追踪。','',
        'HMM固定版保持b0/stay.95/τ.5；LOSO版直接转移 R52 中每个被测序列对应的训练三序列 b/stay/τ 和新ID先验。实际候选上**拟合参数数目为0**，中间帧仅转移。V1/V2也只重放本次同一份观测，未产生新GPU调用。','',
        '| 实际候选版本（全部 Δ10） | HOTA | DetA | AssA | DetPr | DetRe | ΔHOTA | 条件 P | 条件 R | 条件 F1 | 空帧误报率 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append('| '+' | '.join([row['variant'],*[f'{row[k]:.3f}' for k in ['HOTA','DetA','AssA','DetPr','DetRe','gain_HOTA']],
            *[f'{100*row[k]:.2f}%' for k in ['precision','recall','f1','empty_frame_FAR']]])+' |')
    lines+=['','条件P/R/F1沿用R20：候选与GT逐帧Hungarian最大IoU、IoU≥.5后按表达式赋值；未被任何候选覆盖的GT漏检由HOTA计算，因此不能与GT候选上的semantic P/R混用。','',
        '| 序列 | 实际 V0 HOTA | 固定 HMM ΔHOTA | 转移 LOSO HMM ΔHOTA | V1 ΔHOTA | V2 ΔHOTA |',
        '|---|---:|---:|---:|---:|---:|']
    for seq in c['val_sequences']:
        b=v0['per_sequence'][seq]['HOTA']
        lines.append('| '+' | '.join([seq,f'{b:.3f}',*[f'{variants[v]["per_sequence"][seq]["HOTA"]-b:+.3f}'
            for v in ['Actual_HMM10_fixed','Actual_HMM10_LOSO','Actual_V1','Actual_V2']]])+' |')
    lines+=['',f'**实际候选结论：**不改模型、同 Δ10 观测，固定 HMM 回收 {fixed["gain_HOTA"]:+.3f} HOTA；从 GT 三序列训练折直接转移的 LOSO HMM 回收 **{h["gain_HOTA"]:+.3f} HOTA**（{v0["metrics"]["HOTA"]:.3f}→{h["metrics"]["HOTA"]:.3f}）。GT 候选的+4.250与实际候选的增量分开报告；未据实际 val 再调参数。','',
        '[实际候选主表](runs/R53_actual_temporal/main_table.csv) · [逐序列](runs/R53_actual_temporal/sequence_gains.csv) · [类别内增量](runs/R53_actual_temporal/category_gains.csv) · [逐值门槛与历史漂移](runs/R53_actual_temporal/gate.json) · [全部结果](runs/R53_actual_temporal/result.json)','']
    text='\n'.join(lines)
    (ROOT/'analysis/REPORT_round3_actual.md').write_text(text)
    report=ROOT/'analysis/REPORT_round3.md'
    base=report.read_text().split('\n## R53：实际 TempRMOT*')[0]
    report.write_text(base.rstrip()+'\n\n'+text)
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R51_GPU_started':True,'R51_awaiting_approval':False,'R53_GPU_complete':True,
                  'R53_actual_V0_HOTA':v0['metrics']['HOTA'],'R53_actual_LOSO_HOTA':h['metrics']['HOTA'],
                  'R53_actual_LOSO_gain_HOTA':h['gain_HOTA'],'R51_fullframe_cache_authorized':False,
                  'R53_native_max_difference':gate['native_max_difference'],'R51_next_action':'complete'})
    save_json(ROOT/'analysis/round3_state.json',state)
    print('Actual report complete:',json.dumps(state),flush=True)


def main():
    assert not os.environ.get('CUDA_VISIBLE_DEVICES',''),'CPU replay requires no GPU'
    OUT.mkdir(parents=True,exist_ok=True);start=time.monotonic();np.random.seed(2025)
    d=ActualData();observed,q,masks,gate=load_and_gate(d)
    variants={}
    for variant in PLAN['frozen_offline_variants']:
        path=OUT/variant/'result.json'
        if path.exists() and json.loads(path.read_text()).get('complete'):r=json.loads(path.read_text())
        else:r=evaluate(d,variant,scores_for(d,observed,q,masks,variant))
        variants[variant]=r
    baseline=variants['Actual_V0']['metrics']['HOTA']
    for variant,r in variants.items():
        r['gain_HOTA']=r['metrics']['HOTA']-baseline
        save_json(OUT/variant/'result.json',r)
    result={'complete':True,'seed':2025,'native_gate':gate,'variants':variants,
            'actual_candidate_parameter_fits':0,'seconds':time.monotonic()-start,
            'reference':'relative paired native actual TempRMOT* Delta10 baseline'}
    save_json(OUT/'result.json',result);report(result)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        save_json(OUT/'failure.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        raise
