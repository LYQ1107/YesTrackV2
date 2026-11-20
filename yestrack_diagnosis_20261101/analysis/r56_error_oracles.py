#!/usr/bin/env python3
"""R56: fixed R14/R20 partial oracles and sequence-LOSO tracker-only filtering."""
import csv
import itertools
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

import numpy as np
from common import combine_hota,config,hota_rows,log_run,mot,names,official_eval,run_logged,save_json

c=config();ROOT=Path(c['task_root']);OUT=ROOT/'analysis/runs/R56'
PLAN=json.loads((ROOT/'analysis/plans/r56.json').read_text())
BASE=json.loads((ROOT/'analysis/local_baseline.json').read_text())
TAG='default_t0p60'


class Inputs:
    def __init__(self):
        self.names=names(c);self.by_seq={s:[n for n in self.names if n.startswith(s+'__')] for s in PLAN['LOSO']['sequences']}
        self.geometry={};self.scores={};self.y={};self.matched={};self.features={}
        self.counts=[];total=0
        for seq,ns in self.by_seq.items():
            scores=[];ys=[];canonical=None;match=None
            features=np.load(OUT/'features'/f'{seq}.npz')
            self.features[seq]={k:features[k] for k in features.files}
            for name in ns:
                expr=name.split('__',1)[1]
                p=mot(Path(BASE['predictions'])/seq/expr/'predict_with_conf.txt')
                lab=np.load(ROOT/'analysis/runs/R20_oracles/candidate_labels'/seq/f'{expr}.npz')
                matched=lab['matched_gt_id']>=0;y=lab['y'].astype(bool)
                assert np.array_equal(matched,lab['matched_iou']>=.5) and not np.any(y & ~matched)
                if canonical is None:canonical=p[:,:6].copy();match=matched.copy()
                else:assert np.array_equal(p[:,:6],canonical) and np.array_equal(matched,match)
                assert np.array_equal(p[:,:6],features['geometry']) and len(y)==len(p)
                assert np.array_equal(mot(ROOT/'analysis/runs/R20_oracles/tracker_oracle'/seq/expr/'predict_with_conf.txt')[:,6],y.astype(float))
                positive=p[:,6]>=.6
                row={'name':name,'sequence':seq,'candidate_rows':len(p),'predicted_positive':int(positive.sum()),
                    'TP':int((positive & y).sum()),'semantic_FP':int((positive & matched & ~y).sum()),
                    'garbage_FP':int((positive & ~matched).sum()),'semantic_FN':int((~positive & y).sum())}
                assert row['TP']+row['semantic_FP']+row['garbage_FP']==row['predicted_positive']
                self.counts.append(row);scores.append(p[:,6]);ys.append(y);total+=len(p)
            self.geometry[seq]=canonical;self.scores[seq]=np.stack(scores);self.y[seq]=np.stack(ys);self.matched[seq]=match
        assert len(self.names)==862 and total==1850576
        self.total={k:sum(row[k] for row in self.counts) for k in self.counts[0] if k not in ['name','sequence']}
        assert self.total['predicted_positive']==int(BASE['metrics']['Dets'])
        # Composing the two interventions must exactly recover frozen R20 decisions.
        for seq in self.by_seq:
            composed=self.scores[seq].copy();composed[:,~self.matched[seq]]=0
            matched=self.matched[seq];composed[:,matched]=self.y[seq][:,matched].astype(float)
            assert np.array_equal(composed>=.6,self.y[seq])
        write_csv(OUT/'positive_partition_per_expression.csv',self.counts)
        save_json(OUT/'positive_partition.json',{'definition':PLAN['positive_partition'],'total':self.total,
            'per_sequence':{s:{k:sum(a[k] for a in self.counts if a['sequence']==s) for k in self.total} for s in self.by_seq},
            'candidate_rows':total,'expressions':len(self.names),'combined_R20_decision_equivalence':True})

    def keep(self,seq,length,area):
        f=self.features[seq]
        return (f['track_length']>=length)&(f['box_area']>=area)

    def filter_scores(self,masks):
        return {s:np.where(masks[s][None,:],self.scores[s],0.) for s in masks}


def write_csv(path,rows):
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def merge(details_list):
    result={}
    for details in details_list:
        assert not (set(result)&set(details));result.update(details)
    return {n:result[n] for n in sorted(result)}


def aggregate(metric,details):
    return combine_hota(metric,{n:details[n] for n in sorted(details)})


def write_predictions(d,folder,scores):
    for seq,values in scores.items():
        for j,name in enumerate(d.by_seq[seq]):
            path=folder/seq/name.split('__',1)[1]/'predict_with_conf.txt';path.parent.mkdir(parents=True,exist_ok=True)
            a=np.column_stack([d.geometry[seq],values[j]])
            np.savetxt(path,a,delimiter=',',fmt=['%d']*6+['%.6f'])


def evaluate(d,folder,scores,expected_names,seqmap=None):
    result_file=folder/'result.json'
    if result_file.exists() and json.loads(result_file.read_text()).get('complete'):
        result=json.loads(result_file.read_text());metric,details=hota_rows(Path(result['detail_csv']),c)
        assert set(details)==set(expected_names);return metric,details,result
    predictions=folder/'predictions';write_predictions(d,predictions,scores)
    command=official_eval(c,predictions,folder/'evaluation',[.6])
    if seqmap is not None:command[command.index('--seqmap-file')+1]=str(seqmap)
    save_json(folder/'command.json',{'argv':command,'cwd':str(ROOT/c['upstream']),'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','seed':2025})
    log_run(c,'56-eval',str(folder.relative_to(OUT)),[
        'cd '+shlex.quote(str(ROOT/c['upstream'])),
        "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 "+shlex.join(command)],
        f'官方TrackEval；该次完整覆盖{len(expected_names)}表达式；γ=.6、min-area20、offset0；不使用allow-subset-seqmap。')
    run_logged(command,ROOT/c['upstream'],folder/'trackeval.log')
    detail=folder/'evaluation/tracker'/TAG/'pedestrian_detailed.csv';metric,details=hota_rows(detail,c)
    assert set(details)==set(expected_names)
    result={'complete':True,'seed':2025,'metrics':aggregate(metric,details),'expressions':len(details),'detail_csv':str(detail)}
    save_json(result_file,result)
    return metric,details,result


def oracle_scores(d,kind):
    result={}
    for seq in d.by_seq:
        a=d.scores[seq].copy();matched=d.matched[seq];y=d.y[seq]
        if kind=='GarbageOracle':a[:,~matched]=0
        else:
            assert kind=='SemanticOracle'
            wrong=(a>=.6)!=y;select=wrong & matched[None,:];a[select]=y[select].astype(float)
            assert np.array_equal(a[:,~matched],d.scores[seq][:,~matched])
        result[seq]=a
    return result


def evaluate_grid(d,metric,base_details):
    L=PLAN['LOSO']['min_track_length_grid'];A=PLAN['LOSO']['min_box_area_grid']
    grid={};evaluated=0;aliases=0
    # Cache by exact per-video physical mask. Every frozen parameter pair remains recorded.
    per_sequence_masks={s:[] for s in d.by_seq}
    for length,area in itertools.product(L,A):
        key=f'L{length}_A{area}';grid[key]={}
        for seq,ns in d.by_seq.items():
            mask=d.keep(seq,length,area);folder=OUT/'grid'/key/seq;folder.mkdir(parents=True,exist_ok=True)
            match=next((old for old in per_sequence_masks[seq] if np.array_equal(old['mask'],mask)),None)
            if np.all(mask):
                details={n:base_details[n] for n in ns};info={'alias_to':'R14_identity','detail_csv':str(Path(BASE['evaluation'])/'tracker'/TAG/'pedestrian_detailed.csv')};aliases+=1
            elif match is not None:
                details=match['details'];info={'alias_to':match['key'],'detail_csv':match['detail_csv']};aliases+=1
            else:
                _,details,res=evaluate(d,folder,d.filter_scores({seq:mask}),ns,OUT/'seqmaps'/f'{seq}.txt')
                info={'alias_to':None,'detail_csv':res['detail_csv']};evaluated+=1
            record={**info,'complete':True,'sequence':seq,'min_track_length':length,'min_box_area':area,
                'expressions':len(ns),'kept_physical_rows':int(mask.sum()),'removed_physical_rows':int((~mask).sum())}
            save_json(folder/'grid_entry.json',record)
            np.savez_compressed(folder/'filter_mask.npz',keep=mask)
            grid[key][seq]={'details':details,'record':record,'mask':mask}
            if match is None:per_sequence_masks[seq].append({'key':key,'mask':mask,'details':details,'detail_csv':info['detail_csv']})
        print(f'[R56] grid {key} complete; official per-video evaluations={evaluated}, exact-mask aliases={aliases}',flush=True)
    folds=[];training_rows=[];heldout_masks={};heldout_details=[]
    for held in d.by_seq:
        train=[s for s in d.by_seq if s!=held];best=None
        for length,area in itertools.product(L,A):
            key=f'L{length}_A{area}';training=merge([grid[key][s]['details'] for s in train])
            h=aggregate(metric,training)['HOTA']
            training_rows.append({'held_out_sequence':held,'training_sequences':'+'.join(train),
                'min_track_length':length,'min_box_area':area,'training_HOTA':h,'training_expressions':len(training)})
            # Iteration order is smaller length, then area; keep the first tie.
            if best is None or h>best['training_HOTA']+1e-12:
                best={'held_out_sequence':held,'training_sequences':train,'training_expressions':len(training),
                    'min_track_length':length,'min_box_area':area,'training_HOTA':h,'fitted_scalars':2}
        assert held not in best['training_sequences']
        key=f'L{best["min_track_length"]}_A{best["min_box_area"]}'
        heldout_masks[held]=grid[key][held]['mask'];heldout_details.append(grid[key][held]['details']);folds.append(best)
        print('[R56] frozen LOSO fold:',json.dumps(best),flush=True)
    write_csv(OUT/'LOSO/training_grid.csv',training_rows)
    parameters={'complete':True,'seed':2025,'folds':folds,'max_fitted_scalars':2,'fit_on_full_val':False,
        'grid_size':len(L)*len(A),'per_video_TrackEval_runs':evaluated,'exact_mask_reuses':aliases,
        'objective':PLAN['LOSO']['objective'],'tie_break':PLAN['LOSO']['tie_break']}
    save_json(OUT/'LOSO/parameters.json',parameters)
    fixed=PLAN['fixed_rule'];fixed_key=f'L{fixed["min_track_length"]}_A{fixed["min_box_area"]}'
    fixed_details=merge([grid[fixed_key][s]['details'] for s in d.by_seq])
    fixed_masks={s:grid[fixed_key][s]['mask'] for s in d.by_seq}
    return parameters,heldout_masks,merge(heldout_details),fixed_masks,fixed_details


def rule_removals(d,masks):
    rows=[]
    for seq in d.by_seq:
        removed=(d.scores[seq]>=.6)&~masks[seq][None,:]
        row={'sequence':seq,'removed_positive_rows':int(removed.sum()),'TP_removed':int((removed&d.y[seq]).sum()),
            'semantic_FP_removed':int((removed&d.matched[seq][None,:]&~d.y[seq]).sum()),
            'garbage_FP_removed':int((removed&~d.matched[seq][None,:]).sum()),
            'physical_candidates_removed':int((~masks[seq]).sum()),'physical_candidates_total':len(masks[seq])}
        assert row['removed_positive_rows']==row['TP_removed']+row['semantic_FP_removed']+row['garbage_FP_removed'];rows.append(row)
    return {'total':{k:sum(row[k] for row in rows) for k in rows[0] if k!='sequence'},'per_sequence':rows}


def render(result):
    h=result['HOTA'];b=h['R14'];g=h['GarbageOracle'];s=h['SemanticOracle'];both=h['R20_both_oracles'];rule=h['Rule_LOSO'];capture=h['Rule_LOSO_captured_garbage_oracle']
    attribution=result['attribution'];counts=result['positive_partition']['total'];pos=counts['predicted_positive']
    lines=['# R56：实际候选中的未匹配框与语义错误','',
        '2026-11-04；seed=2025；仅CPU，所有数字相对R14 γ=0.6本地基线。R14/R20/R00–R55结果与官方源码、权重均保持原样；本轮新结果仅在`analysis/runs/R56/`。',
        '', '## 定义与输入字段','',
        '全部862份发布候选均为9列，MOT第7列及第8/9列全为常数1，未提供可用检测置信度。规则只使用原tracker的总可见轨迹长度L和逐帧浮点框面积A：保留当且仅当length≥L且area≥A。同一视频的所有表达式使用完全相同的过滤mask；不使用表达式、YesTrack分数、GT或图像作为过滤特征。轨迹长度是完整轨迹的观察数，包含未来，属于离线规则。',
        '', '“垃圾框”严格按用户指定的R20定义：逐帧Hungarian后没有IoU≥0.5的一对一GT匹配。它是未匹配候选的操作性定义，不能据此认定图像上一定不存在真实物体；分类也不等同于HOTA所有IoU阈值的TP/FP。','',
        '| R14判正候选的R20分类 | 候选数（表达式×对象帧） | 判正候选占比 |', '|---|---:|---:|']
    for label,key in [('TP','TP'),('匹配GT但语义不符','semantic_FP'),('未匹配GT（垃圾框）','garbage_FP')]:
        lines.append(f'| {label} | {counts[key]:,} | {100*counts[key]/pos:.2f}% |')
    lines+=['',f'判正共{pos:,}条；三类互斥且覆盖全部。另有语义漏判{counts["semantic_FN"]:,}条（R20匹配GT且符合表达式，但p<.6）。全部候选1,850,576行。',
        '', '## 两个部分oracle及非加性分解','',
        '①只将未匹配候选置负，其他分数不动。②只纠正已匹配候选的语义FP及FN，未匹配分数不动。两者组合的γ判定与R20全oracle在全部候选上逐值相同；全oracle和基线直接读取原官方详细结果。','',
        '| 版本 | HOTA | DetA | AssA | DetPr | DetRe | ΔHOTA相对R14 |', '|---|---:|---:|---:|---:|---:|---:|']
    for name in ['R14','GarbageOracle','SemanticOracle','R20_both_oracles','Rule_fixed','Rule_LOSO','Rule_LOSO_captured_garbage_oracle']:
        m=result['metrics'][name]
        lines.append('| '+' | '.join([name,*[f'{m[k]:.3f}' for k in ['HOTA','DetA','AssA','DetPr','DetRe']],f'{m["HOTA"]-b:+.3f}'])+' |')
    lines+=['',f'两个单独增益不能相加。交互项H(both)−H(①)−H(②)+H0={attribution["interaction"]:+.3f}；总空间={both-b:.3f}。',
        '', '| 加法归因口径 | 垃圾框HOTA空间 | 语义HOTA空间 | 总计 |', '|---|---:|---:|---:|',
        f'| 主口径：先①再纠语义 | {g-b:.3f} | {both-g:.3f} | {both-b:.3f} |',
        f'| 对称归因（两种顺序平均） | {attribution["Shapley_garbage"]:.3f} | {attribution["Shapley_semantic"]:.3f} | {both-b:.3f} |',
        '', '归因依赖口径；②单独收益已经在上表明确给出，未把它与①收益硬相加。',
        '', '## 表达式无关的简单规则','',
        '固定对照预先设L=10帧、A=400px²。LOSO只拟合L/A两个标量；网格L∈{1,5,10,20,40,80}、A∈{0,100,400,900,1600,3600}。每个网格点逐视频独立调用官方TrackEval；每折只合并其余三个视频的详细结果，以官方HOTA最大化选参，平局取较小L再较小A。没有计算或用完整val网格HOTA选参；所有网格点与等价mask别名都保留。固定版由逐视频官方结果合并；LOSO版另用全部862表达式执行官方TrackEval，并核对与留出视频结果合并一致。','',
        '| 留出序列 | 训练序列 | L | A(px²) | 训练HOTA |', '|---|---|---:|---:|---:|']
    for fold in result['LOSO']['folds']:
        lines.append(f'| {fold["held_out_sequence"]} | {",".join(fold["training_sequences"])} | {fold["min_track_length"]} | {fold["min_box_area"]} | {fold["training_HOTA"]:.3f} |')
    lines+=['', '| 序列 | R14 HOTA | ①清垃圾增益 | ②纠语义增益 | 固定规则增益 | LOSO规则增益 |', '|---|---:|---:|---:|---:|---:|']
    for seq in result['per_sequence']:
        row=result['per_sequence'][seq];h0=row['R14']['HOTA']
        lines.append('| '+' | '.join([seq,f'{h0:.3f}',*[f'{row[n]["HOTA"]-h0:+.3f}' for n in ['GarbageOracle','SemanticOracle','Rule_fixed','Rule_LOSO']]])+' |')
    lines+=['', '| 过滤版本 | 去掉TP | 去掉语义FP | 去掉垃圾FP |', '|---|---:|---:|---:|']
    for name in ['Rule_fixed','Rule_LOSO']:
        a=result['rule_removals'][name]['total'];lines.append(f'| {name} | {a["TP_removed"]:,} | {a["semantic_FP_removed"]:,} | {a["garbage_FP_removed"]:,} |')
    removal=result['rule_removals']['Rule_LOSO']['total'];rec=result['recovery']
    lines+=['',f'固定规则净收益={h["Rule_fixed"]-b:+.3f} HOTA，对应①的{100*(h["Rule_fixed"]-b)/(g-b):.2f}%；③的主结果按预注册使用LOSO。',
        '',f'③LOSO实际净收益={rule-b:+.3f} HOTA，拿回①的{100*rec["actual_rule_fraction_of_garbage"]:.2f}%；它同时移除了TP和语义FP，因此不能把全部净收益都归因清垃圾。',
        '',f'诊断oracle只清除被同一LOSO规则命中的垃圾、保留所有其他分数：提升{capture-b:+.3f} HOTA，即①的{100*rec["isolated_garbage_fraction"]:.2f}%。该诊断使用GT判别“哪些被过滤框是垃圾”，不是可部署规则。垃圾FP命中{removal["garbage_FP_removed"]:,}/{counts["garbage_FP"]:,}（{100*removal["garbage_FP_removed"]/counts["garbage_FP"]:.2f}%）。',
        '',f'垃圾oracle仍未被该规则命中的空间为{g-capture:.3f} HOTA；①与③实际净收益的差为{g-rule:.3f} HOTA，后者还混入TP损失和语义FP减少。残余仅证明这个预注册长度/面积规则族未拿回全部空间，不能证明所有非视觉办法均不行，或必须看图才能解决。',
        '', '## 复现与核验','',
        '官方TrackEval保持原γ=.6、min-area20、offset0、统一pedestrian类与整数框/ID。只读原R14/R20详细指标；新oracle及LOSO完整评测均为862表达式。输入字段与几何全量核对、正候选三分互斥、组合oracle决策等同R20、规则mask跨表达式一致、LOSO训练/留出序列隔离、LOSO完整官方评测与留出逐视频结果合并一致均已检查。',
        '', '[方案](plans/r56.json) · [命令](runs.md) · [输入字段](runs/R56/input_audit.json) · [主结果](runs/R56/result.json) · [逐表达式分类](runs/R56/positive_partition_per_expression.csv) · [训练网格](runs/R56/LOSO/training_grid.csv) · [LOSO参数](runs/R56/LOSO/parameters.json)',
        '', f'**一句话结论：**按先清垃圾再纠语义口径，{both-b:.3f}分空间中垃圾框占{g-b:.3f}、语义纠错占{both-g:.3f}；简单规则实际净拿回{rule-b:.3f}（①的{100*rec["actual_rule_fraction_of_garbage"]:.1f}%），其中仅垃圾命中的oracle收益为{capture-b:.3f}，尚余{g-capture:.3f}垃圾空间未被该规则覆盖，不能据此认定必须看图。','']
    (ROOT/'analysis/REPORT_R56.md').write_text('\n'.join(lines))


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and PLAN['CPU_only'] and BASE['gamma']==.6
    assert not json.loads((OUT/'input_audit.json').read_text())['informative_detection_confidence_present']
    start=time.monotonic();np.random.seed(2025);(OUT/'LOSO').mkdir(parents=True,exist_ok=True);(OUT/'seqmaps').mkdir(exist_ok=True)
    d=Inputs()
    for seq,ns in d.by_seq.items():
        with (OUT/'seqmaps'/f'{seq}.txt').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['name']);w.writerows([[n] for n in ns])
    baseline_csv=Path(BASE['evaluation'])/'tracker'/TAG/'pedestrian_detailed.csv'
    oracle_csv=ROOT/'analysis/runs/R20_oracles/eval_tracker_oracle/tracker'/TAG/'pedestrian_detailed.csv'
    metric,base_details=hota_rows(baseline_csv,c);_,both_details=hota_rows(oracle_csv,c)
    assert set(base_details)==set(both_details)==set(d.names)
    metrics={'R14':aggregate(metric,base_details),'R20_both_oracles':aggregate(metric,both_details)}
    details_by_variant={'R14':base_details,'R20_both_oracles':both_details}
    print('[R56] positive partition:',json.dumps(d.total),flush=True)
    for name in ['GarbageOracle','SemanticOracle']:
        _,details,result=evaluate(d,OUT/name,oracle_scores(d,name),d.names)
        metrics[name]=result['metrics'];details_by_variant[name]=details
        print('[R56] partial oracle:',name,json.dumps(result['metrics']),flush=True)
    parameters,masks,selected_details,fixed_masks,fixed_details=evaluate_grid(d,metric,base_details)
    metrics['Rule_fixed']=aggregate(metric,fixed_details);details_by_variant['Rule_fixed']=fixed_details
    write_predictions(d,OUT/'Rule_fixed/predictions',d.filter_scores(fixed_masks))
    save_json(OUT/'Rule_fixed/result.json',{'complete':True,'metrics':metrics['Rule_fixed'],
        'evaluation':'native HOTA.combine_sequences of the four official per-video fixed-grid evaluations','parameters':PLAN['fixed_rule']})
    _,rule_details,rule_result=evaluate(d,OUT/'Rule_LOSO',d.filter_scores(masks),d.names)
    metrics['Rule_LOSO']=rule_result['metrics'];details_by_variant['Rule_LOSO']=rule_details
    expected=aggregate(metric,selected_details)
    maximum=max(abs(expected[k]-metrics['Rule_LOSO'][k]) for k in expected)
    assert maximum<1e-12,('full OOF vs per-video official evaluation',maximum)
    captured={s:np.where((~d.matched[s]&~masks[s])[None,:],0.,d.scores[s]) for s in d.by_seq}
    name='Rule_LOSO_captured_garbage_oracle'
    _,details,res=evaluate(d,OUT/name,captured,d.names);metrics[name]=res['metrics'];details_by_variant[name]=details
    h={name:a['HOTA'] for name,a in metrics.items()};b=h['R14'];g=h['GarbageOracle'];s=h['SemanticOracle'];both=h['R20_both_oracles'];rule=h['Rule_LOSO'];cap=h[name]
    attribution={'total_space':both-b,'garbage_first_garbage':g-b,'garbage_first_semantic_residual':both-g,
        'independent_semantic_gain':s-b,'interaction':both-g-s+b,
        'Shapley_garbage':((g-b)+(both-s))/2,'Shapley_semantic':((s-b)+(both-g))/2}
    assert abs(attribution['Shapley_garbage']+attribution['Shapley_semantic']-(both-b))<1e-12
    perseq={seq:{name:aggregate(metric,{n:details[n] for n in ns}) for name,details in details_by_variant.items()} for seq,ns in d.by_seq.items()}
    result={'complete':True,'date_asia_shanghai':'2026-11-04','seed':2025,'reference':'relative fixed R14 local baseline gamma0.6',
        'metrics':metrics,'HOTA':h,'attribution':attribution,'per_sequence':perseq,'LOSO':parameters,
        'rule_removals':{'Rule_fixed':rule_removals(d,fixed_masks),'Rule_LOSO':rule_removals(d,masks)},
        'recovery':{'actual_rule_fraction_of_garbage':(rule-b)/(g-b),'isolated_garbage_fraction':(cap-b)/(g-b),
            'remaining_garbage_not_captured_HOTA':g-cap,'net_gap_to_garbage_oracle':g-rule},
        'positive_partition':json.loads((OUT/'positive_partition.json').read_text()),'seconds':time.monotonic()-start,
        'validation':{'combined_R20_decisions_identical':True,'full_LOSO_vs_per_video_metric_maximum_difference':maximum,
            'whole_sequence_LOSO':True,'fit_scalars_per_fold':2,'expression_independent_filter_features':True,
            'no_image_or_LLM_calls':True,'old_results_modified':False}}
    save_json(OUT/'result.json',result)
    write_csv(OUT/'metrics.csv',[{'variant':name,**a,'delta_HOTA':a['HOTA']-b} for name,a in metrics.items()])
    render(result)
    print('[R56] complete:',json.dumps({'HOTA':h,'attribution':attribution,'recovery':result['recovery'],'seconds':result['seconds']}),flush=True)


if __name__=='__main__':main()
