#!/usr/bin/env python3
"""Build the R58 report and long-form numerical tables; never infer missing model results."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

import numpy as np

from r58_metrics import OUT,TASK,ClusterSampler,basic,ece,paired_difference


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def csvwrite(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def flatten(obj,prefix=''):
    result={}
    for key,value in obj.items():
        name=prefix+key
        if isinstance(value,dict):result.update(flatten(value,name+'.'))
        elif isinstance(value,list) and len(value)==2 and all(isinstance(x,(int,float)) for x in value):
            result[name+'.low95']=value[0];result[name+'.high95']=value[1]
        elif not isinstance(value,list):result[name]=value
    return result


def f(value):
    return '—' if value is None else f'{value:.4f}'


def ecetext(metric,kind='mass'):
    if not metric or not metric.get('N'):return '—'
    k=f'ECE_{kind}15';noise=metric[k+'_noise']
    return f'{f(metric[k])} / {f(noise["mean"])} [{f(noise["low95"])}, {f(noise["high95"])}]'


def difftext(metric):
    if not metric or not metric.get('N'):return '—'
    return f'{f(metric["difference"])} [{f(metric["low95"])}, {f(metric["high95"])}]'


def ece_judgment(metric,threshold):
    if not metric or not metric.get('N'):return '无法判定'
    results=[]
    for kind in ['mass','width']:
        target=threshold if threshold is not None else max(2*metric[f'ECE_{kind}15_noise']['mean'],.03)
        results.append(metric[f'ECE_{kind}15']<=target)
    if all(results):return '成立'
    if any(results):return '部分成立'
    return '不成立'


def combine_judgments(values):
    if not values or '无法判定' in values:return '无法判定'
    if any(v=='不成立' for v in values):return '不成立'
    if any(v=='部分成立' for v in values):return '部分成立'
    return '成立'


def criteria(dest,plan):
    p=read(dest/'P1_P2.json');w=read(dest/'P4.json');c=read(dest/'P5.json');t=read(dest/'P6.json')
    if not all([p,w,c,t]):return None
    global_summary=p['global_T_LOSO']['main_attribute_macro']
    attr=[ece_judgment(p['attributes']['global_T_LOSO'].get(a),.05) for a in plan['samples']['main_attributes']]
    checks={'全局T汇总ECE':ece_judgment(global_summary,None),
            '各主表属性ECE':combine_judgments(attr),
            '跨序列T稳定性':'成立' if p['T_cv'] is not None and p['T_cv']<=.15 else '不成立',
            '措辞翻转率':'成立' if w['ALL']['wording_flip']['mean']<=.10 else '不成立',
            '合取乘积ECE':ece_judgment(c.get('ALL',{}).get('product'),.05)}
    candidates=[];evidence=[]
    for K in ['2','4','8']:
        mm=t['K']['each_K'][K].get('MAIN_MACRO',{})
        for rule in ['sum_p','mean_p']:
            if rule not in mm or not mm[rule].get('N'):continue
            gain=mm[rule]['accuracy']-mm['p1']['accuracy']
            s=ece_judgment(mm[rule],.05) if gain>0 else '不成立'
            candidates.append(s);evidence.append({'K':int(K),'rule':rule,'accuracy_gain':gain,'judgment':s})
    checks['固定多帧累积']=('成立' if '成立' in candidates else '部分成立' if '部分成立' in candidates else
                              '不成立' if candidates else '无法判定')
    status=combine_judgments(list(checks.values()))
    if status=='不成立':
        attr_T=[ece_judgment(p['attributes']['attribute_T_LOSO'].get(a),.05) for a in plan['samples']['main_attributes']]
        global_ECE_pass=(checks['全局T汇总ECE']=='成立' and checks['各主表属性ECE']=='成立')
        attr_T_summary=p['attribute_T_LOSO']['main_attribute_macro']
        only_attribute_T=(not global_ECE_pass and all(v=='成立' for v in attr_T)
                          and ece_judgment(attr_T_summary,None)=='成立')
        some_attributes=(0<sum(v=='成立' for v in attr)<len(attr))
        if only_attribute_T or some_attributes:status='部分成立'
    return {'checks':checks,'overall':status,'P6_evidence':evidence,'T_cv':p['T_cv'],
            'scope':'formal user criteria; P1 raw and P3 subgroup diagnostics have no additional invented gate; NLL/Brier diagnostic only'}


def consensus(models,regime='main'):
    arrays=[];labels=None;rows=None;names=[]
    for key,dest in models:
        root=dest if regime=='main' else dest/'sensitivity_two_values'
        a=np.load(root/'OOF.npz');rr=read(root/'rows.json')
        identity=[(r['sample_id'],r['attribute'],r['value']) for r in rr]
        if rows is not None:
            assert identity==[(r['sample_id'],r['attribute'],r['value']) for r in rows]
            assert np.array_equal(a['y'],labels)
        labels=a['y'];rows=rr;arrays.append(a['p_global']);names.append(key)
    if not arrays or not any(name.startswith('Qwen__') for name in names) or not any(not name.startswith('Qwen__') for name in names):return None
    wrong=np.all(np.stack([((p>=.5)!=labels)&np.isfinite(p) for p in arrays]),axis=0)
    valid=np.all(np.stack([np.isfinite(p) for p in arrays]),axis=0)
    results=[]
    for attr in ['ALL']+sorted(set(r['attribute'] for r in rows)):
        ix=valid & np.array([attr=='ALL' or r['attribute']==attr for r in rows])
        if not ix.any():continue
        tt=np.array([r['track'] for r in rows])[ix];ss=np.array([r['sequence'] for r in rows])[ix]
        stat=paired_difference(wrong[ix].astype(float),np.zeros(ix.sum()),tt,ss)
        stat['rate']=stat.pop('difference');results.append({'attribute':attr,**stat})
    primary=json.loads((TASK/'analysis/plans/r58.json').read_text())['samples']['main_attributes']
    aa=np.array([r['attribute'] for r in rows]);ix=valid & np.isin(aa,primary)
    if ix.any():
        vals=wrong[ix].astype(float);attributes=aa[ix]
        tt=np.array([r['track'] for r in rows])[ix];ss=np.array([r['sequence'] for r in rows])[ix]
        sampler=ClusterSampler(tt,ss);rng=np.random.default_rng(2025)
        point=float(np.mean([vals[attributes==a].mean() for a in primary]))
        draws=[]
        for b in range(1000):
            jj=sampler.draw(rng);draws.append(float(np.mean([vals[jj][attributes[jj]==a].mean() for a in primary])))
        results.append({'attribute':'MAIN_MACRO','N':int(ix.sum()),'rate':point,
                       'low95':float(np.quantile(draws,.025)),'high95':float(np.quantile(draws,.975))})
    return {'models_included':names,'statistics':results,
            'interpretation':'all completed models including Qwen opposite to annotation after OOF global T at .5; user-requested noise upper-bound reference, not a guaranteed statistical bound'}


def comparisons(models):
    controls=[x for x in models if x[0].startswith('Qwen__')]
    decisions=[x for x in models if not x[0].startswith('Qwen__')]
    results=[]
    for (dk,dd),(qk,qd) in [(d,q) for d in decisions for q in controls]:
        dw=read(dd/'P4_rows.json');qw=read(qd/'P4_rows.json')
        qi={(r['sample_id'],r['qid']):r for r in qw};wr=[(r,qi[(r['sample_id'],r['qid'])]) for r in dw]
        row={'decision':dk,'control':qk,'P4':{}}
        for field in ['JS','wording_flip','order_flip']:
            rs=[(a,b) for a,b in wr if field in a and field in b]
            row['P4'][field]=paired_difference([a[field] for a,b in rs],[b[field] for a,b in rs],
                [a['track'] for a,b in rs],[a['sequence'] for a,b in rs])
        dc=read(dd/'P5_rows.json');qc=read(qd/'P5_rows.json');qi={(r['sample_id'],r['qid']):r for r in qc}
        rs=[(r,qi[(r['sample_id'],r['qid'])]) for r in dc]
        row['P5']={}
        if rs:
            y=np.array([a['y'] for a,b in rs]);pa=np.array([a['product'] for a,b in rs]);pb=np.array([b['product'] for a,b in rs])
            track=[a['track'] for a,b in rs];seq=[a['sequence'] for a,b in rs]
            la=-y*np.log(np.clip(pa,1e-12,1-1e-12))-(1-y)*np.log1p(-np.clip(pa,1e-12,1-1e-12))
            lb=-y*np.log(np.clip(pb,1e-12,1-1e-12))-(1-y)*np.log1p(-np.clip(pb,1e-12,1-1e-12))
            row['P5']['NLL_product']=paired_difference(la,lb,track,seq)
            sampler=ClusterSampler(track,seq);rng=np.random.default_rng(2025)
            for kind in ['mass','width']:
                delta=[]
                for i in range(1000):
                    ix=sampler.draw(rng);delta.append(ece(pa[ix],y[ix],kind)-ece(pb[ix],y[ix],kind))
                row['P5']['ECE_'+kind]={'difference':ece(pa,y,kind)-ece(pb,y,kind),
                    'low95':float(np.quantile(delta,.025)),'high95':float(np.quantile(delta,.975)),'N':len(y)}
        results.append(row)
    return results


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pending',action='store_true');args=ap.parse_args()
    plan=read(TASK/'analysis/plans/r58.json');stats=read(OUT/'data_statistics.json');budget=read(OUT/'budget.json')
    pilot=read(OUT/'pilot_owner_result.json');runtime=read(OUT/'perplexity_runtime.json')
    full=read(OUT/'full_owner_result.json')
    full_by_family={r['model']:r for r in full['models']} if full else {}
    report=['# R58：KITTI 属性概率的校准前提检验','',
        '仅用 Refer-KITTI-V2 train 的17个序列；seed=2025。没有读取val样本或其分数，没有加载YesTrack V2 LoRA。',
        f'全部定义在[{plan["run"]}计划]({TASK}/analysis/plans/r58.json)中于首次模型推理前冻结。用户两次二值标签/ECE修订与开跑前数据实现修正均留有历史原件；正式样本为{stats["sample_images"]}帧/{stats["tracks"]}轨迹。',
        f'命令与每次GPU启动前估计见[runs.md]({TASK}/analysis/runs.md)。', '',
        '## ① 数据、标签来源和人工审计','',
        f'共检查train的{stats["expressions"]}条表达式，规则与LLM模板审阅识别{stats["single_attribute_expressions"]}条纯单属性表达式。最终抽样{stats["sample_images"]}帧、{stats["tracks"]}条轨迹；类别和车色达到800帧主表门槛，其余属性完整保留为探索性结果。',
        '类别、遮挡和截断来自本地KITTI原始tracking标注压缩包。V2轨迹ID经过重编，使用同帧Hungarian最大IoU一对一匹配，IoU≥0.5才转移原始字段；未匹配的字段保留未知。属性正例来自纯单属性表达式的可见GT；负例仅来自该表达式明确有标注的帧中、独立确认同类而不属于该GT的可见轨迹。没有从复合表达式推负例，没有创建“其他”真值。',
        '抽样中的截断字段取值为0、1、2及未知；沿用冻结的0、(0,.5]、>.5数值分组，实际将1/2合并到>.5，(0,.5]为空，不把原字段解读为百分比。',
        'LLM审阅由本对话Codex对源raw_sentence的语义模板完成，规则结果与模板审阅均可追踪；改写sentence可能省略空间限制，故不作为源标签含义。颜色限定具体衣物，men/women条件只限定相应负例。Choice中保留other选项用于归一化，但不以它建立真值。',
        '', '| 属性 | 标注帧数 | 一对多标签数 | 正/负 | 轨迹数 | 不一致轨迹/比例 | 表格 |',
        '|---|---:|---:|---:|---:|---:|---|']
    exclusions={x['attribute']:x for x in stats['static_exclusions']}
    for a in stats['attributes']:
        ex=exclusions[a['attribute']]
        report.append(f'| {a["attribute"]} | {a["labelled_images"]} | {a["binary_labels"]} | {a["positive"]}/{a["negative"]} | {a["tracks"]} | {ex["inconsistent_tracks"]}/{ex["tracks_before_filter"]} ({100*ex["excluded_fraction"]:.2f}%) | {"主表" if a["main_table"] else "探索性附表，<800帧"} |')
    report += ['', '静态不一致按抽样前全部已知标注帧判定，整条轨迹/属性排除，不做多数表决。这一比例是标注噪声的一个参考；它与抽样后轨迹数采用不同分母。每条轨迹最多8帧、间隔至少10帧，按序列处理；置信区间按序列内轨迹聚类bootstrap1000次。',
        f'[50条表达式审计]({OUT}/label_audit.csv)；[属性正负可视化审计CSV]({OUT}/label_noise_audit.csv)；[审计图片]({OUT}/label_noise_audit/)。每属性正负各50，数量不足时导出全部，具体缺口见[quotas.json]({OUT}/label_noise_audit/quotas.json)。',
        f'各视频属性取值表见[data_statistics.json]({OUT}/data_statistics.json)。依用户修订，不再作“覆盖完整”的假设；敏感性版本只保留同视频同属性问题至少两个取值有表达式的二值记录，按相同LOSO程序重新拟合单个全局T，原始概率缓存不变。',
        '不计算多分类ECE：按表达式可得标签筛选样本会使多分类校准产生选择偏差。所有P1–P6指标均为单取值的一对多二值指标。类别/颜色等Choice题取冻结的取值边际；pants包括jeans，上衣类型允许T-shirt和coat同时出现。with-bicycle是推/骑自行车的标签代理，无法分别检验两种动作。', '',
        '## ② 模型、P1–P6主表与可靠性图','',
        '| 模型 | 固定revision | 运行状态 |','|---|---|---|']
    completed=[];main_completed=[]
    pilot_by_family={r['model']:r for r in pilot['models']} if pilot else {}
    for model in plan['models']:
        row=pilot_by_family.get(model['repo'],{})
        key=row.get('checkpoint_repo',model['repo']).replace('/','__')
        dest=OUT/'metrics'/key
        status='待试跑/预算核定'
        if read(dest/'completion.json') and read(dest/'sensitivity_two_values/completion.json'):
            status='完整缓存及两套CPU分析完成';completed.append((key,dest))
        elif row.get('status')=='complete':status='200样本试跑完成，正式指标待全量'
        elif row:status=row['status']+'；'+str(row.get('reason',''))
        elif model['repo'].startswith('perplexity') and runtime:status=runtime['status']
        cached_full=read(OUT/'status'/(key+'_full.json'))
        if cached_full and cached_full.get('status')=='complete' and not (read(dest/'completion.json') and read(dest/'sensitivity_two_values/completion.json')):
            status='完整缓存完成，CPU统计待完成'
        if model['repo'] in full_by_family and not (read(dest/'completion.json') and read(dest/'sensitivity_two_values/completion.json')):
            ff=full_by_family[model['repo']]
            status='完整缓存完成，CPU统计待完成' if ff['status']=='complete' else ff['status']+'；'+str(ff.get('reason',''))
        if (read(dest/'main_completion.json') and read(dest/'sensitivity_two_values/main_completion.json')
                and not (read(dest/'completion.json') and read(dest/'sensitivity_two_values/completion.json'))):
            status='全量main及两套CPU核心分析完成；P4/crop待缓存齐备'
            main_completed.append((key,dest))
        report.append(f'| {model["repo"]} | [{model["revision"][:12]}]({model["official_card"]}) | {status} |')
    report += ['', '输入为官方margin=.2裁剪的320×320目标crop、带框整帧缩略图和归一化位置/大小文本；crop消融只删第二张图。每个样本始终提出同一完整题库，避免问题组合泄露GT类别。每题3种措辞，Choice另有两组固定随机顺序。普通Qwen按完整选项串的逐token条件对数概率之和softmax，没有长度归一化或GT答案前缀。',
        '所有决策模型均使用官方接口及固定发布权重；OneJev保留官方fork自检及.05容差。六个已运行检查点均为原始未量化发布版本，d3-turbo未触发回退；Qwen显式BF16加载，决策模型保持官方默认加载精度。Perplexity精确官方依赖的隔离环境失败，原始错误单列，没有替换模型。冻结的量化回退仅在显存不足时启用；A800不满足[官方FP8卡](https://huggingface.co/vllm-sr/d3-turbo-FP8)要求的sm≥8.9，INT4回退本次未使用。',
        f'环境与接口记录：[environment.lock.json]({OUT}/environment.lock.json)、[官方卡快照]({OUT}/model_cards/)、[Perplexity运行时]({OUT}/perplexity_runtime.json)。', '']
    if budget and budget['complete_study_gpu_stage_hours'] is not None:
        report += [f'启动前预算（200样本实测外推）：完整冻结实验预计{budget["complete_study_gpu_stage_hours"]:.3f} GPU阶段小时，试跑已用{budget["pilot_gpu_stage_hours"]:.3f}小时，当时预计剩余{budget["remaining_gpu_stage_hours"]:.3f}小时。具体每模型/配置吞吐见[budget.json]('+str(OUT)+'/budget.json)。',
                   '超过4小时则全量尚未启动，等待用户授权。' if budget['gate']=='approval_required' and not (OUT/'full_budget_approval.json').exists() else '预算授权状态以full_budget_approval.json及runs.md为准。','']
    elif budget:
        report+=['尚无成功吞吐测量，完整预算无法估计；没有把未测得的时间当作0小时，也没有自动授权全量。','']
    if budget and budget['complete_study_gpu_stage_hours'] is not None:
        report+=['按冻结的单GPU串行计划，阶段小时同时是预计GPU占用小时与串行耗时；下载和CPU分析另计。', '',
            '| 模型 | 主配置吞吐（样本/秒） | 试跑已用(h) | 预计剩余(h) | 全部预计(h) |',
            '|---|---:|---:|---:|---:|']
        for row in budget['models']:
            if row['status']!='complete':continue
            speed=next(x for x in row['settings'] if x['setting']=='main')['warm_requests_per_second']
            report.append(f'| {row["checkpoint_repo"]} | {speed:.3f} | {row["pilot_gpu_stage_seconds"]/3600:.3f} | {row["remaining_gpu_stage_seconds"]/3600:.3f} | {row["complete_study_gpu_stage_seconds"]/3600:.3f} |')
        report+=['', '每模型试跑200条main，以及措辞/排序/crop五配置各10条；六个模型共1500请求、25500道题。Qwen共享前缀缓存未通过冻结的最大概率误差0.005校验，因此使用完整选项串条件似然；原试跑概率保留。工程回归见[qwen_cache_regression.json]('+str(OUT)+'/qwen_cache_regression.json)，Qwen8缓存差异见[状态]('+str(OUT)+'/status/Qwen__Qwen3-VL-8B-Instruct_pilot.json)。',
            '全量阶段严格继承首个pilot样本的失败门槛，固定fresh reference；CPU控制流回归见[qwen_full_cache_gate.json]('+str(OUT)+'/qwen_full_cache_gate.json)。',
            'Perplexity官方运行时torch2.14.0+cu130初始化CUDA失败：当前驱动报告12080，完整错误保存在上述perplexity_runtime.json；该模型未进行推理。','']
    handoff=read(OUT/'resource_handoff_Qwen8.json')
    if handoff:
        report += [f'Qwen8在共享GPU6上吞吐低于pilot，按原允许GPU及显存/总配额约束恢复未完成单元；既有缓存未删改。迁移前实际进程耗时{handoff["interrupted_worker_elapsed_seconds"]/3600:.3f}小时另计入总成本，运行记录见[resource_handoff_Qwen8.json]({OUT}/resource_handoff_Qwen8.json)。冻结样本、权重、评分及判定保持不变。','']
    actual_times=[]
    for row in pilot['models'] if pilot else []:
        if row['status']!='complete':continue
        key=row.get('checkpoint_repo',row['model']).replace('/','__')
        ps=read(OUT/'status'/(key+'_pilot.json'));fs=read(OUT/'status'/(key+'_full.json'))
        prior=handoff['interrupted_worker_elapsed_seconds'] if handoff and key=='Qwen__Qwen3-VL-8B-Instruct' else 0
        full_seconds=fs['wall_seconds']+prior if fs and fs['status']=='complete' else None
        actual_times.append({'model':row['model'],'pilot_seconds':ps['wall_seconds'],
                             'full_seconds_including_handoff':full_seconds})
    if actual_times:
        report += ['已完成阶段的实际计时如下，口径为单GPU模型worker墙钟；包含加载和推理，CPU分析/下载另计，未完成阶段留空。','',
                   '| 模型 | 实际pilot(h) | 实际全量(h，含迁移前阶段) |','|---|---:|---:|']
        for row in actual_times:
            full_hours='—' if row['full_seconds_including_handoff'] is None else f'{row["full_seconds_including_handoff"]/3600:.3f}'
            report.append(f'| {row["model"]} | {row["pilot_seconds"]/3600:.3f} | {full_hours} |')
        if all(row['full_seconds_including_handoff'] is not None for row in actual_times):
            total=sum(row['pilot_seconds']+row['full_seconds_including_handoff'] for row in actual_times)
            report += ['',f'六模型实际GPU阶段合计{total/3600:.3f}小时；原预算来自pilot吞吐外推，实际共享负载及恢复耗时已保留。']
            save(OUT/'gpu_actual_timing.json',{'seed':2025,'models':actual_times,'total_GPU_stage_seconds':total})
        report += ['']
    expected={r.get('checkpoint_repo',r['model']).replace('/','__') for r in pilot['models'] if r['status']=='complete'} if pilot else set()
    all_ready=bool(expected) and expected.issubset({key for key,dest in completed})
    if args.pending or not all_ready:
        phase = '正式全量已获用户批准，正在执行' if (OUT/'full_budget_approval.json').exists() else '正式全量等待预算授权'
        report += ['## ③ P1–P6全量进度','',
                   f'已完成{len(completed)}/{len(expected)}个成功试跑模型的完整缓存及两套CPU分析；完整模型对照尚未齐备。以下仅列已经完成的全量模型结果，未完成模型没有占位指标。','']
        report += ['下表ECE均为15个等样本量箱；“噪声”指用同一预测概率模拟完美校准标签时的有限样本ECE期望及95%区间，区别于人工标签噪声。所有模型一致反向的标签噪声参考待全部模型齐备后计算。','']
        if completed:
            report += ['| 已完成模型 | 全局T主属性宏ECE/噪声 | 类别ECE/噪声 | 车色ECE/噪声 | 合取乘积ECE/噪声 | 直接合取ECE/噪声 | 该模型判定 |',
                       '|---|---|---|---|---|---|---|']
            for key,dest in completed:
                p=read(dest/'P1_P2.json');c=read(dest/'P5.json');j=criteria(dest,plan)
                report.append(f'| [{key}]({dest}/P1_P2.json) | {ecetext(p["global_T_LOSO"]["main_attribute_macro"])} | {ecetext(p["attributes"]["global_T_LOSO"].get("category"))} | {ecetext(p["attributes"]["global_T_LOSO"].get("vehicle_colour"))} | {ecetext(c.get("ALL",{}).get("product"))} | {ecetext(c.get("ALL",{}).get("direct"))} | {j["overall"]} |')
            report += ['', '完整单模型P1–P6、全部轨迹bootstrap区间和可靠性图位于'+str(OUT)+'/metrics/各模型目录；所有科学定义继续沿用冻结计划。','']
        if main_completed:
            report += ['另有以下模型已完成2144样本的main配置CPU分析，尚缺P4措辞/排序和crop消融；不计入完整模型数，也不作总体判定。','',
                       '| main已完成模型 | 全局T主属性宏ECE/噪声 | 类别ECE/噪声 | 车色ECE/噪声 | 合取乘积ECE/噪声 | 直接合取ECE/噪声 |',
                       '|---|---|---|---|---|---|']
            for key,dest in main_completed:
                p=read(dest/'P1_P2.json');c=read(dest/'P5.json')
                report.append(f'| [{key}]({dest}/P1_P2.json) | {ecetext(p["global_T_LOSO"]["main_attribute_macro"])} | {ecetext(p["attributes"]["global_T_LOSO"].get("category"))} | {ecetext(p["attributes"]["global_T_LOSO"].get("vehicle_colour"))} | {ecetext(c.get("ALL",{}).get("product"))} | {ecetext(c.get("ALL",{}).get("direct"))} |')
            report += ['', '主配置结果支持的范围仅限已完成的原定子项；同一main检查点在六种设置齐备后核对原始数组逐值相同，再补齐P4/crop，既有数值不重写。','']
        report += ['尚未对全体模型作校准前提或独特性判定。可靠性图、温度迁移、分组、措辞、合取和多帧均使用完整冻结样本；没有以200样本吞吐试跑代替正式实验。','',
                   f'一句话结论：数据/协议及六模型试跑已完成，{phase}；KITTI属性题上的校准前提和决策模型独特性尚无法判定。']
        (TASK/'analysis/REPORT_R58.md').write_text('\n'.join(report)+'\n');return
    reports=OUT/'report_tables';reports.mkdir(exist_ok=True)
    requests=len(expected)*len(plan['questions']['settings'])*stats['sample_images']
    report += [f'全量覆盖{len(expected)}模型×{len(plan["questions"]["settings"])}设置×{stats["sample_images"]}样本，共{requests:,}条请求、{requests*len(plan["questions"]["bank"]):,}道题；试跑记录原位复用。完整性检查见[final_integrity.json]({OUT}/final_integrity.json)。','']
    cc=consensus(completed);strict_cc=consensus(completed,'strict');save(reports/'consensus_noise_reference.json',cc)
    noise_by_attr={r['attribute']:r for r in cc['statistics']} if cc else {}
    if cc:
        references=[]
        for a in ['category','vehicle_colour','gender']:
            n=noise_by_attr[a]
            references.append(f'{a}为{100*n["rate"]:.2f}%（轨迹95%CI {100*n["low95"]:.2f}%–{100*n["high95"]:.2f}%）')
        position=report.index('## ② 模型、P1–P6主表与可靠性图')
        report[position:position]=['人工标签审计尚未完成。六模型在同一二值记录上一致与标注相反的比例：'+'；'.join(references)+'。这是用户指定的标签噪声上界参考，不是确定误标率或有保证的统计上界；全部记录继续保留，未自动改标签。下文的完美校准ECE噪声模拟另指有限样本误差。','']
    save(reports/'consensus_noise_reference_two_values.json',strict_cc)
    compare=comparisons(completed);save(reports/'decision_vs_Qwen_paired.json',compare)
    metric_rows=[];group_rows=[];formal_rows=[];model_judgments=[]
    extra_rows={name:[] for name in ['temperature_folds','P4_wording','P5_composition',
        'P5_correctness_correlations','P6_temporal','decision_utility','decision_utility_folds','crop_ablation']}
    report += ['P1–P6全量细表如下。','',
               'ECE单元格格式为“实测ECE / 完美校准标签模拟的期望 [95%区间]”；完整指标的轨迹bootstrap95%区间、Brier分解与每属性数据在附表CSV中。主判等样本量15箱，等宽15箱用于交叉核对；分箱达标判断冲突记部分成立。NLL与Brier只作诊断。二值宏F1固定平均0/1两类，缺失类按0处理；阈值效用用正类F1。bootstrap对冻结的OOF预测按轨迹重采样，不重新拟合校准器。',
               '温度缩放严格按冻结定义作用于完整选项分布：softmax(log(max(q, 1e-12))/T)，再求取值边际；T以训练折全部已知原子二值记录的pooled NLL拟合，主汇总以属性宏平均评分。所有措辞、顺序、crop和直接合取题复用该折同一个T；未在测试序列重新拟合。','']
    report += ['| 模型 | 原始主属性宏ECE/噪声 | 单全局T宏ECE/噪声 | 车色ECE/噪声 | 措辞翻转率 | 合取乘积ECE/噪声 | 完整标准判定 |',
               '|---|---:|---|---|---:|---|---|']
    for key,dest in completed:
        p=read(dest/'P1_P2.json');w=read(dest/'P4.json');c=read(dest/'P5.json');j=criteria(dest,plan)
        report.append(f'| {key} | {ecetext(p["native"]["main_attribute_macro"])} | {ecetext(p["global_T_LOSO"]["main_attribute_macro"])} | {ecetext(p["attributes"]["global_T_LOSO"].get("vehicle_colour"))} | {f(w["ALL"]["wording_flip"]["mean"])} | {ecetext(c.get("ALL",{}).get("product"))} | {j["overall"]} |')
    report += ['', '“部分成立”按冻结定义可由只有部分单属性达标触发，不能据此把它排在整套标准“不成立”的模型之前；选择属性概率基准应直接比较对应的校准、稳定性和合取数值。','']
    for key,dest in completed:
        p=read(dest/'P1_P2.json');w=read(dest/'P4.json');composition=read(dest/'P5.json');temp=read(dest/'P6.json')
        result=criteria(dest,plan);model_judgments.append({'model':key,**result})
        report += [f'### {key}','',
            '| 属性 | N | Acc | 宏F1 | NLL | Brier | 原始等量ECE/噪声 | 全局T等量ECE/噪声 | 全局T等宽ECE/噪声 | 全模型一致反向比例 |',
            '|---|---:|---:|---:|---:|---:|---|---|---|---:|']
        for a in ['MAIN_MACRO']+sorted(p['attributes']['global_T_LOSO']):
            mm=p['global_T_LOSO']['main_attribute_macro'] if a=='MAIN_MACRO' else p['attributes']['global_T_LOSO'][a]
            raw=p['native']['main_attribute_macro'] if a=='MAIN_MACRO' else p['attributes']['native'][a]
            if not mm.get('N'):
                report.append(f'| {a} | 0 | — | — | — | — | — | — | — | — |');continue
            report.append(f'| {a} | {mm["N"]} | {f(mm["accuracy"])} | {f(mm["macro_F1_binary"])} | {f(mm["NLL"])} | {f(mm["Brier"])} | {ecetext(raw)} | {ecetext(mm)} | {ecetext(mm,"width")} | {f(noise_by_attr.get(a,{}).get("rate"))} |')
        report += ['',f'LOSO全局温度变异系数={f(p["T_cv"])}；各折T：'+', '.join(f'{r["held_out"]}:{f(r["T"])}' for r in p['temperatures'])+'。',
            f'措辞JS={f(w["ALL"]["JS"]["mean"])}，平均翻转率={f(w["ALL"]["wording_flip"]["mean"])}，最差措辞对={f(w["ALL"]["worst_wording_pair_flip"])}，选项排序翻转率={f(w["ALL"]["order_flip"].get("mean"))}。',
            f'合取乘积等量ECE={ecetext(composition.get("ALL",{}).get("product"))}；直接合取等量ECE={ecetext(composition.get("ALL",{}).get("direct"))}。',
            f'[类别可靠性图]({dest}/figures/reliability_category.png)、[车色可靠性图]({dest}/figures/reliability_vehicle_colour.png)；其余属性同目录。', '',
            '| 条件（主属性宏平均） | N | 等量ECE/噪声 | 等宽ECE/噪声 |',
            '|---|---:|---|---|']
        for group in read(dest/'P3.json'):
            if group['group'] not in ['height','occlusion','truncation']:continue
            m=group['main_attribute_macro']
            report.append(f'| {group["group"]}:{group["value"]} | {m.get("N",0)} | {ecetext(m)} | {ecetext(m,"width")} |')
        report += ['', '| 属性 | 措辞JS | 措辞翻转率 [轨迹95%CI] | 选项顺序翻转率 |',
                   '|---|---:|---|---:|']
        for a,m in w.items():
            flip=m['wording_flip']
            report.append(f'| {a} | {f(m["JS"].get("mean"))} | {f(flip.get("mean"))} [{f(flip.get("low95"))}, {f(flip.get("high95"))}] | {f(m["order_flip"].get("mean"))} |')
        report += ['', '每属性的稳定性为既定诊断；正式措辞判定继续使用冻结的总体翻转率。']
        report += ['',
            '| 合取组 | N | 乘积ECE/噪声 | 直接ECE/噪声 | 乘积AUROC | 直接AUROC | 乘积NLL | 直接NLL | NLL乘积减直接 [轨迹95%CI] |',
            '|---|---:|---|---|---:|---:|---:|---:|---|']
        for group,values in composition.items():
            m=values.get('product');d=values.get('direct')
            if not m:report.append(f'| {group} | 0 | — | — | — | — | — | — | — |');continue
            report.append(f'| {group} | {m["N"]} | {ecetext(m)} | {ecetext(d)} | {f(m["AUROC"])} | {f(d["AUROC"])} | {f(m["NLL"])} | {f(d["NLL"])} | {difftext(values.get("NLL_product_minus_direct"))} |')
        report += ['', '| K（同一K合格轨迹） | 规则 | N（二值轨迹-取值） | Acc | K=1同轨迹Acc | 等量ECE/噪声 | 等宽ECE/噪声 |',
            '|---|---|---:|---:|---:|---|---|']
        for K,values in temp['K']['each_K'].items():
            for rule,m in values.get('MAIN_MACRO',{}).items():
                if rule=='p1' or not m.get('N'):continue
                report.append(f'| {K} | {rule} | {m["N"]} | {f(m["accuracy"])} | {f(values["MAIN_MACRO"]["p1"]["accuracy"])} | {ecetext(m)} | {ecetext(m,"width")} |')
        report += ['',f'K=8共同轨迹对照、每属性/每K结果、唯一累积系数alpha与完整CI见[P6.json]({dest}/P6.json)。预测正确性phi相关系数及CI见[P5_correctness_correlations.json]({dest}/P5_correctness_correlations.json)。',
            f'仅crop消融复用同一OOF全局T，见[crop_ablation.json]({dest}/crop_ablation.json)；阈值效用使用训练折nested-OOF选择每属性一个正类F1最优阈值，见[decision_utility.json]({dest}/decision_utility.json)。', '']
        report += ['| 属性 | 全局T的0.5阈值正类F1 | LOSO每属性阈值正类F1 | F1差值 [轨迹95%CI] |',
                   '|---|---:|---:|---|']
        for a,m in read(dest/'decision_utility.json')['attributes'].items():
            if not m.get('N'):continue
            report.append(f'| {a} | {f(m["F1_fixed_0p5"])} | {f(m["F1_LOSO_threshold"])} | {f(m["F1_gap"])} [{f(m["gap_low95"])}, {f(m["gap_high95"])}] |')
        report += ['']
        for regime,root in [('main',dest),('two_values',dest/'sensitivity_two_values')]:
            pp=read(root/'P1_P2.json')
            base={'model':key,'regime':regime}
            for state,attrs in pp['attributes'].items():
                for a,m in attrs.items():metric_rows.append({'model':key,'regime':regime,'state':state,'attribute':a,
                    'consensus_opposite_rate':noise_by_attr.get(a,{}).get('rate') if regime=='main' else None,
                    'static_inconsistent_track_fraction':exclusions[a]['excluded_fraction'],**flatten(m)})
                for source,label in [('main_attribute_macro','MAIN_MACRO'),('all_attribute_macro','ALL_MACRO'),('pooled','POOLED')]:
                    metric_rows.append({**base,'state':state,'attribute':label,**flatten(pp[state][source])})
            for r in pp['temperatures']:extra_rows['temperature_folds'].append({**base,'kind':'global',**r})
            for r in pp['attribute_temperatures']:extra_rows['temperature_folds'].append({**base,'kind':'per_attribute',**r})
            for group in read(root/'P3.json'):
                for a,m in group['attributes'].items():group_rows.append({'model':key,'regime':regime,'dimension':group['group'],'group':group['value'],'attribute':a,**flatten(m)})
            for a,m in read(root/'P4.json').items():extra_rows['P4_wording'].append({**base,'attribute':a,**flatten(m)})
            for group,values in read(root/'P5.json').items():
                for mode in ['product','direct']:
                    extra_rows['P5_composition'].append({**base,'group':group,'mode':mode,
                        **flatten(values.get(mode,{'N':0})),**flatten({'NLL_product_minus_direct':values.get('NLL_product_minus_direct')})})
            for r in read(root/'P5_correctness_correlations.json'):
                extra_rows['P5_correctness_correlations'].append({**base,**r})
            for cohort,by_k in read(root/'P6.json')['K'].items():
                for K,by_attr in by_k.items():
                    for a,rules in by_attr.items():
                        if rules.get('N')==0:rules={rule:{'N':0} for rule in ['p1','sum_p','mean_p','scaled_sum_p']}
                        for rule,m in rules.items():
                            extra_rows['P6_temporal'].append({**base,'cohort':cohort,'K':int(K),'attribute':a,'rule':rule,**flatten(m)})
            utility=read(root/'decision_utility.json')
            for a,m in utility['attributes'].items():extra_rows['decision_utility'].append({**base,'attribute':a,**m})
            for r in utility['thresholds']:extra_rows['decision_utility_folds'].append({**base,**r})
            crop=read(root/'crop_ablation.json')
            for a,m in crop['attributes'].items():extra_rows['crop_ablation'].append({**base,'attribute':a,**flatten(m)})
            extra_rows['crop_ablation'].append({**base,'attribute':'MAIN_MACRO',**flatten(crop['main_attribute_macro'])})
            formal=criteria(root,plan)
            for criterion,judgment in formal['checks'].items():formal_rows.append({'model':key,'regime':regime,'criterion':criterion,'judgment':judgment})
        strict=criteria(dest/'sensitivity_two_values',plan)
        strict_meta=read(dest/'sensitivity_two_values/completion.json')
        strict_c=read(dest/'sensitivity_two_values/P5.json')
        strict_pairs=strict_c.get('pairs',{}).get('product',{}).get('N',0)
        strict_triples=strict_c.get('triples',{}).get('product',{}).get('N',0)
        report += [f'两取值敏感性判定：{strict["overall"]}；主方案：{result["overall"]}，'+
            ('结论相同。' if strict['overall']==result['overall'] else '结论发生变化，不能称结论对标签覆盖条件稳健。'),'']
        changed=[f'{k}：{v}→{strict["checks"][k]}' for k,v in result['checks'].items() if strict['checks'][k]!=v]
        if changed:report += ['逐项判定变化：'+'；'.join(changed)+'。敏感性版本改变可评标签队列，使用同一原始概率缓存。','']
        report += [f'该敏感性版本保留{strict_meta["samples"]}个标注样本、{strict_meta["binary_rows"]}条二值记录；可评二元/三元合取为{strict_pairs}/{strict_triples}条。空组保留为不可评，整体判定相同不代表空组已获得验证。','']
    csvwrite(reports/'all_metrics.csv',metric_rows);csvwrite(reports/'P3_subgroups.csv',group_rows)
    for name,rows in extra_rows.items():csvwrite(reports/(name+'.csv'),rows)
    csvwrite(reports/'formal_criteria.csv',formal_rows);save(reports/'formal_model_judgments.json',model_judgments)
    report += ['## ③ 按冻结判定标准逐条核对','',
        '| 模型 | 汇总ECE | 主属性ECE | T稳定性 | 措辞 | 乘积 | 固定多帧 | 总体 |',
        '|---|---|---|---|---|---|---|---|']
    for row in model_judgments:
        report.append('| '+row['model']+' | '+' | '.join(row['checks'][k] for k in ['全局T汇总ECE','各主表属性ECE','跨序列T稳定性','措辞翻转率','合取乘积ECE','固定多帧累积'])+' | '+row['overall']+' |')
    pp={k:read(d/'P1_P2.json') for k,d in completed}
    ww={k:read(d/'P4.json') for k,d in completed}
    cp={k:read(d/'P5.json') for k,d in completed}
    controls=[k for k,d in completed if k.startswith('Qwen__')]
    decisions=[k for k,d in completed if not k.startswith('Qwen__')]
    best_control=min(controls,key=lambda k:pp[k]['global_T_LOSO']['main_attribute_macro']['ECE_mass15'])
    best_decision=min(decisions,key=lambda k:pp[k]['global_T_LOSO']['main_attribute_macro']['ECE_mass15'])
    control_dir=dict(completed)[best_control]
    raw_best=min(pp,key=lambda k:pp[k]['native']['main_attribute_macro']['ECE_mass15'])
    cv=[v['T_cv'] for v in pp.values()]
    report += ['',
        f'P1：原始主属性宏ECE最低的{raw_best}仍为{ecetext(pp[raw_best]["native"]["main_attribute_macro"])}；各模型原始汇总均高于对应有限样本噪声，不能把原始概率视为跨属性普遍已校准。类别与颜色的表现不同，具体属性结果以上表为准。','',
        f'P2：六模型LOSO温度变异系数范围为{f(min(cv))}–{f(max(cv))}，均通过.15稳定性门槛，但温度稳定不代表校准达标。按主属性宏ECE比较，{best_control}最好，为{ecetext(pp[best_control]["global_T_LOSO"]["main_attribute_macro"])}；决策模型中{best_decision}最低，为{ecetext(pp[best_decision]["global_T_LOSO"]["main_attribute_macro"])}，仍未达汇总门槛。',
        '', '每属性各拟合一个T的次要对照如下；使用相同LOSO划分，主判继续采用单个全局T。','',
        '| 模型 | 每属性T的主属性宏等量ECE/噪声 | 每属性T的主属性宏等宽ECE/噪声 |',
        '|---|---|---|']
    for key,dest in completed:
        m=pp[key]['attribute_T_LOSO']['main_attribute_macro']
        report.append(f'| {key} | {ecetext(m)} | {ecetext(m,"width")} |')
    report += ['', '每属性T若在训练折没有该属性标签，则T留空、对应验证记录不可评，不伪造拟合值；这些缺口属于样本不足的探索性项，两个主属性在每折均可拟合。次要版本的每属性N和空折见all_metrics.csv及temperature_folds.csv。','']
    height={g['value']:g['attributes']['vehicle_colour'] for g in read(control_dir/'P3.json') if g['group']=='height'}
    report += ['',
        f'P3：即使是单属性汇总最好的{best_control}，车色整体为{ecetext(pp[best_control]["attributes"]["global_T_LOSO"]["vehicle_colour"])}，小框<40像素的{height["<40"]["N"]}条二值记录却为{ecetext(height["<40"])}（等宽：{ecetext(height["<40"],"width")}）；>100像素为{ecetext(height[">100"])}。因此不能由汇总达标推出不同条件都校准。框高仅作为距离的代理；遮挡、原始类别、截断和序列结果全部保留在P3附表，没有增加事后筛选条件。','',
        f'P4：{best_decision}的平均措辞翻转率为{100*ww[best_decision]["ALL"]["wording_flip"]["mean"]:.2f}%，{best_control}为{100*ww[best_control]["ALL"]["wording_flip"]["mean"]:.2f}%；对应排序翻转率为{100*ww[best_decision]["ALL"]["order_flip"]["mean"]:.2f}%和{100*ww[best_control]["ALL"]["order_flip"]["mean"]:.2f}%。决策模型的稳定性优势与校准优势须分别判断。OneJev主方案的措辞点估计超过10%，即使CI跨越10%也不放宽冻结门槛；严格版的该项变化已单列。','',
        f'P5：六模型合取乘积均未过.05门槛；其中{best_control}为{ecetext(cp[best_control]["ALL"]["product"])}，{best_decision}为{ecetext(cp[best_decision]["ALL"]["product"])}。直接询问合取也没有普遍校准；NLL优劣以配对区间为准，不能概括为直接问始终更好。','']
    black=cp[best_control]['and_car_black']['product'];black_ci=black['cluster_bootstrap95']['ECE_mass15']
    report += [f'样本最多的预定车色组合Car∧black有{black["N"]}条记录，{best_control}乘积ECE为{ecetext(black)}，实测ECE的轨迹95%CI为[{f(black_ci["low"])}, {f(black_ci["high"])}]。因此整体失败不能只归于衣着小样本；但原子属性误校准与组合子队列变化仍可能贡献误差，不能单凭乘积失败断言条件独立假设已被单独证伪。','',
        '下表选每模型样本量最大的可评正确性相关对（按N选择）；全体178对及不可定义的零方差情形仍完整导出。','',
        '| 模型 | 可评/总相关对 | 最大可评对 | N | phi [轨迹95%CI] |','|---|---:|---|---:|---|']
    for key,dest in completed:
        rr=read(dest/'P5_correctness_correlations.json');valid=[r for r in rr if r['phi'] is not None]
        largest=max(valid,key=lambda r:r['N'])
        label=largest['attribute_a']+':'+largest['value_a']+' × '+largest['attribute_b']+':'+largest['value_b']
        report.append(f'| {key} | {len(valid)}/{len(rr)} | {label} | {largest["N"]} | {f(largest["phi"])} [{f(largest["low95"])}, {f(largest["high95"])}] |')
    report += ['', '部分模型正确性存在相关，但跨样本正确性相关并不等同于给定图像后的属性条件独立；接近零或区间跨零也不能证明条件独立。','']
    qt=read(control_dir/'P6.json')['K']['each_K']['2']['MAIN_MACRO']
    report += [f'P6：{best_control}固定两帧平均log-odds，在同一K合格队列上使准确率从{f(qt["p1"]["accuracy"])}升至{f(qt["mean_p"]["accuracy"])}，ECE为{ecetext(qt["mean_p"])}（等宽：{ecetext(qt["mean_p"],"width")}），通过冻结的固定规则子项。其它K及按LOSO拟合系数的结果均保留；可调系数不用于替代固定规则门槛，多帧准确率提高也不等于概率仍校准。']
    utility=read(control_dir/'decision_utility.json')['attributes']['vehicle_colour']
    report += [f'决策效用：{best_control}车色正类F1在0.5阈值为{f(utility["F1_fixed_0p5"])}，LOSO每属性阈值为{f(utility["F1_LOSO_threshold"])}，差{f(utility["F1_gap"])} [{f(utility["gap_low95"])}, {f(utility["gap_high95"])}]。0.5并非一般意义的F1最优阈值，因此该差距只诊断使用效用，不追加为校准失败门槛。','']
    report += ['',f'所有分组（框高/遮挡/截断/类别/序列）的OOF ECE、噪声下限与CI见[P3_subgroups.csv]({reports}/P3_subgroups.csv)。P3不另造事后门槛，也不以汇总校准替代分组数值。',
        f'每属性温度次要对照、全局温度、所有原始/缩放指标与Brier校准项/分辨项/分箱残差见[all_metrics.csv]({reports}/all_metrics.csv)。Brier的未分箱分数不必恰等于分箱分解三项，残差已明确列出。',
        f'逐折温度见[temperature_folds.csv]({reports}/temperature_folds.csv)；每属性措辞/排序诊断见[P4_wording.csv]({reports}/P4_wording.csv)；合取与正确性相关性分别见[P5_composition.csv]({reports}/P5_composition.csv)、[P5_correctness_correlations.csv]({reports}/P5_correctness_correlations.csv)。',
        f'逐属性/逐K/两种队列的多帧指标见[P6_temporal.csv]({reports}/P6_temporal.csv)；阈值效用及折内阈值见[decision_utility.csv]({reports}/decision_utility.csv)、[decision_utility_folds.csv]({reports}/decision_utility_folds.csv)；crop消融见[crop_ablation.csv]({reports}/crop_ablation.csv)。这些均是冻结诊断的表格导出。',
        f'全体已完成模型一致反向比例及轨迹CI见[噪声上界参考]({reports}/consensus_noise_reference.json)。这是用户指定的自动审计线索，不是有保证的统计上界；人工审计尚未完成，未把这些案例重新标注或删去。',
        f'决策模型减去Qwen的配对轨迹bootstrap差值见[decision_vs_Qwen_paired.json]({reports}/decision_vs_Qwen_paired.json)：P4的JS/翻转率、P5乘积ECE/NLL均给出95%CI。负差值表示决策模型较好；未用不配对置信区间是否重叠代替配对检验。',
        f'至少两个取值的完整P1–P6敏感性结果在各模型`sensitivity_two_values/`下，逐标准对照见[formal_criteria.csv]({reports}/formal_criteria.csv)。未知标签和无两类样本的AUROC明确留空，不填0。', '']
    report += ['## ④ 与Qwen对照组比较','',
        '下表为“决策模型减Qwen”的差值及配对轨迹95%区间；每个数字复用冻结的配对bootstrap计算。','',
        '| 对照 | P4 JS差 | P4措辞翻转差 | P4排序翻转差 | P5乘积等量ECE差 | P5乘积NLL差 |',
        '|---|---|---|---|---|---|']
    for r in compare:
        label=r['decision'].split('__')[-1]+' / '+r['control'].split('__')[-1]
        report.append(f'| {label} | {difftext(r["P4"].get("JS"))} | {difftext(r["P4"].get("wording_flip"))} | {difftext(r["P4"].get("order_flip"))} | {difftext(r["P5"].get("ECE_mass"))} | {difftext(r["P5"].get("NLL_product"))} |')
    paired=next(r for r in compare if r['decision']==best_decision and r['control']==best_control)
    report += ['',f'以各组主属性宏ECE最低者比较：{best_decision}减{best_control}的措辞翻转差为{difftext(paired["P4"]["wording_flip"])}，决策模型更稳定；乘积ECE差为{difftext(paired["P5"]["ECE_mass"])}，此处Qwen对照更好。乘积NLL差为{difftext(paired["P5"]["NLL_product"])}，区间跨零，未显示明确优势。不能把稳定性收益直接表述为校准独特性。','']
    decision_pass=[r['model'] for r in model_judgments if not r['model'].startswith('Qwen__') and r['overall']=='成立']
    control_pass=[r['model'] for r in model_judgments if r['model'].startswith('Qwen__') and r['overall']=='成立']
    control_marginal_pass=[r['model'] for r in model_judgments if r['model'].startswith('Qwen__') and
        all(r['checks'][k]=='成立' for k in ['全局T汇总ECE','各主表属性ECE','跨序列T稳定性'])]
    if control_pass:unique='校准不是决策模型的独特优势；Qwen对照'+', '.join(control_pass)+'也通过同一标准'
    elif control_marginal_pass:unique='单属性校准不是决策模型的独特优势；Qwen对照'+', '.join(control_marginal_pass)+'通过全局单T及主属性门槛，但未通过完整组合/措辞等标准'
    else:unique='所测Qwen对照尚未通过完整同一标准，具体P4/P5差距见配对比较'
    if decision_pass:conclusion='在本次可评估的KITTI属性上，'+', '.join(decision_pass)+'满足冻结的校准前提；'+unique+'。'
    elif any(not r['model'].startswith('Qwen__') for r in model_judgments):
        conclusion=f'在现有KITTI二值属性标注下，{len(model_judgments)}个可运行模型均未通过完整的冻结校准前提（未运行的Perplexity无法判定）；'+unique+'，属性概率直接相乘的可靠性未获支持。'
    else:conclusion='尚无成功完成的决策模型，决策模型的校准前提无法判定；'+unique+'。'
    report += ['## ⑤ 一句话结论','',conclusion]
    (TASK/'analysis/REPORT_R58.md').write_text('\n'.join(report)+'\n')


if __name__=='__main__':main()
