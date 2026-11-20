#!/usr/bin/env python3
"""Recover complete query checkpoints after an end-of-rank NCCL timeout."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
import traceback

import numpy as np
from common import config, log_run, mot, save_json
import round3 as temporal
from round3_budget import observation_mask
import run_notcp_when_ready as first

c=config(); ROOT=Path(c['task_root']); OUT=first.OUT
ARCHIVE=OUT/'attempt01'; RESUME=OUT/'attempt02'
TASKS=sorted(json.loads((ROOT/'analysis/reproduction_inputs.json').read_text())['tasks'],key=lambda r:r['name'])


def read_records(folder, allow_truncated=False):
    records=[]; receipts=[]
    for path in sorted(folder.glob('rank*.jsonl.gz')):
        count=0; error=None
        try:
            with gzip.open(path,'rt') as f:
                for line in f:
                    try:r=json.loads(line)
                    except json.JSONDecodeError:
                        if not allow_truncated:raise
                        error='interrupted final JSON record';break
                    records.append(r);count+=1
        except EOFError as exc:
            if not allow_truncated:raise
            error=str(exc)
        receipts.append({'path':str(path),'complete_JSON_records':count,'interrupted_stream':error})
    return records,receipts


def as_observations(records):
    result={}
    for r in records:
        obs=result.setdefault(r['name'],{})
        assert len(r['ids'])==len(r['p'])
        for oid,p in zip(r['ids'],r['p']):
            value=obs.setdefault((int(r['frame']),int(oid)),{})
            assert r['mode'] not in value, (r['name'],'duplicate observation')
            value[r['mode']]=float(p)
    return result


def validate_query(item, observed):
    name=item['name'];seq,expr=name.split('__',1)
    path=OUT/'predictions'/seq/expr/'predict_with_conf.txt'
    if not path.exists():return False,'no complete prediction checkpoint'
    tr=mot(path)
    if len(tr)!=item['candidate_rows'] or tr.shape[1]!=7:return False,'incomplete prediction'
    assert np.isfinite(tr).all() and ((tr[:,6]>=0)&(tr[:,6]<=1)).all(),name
    baseline=json.loads((ROOT/'analysis/local_baseline.json').read_text())
    old=mot(Path(baseline['predictions'])/seq/expr/'predict_with_conf.txt')
    assert np.array_equal(tr[:,:6],old[:,:6]),(name,'changed candidate geometry')
    geo=temporal.geometry(tr);mask=observation_mask(geo)
    keys={(int(f),int(i)) for f,i in tr[mask,:2]}
    obs=observed.get(name,{})
    if set(obs)!=keys:return False,'interrupted/missing trace observations'
    for key in keys:
        if 'frame' not in obs[key]:return False,'missing frame observation'
        p=obs[key]['frame'];expected={'frame','video'} if .2<=p<.8 else {'frame'}
        if set(obs[key])!=expected:return False,'interrupted/missing routed video observation'
    recovered=temporal.temporal_variant(tr,geo,obs,'V1')
    difference=float(np.max(np.abs(recovered-tr[:,6])))
    if difference>1e-12:raise RuntimeError(f'STOP: native V1 checkpoint replay mismatch: {name}: {difference}')
    return True,'full geometry, observation schedule, routed video and six-place V1 replay checked'


def write_records(path,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt') as f:
        for r in records:f.write(json.dumps(r)+'\n')


def prepare():
    assert not (RESUME/'recovery.json').exists(),'Recovery already prepared'
    ARCHIVE.mkdir(exist_ok=True);RESUME.mkdir(exist_ok=True)
    if not (ARCHIVE/'raw_scores').exists():
        for name in ['owner.json','admission.json','commands.json','inference_result.json','result.json','inference.log','owner.log']:
            if (OUT/name).exists():shutil.copy2(OUT/name,ARCHIVE/name)
        (OUT/'raw_scores').rename(ARCHIVE/'raw_scores')
    records,receipts=read_records(ARCHIVE/'raw_scores',allow_truncated=True)
    observed=as_observations(records);valid=[];redo=[]
    prediction_count=len(list((ARCHIVE/'predictions_requiring_trace_recovery').glob('*/*/predict_with_conf.txt')))
    for item in TASKS:
        name=item['name'];seq,expr=name.split('__',1);path=OUT/'predictions'/seq/expr/'predict_with_conf.txt'
        prediction_count+=int(path.exists())
        okay,reason=validate_query(item,observed)
        if okay:valid.append(name)
        else:
            redo.append({'name':name,'reason':reason})
            if path.exists():
                target=ARCHIVE/'predictions_requiring_trace_recovery'/seq/expr/path.name
                target.parent.mkdir(parents=True,exist_ok=True);path.rename(target)
    keep=set(valid);retained=[r for r in records if r['name'] in keep]
    write_records(OUT/'raw_scores/rank0.jsonl.gz',retained)
    remaining={r['name'] for r in redo};rank_rows=[0,0]
    assert [r['name'] for r in TASKS]==sorted(r['name'] for r in TASKS)
    for i,item in enumerate(TASKS):
        if item['name'] in remaining:rank_rows[i%2]+=item['candidate_rows']
    old=json.loads((ARCHIVE/'inference_result.json').read_text())
    receipt={'complete':True,'seed':2025,'first_failure':'rank0 completed its shard; end-of-rank collective timeout600000ms while rank1 still running',
        'official_sync_lines':[1191,1193],'original_prediction_files':prediction_count,
        'retained_complete_queries':valid,'redo_queries':redo,'retained_trace_records':len(retained),
        'stream_recovery':receipts,'maximum_retained_V1_replay_difference':0.0,
        'remaining_candidate_rows_by_native_rank':rank_rows,
        'reference_work_ratio':2*max(rank_rows)/1850576,
        'spent_GPU_inference_hours':old['seconds']/3600,
        'infrastructure_fix':'analysis-only wrapper supplies NCCL init timeout8h; official model/observer/decision logic unchanged; official --resume',
        'variants_unchanged':first.PLAN['variants'],'no_skipped_samples':True}
    save_json(RESUME/'recovery.json',receipt)
    log_run(c,'55-recovery','NCCL末尾同步超时；保留完整查询，恢复未完成单元',[
        "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "+shlex.join([c['reproduction_environment'],'analysis/resume_notcp_native.py','prepare']),
        "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "+shlex.join([c['reproduction_environment'],'analysis/resume_notcp_native.py','launch']),
        "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 "+shlex.join([c['reproduction_environment'],'analysis/resume_notcp_native.py','wait'])],
        f'首个错误为rank0末尾collective等待较慢rank1超过600s，非OOM。已运行{old["seconds"]/3600:.3f}h。'
        f'{prediction_count}个预测文件中{len(valid)}个同时通过完整行数/原R09框几何/观测时间表/video路由/原生V1六位逐值差0核对；其余{len(redo)}个查询完整重跑，不丢样本。'
        '原始失败日志与可能缺gzip尾部的trace保存在attempt01，恢复完整JSON前缀仅用于已通过门槛的查询。仅analysis外层将NCCL同步timeout设8h；官方源码、weights、seed、科学参数、三个预注册变体均不改。'
        '续跑仍nproc2、官方--resume；新trace单独存attempt02后严格合并。启动前重新连续3次资源准入；剩余估时=R09全量估时×2×剩余最重rank候选行/全量行，并要求已耗时+剩余估时<8h。')
    print(json.dumps({k:receipt[k] for k in ['original_prediction_files','retained_trace_records','remaining_candidate_rows_by_native_rank','reference_work_ratio','spent_GPU_inference_hours']}),flush=True)
    print('Retain',len(valid),'queries; redo',len(redo),'queries; strict retained gate difference0',flush=True)


def admit(recovery):
    previous=None;stable=0;number=0
    while True:
        snapshot=first.resource_sample();choices=[]
        for choice in snapshot['eligible']:
            estimate=choice['estimated_hours']*recovery['reference_work_ratio']
            total=estimate+recovery['spent_GPU_inference_hours']
            if total<8:choices.append({**choice,'full_job_reference_estimated_hours':choice['estimated_hours'],
                'estimated_hours':estimate,'aggregate_estimated_hours':total})
        choice=choices[0] if choices else None;pair=choice['GPUs'] if choice else None
        stable=stable+1 if pair is not None and pair==previous else (1 if pair else 0)
        previous=pair;number+=1;snapshot.update({'resume_sample':number,'stable_samples':stable,'resume_choice':choice})
        with (RESUME/'resource_samples.jsonl').open('a') as f:f.write(json.dumps(snapshot)+'\n')
        save_json(OUT/'run_state.json',{'phase':'waiting_for_low_load_resume','sample':number,'stable_samples':stable,'eligible_choice':choice,'GPU_model_loaded':False})
        if stable>=3:
            choice.update({'admitted_unix':time.time(),'stable_samples':stable})
            save_json(RESUME/'admission.json',choice);return choice
        time.sleep(30)


def run():
    recovery=json.loads((RESUME/'recovery.json').read_text());admission=admit(recovery)
    cmd=first.native_command();index=cmd.index(str(ROOT/'analysis/observed_inference.py'))
    cmd[index]=str(ROOT/'analysis/observed_inference_timeout.py')
    cmd[cmd.index('--trace-root')+1]=str(RESUME/'raw_scores');cmd.append('--resume')
    gpus=','.join(map(str,admission['GPUs']))
    save_json(RESUME/'commands.json',{'inference':cmd,'cwd':str(ROOT/c['upstream']),'CUDA_VISIBLE_DEVICES':gpus,'seed':2025,'sync_timeout_seconds':28800})
    log_run(c,'55-resume-start','续跑前资源、预计剩余耗时与展开命令',[
        '# 原生入口工作目录：'+str(ROOT/c['upstream']),
        'CUDA_VISIBLE_DEVICES='+gpus+' OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join(cmd)],
        f'连续3次30s准入通过；物理GPU={gpus}，剩余预计{admission["estimated_hours"]:.3f}h，含失败前计算的总预计{admission["aggregate_estimated_hours"]:.3f}h<8。'
        f'全量R09参考估时{admission["full_job_reference_estimated_hours"]:.3f}h乘最重剩余rank工作比{recovery["reference_work_ratio"]:.6f}；现场selected={json.dumps(admission["selected"])}。'
        '仅官方--resume和analysis同步超时外层，保持seed2025和全部模型参数；不是新变体。')
    start=time.time();save_json(OUT/'run_state.json',{'phase':'native_noTCP_inference','physical_GPUs':admission['GPUs'],
        'inference_started_unix':start,'resume':True,'spent_before_resume_hours':recovery['spent_GPU_inference_hours']})
    with (RESUME/'inference.log').open('w') as f:
        result=subprocess.run(cmd,cwd=ROOT/c['upstream'],env={**os.environ,'CUDA_VISIBLE_DEVICES':gpus,
            'OMP_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false'},stdout=f,stderr=subprocess.STDOUT)
    seconds=time.time()-start
    save_json(RESUME/'inference_result.json',{'complete':result.returncode==0,'returncode':result.returncode,'seconds':seconds,'physical_GPUs':admission['GPUs']})
    if result.returncode:raise RuntimeError(f'Native noTCP resume exited{result.returncode}; inspect attempt02/inference.log')
    assert not any('[ERR]' in s or 'Traceback (most recent call last)' in s for s in (RESUME/'inference.log').read_text().splitlines())
    old_records,_=read_records(OUT/'raw_scores');new_records,_=read_records(RESUME/'raw_scores')
    old_names={r['name'] for r in old_records};new_names={r['name'] for r in new_records}
    assert old_names.isdisjoint(new_names)
    observed=as_observations(old_records+new_records)
    for item in TASKS:
        okay,reason=validate_query(item,observed);assert okay,(item['name'],reason)
    assert len(observed)==862
    write_records(OUT/'raw_scores/rank0.jsonl.gz',old_records+new_records)
    save_json(RESUME/'merge_validation.json',{'complete':True,'retained_queries':len(old_names),'resumed_queries':len(new_names),
        'expressions':862,'candidate_rows':1850576,'maximum_V1_replay_difference':0.0,'no_duplicate_observations':True})
    original=json.loads((ARCHIVE/'inference_result.json').read_text())
    save_json(OUT/'inference_result.json',{'complete':True,'returncode':0,'seconds':original['seconds']+seconds,
        'physical_GPUs':sorted(set(original['physical_GPUs'])|set(admission['GPUs'])),
        'estimated_hours':original['estimated_hours'],'resume_estimated_hours':admission['estimated_hours'],
        'aggregate_resume_estimated_hours':admission['aggregate_estimated_hours'],'attempt01_seconds':original['seconds'],
        'attempt02_seconds':seconds,'seed':2025,'TCP':False,'Delta':10,'sync_timeout_only_fix':True})
    save_json(OUT/'coverage.json',{'complete':True,'expressions':862,'candidate_rows':1850576})
    save_json(OUT/'run_state.json',{'phase':'CPU_LOSO_and_TrackEval','GPU_inference_complete':True})
    with (OUT/'CPU_replay.log').open('w') as f:
        result=subprocess.run([c['reproduction_environment'],'-u',str(ROOT/'analysis/notcp_actual_replay.py')],cwd=ROOT,
            env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'},stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'CPU replay exited{result.returncode}; inspect CPU_replay.log')
    r=json.loads((ROOT/'analysis/runs/R55_notcp_actual/result.json').read_text());assert r['complete']
    save_json(OUT/'result.json',{'complete':True,'returncode':0,'seed':2025,'GPU_inference_seconds':original['seconds']+seconds,
        'resumed_after_NCCL_timeout':True,'fullframe_cache_run':False,'HOTA':{v:x['metrics']['HOTA'] for v,x in r['variants'].items()}})
    save_json(OUT/'run_state.json',{'phase':'complete','GPU_inference_complete':True,'all_CPU_analysis_complete':True})


def launch():
    assert (RESUME/'recovery.json').exists() and not (RESUME/'owner.json').exists()
    (OUT/'result.json').unlink()
    with (RESUME/'owner.log').open('w') as f:
        child=subprocess.Popen([c['reproduction_environment'],'-u',str(Path(__file__).resolve()),'run'],cwd=ROOT,
            env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,
            stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    record={'pid':child.pid,'started_unix':time.time(),'resume':True}
    save_json(RESUME/'owner.json',record);save_json(OUT/'owner.json',record)
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R55_owner_pid':child.pid,'R55_status':'NCCL_timeout_recovered_wait_for_low_load_resume',
        'R55_complete':False,'R55_retained_queries':len(json.loads((RESUME/'recovery.json').read_text())['retained_complete_queries']),
        'R55_fullframe_cache_run':False})
    save_json(ROOT/'analysis/round3_state.json',state)
    print(json.dumps(record),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','launch','run','wait']);args=p.parse_args()
    try:
        if args.action=='wait':first.wait()
        else:globals()[args.action]()
    except BaseException as exc:
        if args.action=='run':
            save_json(OUT/'result.json',{'complete':False,'returncode':1,'message':str(exc),'traceback':traceback.format_exc()})
            raise
        raise
