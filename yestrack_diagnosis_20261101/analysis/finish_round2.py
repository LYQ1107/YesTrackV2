#!/usr/bin/env python3
"""Single blocking continuation owner: finish all analysis once valid GPU receipts arrive."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from common import config,log_run,save_json

p=argparse.ArgumentParser();p.add_argument('--resume-h2-deliverables',action='store_true');args=p.parse_args()
c=config();t=Path(c['task_root']);out=t/'analysis/runs/R30_completion'
out.mkdir(parents=True,exist_ok=True)
log_run(c,30,'第二轮全部交付的阻塞完成命令',[
 'CUDA_VISIBLE_DEVICES=\'\' OMP_NUM_THREADS=2 '+c['reproduction_environment']+' -u analysis/finish_round2.py'],
 '此单一阻塞owner内部等待完整receipt，不进行模型端进程/日志轮询。先完成H2分类表与错误样例；'
 '获批R22全量缓存结束后，R26新生ID批次预计0.5–1.5小时/4GPU（28676条），SoM预计2–4小时/1GPU；每阶段启动前另记预算。'
 '校准与TRP共享缓存，失败即明确返回该子命令日志；不跳样本、不更换指标。')


def wait_for(paths):
    while not all((t/p).exists() for p in paths):time.sleep(20)


def cpu(script,log_name=None):
    logfile=out/(log_name or (Path(script).stem+'.log'))
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=''
    with logfile.open('w') as f:
        status=subprocess.run([c['reproduction_environment'],'-u',str(t/script)],cwd=t,env=env,
                              stdout=f,stderr=subprocess.STDOUT)
    if status.returncode:raise RuntimeError(f'{script} failed ({status.returncode}); inspect {logfile}')
    print('[R30] Completed '+script,flush=True)


started=time.monotonic()
try:
    wait_for(['analysis/runs/R17_h2/result.json','analysis/runs/R23_context/result.json'])
    if not (args.resume_h2_deliverables and (t/'analysis/runs/R23_context/analysis.json').exists()):cpu('analysis/analyze_context.py')
    if not (args.resume_h2_deliverables and (t/'analysis/runs/R21_decomposition/result.json').exists()):cpu('analysis/decompose.py')
    if not (args.resume_h2_deliverables and (t/'analysis/errors/manifest.json').exists()):cpu('analysis/error_examples.py')
    if not (args.resume_h2_deliverables and (t/'analysis/runs/R31_heuristics/result.json').exists()):cpu('analysis/heuristic_diagnostics.py')
    cpu('analysis/render_report.py','report_after_H2.log')
    print('[R30] H2 tables and FP/FN images delivered; awaiting approved full score cache.',flush=True)
    wait_for(['analysis/runs/R22_full_scores/result.json','analysis/runs/R24_v1_calibration/result.json'])
    resource=subprocess.run(['nvidia-smi','-i','3,4,5,6','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],
                            text=True,capture_output=True,check=True)
    (out/'R26_resource_start.csv').write_text(resource.stdout)
    assert all(int(line.split(',')[1])>=16000 for line in resource.stdout.splitlines()),resource.stdout
    command=[c['reproduction_environment'],'-u','analysis/run_score_cache.py','--plan','analysis/plans/trp_births.json',
        '--out','analysis/runs/R26_birth_scores','--gpus','3,4,5,6','--run-number','26',
        '--estimated-hours','1','--video']
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='3,4,5,6'
    birth_log=(out/'birth_scores.log').open('w')
    births=subprocess.Popen(command,cwd=t,env=env,stdout=birth_log,stderr=subprocess.STDOUT,start_new_session=True)
    cpu('analysis/calibration.py')
    birth_status=births.wait();birth_log.close()
    assert not birth_status,f'R26 failed; inspect {out/"birth_scores.log"}'
    print('[R30] Complete frame and newborn caches validated; starting SoM.',flush=True)
    som_log=(out/'som_probe.log').open('w');env['CUDA_VISIBLE_DEVICES']='6'
    som=subprocess.Popen([c['reproduction_environment'],'-u','analysis/som_probe.py'],cwd=t,env=env,
                         stdout=som_log,stderr=subprocess.STDOUT,start_new_session=True)
    cpu('analysis/trp_probe.py')
    cpu('analysis/render_report.py','report_after_calibration.log')
    som_status=som.wait();som_log.close()
    assert not som_status,f'SoM failed; inspect {out/"som_probe.log"}'
    cpu('analysis/analyze_som.py')
    cpu('analysis/render_report.py','report_final.log')
    status=json.loads((t/'analysis/round2_status.json').read_text());assert status['complete'],status
    source=subprocess.run(['git','diff','--exit-code'],cwd=t/c['upstream'],text=True,capture_output=True)
    assert source.returncode==0,source.stdout
    save_json(out/'result.json',{'complete':True,'seed':c['seed'],'seconds':time.monotonic()-started,
        'reference':'相对本地基线','report':str(t/'analysis/REPORT.md'),'upstream_tracked_diff_empty':True})
    print('[R30] COMPLETE: all five report sections, full calibration/TRP, SoM and error images validated.',flush=True)
except Exception as e:
    save_json(out/'failure.json',{'complete':False,'error':str(e),'elapsed_seconds':time.monotonic()-started})
    raise
