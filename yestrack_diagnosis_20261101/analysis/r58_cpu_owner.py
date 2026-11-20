#!/usr/bin/env python3
"""One blocking CPU owner for all frozen R58 analyses and the final report."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
PYTHON=str(TASK/'analysis/.venv-yestrack/bin/python')


def analyze(row,main_only=False):
    key=row['checkpoint_repo'].replace('/','__')
    dest=OUT/'metrics'/key
    complete=[dest/'completion.json',dest/'sensitivity_two_values/completion.json']
    if all(p.exists() and json.loads(p.read_text()).get('complete') for p in complete):
        result={'model':row['model'],'checkpoint_repo':row['checkpoint_repo'],
                'returncode':0,'status':'complete','reused_complete_analysis':True}
        print(json.dumps(result),flush=True)
        return result
    command=[PYTHON,'-u','analysis/r58_analyze.py','--model-key',key]
    if main_only:
        command.append('--main-only')
    with (TASK/'analysis/runs.md').open('a') as f:
        scope='完整main设置：P1/P2/P3/P5/P6及效用；P4/crop待对应缓存' if main_only else '所有P1–P6及两取值敏感性'
        f.write('\nR58既定CPU分析（'+scope+'，bootstrap1000，seed2025）：\n\n```bash\n'+shlex.join(command)+'\n```\n')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    log=OUT/'logs'/(key+'_analysis.log');log.parent.mkdir(exist_ok=True)
    print(json.dumps({'event':'CPU_analysis_start','model':key,'scope':'main_only' if main_only else 'all_settings'}),flush=True)
    with log.open('a') as f:
        child=subprocess.Popen(command,cwd=TASK,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in child.stdout:
            f.write(line);f.flush()
            if line.startswith('{"analysis":'):print(line.rstrip(),flush=True)
        child.wait()
    result={'model':row['model'],'checkpoint_repo':row['checkpoint_repo'],'returncode':child.returncode,
            'status':'complete' if child.returncode==0 else 'analysis_failed','log':str(log),
            'scope':'main_only' if main_only else 'all_settings'}
    print(json.dumps(result),flush=True)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model-key');ap.add_argument('--main-only',action='store_true');args=ap.parse_args()
    assert not args.main_only or args.model_key,'--main-only requires --model-key'
    if args.model_key:
        suffix='_pilot.json' if args.main_only else '_full.json'
        status=json.loads((OUT/'status'/(args.model_key+suffix)).read_text())
        assert status['status']=='complete','The frozen inference stage is required before CPU analysis'
        rows=[{'model':status['model'],'checkpoint_repo':status['checkpoint_repo'],'status':'complete'}]
    else:
        full=json.loads((OUT/'full_owner_result.json').read_text())
        rows=[r for r in full['models'] if r['status']=='complete']
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(lambda row:analyze(row,args.main_only),rows))
    result_name='cpu_'+args.model_key+('_main' if args.main_only else '')+'_result.json' if args.model_key else 'cpu_owner_result.json'
    (OUT/result_name).write_text(json.dumps(result,indent=2)+'\n')
    if any(r['status']!='complete' for r in result):
        raise RuntimeError('CPU analysis failed; do not publish incomplete results as final')
    if args.model_key:
        return
    command=[PYTHON,'analysis/r58_report.py']
    with (TASK/'analysis/runs.md').open('a') as f:f.write('\nR58汇总报告与配对模型比较：\n\n```bash\n'+shlex.join(command)+'\n```\n')
    subprocess.run(command,cwd=TASK,check=True)


if __name__=='__main__':main()
