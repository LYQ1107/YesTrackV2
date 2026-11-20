#!/usr/bin/env python3
"""Validate complete frozen R54/R55 artifacts and render the final research report."""
import json
import os
from pathlib import Path
import shlex
import subprocess

import numpy as np
from common import config,combine_hota,hota_rows,log_run,mot,save_json
import gamma_loso_control as gamma
import notcp_actual_replay as native


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    c=config();root=Path(c['task_root']);out=root/'analysis/runs/R55_notcp_actual'
    r=json.loads((out/'result.json').read_text());plan=native.PLAN
    assert r['complete'] and r['seed']==2025 and set(r['variants'])==set(plan['variants'])
    gate=r['native_gate'];assert gate['expressions']==862 and gate['candidate_rows']==1850576
    assert gate['native_V1_maximum_difference']==0 and not gate['TCP_enabled']
    source=root/c['upstream']
    subprocess.run(['git','diff','--exit-code'],cwd=source,check=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    assert commit==c['upstream_commit']
    labels=json.loads((root/'analysis/labels/expressions.json').read_text())
    byseq={s:[a['name'] for a in labels if a['sequence']==s] for s in c['val_sequences']}
    counts={s:0 for s in byseq};positive={s:0 for s in byseq}
    for seq,names in byseq.items():
        for name in names:
            a=np.load(root/'analysis/runs/R20_oracles/candidate_labels'/seq/(name.split('__',1)[1]+'.npz'))['y']
            counts[seq]+=len(a);positive[seq]+=int(a.sum())
    for fold in r['LOSO']['folds']:
        held=fold['held_out_sequence'];train=fold['training_sequences']
        assert held not in train and set(train)==set(byseq)-{held} and fold['fitted_scalars']<=3
        n=sum(counts[s] for s in train);yes=sum(positive[s] for s in train)
        assert n==fold['training_rows'] and yes==fold['training_positive_rows']
        assert abs(yes/n-fold['new_ID_prior'])<1e-15
    checks={};eval_commands=[]
    for variant,method in r['variants'].items():
        folder=out/variant
        metric,details=hota_rows(folder/'evaluation/tracker/default_t0p60/pedestrian_detailed.csv',c)
        assert set(details)=={a['name'] for a in labels}
        combined=combine_hota(metric,details)
        assert max(abs(combined[k]-method['metrics'][k]) for k in combined)<1e-12
        rows=0;maximum=0.0
        for seq in byseq:
            cache=np.load(folder/f'scores_{seq}.npz');names=cache['names'].tolist();scores=cache['scores']
            assert names==byseq[seq]
            if variant!=plan['variants'][0]:
                posterior=np.load(folder/f'posterior_{seq}.npz')
                assert posterior['names'].tolist()==names
                assert np.array_equal(scores,(posterior['posterior']>=float(posterior['threshold'])).astype(float))
            for j,name in enumerate(names):
                pred=mot(folder/'predictions'/seq/name.split('__',1)[1]/'predict_with_conf.txt')
                assert len(pred)==scores.shape[1]
                maximum=max(maximum,float(np.max(np.abs(pred[:,6]-scores[j]))));rows+=len(pred)
        assert rows==1850576 and maximum==0
        if variant!=plan['variants'][0]:
            transition=json.loads((folder/'transition_validation.json').read_text())
            assert transition['complete'] and transition['maximum_transition_prediction_error']==0
            assert transition['unobserved_rows_checked']==1850576-gate['frame_candidate_observations']
        assert method['conditional_referring']['n']==1850576
        assert method['empty_GT_frame_false_alarm']['denominator']==237085
        checks[variant]={'prediction_rows':rows,'score_cache_to_output_maximum_difference':maximum,
            'detailed_TrackEval_queries':len(details),'HOTA':combined['HOTA']}
        eval_commands.append(method['evaluation_command'])
    baseline=json.loads((root/'analysis/local_baseline.json').read_text())
    metric,details=hota_rows(Path(baseline['evaluation'])/'tracker/default_t0p60/pedestrian_detailed.csv',c)
    assert abs(combine_hota(metric,details)['HOTA']-r['V0_R14']['metrics']['HOTA'])<1e-12
    r['V0_R14']['categories']={cat:{'expressions':sum(cat in a['labels'] for a in labels),
        'metrics':combine_hota(metric,{a['name']:details[a['name']] for a in labels if cat in a['labels']})}
        for cat in 'ABCDEFGH'}
    archived=root/'analysis/runs/R55_notcp_native/attempt01/predictions_requiring_trace_recovery'
    resume_maximum=0.0;resumed_checks=0
    for path in archived.glob('*/*/predict_with_conf.txt'):
        seq=path.parent.parent.name;expr=path.parent.name
        old=mot(path);new=mot(root/'analysis/runs/R55_notcp_native/predictions'/seq/expr/path.name)
        assert np.array_equal(old[:,:6],new[:,:6])
        resume_maximum=max(resume_maximum,float(np.max(np.abs(old[:,6]-new[:,6]))));resumed_checks+=1
    assert resumed_checks==8 and resume_maximum==0
    assert not r['full_val_tuning'] and not r['fullframe_cache_run']
    save_json(out/'result.json',r)
    g=json.loads((root/'analysis/runs/R54_gamma_control/result.json').read_text())
    gamma.report(g);native.write_report(r)
    main_report=root/'analysis/REPORT_round3.md'
    body=main_report.read_text().split('\n## R49：',1)[1]
    v0=r['V0_R14']['metrics']['HOTA'];v1=r['variants'][plan['variants'][0]]['metrics']['HOTA']
    fixed=r['variants'][plan['variants'][1]]['metrics']['HOTA'];loso=r['variants'][plan['variants'][2]]['metrics']['HOTA']
    introduction=(
        '# YesTrack 第三轮：时序决策层诊断\n\n'
        '2026-11-02；seed=2025。全部为**相对本地基线**，使用发布V2权重，不与论文数字混用。R49–R54为GT候选；R55为TempRMOT*实际候选。官方权重、crop、prompt、frame/video计算及推理源码未改；实际候选按用户授权删除`--stability_enable`重新运行原生推理，所有HMM只离线重放缓存。分布式恢复仅在analysis外层延长同步timeout。\n\n'
        f'**本轮最终结论：在实际候选、相同Δ10推理预算下，本轮预注册版本最多收回{v1-v0:.3f} HOTA（去TCP：{v0:.3f}→{v1:.3f}）。固定HMM为{fixed:.3f}、LOSO HMM为{loso:.3f}，均未超过直接去TCP。GT候选上的HMM收益不能直接外推到实际候选。**\n\n'
        f'GT候选的单参数γ-LOSO为{g["V1_gamma_LOSO"]["metrics"]["HOTA"]:.3f}，HMM-LOSO为{g["HMM_Delta10_LOSO"]["metrics"]["HOTA"]:.3f}，差{g["HMM_minus_threshold_control_HOTA"]:.3f}；该判定限于预注册0.1步长网格和micro-F1目标。R49–R52保留各自观测预算，R55给出已完成的实际验证。\n\n'
        '预注册：[R49/R50](plans/round3.json)、[R52预算对齐](plans/round3_budget.json)、[R54阈值控制](plans/round3_gamma_control.json)、[R55实际候选](plans/round3_actual_notcp.json)。[完整命令记录](runs.md)。各阶段结果前冻结变体，未按结果增删，未用完整val调参。\n\n'
    )
    text=introduction+'## R49：'+body
    text=text.replace('](runs/R49_self_lock/self_lock_curves.png)',']('+str(root/'analysis/runs/R49_self_lock/self_lock_curves.png')+')')
    main_report.write_text(text)
    validation={'complete':True,'seed':2025,'source_commit':commit,'official_tracked_diff_empty':True,
        'native_gate_maximum_difference':0.0,'expressions':862,'candidate_rows':1850576,
        'LOSO_whole_sequence_disjoint':True,'max_fitted_scalars_per_fold':3,'new_ID_priors_training_only':True,
        'variants':checks,'rerun_completed_query_checks':resumed_checks,'rerun_score_maximum_difference':resume_maximum,
        'fullframe_cache_run':False,'parameters_or_variants_changed_after_results':False}
    save_json(out/'final_validation.json',validation)
    marker='## R55-complete'
    if marker not in (root/'analysis/runs.md').read_text():
        commands=["CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 "+
            shlex.join([c['reproduction_environment'],'-u','analysis/finalize_round3.py']),
            '# 以下为已执行的三次官方TrackEval精确命令；仅重评测时使用，无需GPU',
            'cd '+shlex.quote(str(source))]
        commands+= ["CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "+shlex.join(cmd) for cmd in eval_commands]
        log_run(c,'55-complete','全量实际候选结论、分类汇总和最终核验',commands,
            f'862表达式/1850576行；frame239467、video58209；新原生V1六位重放最大差0，三版本缓存对输出差0，官方详细结果均覆盖862条。'
            f'R14 V0={v0:.9f}，原生V1={v1:.9f}(+{v1-v0:.9f})，固定HMM={fixed:.9f}，LOSOHMM={loso:.9f}；后两版相对V1分别{fixed-v1:+.9f}/{loso-v1:+.9f}，四序列LOSO HMM均低于V1。'
            'LOSO每折整视频隔离、3标量、先验仅训练3序列；每版1611109未观测行均只状态转移且误差0。8份重跑完整预测相对失败前原预测最大差0。'
            '新GPU原生运行累计5.136628h（首轮2.526356h+恢复2.610272h），未运行全帧缓存。GT单γ对照68.034903 vs HMM69.482083，限冻结网格目标。'
            '新增类别表只是既有官方详细结果按固定A–H聚合，不新增变体。报告重绘修正开头GT/实际范围，并防止重绘R54删掉R55；模型/指标/参数不变。')
    note=(f'\n### YesTrack R55-complete（2026-11-02）\n\n'
          f'实际候选全量862表达式、1850576行完成。原生V1去TCP {v1:.6f} HOTA，相对R14 {v1-v0:+.6f}；固定HMM {fixed:.6f}、LOSO HMM {loso:.6f}，均未超过V1，LOSO四序列相对V1均下降。GT候选HMM收益未直接转化为实际收益。新原生V1逐值差0，三版输出/缓存一致、LOSO整序列隔离≤3标量、未观测行仅转移；8条因trace不完整重跑的预测与原预测也差0。累计GPU原生5.137h，未跑全帧缓存。保留原NCCL失败和CPU排序修正记录；只延长同步timeout，不改官方权重/推理逻辑/seed。结果及命令见任务analysis/REPORT_round3.md、runs.md。\n')
    for path in [Path(c['project_root'])/'research_log.md',root/'analysis/research_log.md']:
        if '### YesTrack R55-complete' not in path.read_text():
            with path.open('a') as f:f.write(note)
    print(json.dumps(validation,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
