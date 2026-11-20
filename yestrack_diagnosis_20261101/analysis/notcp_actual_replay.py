#!/usr/bin/env python3
"""Native noTCP V1 and two HMMs; full actual-candidate sequence LOSO, no full-val tuning."""
import csv
import json
import os
from pathlib import Path
import time
import traceback

import numpy as np
import actual_temporal_replay as actual
import round3 as temporal
import round3_budget as budget
from common import combine_hota,config,hota_rows,save_json
from replay import load_observations

c=config();ROOT=Path(c['task_root']);OUT=ROOT/'analysis/runs/R55_notcp_actual'
NATIVE=ROOT/'analysis/runs/R55_notcp_native'
PLAN=json.loads((ROOT/'analysis/plans/round3_actual_notcp.json').read_text())


def load_trace(d):
    observed=load_observations(NATIVE/'raw_scores')
    assert set(observed)==set(d.meta),'Incomplete native noTCP trace'
    q={};masks={};maximum=0.;frame_n=video_n=0;per_expression=[]
    for seq,names in d.by_seq.items():
        tr=d.tracks[seq];g=d.geo[seq];mask=budget.observation_mask(g);masks[seq]=mask
        rows=np.flatnonzero(mask);keys=[(int(tr[i,0]),int(tr[i,1])) for i in rows]
        a=np.full(d.native[seq].shape,np.nan)
        for j,name in enumerate(names):
            obs=observed[name];assert set(obs)==set(keys),(name,'observation schedule mismatch')
            replayed=temporal.temporal_variant(tr,g,obs,'V1')
            diff=float(np.max(np.abs(replayed-d.native[seq][j])));maximum=max(maximum,diff)
            if diff>1e-12:raise RuntimeError(f'STOP: native noTCP V1 replay mismatch {name}: {diff}')
            for i,key in zip(rows,keys):
                p=float(obs[key]['frame']);frame_n+=1
                if .2<=p<.8:p=float(obs[key]['video']);video_n+=1
                a[j,i]=p
            per_expression.append({'name':name,'rows':len(tr),'maximum_V1_replay_difference':diff})
        assert np.isfinite(a[:,mask]).all() and np.isnan(a[:,~mask]).all()
        q[seq]=a
        np.savez_compressed(OUT/f'observations_{seq}.npz',names=np.asarray(names),row_index=rows,q=a[:,mask])
    with (OUT/'gate_per_expression.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(per_expression[0]));w.writeheader();w.writerows(per_expression)
    gate={'complete':True,'native_V1_maximum_difference':maximum,'expressions':len(d.meta),
          'candidate_rows':d.row_total,'frame_candidate_observations':frame_n,'video_candidate_observations':video_n,
          'formatting':'R36 Python float(f\'{p:.6f}\')','TCP_enabled':False}
    save_json(OUT/'gate.json',gate);print('Native V1 gate:',json.dumps(gate),flush=True)
    return q,masks,observed,gate


def parity_old_trace(observed):
    """An optional archived-input check, never a replacement for new native outputs."""
    folder=ROOT/'analysis/runs/R53_native_trace'
    old=load_observations(folder/'raw_scores')
    complete={f'{p.parent.parent.name}__{p.parent.name}' for p in (folder/'predictions').glob('*/*/predict_with_conf.txt')}
    differences={'frame':0.,'video':0.};counts={'frame':0,'video':0};key_mismatches=[]
    for name in sorted(complete):
        a=old[name];b=observed[name]
        for mode in ['frame','video']:
            ka={k for k,v in a.items() if mode in v};kb={k for k,v in b.items() if mode in v}
            if ka!=kb:key_mismatches.append({'name':name,'mode':mode,'old_only':len(ka-kb),'new_only':len(kb-ka)})
            for key in ka & kb:
                differences[mode]=max(differences[mode],abs(a[key][mode]-b[key][mode]));counts[mode]+=1
    result={'expressions':len(complete),'compared_observations':counts,'maximum_probability_differences':differences,
            'observation_key_mismatches':key_mismatches,
            'scope':'Archived complete TCP-on queries vs fresh native TCP-off; different physical GPUs, same weights/inputs. This verifies observations where available; source-code ordering is the primary routing argument.'}
    save_json(OUT/'routing_parity_archived.json',result)
    return result


def generate(d,q,masks,parameters,variant):
    fixed=variant=='Actual_HMM10_fixed_noTCP_trace';folder=OUT/variant;folder.mkdir(parents=True,exist_ok=True)
    folds={r['held_out_sequence']:r for r in parameters['folds']};scores={};maximum=0.;checked=0
    for seq in d.by_seq:
        fold=folds[seq];p=PLAN['fixed_HMM'] if fixed else fold
        post=budget.sparse_forward(temporal.emission(q[seq],p['bias']),d.geo[seq],masks[seq],
                                   p['p_stay'],fold['new_ID_prior'])
        scores[seq]=(post>=p['posterior_threshold']).astype(float)
        geo=d.geo[seq]
        for oid in geo['unique_ids']:
            ix=np.flatnonzero(geo['ids']==oid);before,after=ix[:-1],ix[1:]
            select=~masks[seq][after];before=before[select];after=after[select]
            if not len(after):continue
            gap=geo['frames'][after]-geo['frames'][before]
            expected=.5+(post[:,before]-.5)*np.power(2*p['p_stay']-1,gap)[None,:]
            maximum=max(maximum,float(np.max(np.abs(expected-post[:,after]))));checked+=expected.size
        np.savez_compressed(folder/f'posterior_{seq}.npz',names=np.asarray(d.by_seq[seq]),posterior=post,
                            threshold=p['posterior_threshold'],observed=masks[seq])
    assert maximum<1e-14
    save_json(folder/'transition_validation.json',{'complete':True,'unobserved_rows_checked':checked,
        'maximum_transition_prediction_error':maximum,'fresh_emission_only':True})
    return scores


def write_report(result):
    variants=result['variants'];v0=result['V0_R14'];v1=variants[PLAN['variants'][0]]
    lines=['## R55：官方关闭 TCP 的实际候选验证','',
        '按用户指定，新运行直接删除官方 R09 命令的 `--stability_enable`；其他模型/数据/TCP惰性参数/TRP10/video配置/seed均保留。未改官方源码或权重。旧 R53 已终止，不续跑；V0 直接使用 R14 发布权重推荐γ=.6的历史本地结果。','',
        f'新原生 V1 完整覆盖862表达式、1,850,576行；frame候选观测 {result["native_gate"]["frame_candidate_observations"]:,}，video {result["native_gate"]["video_candidate_observations"]:,}。从新 trace 离线重放 V1 的六位输出，最大差 **{result["native_gate"]["native_V1_maximum_difference"]}**。',
        '', 'HMM固定版 b0/T1/stay.95/τ.5。实际候选LOSO版按完整视频留出，在其他三视频的冻结R20 Hungarian-IoU≥.5候选标签上拟合 b/stay/τ（≤3标量），训练目标/网格与R52相同；新ID先验来自训练三视频。中间帧仅转移，没有重复发射；未用完整val选参。此处实际候选LOSO是三训练视频的重新拟合，GT候选R52结果另列。',
        '', '| 实际候选版本 | HOTA | DetA | AssA | DetPr | DetRe | 相对R14 ΔHOTA | 相对原生V1 ΔHOTA |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    methods=[('V0：R14历史基线',v0),*[(v,r) for v,r in variants.items()]]
    rows=[]
    for label,r in methods:
        m=r['metrics'];gain0=m['HOTA']-v0['metrics']['HOTA'];gain1=m['HOTA']-v1['metrics']['HOTA']
        lines.append('| '+' | '.join([label,*[f'{m[k]:.3f}' for k in ['HOTA','DetA','AssA','DetPr','DetRe']],f'{gain0:+.3f}',f'{gain1:+.3f}'])+' |')
        rows.append({'variant':label,**{k:m[k] for k in ['HOTA','DetA','AssA','DetPr','DetRe']},'gain_vs_R14':gain0,'gain_vs_nativeV1':gain1})
    with (OUT/'main_table.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines+=['','| 序列 | R14 V0 | 原生V1 ΔHOTA | 固定HMM ΔHOTA | LOSO HMM ΔHOTA |',
            '|---|---:|---:|---:|---:|']
    for seq in c['val_sequences']:
        h0=v0['per_sequence'][seq]['HOTA']
        lines.append('| '+' | '.join([seq,f'{h0:.3f}',*[f'{r["per_sequence"][seq]["HOTA"]-h0:+.3f}' for r in variants.values()]])+' |')
    lines+=['','LOSO HMM相对原生V1的四序列HOTA差为 '+ '、'.join(
        f'{s} {variants[PLAN["variants"][2]]["per_sequence"][s]["HOTA"]-v1["per_sequence"][s]["HOTA"]:+.3f}'
        for s in c['val_sequences'])+'；四个序列均下降。','',
        '| 实际候选版本 | 条件 P | 条件 R | 条件 F1 | 空GT帧误报率 |',
        '|---|---:|---:|---:|---:|']
    for label,r in variants.items():
        pr=r['conditional_referring'];far=r['empty_GT_frame_false_alarm']
        lines.append('| '+' | '.join([label,*[f'{100*pr[k]:.2f}%' for k in ['precision','recall','f1']],f'{100*far["rate"]:.2f}%'])+' |')
    lines+=['','P/R/F1以R20冻结的Hungarian-IoU≥.5候选标签计算；没有候选覆盖的GT漏检只进入HOTA。三版分母均为1,850,576候选行，空GT帧误报分母237,085。LOSO HMM比V1的精度略高，但召回和F1下降，未复现GT候选上的总体收益。',
        '', '| 类别 | 表达式数 | R14 HOTA | 原生V1 ΔHOTA | 固定HMM ΔHOTA | LOSO HMM ΔHOTA |',
        '|---|---:|---:|---:|---:|---:|']
    category_rows=[]
    for cat in 'ABCDEFGH':
        h0=v0['categories'][cat]['metrics']['HOTA'];n=v1['categories'][cat]['expressions']
        gains=[r['categories'][cat]['metrics']['HOTA']-h0 if h0 is not None else None for r in variants.values()]
        lines.append('| '+' | '.join([cat,str(n),'NA' if h0 is None else f'{h0:.3f}',*['NA' if x is None else f'{x:+.3f}' for x in gains]])+' |')
        category_rows.append({'category':cat,'expressions':n,'R14_HOTA':h0,**{v:g for v,g in zip(variants,gains)}})
    with (OUT/'category_table.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(category_rows[0]));w.writeheader();w.writerows(category_rows)
    lines+=['','这里是类别内HOTA差，类别重叠，不能相加；不是第二轮只替换某类referring的总体oracle ΔHOTA_X。G类无整条GT为空的表达式，记NA。','']
    lines+=['','| 留出序列 | 训练候选正例先验 | b | stay | τ |', '|---|---:|---:|---:|---:|']
    for fold in result['LOSO']['folds']:
        lines.append(f'| {fold["held_out_sequence"]} | {100*fold["new_ID_prior"]:.2f}% | {fold["bias"]:.6f} | {fold["p_stay"]} | {fold["posterior_threshold"]} |')
    inference=json.loads((NATIVE/'inference_result.json').read_text())
    lines+=['',f'本次现场准入估计 {inference["estimated_hours"]:.3f}小时，实际原生推理 {inference["seconds"]/3600:.3f}小时；物理GPU为 {inference["physical_GPUs"]}。启动前资源快照和展开命令已先写 runs.md；没有启动全帧缓存。',
        '', '[完整结果](runs/R55_notcp_actual/result.json) · [主表](runs/R55_notcp_actual/main_table.csv) · [实际候选LOSO参数](runs/R55_notcp_actual/LOSO/parameters.json) · [原生V1逐值门槛](runs/R55_notcp_actual/gate.json) · [旧TCP trace观测配对检查](runs/R55_notcp_actual/routing_parity_archived.json)',
        '', f'**实际候选结论：**原生去TCP的V1相对R14改善 {v1["metrics"]["HOTA"]-v0["metrics"]["HOTA"]:+.3f} HOTA；同份Δ10 noTCP trace上的固定HMM额外 {variants[PLAN["variants"][1]]["metrics"]["HOTA"]-v1["metrics"]["HOTA"]:+.3f}、LOSO HMM额外 {variants[PLAN["variants"][2]]["metrics"]["HOTA"]-v1["metrics"]["HOTA"]:+.3f}。不改模型、只改时序层，本轮预注册的实际候选版本最多收回约0.784 HOTA，来自去TCP；GT候选上的HMM增益未转化为实际收益。GT候选的单参数γ对照只在R54解释，不与实际候选增量混用。','']
    parity=result['archived_routing_parity']
    lines+=['',f'路由的配对核验：旧R53的{parity["expressions"]}个完整TCP开启查询与本次关闭TCP查询，frame观测{parity["compared_observations"]["frame"]:,}、video观测{parity["compared_observations"]["video"]:,}完全一致，最大概率差均为0，观测键差异为空。这与R54代码次序核查一致：fresh frame→video→TCP。核对限于归档完整查询，不把89条当作全量评测。','']
    if inference.get('sync_timeout_only_fix'):
        lines+=['',f'执行记录：首轮在 {inference["attempt01_seconds"]/3600:.3f}小时因rank0末尾NCCL collective等待rank1超过默认600s退出。原生源码1191–1193行是末尾同步；760份完整预测中752份同时具有完整trace并通过逐值差0核对。8份预测的trace在强制退出时未写完，连同102个未完成查询共110个查询用官方`--resume`完整重跑；没有丢弃样本。原始日志/中断gzip留在`R55_notcp_native/attempt01`。仅analysis外层将分布式同步timeout设8h，未改官方计算或权重。续跑前剩余预算{inference["resume_estimated_hours"]:.3f}小时，含已运行工作的总估计{inference["aggregate_resume_estimated_hours"]:.3f}小时；续跑实际{inference["attempt02_seconds"]/3600:.3f}小时。上面的实际原生耗时包含失败前计算与续跑。','']
    text='\n'.join(lines);(ROOT/'analysis/REPORT_round3_actual_notcp.md').write_text(text)
    path=ROOT/'analysis/REPORT_round3.md';base=path.read_text().split('\n## R55：官方关闭 TCP')[0]
    path.write_text(base.rstrip()+'\n\n'+text)
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R55_complete':True,'R55_status':'complete','R51_next_action':'complete',
        'R55_native_V1_HOTA':v1['metrics']['HOTA'],'R55_LOSO_HMM_HOTA':variants[PLAN['variants'][2]]['metrics']['HOTA'],
        'R51_awaiting_approval':False,'R55_fullframe_cache_run':False})
    save_json(ROOT/'analysis/round3_state.json',state)


def main():
    assert not os.environ.get('CUDA_VISIBLE_DEVICES',''),'CPU-only replay'
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True);np.random.seed(2025)
    actual.OUT=OUT;actual.NATIVE=NATIVE;actual.PLAN=PLAN
    d=actual.ActualData();q,masks,observed,gate=load_trace(d)
    parity=parity_old_trace(observed)
    budget.OUT=OUT;budget.PLAN=PLAN
    parameters=budget.fit_loso(d,q,masks)
    variants={}
    for variant in PLAN['variants']:
        path=OUT/variant/'result.json'
        if path.exists() and json.loads(path.read_text()).get('complete'):r=json.loads(path.read_text())
        else:
            scores=d.native if variant==PLAN['variants'][0] else generate(d,q,masks,parameters,variant)
            r=actual.evaluate(d,variant,scores,native_predictions=NATIVE/'predictions' if variant==PLAN['variants'][0] else None)
        r['reference']='relative R14 local TempRMOT* V0; native V1 directly generated withoutTCP'
        r['actual_candidate_parameter_fits']=0 if variant!=PLAN['variants'][2] else 3
        r['LOSO_parameter_source']=str(OUT/'LOSO/parameters.json') if variant!=PLAN['variants'][0] else None
        save_json(path,r);variants[variant]=r
    baseline=json.loads((ROOT/'analysis/local_baseline.json').read_text())
    metric,details=hota_rows(Path(baseline['evaluation'])/'tracker/default_t0p60/pedestrian_detailed.csv',c)
    v0={'source':'R14, no rerun','metrics':combine_hota(metric,details),
        'per_sequence':{s:combine_hota(metric,{n:details[n] for n in names}) for s,names in d.by_seq.items()},
        'categories':{cat:{'expressions':sum(cat in r['labels'] for r in d.labels),
            'metrics':combine_hota(metric,{r['name']:details[r['name']] for r in d.labels if cat in r['labels']})}
            for cat in 'ABCDEFGH'}}
    for variant,r in variants.items():
        r['gain_vs_R14']=r['metrics']['HOTA']-v0['metrics']['HOTA']
        r['gain_vs_nativeV1']=r['metrics']['HOTA']-variants[PLAN['variants'][0]]['metrics']['HOTA']
        save_json(OUT/variant/'result.json',r)
    result={'complete':True,'seed':2025,'native_gate':gate,'V0_R14':v0,'variants':variants,
        'LOSO':parameters,'archived_routing_parity':parity,'seconds':time.monotonic()-start,
        'official_source_or_weights_modified':False,'full_val_tuning':False,'fullframe_cache_run':False}
    save_json(OUT/'result.json',result);write_report(result)
    print('R55 offline analysis complete:',json.dumps({v:r['metrics']['HOTA'] for v,r in variants.items()}),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        save_json(OUT/'failure.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        raise
