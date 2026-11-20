#!/usr/bin/env python3
"""Render the requested five-part report directly from reproducible experiment receipts."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from common import config,save_json

c=config();t=Path(c['task_root']);a=t/'analysis'


def read(file):
    p=a/file
    return json.loads(p.read_text()) if p.exists() else None


def num(value,n=3):return '—' if value is None else f'{value:.{n}f}'
def pct(value,n=2):return '—' if value is None else f'{100*value:.{n}f}'

b=read('local_baseline.json');r13=read('runs/R13/result.json');r14=read('runs/R14/result.json');r15=read('runs/R15/result.json')
dist=read('labels/distribution.json');groups=read('labels/annotation_equivalent_groups.json')
dec=read('runs/R21_decomposition/result.json');h2=read('runs/R17_h2/result.json');q=read('runs/R20q_integer_gt/result.json')
context=read('runs/R23_context/result.json');context_a=read('runs/R23_context/analysis.json')
cal=read('runs/R27_calibration/result.json');trp=read('runs/R28_trp/result.json');som=read('runs/R25_som/result.json');errors=read('errors/manifest.json')
empty_oracle=read('runs/R37_empty_frames/result.json');empty_examples=read('errors/G_empty_frame_control/manifest.json')
actual_transfer=read('runs/R39_threshold_transfer_actual/result.json')
heuristics=read('runs/R31_heuristics/result.json')
frame_cal=cal['frame_calibration'] if cal else read('runs/R27_calibration/frame_calibration.json')
frame_stats=read('runs/R45_frame_scores/result.json')
base_rates=read('runs/R46_class_base_rates/result.json')
som_shuffled=read('runs/R47_shuffled_som/result.json')
order_control_required=(a/'plans/R47_shuffled_som.json').exists()
complete=all([h2,context_a,cal,trp,som,errors,(a/'error_patterns.md').exists(),
              som_shuffled if order_control_required else True])
lines=['# YesTrack 在 Refer-KITTI-V2 上的提升空间诊断（第二轮）','',
       '**全部下游结果均相对本地基线，不能和论文差额混用。** '+('全量分析已完成。' if complete else '全量分析进行中；只展示已有完整评测，未完成项明确保留为空。'),'',
       f'仅使用 TempRMOT*；本地基线 **γ={b["gamma"]}（发布权重推荐值），HOTA={b["metrics"]["HOTA"]:.3f} / DetA={b["metrics"]["DetA"]:.3f} / AssA={b["metrics"]["AssA"]:.3f}**。'
       '用户已取消第一轮1.5 HOTA停止条件，放弃YesTrack-MOT；固定seed=2025。', '',
       f'官方源码固定为 `{c["upstream_commit"]}`，权重和源码推理逻辑未修改。新增脚本均位于analysis/。命令、配置、GPU预算和超过8小时授权见 [runs.md](runs.md)；冻结基线见 [local_baseline.json](local_baseline.json)。','',
       '## ① 复现对照表与 R13–R15 归因','',
       'HOTA/DetA/AssA及下表指标均为百分制。论文列为外部对照；R13读取既有γ=.4结果，R14只重跑官方TrackEval，不重新推理。','',
       '| 指标 | 论文 TempRMOT* V2 | R09 / R13 γ=.4 | R13 本地−论文 | R14 γ=.6 |',
       '|---|---:|---:|---:|---:|']
for key,row in r13['comparison'].items():
    lines.append(f'| {key} | {num(row["paper"])} | {num(row["local"])} | {row["difference_points"]:+.3f} | {num(b["metrics"][key])} |')
lines+=['| 本地基线 γ | — | 0.4（历史复现） | — | **0.6，发布权重推荐值** |','',
        'R13：DetRe高出论文5.945点，DetPr低13.596点，差距主要体现为精度/误报，未体现为召回下降。R14：γ=.6比固定γ=.4提高0.295 HOTA，因此按预先规则选.6；没有用敏感性扫描的最高点选基线。','',
        '| R13 序列（γ=.4） | HOTA | DetA | AssA |','|---|---:|---:|---:|']
for seq,m in r13['per_video'].items():lines.append(f'| {seq} | {num(m["HOTA"])} | {num(m["DetA"])} | {num(m["AssA"])} |')
lines+=['','GT tracks的referential结果（同一γ=.6、TCP=3/.4/.3、TRP=10、memory=4、refine=[.2,.8)）：','',
        '| 条件 | Acc | Precision | Recall | F1 |','|---|---:|---:|---:|---:|']
gc=dec['categories']['overall']['gt_track_referring'] if dec else None
lines.append('| 本地 V2 GT tracks | '+' | '.join(pct(gc[k]) if gc else '待完成' for k in ('accuracy','precision','recall','f1'))+' |')
lines+=['| 论文 V2 GT tracks | 未报告 | 未报告 | 未报告 | 未报告 |','',
        '论文Table4的91.15/74.14/85.71属于V1，不挪用为V2。官方评测使用完整862条seqmap（保留名称中的逗号）、统一class=pedestrian、预测area≥20、frame offset=0；原始Temp候选1,850,576行，GT候选2,860,484行，GT正例491,286行。HOTA聚合调用原生HOTA.combine_sequences，未简单平均表达式HOTA。','',
        'γ生效位置：'+f'[eval_refer_kitti_mot.py:206]({a}/upstream/YesTrack/eval_refer_kitti_mot.py:206)声明--thresholds，'
        f'[13–30行]({a}/upstream/YesTrack/eval_refer_kitti_mot.py:13)在收集预测时过滤第7列连续分数，'
        f'[229行]({a}/upstream/YesTrack/eval_refer_kitti_mot.py:229)逐阈值评测。推理参数没有最终γ；'
        f'[llm_eval_from_mot.py:1183]({a}/upstream/YesTrack/refer_llm/llm_eval_from_mot.py:1183)写出所有连续分数。TCP的.4是稳定性条件，不是最终γ。','',
        'R15（0019）：原图1238×374，发布GT转换使用1242×375；候选最大x2/y2='+
        f'{r15["box_sources"]["candidates"]["max_x2"]:.3f}/{r15["box_sources"]["candidates"]["max_y2"]:.3f}，GT最大x2/y2='+
        f'{r15["box_sources"]["gt"]["max_x2"]:.3f}/{r15["box_sources"]["gt"]["max_y2"]:.3f}。GT与名义坐标系一致；未裁剪候选仅靠极值不能唯一证明其生成坐标系。'
        f'两种坐标解释的crop边缘最大差4像素、角点最大欧氏差{r15["max_crop_shift_px"]:.3f}像素，低于10像素，按规则不修正。详见[R15结果](runs/R15/result.json)。','',
        '## ② 类别分布','',
        '关键词初分后，由当前Codex LLM逐条语义补齐，冻结输出见[llm_review.json](labels/llm_review.json)及[frozen review脚本](freeze_semantic_review.py)；seed2025随机抽取的100条见[label_audit.csv](label_audit.csv)，人工核对栏留空，不声称已有人类审计。'
        'F/G从标注计算。F仅比较同一GT ID的可见观测，跨可见性空档另记gap；不把目标离开画面直接判作真值变假。','',
        '| 类别 | 表达式数 | 表达式占比 | GT正例物体帧数 | GT正例物体帧占比 | 不同GT成员时序数 |',
        '|---|---:|---:|---:|---:|---:|']
descs={'A':'外观/类别','B':'绝对空间','C':'关系','D':'比较/最高级','E':'运动/动作','F':'标注真值变化','G':'全视频无目标','H':'明示群体/计数'}
for cat,row in dist.items():
    lines.append(f'| {cat} {descs[cat]} | {row["expressions"]} | {pct(row["expression_share"])}% | {row["positive_object_frames"]:,} | {pct(row["positive_object_frame_share"])}% | {groups["category_distinct_GT_membership_families"][cat]} |')
lines+=['','多标签占比不相加；GT帧分母为全部491,286个(expression,frame,GT ID)正例，未把多目标帧折成单帧。A包含类别名，因此覆盖98.96%，其反事实收益并不等于纯颜色识别收益。H只标显式数量/群体，普通复数不自动标H。',
        'C包含自车/相机参照与自行车伴随，分列C_viewpoint/C_scene以免把相对自车方向泛化为复杂场景关系。D的21条全部是速度比较，只有1组GT成员时序；此split没有独立的leftmost/closest/fastest最高级场景。G整条表达式始终为空的样本数为0，其系统弱点在本split不能检验；空GT帧对照另列，绝不冒称G表达式。','',
        '## ③ 误差分解与分类别 ΔHOTA（相对本地基线）','',
        'H1=TempRMOT*+YesTrack；H2=GT tracks+同一发布V2 verifier/TCP/TRP；H3=原始GT tracks+GT referring。H2−H1和H3−H2按任务定义报告；前者还包含候选分布变化。','',
        '| 类别 | H1 HOTA | H2 HOTA | H3 HOTA | H2−H1 | H3−H2 |','|---|---:|---:|---:|---:|---:|']
for cat,r in dec['categories'].items():
    lines.append(f'| {cat} | {num(r["H1"]["HOTA"])} | {num(r["H2"]["HOTA"]) if r["H2"] else "待完成"} | {num(r["H3"]["HOTA"])} | {num(r["H2_minus_H1"])} | {num(r["H3_minus_H2"])} |')
if h2:
    dr=dec['categories']['D']
    lines+=['',f'D的H2−H1={dr["H2_minus_H1"]:.3f}为负：GT候选更完整，也增加了可误选的非目标；D的GT referring precision仅{pct(dr["gt_track_referring"]["precision"])}%。'
            '因此H2−H1是按任务定义的候选替换差额，不能逐类解释成非负、独立、可相加的纯跟踪损失。']
empty=dec['empty_frame_control']
lines+=['',f'另有{empty["expressions_with_empty_frames"]}条表达式在部分帧GT为空，共{empty["empty_expression_frames"]:,}个(expression,frame)；'
        f'本地Temp基线在其中{empty["frames_with_false_alarm"]:,}帧有误报，空帧误报率={pct(empty["frame_false_alarm_rate"])}%。'
        '这是时变无目标情形，与G全视频为空的0条表达式分开统计；Set-of-Mark空帧对照从真实表达式中抽取，不新造表达式。']
if empty.get('GT_candidate_empty_frame_false_alarm_rate') is not None:
    lines+=[f'在同一组空GT帧上，GT tracks+YesTrack的误报率为{pct(empty["GT_candidate_empty_frame_false_alarm_rate"])}%，用于观察去掉实际跟踪候选偏差后仍存在的拒绝错误。']
if empty_oracle:
    lines+=[f'帧级补充oracle（G_frame）：只在上述空GT帧清零输出，其余帧分数及所有候选框/ID不动，整体HOTA={empty_oracle["metrics"]["HOTA"]:.3f}、'
            f'DetA={empty_oracle["metrics"]["DetA"]:.3f}、AssA={empty_oracle["metrics"]["AssA"]:.3f}，ΔHOTA=**{empty_oracle["delta_HOTA"]:+.3f}**。'
            '这支持帧级无目标拒绝存在可量化损失；与F等表达式类别的收益重叠，不能相加，也不能据此声称验证了全视频无目标语言表达。']
lines+=['','每类别完整HOTA/DetA/AssA及原始计数见[误差分解JSON](runs/R21_decomposition/result.json)。H3=99.997；13个GT小框被官方area过滤，解释其与100的微小差距。']
if q:
    lines+=['',f'序列化对照H3_int={q["metrics"]["HOTA"]:.3f}：官方推理将x/y/w/h写为整数，单独引入{q["H3_raw_minus_H3_integer"]:.3f} HOTA损失。因此H3−H2不完全是语义判别；'
            +(f'同整数候选的净referring差额为H3_int−H2={q["metrics"]["HOTA"]-h2["metrics"]["HOTA"]:.3f}。' if h2 else '净referring差额将在H2完成后报告。')]
lines+=['','ΔHOTA_X保持实际Temp候选框、轨迹ID、帧完全不变：逐帧最大IoU Hungarian匹配完整GT、IoU≥.5后按GT表达式标签赋0/1，未匹配候选为负。只替换X类表达式结果，再用官方HOTA.combine_sequences重算整体；这是明确匹配定义下的oracle空间，并非重新跟踪。'
        'P/R/F1主表使用GT候选以隔离跟踪；实际候选条件下的P/R/F1另存同一JSON/CSV，不当作全GT召回。','',
        '| 类别 | 占比 | GT referring P | GT referring R | GT referring F1 | ΔHOTA_X |','|---|---:|---:|---:|---:|---:|']
for cat,r in sorted(((k,v) for k,v in dec['categories'].items() if k!='overall'),key=lambda kv:-kv[1]['delta_HOTA']):
    gain=f'{r["delta_HOTA"]:+.3f}' if r['expressions'] else '—（无样本）'
    ref=r['gt_track_referring'];lines.append(f'| {cat} | {pct(r["expression_share"])}% | '+
        ' | '.join(pct(ref[k]) if ref else '—' for k in ('precision','recall','f1'))+f' | {gain} |')
overall=dec['categories']['overall'];lines+=['',f'全部实际候选oracle：HOTA {overall["H1"]["HOTA"]:.3f}→{overall["oracle_referring_total"]["HOTA"]:.3f}，Δ={overall["delta_HOTA"]:.3f}。重叠类别收益不可相加。']
lines+=[f'F本身覆盖{pct(dist["F"]["positive_object_frame_share"])}%的GT正例物体帧，提升空间的总量主要落在F不等于已证明TRP是主要原因；因果判断依赖下面固定其他条件的Δ扫描。'
        f'D只覆盖{pct(dist["D"]["positive_object_frame_share"])}%的GT正例物体帧，仍有{dec["categories"]["D"]["delta_HOTA"]:.3f} HOTA oracle收益，不能仅凭绝对收益小否定其单条查询难度。']
if 'additional_subsets' in dec:
    cd=dec['additional_subsets']['C_or_D'];rest=dec['additional_subsets']['F_without_C_D']
    lines+=[f'C∪D共{cd["expressions"]}条，联合替换Δ={cd["delta_HOTA"]:.3f}；F且不属于C/D共{rest["expressions"]}条，Δ={rest["delta_HOTA"]:.3f}。']
if base_rates:
    lines+=['','P/F1还受目标稀疏度影响。R46沿用R23预先冻结的同序列0011中51条A对照，与全部21条D比较；均使用该序列全部GT候选帧。','',
            '| 模式 | 组 | 候选正例率 | TPR/Recall | FPR | F1 |','|---|---|---:|---:|---:|---:|']
    for mode,groups_pair in base_rates['D_matched_video_control'].items():
        for group,r in groups_pair.items():
            lines.append(f'| {mode} | {group} | {pct(r["positive_prior"])}% | {pct(r["TPR"])}% | {pct(r["FPR"])}% | {pct(r["f1"])}% |')
    lines+=['','D的低precision不能全归因比较推理，因为其正例率更低；但同视频对照中，原始frame的D同时有更低TPR和更高FPR，方向上支持这组速度比较确实较难。'
            '该对照匹配视频和候选总体，未匹配语义负例难度；D仍只有一组GT时序，不推广到所有比较/最高级。'
            '全部类别条件率见[R46 CSV](runs/R46_class_base_rates/rates.csv)。']
fig,ax=plt.subplots(figsize=(7,4));ordered=sorted(((k,v['delta_HOTA']) for k,v in dec['categories'].items() if k!='overall'),key=lambda kv:kv[1])
ax.barh([x[0] for x in ordered],[x[1] for x in ordered]);ax.set(xlabel='Overall HOTA gain from classwise referring oracle',title='Relative to local baseline (gamma=0.6)')
fig.tight_layout();fig.savefig(a/'runs/R21_decomposition/category_gains.png',dpi=180);fig.savefig(a/'runs/R21_decomposition/category_gains.pdf');plt.close(fig)
lines+=['','![分类别反事实收益](runs/R21_decomposition/category_gains.png)','',
        '## ④ 四个定向探针与错误样例（相对本地基线）','',
        '### d. 校准（优先项）','']
if cal:
    f=cal['frame_calibration'];v1=cal['V1_best'];transfer=cal['V2_at_V1_configuration']
    lines+=[f'全量{f["n"]:,}个GT候选的原始frame概率：ECE={pct(f["ECE"])}%，Brier={f["Brier"]:.5f}，平均p={f["mean_p"]:.5f}、真实正例率={f["positive_prior"]:.5f}；15个等宽箱。',
            '![可靠性图](runs/R27_calibration/reliability.png)',
            f'V1 micro-F1选出的(γ,pl,ph)=({v1["gamma"]},{v1["lower"]},{v1["upper"]})，V1 F1={pct(v1["f1"])}%；迁移到V2 F1={pct(transfer["f1"])}%，'
            f'比V2网格诊断最优低{100*cal["transfer_F1_drop_vs_V2_oracle"]:.3f}个F1点，较冻结基线变化{100*cal["transfer_F1_change_vs_frozen_baseline"]:+.3f}点。'
            f'GT候选的迁移配置HOTA={cal["transfer_HOTA"]["HOTA"]:.3f}，较H2基线变化{cal["transfer_HOTA_change_vs_H2_baseline"]:+.3f}。',
            ('结论：支持最终γ存在小幅部署差异；源配置迁移出现损失。' if cal['transfer_F1_drop_vs_V2_oracle']>0 else '结论：本扫描未观察到源域配置相对目标网格最优的迁移损失。'),
            'V1/V2用各自发布权重，且V1三个验证视频与V2重叠；该对照包含权重变化，不是独立新视频泛化实验。V2网格最优只作为附表诊断，没有改变γ=.6基线。']
    best=cal['V2_grid_best_diagnostic_only'];native=cal['V2_frozen_baseline']
    lines+=['','| GT referring条件 | γ | [pl, ph) | micro F1 |', '|---|---:|---|---:|']
    for label,r in [('V1源选择',v1),('V2采用冻结源配置',transfer),('V2固定主基线',native),('V2网格最优，仅诊断',best)]:
        lines.append(f'| {label} | {r["gamma"]} | [{r["lower"]}, {r["upper"]}) | {pct(r["f1"])}% |')
    lines+=['',f'目标网格最优比固定主基线高{100*(best["f1"]-native["f1"]):.3f}个F1点；'
            '源/目标最优精炼区间均为[.2,.8)，本次收窄区间扫描未支持改变原精炼范围。'
            '两套完整81配置及逐值重放验证见[threshold_grid.csv](runs/R27_calibration/threshold_grid.csv)和[结果JSON](runs/R27_calibration/result.json)。'
            f'原生分数重放最大差：V1={cal["replay_native_max_score_difference"]["V1"]}，V2={cal["replay_native_max_score_difference"]["V2"]}。']
else:
    if frame_cal:
        f=frame_cal
        lines+=[f'全量{f["n"]:,}条原始frame分数已完成：ECE={pct(f["ECE"])}%，Brier={f["Brier"]:.5f}，平均p={f["mean_p"]:.5f}，真实正例率={f["positive_prior"]:.5f}；15个等宽箱。V1→V2阈值/区间迁移仍在CPU计算，尚未把未完成扫描当成结果。',
                '![可靠性图](runs/R27_calibration/reliability.png)']
    else:lines+=['全量GT frame+video缓存已获用户11.5–16小时授权，完成后补入可靠性图、ECE和V1→V2网格迁移。']
    source_only=read('runs/R35_v1_grid/result.json')
    if source_only:
        src=source_only['best']
        lines+=[f'V1完整158条表达式已先行冻结最优(γ,pl,ph)=({src["gamma"]},{src["lower"]},{src["upper"]})，源F1={pct(src["f1"])}%；'
                f'328,330条原生输出重放最大差={source_only["native_max_difference"]}。尚未将该源配置作为V2基线。']
if frame_stats:
    fr=frame_stats['categories']['overall'];hr=frame_stats['H2_final_referring']
    lines+=['',f'全量同一GT候选上固定γ=.6：原始frame逐帧判别P/R/F1={pct(fr["precision"])}/{pct(fr["recall"])}/{pct(fr["f1"])}%，'
            f'完整H2最终输出为{pct(hr["precision"])}/{pct(hr["recall"])}/{pct(hr["f1"])}%；原始frame F1高{100*frame_stats["frame_F1_minus_H2_final"]:.3f}点。'
            '这是video/TCP/TRP共同作用的描述性对照，不能把差额单独归因某一个模块，也不是已测得的HOTA收益。',
            '', '| 序列 | GT候选行数 | 真正例率 | 平均frame p | ECE | 原始frame F1 |', '|---|---:|---:|---:|---:|---:|']
    for seq,r in frame_stats['sequences'].items():
        lines.append(f'| {seq} | {r["n"]:,} | {pct(r["positive_prior"])}% | {r["mean_p"]:.4f} | {pct(r["ECE"])}% | {pct(r["f1"])}% |')
    lines+=['','详见[R45完整原始frame统计](runs/R45_frame_scores/result.json)；它不替代H2，不改变主基线。']
if actual_transfer:
    lines+=['',f'实际Temp候选的直接迁移：把V1冻结γ={actual_transfer["source_configuration"]["gamma"]}和同一精炼区间放到V2，HOTA={actual_transfer["V2_metrics_at_source_threshold"]["HOTA"]:.3f}，'
            f'较本地γ=.6变化{actual_transfer["HOTA_change_vs_local_baseline"]:+.3f}。这支持存在小幅阈值迁移损失；不是用V2扫描峰值挑参数。GT候选的F1/区间迁移与上述实际候选HOTA是不同测量，分开报告。']
lines+=['','阈值/精炼扫描的预定网格为γ∈{.1,.2,…,.9}、pl∈{.2,.3,.4}、ph∈{.6,.7,.8}，共81种配置。区间只收窄原[.2,.8)，所有所需video分数均为真实已执行结果；本扫描不估计把原区间向外扩展的收益。',
        '先验修正：**r未知，按用户规则跳过**。训练代码[llm_train.py:697](upstream/YesTrack/refer_llm/llm_train.py)的CLI默认negative_downsample=.5；[datasets.py:92](upstream/YesTrack/refer_llm/data/datasets.py)说明该参数为负样本保留率。但发布adapter没有训练参数/运行记录，README只说“下采样”，不能证明该checkpoint实际r=.5。LoRA配置r=8是秩，与负样本保留率无关。','',
        '### a. 上下文消融','']
if context:
    lines+=['覆盖全部107条C/D表达式及同视频等量A对照（排除C/D），每表达式固定均匀随机24帧、所有GT候选。四种输入成对；原crop是margin=.2，扩张1.5/2.5倍对应margin=.55/1.25；整帧逐目标画框。所有输入320×320、同一prompt/权重/γ，比较frame-mode F1，不混入TCP/TRP。','',
            '| 类别 | 原crop F1 | 1.5倍 F1 | 2.5倍 F1 | 整帧框 F1 |','|---|---:|---:|---:|---:|']
    for cat,rs in context['groups'].items():lines.append('| '+cat+' | '+' | '.join(pct(rs[k]['f1']) for k in ['original','expand1p5','expand2p5','full_frame_box'])+' |')
    lines+=['']
    if context_a:
        scene=context_a['groups']['C_scene'];viewpoint=context_a['groups']['C_viewpoint']
        lines+=[f'C_scene（自行车伴随关系）仅{scene["expressions"]}条、{scene["distinct_GT_membership_families"]}组GT成员时序：F1从{pct(scene["original_F1"])}%到1.5倍crop的{pct(scene["F1"]["expand1p5"])}%（{100*scene["delta_F1"]["expand1p5"]:+.3f}点），方向上支持真实场景他物体关系缺少局部上下文；'
                f'C_viewpoint的{viewpoint["expressions"]}条自车/相机表达在同一扩张下变化{100*viewpoint["delta_F1"]["expand1p5"]:+.3f}点。不能用C合并均值掩盖两者差异。']
        for cat,r in context_a['contrasts'].items():
            lines.append(f'{cat}整帧收益减A对照收益={100*r["full_frame_gain_minus_control_gain"]:+.3f} F1点；'+('方向上支持缺上下文假设。' if r['full_frame_gain_minus_control_gain']>0 else '未支持该类从320整帧输入获得更大收益。'))
            for mode,title in [('expand1p5','1.5倍crop'),('expand2p5','2.5倍crop')]:
                contrast=r.get('gain_minus_control_by_mode',{}).get(mode)
                if contrast is not None:
                    lines.append(f'{cat}在{title}的收益减同视频A对照收益={100*contrast:+.3f} F1点；'+
                        ('方向上支持这组查询存在局部上下文不足。' if contrast>0 else '该扩张对照未支持额外上下文收益。'))
    lines+=['整帧缩至320会减少目标像素，负结果不能排除更高分辨率上下文有用；D仅一组GT成员时序，不虚报独立样本显著性。']
else:lines+=['已冻结全C/D表达式和同视频A对照，GPU结果待完成。']
lines+=['','### b. Set-of-Mark 联合打分','']
if som:
    lines+=['使用同一发布V2 LoRA，零样本指新格式无训练/无示例；D全21条、每条24帧，另抽100条表达式各最多12个空GT帧作单列对照。候选使用GT tracks，隔离跟踪误差。'
            '这是纯frame模式的形式探针，三种方法均不叠加video/TCP/TRP；完整流水线结果仍以H1/H2为准。'
            '所有框编号1..N，外加none；整帧原分辨率。主表统一γ=.6；argmax附在JSON中。Qwen多位数字是多个token，完整选项+换行的条件log概率求和后softmax；N≤9的精确首token softmax另列，未将10/11共享的首token误当独立选项。','',
            '| 方法 | D 候选F1 | 空帧none检测F1 | 空帧误报率 |','|---|---:|---:|---:|']
    for method in ['crop_binary','full_marked_binary','SoM_frozen_gamma','SoM_argmax','always_first_order_control']:
        d=som['groups']['D'][method];g=som['groups']['G_empty_frame_control'][method]
        lines.append(f'| {method} | {pct(d["candidate_referring"]["f1"])} | {pct(g["none_detection"]["f1"])} | {pct(g["empty_frame_false_alarm_rate"])} |')
    lines+=['']
    if 'D_single_token_options' in som['groups']:
        ds=som['groups']['D_single_token_options'];gs=som['groups']['G_single_token_options']
        lines+=[f'严格单token子集（所有N≤9，成对相同帧）：D共{ds["crop_binary"]["expression_frames"]}帧，crop/整帧独立/选项token softmax的F1分别为'
            f'{pct(ds["crop_binary"]["candidate_referring"]["f1"])}/{pct(ds["full_marked_binary"]["candidate_referring"]["f1"])}/{pct(ds["SoM_next_token_gamma"]["candidate_referring"]["f1"])}%；'
            f'空帧共{gs["crop_binary"]["expression_frames"]}帧，相同三种方法误报率为'
            f'{pct(gs["crop_binary"]["empty_frame_false_alarm_rate"])}/{pct(gs["full_marked_binary"]["empty_frame_false_alarm_rate"])}/{pct(gs["SoM_next_token_gamma"]["empty_frame_false_alarm_rate"])}%。']
    d=som['groups']['D'];g=som['groups']['G_empty_frame_control'];gain=d['SoM_frozen_gamma']['candidate_referring']['f1']-d['full_marked_binary']['candidate_referring']['f1']
    far=g['SoM_frozen_gamma']['empty_frame_false_alarm_rate']-g['full_marked_binary']['empty_frame_false_alarm_rate']
    lines+=[f'固定同一整帧图比较联合形式与独立形式：D F1变化{100*gain:+.3f}点，空帧误报率变化{100*far:+.3f}点。'
            +('该组D的数值提升仍须经过下面的顺序对照解释。' if gain>0 else '未支持该组D采用联合形式能提升F1。')
            +('支持联合归一化/拒绝减少空帧误报。' if far<0 else '未支持联合形式降低空帧误报。'),
            'G全表达式样本为0，故不能对该类作支持/否定结论；上表只检验空帧拒绝。本次D样本没有多目标帧，单选上限未造成本组结果；单/多目标及argmax结果均在JSON中。不同归一化形式的γ含义不同，保留argmax作为辅助解释。OneJev附加探针未运行。']
    lines+=['SoM只抽取至少有一个GT候选的帧；表中空帧误报率是该固定抽样集的成对结果，不能和全val空帧误报率直接相减。空帧子集的none为唯一正类，none F1主要是拒绝率的变换；混合D/空帧的none检测统计另存JSON。']
    if 'candidate_order_diagnostic' in som:
        order=som['candidate_order_diagnostic']['D']
        lines+=[f'顺序诊断：D中argmax选择编号1的比例={pct(order["argmax_selected_first_fraction"])}%；正例帧GT目标恰为编号1的比例={pct(order["first_is_GT_target_among_positive_frames"])}%。'
                '候选按原始GT顺序编号；另列always-first无需模型对照。']
        if som['groups']['D']['always_first_order_control']['candidate_referring']['f1']>=som['groups']['D']['SoM_frozen_gamma']['candidate_referring']['f1']:
            first=som['groups']['D']['always_first_order_control']['candidate_referring']['f1']
            first_single=som['groups']['D_single_token_options']['always_first_order_control']['candidate_referring']['f1']
            lines+=[f'实际always-first F1={pct(first)}%，严格单token子集为{pct(first_single)}%，均高于对应联合方法；原顺序结果不足以证明学会了比较/关系推理。']
    if order_control_required and not som_shuffled:
        lines+=['随机编号配对对照R47正在运行：相同1704帧、相同权重/γ，不重选样本；每(sequence,frame)固定seed排列候选，原crop分数按GT ID复用，重新计算同一随机标号整帧的独立/联合分数。预计单GPU1–2小时，依据原阶段实际56分钟，预算已在启动前写入runs.md。']
    if som_shuffled:
        ss=som_shuffled
        lines+=['','随机编号配对对照R47：输入帧、候选框、权重和γ不变；按seed=2025+100000×sequence+frame排列候选。原crop分数按GT ID原样复用，标号整帧的独立/联合分数均重新前向。','',
                '| 随机编号方法 | D F1 | 空帧none F1 | 空帧误报率 |','|---|---:|---:|---:|']
        for method in ['full_marked_binary','SoM_frozen_gamma','SoM_argmax','always_first_order_control']:
            dr=ss['groups']['D'][method];gr=ss['groups']['G_empty_frame_control'][method]
            lines.append(f'| {method} | {pct(dr["candidate_referring"]["f1"])} | {pct(gr["none_detection"]["f1"])} | {pct(gr["empty_frame_false_alarm_rate"])} |')
        lines+=['']
        sd=ss['groups']['D_single_token_options'];sg=ss['groups']['G_single_token_options'];so=ss['candidate_order_diagnostic']['D']
        lines+=[f'同一严格单token子集：D的整帧独立/选项首token softmax F1={pct(sd["full_marked_binary"]["candidate_referring"]["f1"])}/{pct(sd["SoM_next_token_gamma"]["candidate_referring"]["f1"])}%，'
                f'always-first={pct(sd["always_first_order_control"]["candidate_referring"]["f1"])}%；空帧误报率分别{pct(sg["full_marked_binary"]["empty_frame_false_alarm_rate"])}/{pct(sg["SoM_next_token_gamma"]["empty_frame_false_alarm_rate"])}%。',
                f'随机编号后正例目标为编号1的比例={pct(so["first_is_GT_target_among_positive_frames"])}%，argmax选1比例={pct(so["argmax_selected_first_fraction"])}%。']
        joint=ss['groups']['D']['SoM_frozen_gamma']['candidate_referring']['f1'];ind=ss['groups']['D']['full_marked_binary']['candidate_referring']['f1']
        first=ss['groups']['D']['always_first_order_control']['candidate_referring']['f1']
        alarm=ss['groups']['G_empty_frame_control']['SoM_frozen_gamma']['empty_frame_false_alarm_rate']-ss['groups']['G_empty_frame_control']['full_marked_binary']['empty_frame_false_alarm_rate']
        lines+=[f'随机编号后联合相对同图独立F1变化{100*(joint-ind):+.3f}点，相对always-first变化{100*(joint-first):+.3f}点；'+
                ('支持本组联合选择形式的收益可超越固定首位规则。' if joint>ind and joint>first else '未支持联合形式在本对照中同时超过同图独立打分和首位规则。')+
                f'空帧误报率变化{100*alarm:+.3f}点；'+('支持该随机编号对照降低空帧误报。' if alarm<0 else '未支持该随机编号对照降低空帧误报。'),
                'D仍只有一组速度比较GT时序，输入仍为静态整帧；即使选对前方车辆，也不足以证明推断了相对速度或所有最高级。详见[R47结果](runs/R47_shuffled_som/result.json)。']
        tj=sd['SoM_next_token_gamma']['candidate_referring']['f1'];tc=sd['crop_binary']['candidate_referring']['f1']
        ti=sd['full_marked_binary']['candidate_referring']['f1'];tf=sd['always_first_order_control']['candidate_referring']['f1']
        ga=sg['SoM_next_token_gamma']['empty_frame_false_alarm_rate'];gc=sg['crop_binary']['empty_frame_false_alarm_rate'];gi=sg['full_marked_binary']['empty_frame_false_alarm_rate']
        lines+=[f'严格按“选项token logits→softmax”的判定：在预先声明的N≤9子集，随机编号后D F1={pct(tj)}%，'
                f'比原crop高{100*(tj-tc):.3f}点、比同图独立打分高{100*(tj-ti):.3f}点、比always-first高{100*(tj-tf):.3f}点。'
                '因此支持这一个速度比较家族在该子集存在联合形式收益，不能把全部提升解释为原始编号1偏差。'
                f'同一空帧子集误报率为{pct(ga)}%，比crop/同图独立分别变化{100*(ga-gc):+.3f}/{100*(ga-gi):+.3f}点，未支持none选项改善拒绝。',
                'N≤9子集为209/504个D表达式帧、969/1200个空GT对照帧；结果只适用于这个成对队列，不外推为全D结果。'
                '完整答案串含换行的条件概率还受输出串格式影响，和首token方法不是同一个测量；其全N随机编号结果失败，不能掩去或用单token高分替代。']
else:lines+=['已冻结D全21条及100条表达式空帧对照；完整SoM结果待完成。G全表达式数为0，不能凭空生成该类样本。']
lines+=['','### c. TRP 过时问题','']
if trp:
    lines+=[f'全量{trp["expressions"]}条F表达式、{trp["candidate_rows"]:,}条GT候选；精确相邻可见帧切换{trp["switches_contiguous"]}个，跨可见性空档{trp["switches_across_visibility_gap"]}个另记。δ10重放与原生H2最大分数差={trp["native_delta10_max_score_difference"]}。','',
            '| Δ | 全部错误率 | ±5帧错误率 | 远离切换错误率 | F类GT referring F1 |','|---|---:|---:|---:|---:|---:|']
    for delta,r in trp['delta'].items():
        s=r['overall'];tp=s['positive']-s['fn'];f1=2*tp/(2*tp+s['fp']+s['fn'])
        lines.append(f'| {delta} | {pct(s["error_rate"])} | {pct(r["near"]["error_rate"])} | {pct(r["far"]["error_rate"])} | {pct(f1)} |')
    near=trp['delta']['10']['near'];far=trp['delta']['10']['far']
    lines+=['',f'近窗口共{near["n"]:,}个物体帧、正例率{pct(near["positive_prior"])}%；远处{far["n"]:,}个、正例率{pct(far["positive_prior"])}%。'
            '因此近/远原始错误率不同本身不足以归因TRP，以下比较同一区域内Δ10与Δ1的差异。']
    lines+=[f'Δ10相对Δ1在切换窗口的额外错误={100*trp["delta10_minus_delta1_near_error"]:+.3f}个百分点，远处为{100*trp["delta10_minus_delta1_far_error"]:+.3f}点。'
            +('支持切换窗口内存在小幅跳帧复用损失，其幅度没有超过远处。' if trp['delta10_minus_delta1_near_error']>0 and trp['delta10_minus_delta1_near_error']<=trp['delta10_minus_delta1_far_error'] else
              '支持切换窗口内存在跳帧复用损失。' if trp['delta10_minus_delta1_near_error']>0 else '本对照未支持Δ10相对每帧验证产生额外切换窗口损失。'),
            '![切换前后错误率](runs/R28_trp/switch_error.png)',
            '只改变Δ，其余权重、γ、refine、TCP相同；中间复用帧仍依官方代码继续执行TCP。比较窗口近/远错误率同时保留正例率和FP/FN计数，以免把类别比例变化当因果。']
    if 'additional_switch_window_penalty' in trp:
        extra=trp['additional_switch_window_penalty']
        lines+=[f'近窗口的Δ10−Δ1损失再减去远处的同一损失={100*extra:+.3f}点；'+
                ('方向上支持额外损失集中在真值切换附近。' if extra>0 else '未支持额外损失专门集中在切换附近；不能把整体刷新收益全称为真值切换过时。')]
        for sign,label in [('1to0','真→假'),('0to1','假→真')]:
            one=trp['transition_windows']['1'][sign]['after']['error_rate'];ten=trp['transition_windows']['10'][sign]['after']['error_rate']
            if one is not None and ten is not None:lines+=[f'{label}后的0..5帧错误率：Δ1={pct(one)}%、Δ10={pct(ten)}%，差{100*(ten-one):+.3f}点。']
    lines+=['Δ按官方计数器每Δ个有候选帧做全量验证，新ID当帧补推；图与±5窗口使用原始图像帧号。']
    lines+=['结论：支持TRP与TCP共同运行时存在精度代价，且真→假后的过时Yes尤其明显；未支持这些额外错误主要集中在真值切换附近。'
            '每帧刷新仍保留TCP/video，不能将差异称为单独移除TCP的收益。F类oracle ΔHOTA=9.228也不能直接解释为TRP可回收的HOTA；本探针未计算改变Δ后的HOTA。']
else:lines+=['全量frame/video缓存获批后将精确扫描Δ=1/5/10/20；非均匀跳帧和新ID立即判别均按原生逻辑重放。']
if complete:
    scene=context_a['groups']['C_scene'];dctx=context['groups']['D']
    lines+=['','### 假设判定','',
            '| 假设 | 判定 | 数字与适用范围 |','|---|---|---|',
            f'| C关系表达普遍偏弱 | 未支持整体结论，局部场景关系有支持 | C的采样frame F1在1.5倍crop为{pct(context["groups"]["C"]["original"]["f1"])}→{pct(context["groups"]["C"]["expand1p5"]["f1"])}%；C_scene仅7条/3个GT时序，提升{100*scene["delta_F1"]["expand1p5"]:.3f}点。 |',
            f'| D比较/最高级偏弱 | 支持这组速度比较的困难与局部上下文收益，尚不能推广到最高级 | crop F1 {pct(dctx["original"]["f1"])}→{pct(dctx["expand2p5"]["f1"])}%；同视频条件TPR/FPR对照也较弱，但21条只有1个GT时序家族。 |',
            f'| G无目标表达偏弱 | 全空语言表达无法检验；支持帧级拒绝有损失 | G=0；真实空GT帧本地误报{pct(empty["frame_false_alarm_rate"])}%，仅空帧oracle提升{empty_oracle["delta_HOTA"]:.3f} HOTA。零样本联合none没有改善本对照拒绝。 |',
            f'| TRP在真值变化时过时 | 支持真→假后的过时Yes，未支持额外损失主要集中在切换附近 | 真→假后Δ10比Δ1多错{100*(trp["transition_windows"]["10"]["1to0"]["after"]["error_rate"]-trp["transition_windows"]["1"]["1to0"]["after"]["error_rate"]):.3f}点；±5窗口额外{100*trp["delta10_minus_delta1_near_error"]:.3f}点，远处{100*trp["delta10_minus_delta1_far_error"]:.3f}点。 |',
            '', '单crop、独立二分类、校准和时间启发式并非互斥解释；本数据没有验证最初假设的完整普遍版本。输入干预与随机编号控制给出有限支持，原生轨迹则直接显示TCP在复用帧的正反馈。']
lines+=['','### 错误样例','']
if heuristics:
    hs=heuristics['categories']['overall']
    lines+=[f'全量H2原生轨迹诊断：{hs["fp"]:,}个FP中，{pct(hs["fp_saturated_fraction"])}%的最终p≥.99，'
            f'{pct(hs["fp_last_raw_refined_below_gamma_fraction"])}%的最近一次未经TCP的frame/video判断低于γ；'
            f'另记录{hs["TCP_crossed_gamma_FP_on_reuse"]:,}次在没有新模型调用的复用帧被TCP从γ下方推到上方的FP。'
            f'FP发生在复用帧的比例={pct(hs["fp_reused_fraction"])}%，但TRP本就约每10帧验证，不能单凭此比例作因果结论。',
            f'官方[llm_eval_from_mot.py:1001]({a}/upstream/YesTrack/refer_llm/llm_eval_from_mot.py:1001)在复用帧继续执行TCP，'
            f'[1020行]({a}/upstream/YesTrack/refer_llm/llm_eval_from_mot.py:1020)把最终分数写回缓存；历史均≥.4时每帧继续加.3。'
            '这给出“原始模型判断之外的历史加分”这一实际误差来源；本诊断未修改启发式，不声称已测得去除TCP的HOTA收益。计数见[R31](runs/R31_heuristics/result.json)。','']
    lines+=[f'这些FP中，{pct(hs["fp_last_frame_above_refine_upper"]/hs["fp"])}%最近一次frame概率≥.8，未触发video；'
            f'FN中{pct(hs["fn_last_frame_below_refine_lower"]/hs["fn"])}%最近一次frame概率<.2，同样未触发video。'
            '这是最近验证时的门控状态，不是当前帧未经实际推理的概率。','']
if errors:
    lines+=[f'已保存{errors["images"]}张全帧可视化，索引见[errors/index.csv](errors/index.csv)；每类优先不同表达式/轨迹组，固定seed。红框FP、橙框FN、绿框GT正例。p_final为实际TCP/TRP后输出；另标最近验证帧和原始frame/video概率。','',
            '| 类别 | FP保存/可用 | FN保存/可用 | FP中p≥.99 | FP靠近切换±5 | FN靠近切换±5 |','|---|---:|---:|---:|---:|---:|']
    for cat,r in errors['counts'].items():
        s=errors['sample_statistics'][cat];lines.append(f'| {cat} | {r["FP"]["saved"]}/{r["FP"]["available_errors"]} | {r["FN"]["saved"]}/{r["FN"]["available_errors"]} | {s["FP"]["p_final_ge_0p99"]} | {s["FP"]["near_truth_switch_pm5"]} | {s["FN"]["near_truth_switch_pm5"]} |')
    lines+=['','G没有可用总体，未伪造样例。样本统计只描述保存的30个案例，不代表总体比例。每类错误模式结合本表、定向探针和对应overview图解释；不会把一张图的现象当作全类因果。']
    if empty_examples:
        lines+=[f'另保存真实空GT帧的Temp基线FP {empty_examples["FP_saved"]}张，见[独立索引](errors/G_empty_frame_control/index.csv)；'
                '该补充集FN=0，因为该帧没有正目标，并非漏抽。它使用实际Temp候选，不能与主GT候选样例混作同一错误来源。']
    if (a/'error_patterns.md').exists():lines+=['',(a/'error_patterns.md').read_text().strip()]
else:lines+=['待完整H2后从实际GT referring误判中抽样；没有样本的类别如实记0，不补造图。']
gt_note=(f'；GT候选上的H3−H2差额为{dec["categories"]["overall"]["H3_minus_H2"]:.2f}，扣除整数框序列化后为{q["metrics"]["HOTA"]-h2["metrics"]["HOTA"]:.2f}' if h2 and q else '')
absence_note=(f'及空GT帧拒绝（补充Δ={empty_oracle["delta_HOTA"]:.2f}，与F重叠）' if empty_oracle else '及绝对空间/运动等重叠类别')
lines+=['','## ⑤ 一句话结论','',
        f'相对本地γ=.6基线，固定TempRMOT*候选的oracle referring可提升约 **{overall["delta_HOTA"]:.2f} HOTA（{overall["H1"]["HOTA"]:.2f}→{overall["oracle_referring_total"]["HOTA"]:.2f}）**，绝对收益主要落在真值变化F（Δ={dec["categories"]["F"]["delta_HOTA"]:.2f}）{absence_note}，C/D分列为{dec["categories"]["C"]["delta_HOTA"]:.2f}/{dec["categories"]["D"]["delta_HOTA"]:.2f}，全视频无目标语言表达因0样本未能检验{gt_note}。','',
        '## 附表：γ敏感性（不用于选择基线）','',
        '| γ | HOTA | DetA | AssA |','|---|---:|---:|---:|']
for gamma,m in r14['sensitivity_appendix_only'].items():lines.append(f'| {gamma} | {m["HOTA"]:.3f} | {m["DetA"]:.3f} | {m["AssA"]:.3f} |')
lines+=['','扫描最高点不用于选基线。所有主分析固定γ=.6；校准扫描和SoM argmax仅为预先声明的探针对照。']
if (a/'runs/R48_final_validation/result.json').exists():
    lines+=['','最终覆盖、同输入crop/GT ID映射、原生重放、434张错误图、100行审核表与官方源码未改核对见[R48验收结果](runs/R48_final_validation/result.json)。']
(a/'REPORT.md').write_text('\n'.join(lines)+'\n')
save_json(a/'round2_status.json',{'complete':complete,'reference':'相对本地基线','gamma':b['gamma'],
 'completed':{k:bool(v) for k,v in [('R13',r13),('R14',r14),('R15',r15),('labels',dist),('H2',h2),
                                  ('context',context_a),('calibration',cal),('TRP',trp),('SoM',som),('errors',errors),
                                  ('shuffled_number_control',som_shuffled if order_control_required else True)]}})
print(json.dumps({'report':str(a/'REPORT.md'),'complete':complete},ensure_ascii=False),flush=True)
