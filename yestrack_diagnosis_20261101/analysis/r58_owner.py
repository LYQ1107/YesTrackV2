#!/usr/bin/env python3
"""One blocking owner: wait for downloads, honor GPU quota, run only frozen R58 pilots."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parent
OUT = TASK/'analysis/runs/R58_calibration'
PLAN = json.loads((TASK/'analysis/plans/r58.json').read_text())
PYTHON = '/data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def wait_download(repo):
    path = OUT/'download_status'/(repo.replace('/', '__')+'.json')
    while not path.exists():
        time.sleep(10)
    return json.loads(path.read_text())


def select_gpu(required_gib):
    while True:
        result = subprocess.run(['nvidia-smi', '--query-gpu=index,uuid,memory.free,utilization.gpu', '--format=csv,noheader,nounits'],
                                capture_output=True, text=True, check=True)
        devices = {}
        for line in result.stdout.splitlines():
            index, uuid, free, utilization = [s.strip() for s in line.split(',')]
            devices[uuid] = {'index': int(index), 'free_gib': float(free)/1024,
                             'utilization': float(utilization)}
        apps = subprocess.run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, check=True)
        project_gpus = set()
        for line in apps.stdout.splitlines():
            uuid, pid = [s.strip() for s in line.split(',')]
            try:
                cwd = Path('/proc')/pid/'cwd'
                if cwd.resolve().is_relative_to(ROOT):
                    project_gpus.add(devices[uuid]['index'])
            except (FileNotFoundError, PermissionError):
                continue
        choices = [d for d in devices.values() if d['index'] in PLAN['resources']['allowed_gpus']
                   and d['free_gib'] >= required_gib and len(project_gpus | {d['index']}) <= 4]
        if choices:
            return min(choices, key=lambda d: (d['utilization'], -d['free_gib']))['index']
        state={'event':'waiting_for_gpu','required_free_gib':required_gib,
               'project_gpus':sorted(project_gpus),
               'allowed_free_gib':{d['index']:round(d['free_gib'],2) for d in devices.values()
                                   if d['index'] in PLAN['resources']['allowed_gpus']}}
        if state != locals().get('last_wait_state'):
            print(json.dumps(state),flush=True)
            last_wait_state=state
        time.sleep(30)


def run_model(family, repo, min_gib, stage='pilot'):
    status = OUT/'status'/(repo.replace('/', '__')+'_'+stage+'.json')
    if status.exists() and json.loads(status.read_text())['status'] == 'complete':
        return json.loads(status.read_text())
    gpu = select_gpu(min_gib)
    python = '/home/user/.cache/r58_calibration/env-pplx/bin/python' if family.startswith('perplexity') else PYTHON
    command = [python, '-u', 'analysis/r58_gpu.py', '--model', family, '--stage', stage]
    if repo != family:
        command += ['--checkpoint-repo', repo]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), OMP_NUM_THREADS='4', TOKENIZERS_PARALLELISM='false')
    extra = '/home/user/.cache/r58_calibration/extra310'
    if family.startswith('perplexity'):
        env.pop('PYTHONPATH',None)
    else:
        env['PYTHONPATH'] = extra+(':'+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    with (TASK/'analysis/runs.md').open('a') as f:
        if stage=='pilot':
            estimate='200条main + 其它5配置各10条；预估5–30分钟，27B预估10–40分钟（启动前工程估计，正式预算待实测）'
        else:
            budget=json.loads((OUT/'budget.json').read_text())
            row=next(r for r in budget['models'] if r.get('checkpoint_repo')==repo)
            estimate=f'根据200样本吞吐预计本阶段剩余{row["remaining_gpu_stage_seconds"]/3600:.3f}小时；复用已缓存样本，执行同一冻结计划'
        f.write(f'\nR58 GPU {stage} 阶段开始：`{repo}`，物理GPU {gpu}；{estimate}。\n\n```bash\n')
        f.write(f'CUDA_VISIBLE_DEVICES={gpu} OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false '+
                (f'PYTHONPATH={shlex.quote(env["PYTHONPATH"])} ' if env.get('PYTHONPATH') else '')+
                shlex.join(command)+'\n```\n')
    print(json.dumps({'event': stage+'_start', 'repo': repo, 'gpu': gpu}), flush=True)
    log = OUT/'logs'/(repo.replace('/', '__')+'_'+stage+'.log')
    log.parent.mkdir(exist_ok=True)
    with log.open('a') as f:
        child = subprocess.Popen(command,cwd=TASK,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in child.stdout:
            f.write(line);f.flush()
            if line.startswith('{"model":'):
                print(line.rstrip(),flush=True)
        child.wait()
    result = json.loads(status.read_text()) if status.exists() else {'status': 'failed', 'exception': 'worker exited without status', 'returncode': child.returncode}
    print(json.dumps({'event': stage+'_end', 'repo': repo, 'status': result['status'],
                      'seconds': result.get('wall_seconds'), 'exception': result.get('exception')}), flush=True)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['pilot','full'],default='pilot');args=ap.parse_args()
    assert json.loads((OUT/'validation_pre_inference.json').read_text())['status']=='passed'
    if args.stage=='full':
        assert (OUT/'full_budget_approval.json').exists(),'Full GPU budget has not been approved'
        authorization=json.loads((OUT/'full_budget_approval.json').read_text())
        if authorization.get('authorization')=='user automatic <=4h rule':
            assert json.loads((OUT/'budget.json').read_text())['gate']=='within_user_automatic_budget'
        pilot=json.loads((OUT/'pilot_owner_result.json').read_text())
        full=[]
        priority=['vllm-sr/d3-mini','vllm-sr/d3-flash','OmniJev/OneJev1.5-9B',
                  'Qwen/Qwen3-VL-2B-Instruct','Qwen/Qwen3-VL-8B-Instruct','vllm-sr/d3-turbo']
        ordered=sorted(pilot['models'],key=lambda r:priority.index(r['model']) if r['model'] in priority else len(priority))
        for r in ordered:
            if r['status']!='complete':
                full.append(r);continue
            repo=r['checkpoint_repo'];memory=50 if ('turbo' in repo and not repo.endswith('INT4')) or repo.startswith('perplexity') else 28 if '9B' in repo or '8B' in repo or repo.endswith('INT4') else 24 if 'flash' in repo else 14
            result=run_model(r['model'],repo,memory,'full')
            full.append({'model':r['model'],'checkpoint_repo':repo,'status':result['status'],'reason':result.get('exception')})
        write(OUT/'full_owner_result.json',{'seed':2025,'models':full,'full_inference_started':True})
        return
    results = []
    # Small decision models and both controls first, larger model last.
    order = [('vllm-sr/d3-mini', 14), ('vllm-sr/d3-flash', 24), ('OmniJev/OneJev1.5-9B', 28),
             ('Qwen/Qwen3-VL-2B-Instruct', 12), ('Qwen/Qwen3-VL-8B-Instruct', 28),
             ('vllm-sr/d3-turbo', 50)]
    # An already cached pinned model can pilot while other model downloads continue.
    order.sort(key=lambda item: not ((OUT/'download_status'/(item[0].replace('/', '__')+'.json')).exists()
        and json.loads((OUT/'download_status'/(item[0].replace('/', '__')+'.json')).read_text())['status']=='downloaded'))
    for repo, memory in order:
        d = wait_download(repo)
        if d['status'] != 'downloaded':
            results.append({'model': repo, 'status': 'download_failed', 'reason': d})
            continue
        result = run_model(repo, repo, memory)
        error=result.get('exception','')
        if repo == 'vllm-sr/d3-turbo' and result['status'] == 'failed' and ('OutOfMemory' in error or 'out of memory' in error.lower()):
            fallback = 'vllm-sr/d3-turbo-INT4'  # A800 sm80 cannot execute official FP8 W8A8.
            with (TASK/'analysis/runs.md').open('a') as f:
                f.write('\nR58 d3-turbo BF16显存不足，保留失败记录；A800不支持官方FP8所需sm89，依冻结计划改用官网INT4，整个200样本重跑，不混合精度结果。\n\n```bash\n'+
                    shlex.join([PYTHON,'-u','analysis/r58_download.py','--repos',fallback])+'\n```\n')
            with (OUT/'download_INT4.log').open('a') as f:
                subprocess.run([PYTHON,'-u','analysis/r58_download.py','--repos',fallback], cwd=TASK, stdout=f, stderr=subprocess.STDOUT, check=True)
            result = run_model(repo, fallback, 28)
        results.append({'model': repo, 'checkpoint_repo': result.get('checkpoint_repo', repo),
                        'status': result['status'], 'reason': result.get('exception')})
    runtime_path = OUT/'perplexity_runtime.json'
    while not runtime_path.exists():
        time.sleep(10)
    runtime = json.loads(runtime_path.read_text())
    repo = 'perplexity-ai/pplx-decider-v1.2'
    if runtime['status'] == 'runtime_ready':
        with (OUT/'download_Perplexity.log').open('a') as f:
            subprocess.run([PYTHON,'-u','analysis/r58_download.py','--repos',repo], cwd=TASK, stdout=f, stderr=subprocess.STDOUT, check=True)
        result = run_model(repo, repo, 50)
        results.append({'model': repo, 'checkpoint_repo': repo, 'status': result['status'], 'reason': result.get('exception')})
    else:
        results.append({'model': repo, 'status': runtime['status'], 'reason': str(runtime_path)})
    write(OUT/'pilot_owner_result.json', {'seed': 2025, 'models': results, 'full_inference_started': False})
    subprocess.run([PYTHON,'analysis/r58_budget.py'], cwd=TASK, check=True)


if __name__ == '__main__':
    main()
