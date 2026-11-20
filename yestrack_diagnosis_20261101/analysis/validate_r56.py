#!/usr/bin/env python3
"""Check R56 oracle definitions, held-out filtering, train-only selection and metrics."""
import csv
import itertools
import json
import os
from pathlib import Path
import shlex
import subprocess

import numpy as np
from common import config,hota_rows,log_run,mot,save_json
import r56_error_oracles as run


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    c=config();root=Path(c['task_root']);out=run.OUT;p=run.PLAN
    r=json.loads((out/'result.json').read_text());assert r['complete']
    command="CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 "+shlex.join([c['reproduction_environment'],'-u','analysis/validate_r56.py'])
    log_run(c,'56-validation','R56完成后核对与报告重绘',[command],
        'CPU；只验证R56新产物，重算每折全部36个训练HOTA并核对选参、检查五个新输出的框/ID和逐行分数；旧R14/R20/R00–R55报告及结果不写入。没有新规则或阈值。')
    subprocess.run(['git','diff','--exit-code'],cwd=root/c['upstream'],check=True)
    names_by_seq={s:[] for s in p['LOSO']['sequences']}
    for row in r['positive_partition']['per_sequence']:assert row in names_by_seq
    from common import names
    for name in names(c):names_by_seq[name.split('__',1)[0]].append(name)
    metric,_=hota_rows(Path(run.BASE['evaluation'])/'tracker'/run.TAG/'pedestrian_detailed.csv',c)
    cache={}
    def point_details(length,area,seq):
        folder=out/'grid'/f'L{length}_A{area}'/seq
        entry=json.loads((folder/'grid_entry.json').read_text());csv_path=entry['detail_csv']
        if csv_path not in cache:cache[csv_path]=hota_rows(Path(csv_path),c)[1]
        return {n:cache[csv_path][n] for n in names_by_seq[seq]}
    training_rows=list(csv.DictReader((out/'LOSO/training_grid.csv').open()))
    maximum_training_difference=0.0
    for fold in r['LOSO']['folds']:
        held=fold['held_out_sequence'];train=fold['training_sequences']
        assert set(train)==set(names_by_seq)-{held} and fold['fitted_scalars']==2
        table=[a for a in training_rows if a['held_out_sequence']==held]
        assert len(table)==36
        recomputed=[]
        for length,area in itertools.product(p['LOSO']['min_track_length_grid'],p['LOSO']['min_box_area_grid']):
            details=run.merge([point_details(length,area,s) for s in train])
            assert all(not n.startswith(held+'__') for n in details)
            h=run.aggregate(metric,details)['HOTA']
            entry=next(a for a in table if int(a['min_track_length'])==length and int(a['min_box_area'])==area)
            assert entry['training_sequences'].split('+')==train
            maximum_training_difference=max(maximum_training_difference,abs(h-float(entry['training_HOTA'])))
            recomputed.append((h,length,area))
        best=None
        for value in recomputed:
            if best is None or value[0]>best[0]+1e-12:best=value
        assert (best[1],best[2])==(fold['min_track_length'],fold['min_box_area'])
        assert abs(best[0]-fold['training_HOTA'])<1e-12
    assert maximum_training_difference<1e-12
    folds={a['held_out_sequence']:a for a in r['LOSO']['folds']}
    maximum_score_difference=0.0;checked={v:0 for v in p['variants']}
    for seq,ns in names_by_seq.items():
        features=np.load(out/'features'/f'{seq}.npz')
        fold=folds[seq];fixed=p['fixed_rule']
        rule_mask=(features['track_length']>=fold['min_track_length'])&(features['box_area']>=fold['min_box_area'])
        fixed_mask=(features['track_length']>=fixed['min_track_length'])&(features['box_area']>=fixed['min_box_area'])
        for name in ns:
            expr=name.split('__',1)[1]
            base=mot(Path(run.BASE['predictions'])/seq/expr/'predict_with_conf.txt')
            labels=np.load(root/'analysis/runs/R20_oracles/candidate_labels'/seq/f'{expr}.npz')
            y=labels['y'];matched=labels['matched_gt_id']>=0
            expected={}
            expected['GarbageOracle']=np.where(matched,base[:,6],0.)
            semantic=base[:,6].copy();wrong=matched & ((semantic>=.6)!=y);semantic[wrong]=y[wrong]
            expected['SemanticOracle']=semantic
            expected['Rule_fixed']=np.where(fixed_mask,base[:,6],0.)
            expected['Rule_LOSO']=np.where(rule_mask,base[:,6],0.)
            expected['Rule_LOSO_captured_garbage_oracle']=np.where(~matched & ~rule_mask,0.,base[:,6])
            for variant,values in expected.items():
                pred=mot(out/variant/'predictions'/seq/expr/'predict_with_conf.txt')
                assert np.array_equal(pred[:,:6],base[:,:6]),(variant,name,'geometry changed')
                maximum_score_difference=max(maximum_score_difference,float(np.max(np.abs(pred[:,6]-values))))
                checked[variant]+=len(pred)
    assert maximum_score_difference==0.0 and all(n==1850576 for n in checked.values())
    assert r['positive_partition']['total']['predicted_positive']==496433
    # Reaggregate all full evaluations and the predefined fixed rule from official CSVs.
    maximum_metric_difference=0.0
    for variant in p['variants']:
        if variant=='Rule_fixed':
            fixed=p['fixed_rule'];details=run.merge([point_details(fixed['min_track_length'],fixed['min_box_area'],s) for s in names_by_seq])
        else:
            _,details=hota_rows(out/variant/'evaluation/tracker'/run.TAG/'pedestrian_detailed.csv',c)
        assert len(details)==862
        m=run.aggregate(metric,details)
        maximum_metric_difference=max(maximum_metric_difference,max(abs(m[k]-r['metrics'][variant][k]) for k in m))
    assert maximum_metric_difference<1e-12
    validation={'complete':True,'seed':2025,'client_date_asia_shanghai':'2026-11-04',
        'whole_sequence_training_only_grid_checked':144,'maximum_training_HOTA_difference':maximum_training_difference,
        'LOSO_chosen_parameters_match_train_only_argmax':True,'maximum_score_difference':maximum_score_difference,
        'prediction_rows_checked_by_variant':checked,'candidate_geometry_and_IDs_unchanged':True,
        'maximum_official_metric_reaggregation_difference':maximum_metric_difference,
        'official_source_tracked_diff_empty':True,'all_previous_results_read_only':True,'CPU_only':True}
    save_json(out/'final_validation.json',validation)
    run.render(r)
    report=root/'analysis/REPORT_R56.md'
    text=report.read_text().replace('[LOSO参数](runs/R56/LOSO/parameters.json)',
        '[LOSO参数](runs/R56/LOSO/parameters.json) · [最终核验](runs/R56/final_validation.json)')
    report.write_text(text)
    marker='## R56-complete'
    if marker not in (root/'analysis/runs.md').read_text():
        h=r['HOTA'];a=r['attribution'];rec=r['recovery']
        log_run(c,'56-complete','两个部分oracle及LOSO元数据规则的最终结果',[command],
            'R56仅CPU，约14.42min；104次逐视频网格官方TrackEval、40个完全相同mask复用，36点全部保留；另两个部分oracle、OOF规则和垃圾命中诊断全量官方评测均覆盖862表达式。'
            f'R14 HOTA{h["R14"]:.9f}；清垃圾{h["GarbageOracle"]:.9f}(+{a["garbage_first_garbage"]:.9f})；纠语义{h["SemanticOracle"]:.9f}(+{a["independent_semantic_gain"]:.9f})；R20全oracle{h["R20_both_oracles"]:.9f}。'
            f'交互{a["interaction"]:+.9f}；先垃圾后语义分账{a["garbage_first_garbage"]:.9f}/{a["garbage_first_semantic_residual"]:.9f}；对称归因{a["Shapley_garbage"]:.9f}/{a["Shapley_semantic"]:.9f}。'
            f'固定规则{h["Rule_fixed"]:.9f}，LOSO规则{h["Rule_LOSO"]:.9f}(净回收①{100*rec["actual_rule_fraction_of_garbage"]:.6f}%)；仅垃圾命中诊断{h["Rule_LOSO_captured_garbage_oracle"]:.9f}，回收①{100*rec["isolated_garbage_fraction"]:.6f}%，未覆盖垃圾空间{rec["remaining_garbage_not_captured_HOTA"]:.9f}。'
            '逐行核对五个新输出共9252880行，最大score差0，geometry/ID不变；每折36点共144个训练HOTA独立重聚合，选参一致，官方source diff空。之前结果/报告不写入，仅追加runs/research日志。R56报告单独REPORT_R56.md。')
    note=('\n### YesTrack R56-complete（2026-11-04）\n\n'
        'R14正候选496433：R20 TP259690、语义FP179889、未匹配垃圾FP56854；语义FN23296。清垃圾HOTA41.802012（+1.374550），纠语义含FN49.490162（+9.062700），全oracle51.946196，交互+1.081484。先垃圾后语义分账1.374550/10.144184，对称归因1.915292/9.603442。'
        '仅tracker元数据L/A，confidence列恒1不可用；固定规则HOTA40.555148，整视频LOSO40.510874（+0.083412，清垃圾空间的6.07%）。LOSO删除TP3733、语义FP2924、垃圾FP5751；仅垃圾命中诊断+0.162175（11.80%），尚余1.212375垃圾空间未被该规则覆盖，不能据此证明必须看图。'
        '全CPU104次独立逐视频网格评测及40别名复用，未用完整val选阈值；144个训练目标重算、5个输出每行与定义一致、官方源码不变。仅新增R56目录及独立报告，原结果不改；保留该诊断，不扩网格/变体。\n')
    for path in [Path(c['project_root'])/'research_log.md',root/'analysis/research_log.md']:
        if '### YesTrack R56-complete' not in path.read_text():
            with path.open('a') as f:f.write(note)
    print(json.dumps(validation),flush=True)


if __name__=='__main__':main()
