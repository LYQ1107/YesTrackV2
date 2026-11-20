#!/usr/bin/env python3
"""One-scalar LOSO threshold control, code routing audit and budget correction."""
import csv
import json
import os
from pathlib import Path
import time

import numpy as np
import round3 as temporal
from common import config,save_json

c=config();ROOT=Path(c['task_root']);OUT=ROOT/'analysis/runs/R54_gamma_control'
PLAN=json.loads((ROOT/'analysis/plans/round3_gamma_control.json').read_text())


def audit_and_budget():
    source=ROOT/c['upstream']/'refer_llm/llm_eval_from_mot.py'
    audit={'scope':'R09/R17 frame mode with selective video refinement',
        'routing_score':'fresh frame helper probability, before video replacement and TCP',
        'TCP_changes_video_routing':False,
        'full_frame_raw_forward_lines':[877,886],
        'full_frame_refine_candidate_line':892,
        'new_ID_raw_forward_lines':[928,941],
        'new_ID_refine_candidate_line':944,
        'video_gate_lines':[945,949],
        'TCP_lines':[1004,1017],
        'cached_final_score_lines':[899,900,1020,1021],
        'explanation':'Only current fresh full-frame/new-ID candidates enter refine_indices. Reused old-ID final scores are excluded, including frames where some new IDs cause did_infer_any=True. Thus turning TCP off cannot remove required video observations under identical model outputs.',
        'source':str(source),'official_commit':c['upstream_commit']}
    save_json(OUT/'routing_audit.json',audit)
    folder=ROOT/'analysis/runs/R53_native_trace'
    old=json.loads((folder/'budget_pause.json').read_text())
    tasks={r['name']:r for r in json.loads((ROOT/'analysis/reproduction_inputs.json').read_text())['tasks']}
    files=[f for f in (folder/'predictions').glob('*/*/predict_with_conf.txt') if f.stat().st_mtime<=old['paused_unix']]
    actual=[f'{f.parent.parent.name}__{f.parent.name}' for f in files]
    frame_done=sum(tasks[n]['sequence_images'] for n in actual)
    rows_done=sum(tasks[n]['candidate_rows'] for n in actual)
    steady=old['elapsed_wall_seconds_before_pause']-120
    corrected={'old_rank0_OK_count':old['completed_expressions'],'complete_files_before_pause_all_ranks':len(files),
        'proof':'all listed files have mtime<=recorded pause time; official lines1184-1185 print OK only on rank0',
        'elapsed_seconds':old['elapsed_wall_seconds_before_pause'],'initialization_allowance_seconds':120,
        'completed_expression_image_frames':frame_done,'completed_candidate_rows':rows_done,
        'corrected_frame_proxy_hours':(120+steady*old['total_expression_image_frames']/frame_done)/3600,
        'corrected_candidate_proxy_hours':(120+steady*old['total_candidate_rows']/rows_done)/3600,
        'old_12p7_to_14p8_hour_estimate_valid':False,'old_run_status':'cancelled by user; not resumed',
        'completed_names_all_ranks':sorted(actual)}
    save_json(folder/'budget_correction.json',corrected)
    print('Routing audit:',json.dumps(audit),flush=True)
    print('Old budget corrected:',json.dumps({k:v for k,v in corrected.items() if k!='completed_names_all_ranks'}),flush=True)
    return audit,corrected


def main():
    assert not os.environ.get('CUDA_VISIBLE_DEVICES','')
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True);np.random.seed(2025)
    audit,correction=audit_and_budget();d=temporal.Dataset(with_scores=False)
    scores={}
    for seq,names in d.by_seq.items():
        a=np.load(ROOT/'analysis/runs/R50_temporal/V1'/f'scores_{seq}.npz')
        assert np.array_equal(a['names'],np.asarray(names));scores[seq]=a['scores']
    folds=[];prediction={};grid_rows=[]
    for held in c['val_sequences']:
        train=[s for s in c['val_sequences'] if s!=held];current=[]
        for gamma in PLAN['gamma_grid']:
            conf=temporal.aggregate_conf([temporal.confusion(d.y[s].ravel(),scores[s].ravel(),gamma) for s in train])
            row={'held_out':held,'gamma':gamma,**{k:conf[k] for k in ['tp','fp','fn','f1']}}
            current.append(row);grid_rows.append(row)
        best=min(current,key=lambda r:(-r['f1'],abs(r['gamma']-.6),r['gamma']))
        fold={'held_out_sequence':held,'training_sequences':train,'gamma':best['gamma'],
              'training_micro_F1':best['f1'],'fitted_scalars':1,
              'training_rows':sum(d.y[s].size for s in train)}
        folds.append(fold);prediction[held]=(scores[held]>=best['gamma']).astype(float)
    save_json(OUT/'parameters.json',{'complete':True,'seed':2025,'folds':folds,'max_fitted_scalars':1,'full_val_tuning':False})
    with (OUT/'training_grid.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(grid_rows[0]));w.writeheader();w.writerows(grid_rows)
    temporal.OUT=OUT
    variant=PLAN['new_variant'];temporal.write_predictions(d,variant,prediction)
    tuned=temporal.evaluate_variant(d,variant,prediction)
    previous=json.loads((ROOT/'analysis/runs/R50_temporal/result.json').read_text())
    sparse=json.loads((ROOT/'analysis/runs/R52_budget/result.json').read_text())
    v1=previous['variants']['V1'];hmm=sparse['variants']['V4_D10_LOSO']
    threshold_gain=tuned['metrics']['HOTA']-v1['metrics']['HOTA']
    original_gap=hmm['metrics']['HOTA']-v1['metrics']['HOTA']
    residual=hmm['metrics']['HOTA']-tuned['metrics']['HOTA']
    result={'complete':True,'seed':2025,'reference':'GT candidates, Delta10, relative local baseline',
        'LOSO':folds,'V1_fixed_gamma06':v1,'V1_gamma_LOSO':tuned,'HMM_Delta10_LOSO':hmm,
        'original_HMM_minus_V1_HOTA':original_gap,'threshold_control_gain_HOTA':threshold_gain,
        'HMM_minus_threshold_control_HOTA':residual,'seconds':time.monotonic()-start,
        'routing_audit':audit,'old_budget_correction':correction,'fit_scalars_per_fold':1}
    save_json(OUT/'result.json',result)
    report(result)
    print('Gamma control complete:',json.dumps({'gamma_by_fold':{f['held_out_sequence']:f['gamma'] for f in folds},
          'V1_fixed_HOTA':v1['metrics']['HOTA'],'V1_gamma_LOSO_HOTA':tuned['metrics']['HOTA'],
          'HMM_LOSO_HOTA':hmm['metrics']['HOTA'],'threshold_gain':threshold_gain,'HMM_residual':residual}),flush=True)


def report(r):
    lines=['## R54：video 路由核查及单参数 γ-LOSO 对照','',
        '本节按用户新指令追加。旧 R53 开 TCP 的实际候选运行已终止、显存释放，旧输出归档保留，后续不续跑。','',
        '### 路由到底读取哪个分数','',
        '在 R09/R17 的 frame→选择性 video 分支中，路由读取**本次新推理的 frame 原始分数**：', '',
        '- 全量推理在 [877–886 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L877) 产生 frame 概率，[892 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L892) 把本次全部候选列为可精炼项。',
        '- 跳过帧只对新 ID 推理，[938–944 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L938) 把这些新原始分数回填，并仅将 `new_indices` 列为可精炼项。旧 ID 虽复用了最终分数，也不参与 video 路由。',
        '- [945–949 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L945) 在这些新鲜候选上测试 `[.2,.8)`；video 回填到 [1002–1003 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1002) 后，[1004–1017 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1004) 才执行 TCP。','',
        '**代码结论：当前参数路径下，TCP 开关不决定 video 调用集合；不会因开启 TCP 的 trace 而缺失去 TCP 重放所需的 video 分数。**原 GT 候选缓存对照依然有效。仍遵用户指定，实际候选另跑官方关闭 TCP 的直接验证，形成原生 V1。','',
        '### V1 只调 γ 的四折 LOSO','',
        '先于结果冻结 [R54 方案](plans/round3_gamma_control.json)。沿用 Δ10、固定 video 路由、无 TCP 的 V1 连续分数；每折只在其余三个视频用 pooled micro-F1 选择 γ∈{.1,.2,.3,.4,.5,.6,.7,.8,.9}，与 R52 HMM 的训练目标/阈值网格一致，仅拟合1个标量。留出序列的决策合并后由官方 TrackEval 计算 HOTA。固定 γ=.6 的 V1 仍为未调参参照。','',
        '| 留出序列 | 选定 γ | 训练三序列 micro-F1 |',
        '|---|---:|---:|']
    for f in r['LOSO']:lines.append(f'| {f["held_out_sequence"]} | {f["gamma"]} | {100*f["training_micro_F1"]:.2f}% |')
    lines+=['','| GT候选版本（全部Δ10） | HOTA | DetA | AssA | DetPr | DetRe | P | R | F1 |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    methods=[('V1固定γ=.6',r['V1_fixed_gamma06']),('V1单参数γ-LOSO',r['V1_gamma_LOSO']),('HMM三参数LOSO',r['HMM_Delta10_LOSO'])]
    for label,method in methods:
        lines.append('| '+' | '.join([label,*[f'{method["metrics"][k]:.3f}' for k in ['HOTA','DetA','AssA','DetPr','DetRe']],
            *[f'{100*method["referring"][k]:.2f}%' for k in ['precision','recall','f1']]])+' |')
    lines+=['','| 序列 | V1固定γ HOTA | γ-LOSO HOTA | HMM-LOSO HOTA | HMM−γ-LOSO |',
            '|---|---:|---:|---:|---:|---:|']
    for seq in c['val_sequences']:
        vals=[method['per_sequence'][seq]['HOTA'] for _,method in methods]
        lines.append('| '+' | '.join([seq,*[f'{v:.3f}' for v in vals],f'{vals[2]-vals[1]:+.3f}'])+' |')
    original=r['original_HMM_minus_V1_HOTA'];gain=r['threshold_control_gain_HOTA'];gap=r['HMM_minus_threshold_control_HOTA']
    lines+=['',f'原 HMM 比固定γ V1 高 **{original:.3f} HOTA**；单参数γ控制带来 **{gain:+.3f}**，公平比较后 HMM−γ控制剩 **{gap:+.3f} HOTA**。',
        '',('**判定：本次单参数阈值对照已达到或超过 HMM 的总体 HOTA，原约0.74优势可被阈值调整对照覆盖，不支持把这0.74归为独立时序滤波收益。**' if gap<=0 else
            '**判定：在冻结网格、相同LOSO目标下，单参数阈值未覆盖全部HMM增量；剩余差值如上，不能仅凭这四个序列声称显著或普遍的独立滤波收益。**'),
        '', '这里只比较预注册的训练目标与网格；未将完整 val 最佳γ当作LOSO结果，也未根据结果扩大网格。两条流程的训练自由度不同，结论属于这个对照，不是任意阈值/滤波器的理论证明。',
        '', f'切换和空帧对照：γ-LOSO在F类真→假后0–5帧错误率为{100*r["V1_gamma_LOSO"]["F_true_to_false_post0to5"]["error_rate"]:.2f}%，HMM-LOSO为{100*r["HMM_Delta10_LOSO"]["F_true_to_false_post0to5"]["error_rate"]:.2f}%（均3529条）；空GT帧误报率分别为{100*r["V1_gamma_LOSO"]["empty_GT_frames"]["false_alarm_rate"]:.2f}%和{100*r["HMM_Delta10_LOSO"]["empty_GT_frames"]["false_alarm_rate"]:.2f}%。因此HMM较高的HOTA不能解释为更快解除真→假锁存。',
        '', '[完整数值](runs/R54_gamma_control/result.json) · [每折参数](runs/R54_gamma_control/parameters.json) · [训练网格](runs/R54_gamma_control/training_grid.csv) · [路由核查](runs/R54_gamma_control/routing_audit.json)',
        '', '### 更正旧 R53 的进度与耗时外推','',
        f'官方 [1184–1185 行](upstream/YesTrack/refer_llm/llm_eval_from_mot.py#L1184) 只让 rank0 打印 `[OK]`。此前据47条日志外推12.7–14.8小时漏计了rank1；文件mtime证明暂停前实际已有 **{r["old_budget_correction"]["complete_files_before_pause_all_ranks"]}条完整输出**。按全rank输出修正的同一工作量代理估计约 **{r["old_budget_correction"]["corrected_frame_proxy_hours"]:.2f}–{r["old_budget_correction"]["corrected_candidate_proxy_hours"]:.2f}小时**，旧12.7–14.8估计作废。原始快照保留，更正单列；后续监控将核对全部rank完整文件。',
        '', '[预算更正证据](runs/R53_native_trace/budget_correction.json)。旧run仍按用户新方案取消，不因更正而续跑；后续仅运行官方关闭TCP的一次完整实际候选推理，并等低负载、现场估计<8小时后自动启动。','']
    text='\n'.join(lines);(ROOT/'analysis/REPORT_round3_gamma_control.md').write_text(text)
    path=ROOT/'analysis/REPORT_round3.md';existing=path.read_text()
    suffix='\n## R55：'+existing.split('\n## R55：',1)[1] if '\n## R55：' in existing else ''
    base=existing.split('\n## R54：video 路由核查')[0]
    start=base.find('\n## R53：当前共享负载下的预算复核与暂停')
    if start>=0:
        old_section=base[start:]
        archive=ROOT/'analysis/runs/R53_native_trace/report_before_budget_correction.md'
        if not archive.exists():archive.write_text(old_section)
        base=base[:start]+'\n\n## R53：已取消的旧 TCP trace\n\n旧run已按用户指令终止并释放GPU，输出保留不续跑。原47条/12.7–14.8小时预算误用了仅rank0的日志，已作废；全rank证据与更正见R54。\n'
    path.write_text(base.rstrip()+'\n\n'+text+suffix)
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R54_CPU_complete':True,'R54_gamma_control_HOTA':r['V1_gamma_LOSO']['metrics']['HOTA'],
        'R54_HMM_minus_gamma_control_HOTA':gap,
        'R53_old_budget_estimate_invalid_rank0_only':True,'R51_awaiting_approval':False})
    if not state.get('R55_complete'):state['R55_status']='awaiting_low_load_admission_noTCP'
    save_json(ROOT/'analysis/round3_state.json',state)


if __name__=='__main__':main()
