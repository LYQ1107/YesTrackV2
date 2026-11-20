#!/usr/bin/env python3
"""One authorized native Delta10 GPU run, passive R17 trace, then CPU replay."""
import argparse
import csv
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import traceback

from common import config,mot,save_json

c=config();ROOT=Path(c['task_root']);OUT=ROOT/'analysis/runs/R53_native_trace'
PLAN=json.loads((ROOT/'analysis/plans/round3_actual_native_trace.json').read_text())
GPUS=','.join(map(str,PLAN['physical_GPUs']))
OUT.mkdir(parents=True,exist_ok=True)


def commands():
    old=json.loads((ROOT/'analysis/runs/temprmot_star_paper_v2/commands.json').read_text())
    infer=old['inference'].copy()
    i=next(i for i,a in enumerate(infer) if a.endswith('/analysis/seeded_run.py'))
    infer[i]=str(ROOT/'analysis/observed_inference.py')
    separator=infer.index('--')
    infer[separator:separator]=['--trace-root',str(OUT/'raw_scores')]
    infer[infer.index('--output_root')+1]=str(OUT/'predictions')
    cpu=[c['reproduction_environment'],'-u',str(ROOT/'analysis/actual_temporal_replay.py')]
    return infer,cpu


def prelaunch_resources():
    command=['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits']
    text=subprocess.check_output(command,text=True)
    devices=[]
    for row in csv.reader(text.splitlines()):
        devices.append({'index':int(row[0]),'uuid':row[1].strip(),'free_MiB':int(row[2]),'utilization':int(row[3])})
    selected=[r for r in devices if r['index'] in PLAN['physical_GPUs']]
    assert len(selected)==2 and all(r['free_MiB']>=24576 for r in selected),selected
    allow=json.loads((Path(c['project_root'])/'configs/groundjev/resources.json').read_text())
    assert set(PLAN['physical_GPUs'])<=set(allow['physical_gpu_allowlist'])
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True)
    uuid_to_index={r['uuid']:r['index'] for r in devices};owned=set();project_processes=[]
    for row in csv.reader(apps.splitlines()):
        if len(row)<2:continue
        pid=int(row[0]);gpu=uuid_to_index[row[1].strip()];p=Path('/proc')/str(pid)
        try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (PermissionError,FileNotFoundError):cmd=''
        try:cwd=str((p/'cwd').resolve(strict=True))
        except (PermissionError,FileNotFoundError):cwd=''
        if c['project_root'] in cmd or cwd.startswith(c['project_root']):
            owned.add(gpu);project_processes.append({'pid':pid,'gpu':gpu})
    assert len(owned|set(PLAN['physical_GPUs']))<=4,(owned,PLAN['physical_GPUs'])
    receipt={'inspected_unix':time.time(),'selected':selected,'existing_project_gpu_indices':sorted(owned),
             'existing_project_processes':project_processes,'combined_physical_GPUs':sorted(owned|set(PLAN['physical_GPUs'])),
             'other_processes_preserved':True}
    save_json(OUT/'prelaunch_resources.json',receipt)
    return receipt


def launch():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==GPUS
    decision=json.loads((ROOT/'analysis/runs/R52_budget/GPU_decision.json').read_text())
    validation=json.loads((ROOT/'analysis/runs/R52_budget/validation.json').read_text())
    assert decision['sparse_HMM_reaches_plus2'] and validation['complete']
    assert PLAN['runtime_estimate']['estimated_wall_hours']<8
    assert not (OUT/'owner.json').exists(),'Owner already registered; inspect its completion receipt instead of duplicate inference'
    resources=prelaunch_resources()
    infer,cpu=commands()
    save_json(OUT/'commands.json',{'inference':infer,'CPU_replay':cpu,'cwd':str(ROOT/c['upstream']),
        'CUDA_VISIBLE_DEVICES':GPUS,'seed':2025,'estimated_hours':PLAN['runtime_estimate']['estimated_wall_hours'],
        'observation_delta':10,'passive_wrapper':'analysis/observed_inference.py unchanged fromR17'})
    with (ROOT/'analysis/runs.md').open('a') as f:
        f.write('\nR53 启动前命令展开（已通过用户条件授权与R52验证）：\n\n```bash\ncd '+shlex.quote(str(ROOT/c['upstream']))+'\n')
        f.write('CUDA_VISIBLE_DEVICES='+GPUS+' OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join(infer)+'\n```\n')
    env={**os.environ,'CUDA_VISIBLE_DEVICES':GPUS,'OMP_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false'}
    with (OUT/'owner.log').open('w') as handle:
        child=subprocess.Popen([c['reproduction_environment'],'-u',str(Path(__file__).resolve()),'run'],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
    save_json(OUT/'owner.json',{'pid':child.pid,'started_unix':time.time(),'physical_GPUs':PLAN['physical_GPUs'],
        'estimated_hours':PLAN['runtime_estimate']['estimated_wall_hours'],'authorization':PLAN['authorization']})
    state=json.loads((ROOT/'analysis/round3_state.json').read_text())
    state.update({'R51_GPU_started':True,'R51_awaiting_approval':False,'R53_GPU_complete':False,
                  'R53_owner_pid':child.pid,'R53_physical_GPUs':PLAN['physical_GPUs'],
                  'R51_next_action':'native_Delta10_trace_then_CPU_replay','R51_fullframe_cache_authorized':False})
    save_json(ROOT/'analysis/round3_state.json',state)
    print(json.dumps({'owner_pid':child.pid,'estimated_hours':PLAN['runtime_estimate']['estimated_wall_hours'],
                     'physical_GPUs':PLAN['physical_GPUs'],'free_MiB':[r['free_MiB'] for r in resources['selected']]}),flush=True)


def run():
    start=time.monotonic();infer,cpu=commands()
    with (OUT/'inference.log').open('w') as f:
        r=subprocess.run(infer,cwd=ROOT/c['upstream'],stdout=f,stderr=subprocess.STDOUT)
    seconds=time.monotonic()-start
    save_json(OUT/'inference_result.json',{'complete':r.returncode==0,'returncode':r.returncode,'seconds':seconds,
              'physical_GPUs':PLAN['physical_GPUs'],'seed':2025,'Delta':10})
    if r.returncode:raise RuntimeError(f'Native trace inference exited {r.returncode}; inspect inference.log')
    lines=(OUT/'inference.log').read_text().splitlines()
    failures=[line for line in lines if '[ERR]' in line or 'Traceback (most recent call last)' in line]
    if failures:raise RuntimeError('Native inference failure: '+failures[0])
    inputs=json.loads((ROOT/'analysis/reproduction_inputs.json').read_text())
    actual={f'{p.parent.parent.name}__{p.parent.name}' for p in (OUT/'predictions').glob('*/*/predict_with_conf.txt')}
    assert actual=={r['name'] for r in inputs['tasks']}
    total=0
    for item in inputs['tasks']:
        seq,expr=item['name'].split('__',1)
        p=mot(OUT/'predictions'/seq/expr/'predict_with_conf.txt')
        assert len(p)==item['candidate_rows'] and p.shape[1]==7
        assert bool(((p[:,6]>=0)&(p[:,6]<=1)).all())
        total+=len(p)
    assert total==1850576
    save_json(OUT/'coverage.json',{'complete':True,'expressions':len(actual),'candidate_rows':total})
    print('GPU inference complete, exact coverage validated:',seconds,'seconds',flush=True)
    env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
    with (OUT/'CPU_replay.log').open('w') as f:
        r=subprocess.run(cpu,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError(f'CPU replay exited {r.returncode}; inspect CPU_replay.log')
    result=json.loads((ROOT/'analysis/runs/R53_actual_temporal/result.json').read_text());assert result['complete']
    save_json(OUT/'result.json',{'complete':True,'returncode':0,'seconds':time.monotonic()-start,
        'GPU_inference_seconds':seconds,'seed':2025,'physical_GPUs':PLAN['physical_GPUs'],
        'coverage':{'expressions':862,'candidate_rows':total},'fullframe_cache_run':False,
        'paired_native_HOTA':result['variants']['Actual_V0']['metrics']['HOTA'],
        'transferred_LOSO_HOTA':result['variants']['Actual_HMM10_LOSO']['metrics']['HOTA'],
        'transferred_LOSO_gain':result['variants']['Actual_HMM10_LOSO']['gain_HOTA']})


def wait():
    """One blocking shell command; all process/log checks remain inside this process."""
    owner=json.loads((OUT/'owner.json').read_text());offset=0;completed=0;last_notice=0.;announced=set()
    while not (OUT/'result.json').exists():
        os.kill(owner['pid'],0)
        log=OUT/'inference.log'
        if log.exists():
            with log.open() as f:
                f.seek(offset)
                for line in f:
                    if line.startswith('[OK]'):completed+=1
                offset=f.tell()
        now=time.time()
        if now-last_notice>=60:
            print(f'Native Delta10 trace: {completed}/862 expressions; elapsed={(now-owner["started_unix"])/3600:.3f}h',flush=True)
            last_notice=now
        phase=OUT/'inference_result.json'
        if phase.exists() and 'inference' not in announced:
            print('GPU phase receipt:',phase.read_text().strip(),flush=True);announced.add('inference')
        for variant in PLAN['frozen_offline_variants']:
            path=ROOT/'analysis/runs/R53_actual_temporal'/variant/'result.json'
            if path.exists() and variant not in announced:
                r=json.loads(path.read_text());print('CPU TrackEval:',variant,json.dumps(r['metrics']),flush=True);announced.add(variant)
        time.sleep(10)
    result=json.loads((OUT/'result.json').read_text());print('R53 completed:',json.dumps(result),flush=True)
    if not result.get('complete'):
        print((OUT/'owner.log').read_text()[-12000:],flush=True)
    sys.exit(result.get('returncode',1))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['launch','run','wait']);a=ap.parse_args()
    try:globals()[a.action]()
    except BaseException as exc:
        if a.action=='run':save_json(OUT/'result.json',{'complete':False,'returncode':1,'message':str(exc),'traceback':traceback.format_exc()})
        raise
