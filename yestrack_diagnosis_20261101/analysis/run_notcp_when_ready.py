#!/usr/bin/env python3
"""Wait internally for a <8h GPU budget, run official noTCP once, then CPU HMMs."""
import argparse
import csv
from itertools import combinations
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import traceback

from common import config,log_run,mot,save_json

c=config();ROOT=Path(c['task_root']);OUT=ROOT/'analysis/runs/R55_notcp_native'
PLAN=json.loads((ROOT/'analysis/plans/round3_actual_notcp.json').read_text())
OUT.mkdir(parents=True,exist_ok=True)


def native_command():
    old=json.loads((ROOT/'analysis/runs/temprmot_star_paper_v2/commands.json').read_text())['inference']
    cmd=old.copy();cmd.remove('--stability_enable')
    wrapper=next(i for i,v in enumerate(cmd) if v.endswith('/analysis/seeded_run.py'))
    cmd[wrapper]=str(ROOT/'analysis/observed_inference.py')
    sep=cmd.index('--');cmd[sep:sep]=['--trace-root',str(OUT/'raw_scores')]
    cmd[cmd.index('--output_root')+1]=str(OUT/'predictions')
    # Verify the exact scientific argument change; output path is bookkeeping.
    expected=old[old.index('--')+1:].copy();expected.remove('--stability_enable')
    observed=cmd[cmd.index('--')+1:].copy()
    expected[expected.index('--output_root')+1]='OUTPUT'
    observed[observed.index('--output_root')+1]='OUTPUT'
    assert observed==expected,'Unexpected change to an R09 scientific argument'
    return cmd


def resource_sample():
    raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu',
                                 '--format=csv,noheader,nounits'],text=True)
    devices={}
    for r in csv.reader(raw.splitlines()):
        devices[int(r[0])]={'index':int(r[0]),'uuid':r[1].strip(),'free_MiB':int(r[2]),'utilization':int(r[3])}
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True)
    contexts={v['uuid']:set() for v in devices.values()};owned=set();uuid_index={v['uuid']:k for k,v in devices.items()}
    for r in csv.reader(apps.splitlines()):
        if len(r)<2:continue
        pid=int(r[0]);uuid=r[1].strip();contexts[uuid].add(pid);p=Path('/proc')/str(pid)
        try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (PermissionError,FileNotFoundError,ProcessLookupError):cmd=''
        try:cwd=str((p/'cwd').resolve(strict=True))
        except (PermissionError,FileNotFoundError,ProcessLookupError):cwd=''
        if c['project_root'] in cmd or cwd.startswith(c['project_root']):owned.add(uuid_index[uuid])
    resources=json.loads((Path(c['project_root'])/'configs/groundjev/resources.json').read_text())
    reference=json.loads((ROOT/'analysis/runs/temprmot_star_paper_v2/result.json').read_text())['elapsed_seconds']/3600
    eligible=[]
    for pair in combinations(resources['physical_gpu_allowlist'],2):
        selected=[devices[i] for i in pair]
        if any(r['free_MiB']<24576 for r in selected) or len(set(pair)|owned)>4:continue
        active=max(len(contexts[r['uuid']]) if r['utilization']>30 else 0 for r in selected)
        hours=reference*1.25*(1+active)
        if hours<8:
            eligible.append({'GPUs':list(pair),'estimated_hours':hours,'busy_existing_contexts':active,
                'selected':[{**r,'existing_contexts':len(contexts[r['uuid']])} for r in selected],
                'existing_project_GPU_indices':sorted(owned)})
    eligible.sort(key=lambda r:(r['estimated_hours'],r['GPUs']!=PLAN['GPU_admission']['preferred_pair'],r['GPUs']))
    return {'unix':time.time(),'devices':list(devices.values()),'eligible':eligible,
            'reference_R09_hours':reference,'estimate_formula':'R09_hours*1.25*(1+max busy pre-existing contexts)'}


def admit():
    previous=None;stable=0;number=0
    while True:
        snapshot=resource_sample();choice=snapshot['eligible'][0] if snapshot['eligible'] else None
        pair=choice['GPUs'] if choice else None
        stable=stable+1 if pair is not None and pair==previous else (1 if pair else 0)
        previous=pair;number+=1
        snapshot.update({'sample':number,'stable_samples':stable})
        with (OUT/'resource_samples.jsonl').open('a') as f:f.write(json.dumps(snapshot)+'\n')
        save_json(OUT/'run_state.json',{'phase':'waiting_for_low_load','sample':number,'stable_samples':stable,
                  'eligible_choice':choice,'GPU_model_loaded':False})
        if stable>=PLAN['GPU_admission']['stable_samples_required']:
            choice.update({'admitted_unix':time.time(),'stable_samples':stable,'resource_samples':number})
            save_json(OUT/'admission.json',choice);return choice
        time.sleep(PLAN['GPU_admission']['sample_interval_seconds'])


def run():
    start=time.monotonic();admission=admit();gpus=','.join(map(str,admission['GPUs']));cmd=native_command()
    save_json(OUT/'commands.json',{'inference':cmd,'cwd':str(ROOT/c['upstream']),'CUDA_VISIBLE_DEVICES':gpus,
              'estimated_hours':admission['estimated_hours'],'seed':2025,'only_scientific_change':'remove --stability_enable'})
    log_run(c,'55-start','低负载准入通过；GPU启动前估算与完整命令',[
        '# 原生入口工作目录：'+str(ROOT/c['upstream']),
        'CUDA_VISIBLE_DEVICES='+gpus+' OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join(cmd)],
        f'加载模型前连续{admission["stable_samples"]}次、间隔30s资源准入通过；预计{admission["estimated_hours"]:.3f}h<8，物理GPU={gpus}。'
        f'现场selected={json.dumps(admission["selected"])}。按R09实际2.209h乘1.25余量和(1+繁忙卡既有context数{admission["busy_existing_contexts"]})估算。'
        '用户已授权满足条件自动启动，不再问。官方模型科学参数与R09差异经列表比较仅有--stability_enable删除；wrapper仍为R17同一文件。')
    env={**os.environ,'CUDA_VISIBLE_DEVICES':gpus,'OMP_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false'}
    started=time.time();save_json(OUT/'run_state.json',{'phase':'native_noTCP_inference','physical_GPUs':admission['GPUs'],
        'estimated_hours':admission['estimated_hours'],'inference_started_unix':started})
    with (OUT/'inference.log').open('w') as f:
        r=subprocess.run(cmd,cwd=ROOT/c['upstream'],env=env,stdout=f,stderr=subprocess.STDOUT)
    elapsed=time.time()-started
    save_json(OUT/'inference_result.json',{'complete':r.returncode==0,'returncode':r.returncode,'seconds':elapsed,
        'physical_GPUs':admission['GPUs'],'estimated_hours':admission['estimated_hours'],'seed':2025,'TCP':False,'Delta':10})
    if r.returncode:raise RuntimeError(f'Native noTCP inference exited{r.returncode}; inspect inference.log')
    failures=[s for s in (OUT/'inference.log').read_text().splitlines() if '[ERR]' in s or 'Traceback (most recent call last)' in s]
    if failures:raise RuntimeError('Native noTCP task failure: '+failures[0])
    inputs=json.loads((ROOT/'analysis/reproduction_inputs.json').read_text());total=0
    actual={f'{p.parent.parent.name}__{p.parent.name}' for p in (OUT/'predictions').glob('*/*/predict_with_conf.txt')}
    assert actual=={r['name'] for r in inputs['tasks']}
    for item in inputs['tasks']:
        seq,expr=item['name'].split('__',1);p=mot(OUT/'predictions'/seq/expr/'predict_with_conf.txt')
        assert len(p)==item['candidate_rows'] and p.shape[1]==7 and ((p[:,6]>=0)&(p[:,6]<=1)).all()
        total+=len(p)
    assert total==1850576
    save_json(OUT/'coverage.json',{'complete':True,'expressions':len(actual),'candidate_rows':total})
    save_json(OUT/'run_state.json',{'phase':'CPU_LOSO_and_TrackEval','GPU_inference_complete':True,'seconds':elapsed})
    cpu=[c['reproduction_environment'],'-u',str(ROOT/'analysis/notcp_actual_replay.py')]
    with (OUT/'CPU_replay.log').open('w') as f:
        r=subprocess.run(cpu,cwd=ROOT,env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'},
                         stdout=f,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError(f'NoTCP CPU replay exited{r.returncode}; inspect CPU_replay.log')
    result=json.loads((ROOT/'analysis/runs/R55_notcp_actual/result.json').read_text());assert result['complete']
    save_json(OUT/'result.json',{'complete':True,'returncode':0,'seed':2025,'seconds':time.monotonic()-start,
        'GPU_inference_seconds':elapsed,'physical_GPUs':admission['GPUs'],'fullframe_cache_run':False,
        'HOTA':{v:r['metrics']['HOTA'] for v,r in result['variants'].items()}})
    save_json(OUT/'run_state.json',{'phase':'complete','GPU_inference_complete':True,'all_CPU_analysis_complete':True})


def launch():
    assert not (OUT/'owner.json').exists(),'Owner already registered; no duplicate job'
    cmd=native_command();save_json(OUT/'prepared_command.json',{'argv':cmd,'GPU_not_started':True,'conditional_authorization':PLAN['authorization']})
    with (OUT/'owner.log').open('w') as f:
        child=subprocess.Popen([c['reproduction_environment'],'-u',str(Path(__file__).resolve()),'run'],cwd=ROOT,
            env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,
            stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    save_json(OUT/'owner.json',{'pid':child.pid,'started_unix':time.time(),'phase':'wait_for_low_load','seed':2025})
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R55_owner_pid':child.pid,'R55_status':'wait_for_low_load_then_native_noTCP',
        'R51_awaiting_approval':False,'R53_status':'cancelled_no_resume','R55_complete':False})
    save_json(ROOT/'analysis/round3_state.json',state)
    print(json.dumps({'owner_pid':child.pid,'conditional_GPU_start':'stable low load and estimated<8h','no_new_approval_needed':True}),flush=True)


def wait():
    owner=json.loads((OUT/'owner.json').read_text());last=0.;complete=set();announced=set()
    tasks={r['name']:r for r in json.loads((ROOT/'analysis/reproduction_inputs.json').read_text())['tasks']}
    while not (OUT/'result.json').exists():
        os.kill(owner['pid'],0)
        if time.time()-last>=60:
            state=json.loads((OUT/'run_state.json').read_text()) if (OUT/'run_state.json').exists() else {'phase':'starting'}
            if state['phase']=='native_noTCP_inference':
                for p in (OUT/'predictions').glob('*/*/predict_with_conf.txt'):
                    name=f'{p.parent.parent.name}__{p.parent.name}'
                    if name in complete:continue
                    lines=p.read_text().splitlines()
                    if len(lines)==tasks[name]['candidate_rows']:
                        complete.add(name)
                print('Native noTCP (all ranks):',json.dumps({'complete_expressions':len(complete),'total':862,
                    'completed_candidate_rows':sum(tasks[n]['candidate_rows'] for n in complete),
                    'elapsed_hours':(time.time()-state['inference_started_unix'])/3600,
                    'physical_GPUs':state['physical_GPUs']}),flush=True)
            else:print('R55 state:',json.dumps(state),flush=True)
            last=time.time()
        for variant in PLAN['variants']:
            path=ROOT/'analysis/runs/R55_notcp_actual'/variant/'result.json'
            if path.exists() and variant not in announced:
                r=json.loads(path.read_text());print('TrackEval:',variant,json.dumps(r['metrics']),flush=True);announced.add(variant)
        time.sleep(10)
    result=json.loads((OUT/'result.json').read_text());print('R55 completed:',json.dumps(result),flush=True)
    if not result['complete']:print((OUT/'owner.log').read_text()[-12000:],flush=True)
    sys.exit(result['returncode'])


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['launch','run','wait']);args=ap.parse_args()
    try:globals()[args.action]()
    except BaseException as exc:
        if args.action=='run':save_json(OUT/'result.json',{'complete':False,'returncode':1,'message':str(exc),'traceback':traceback.format_exc()})
        raise
