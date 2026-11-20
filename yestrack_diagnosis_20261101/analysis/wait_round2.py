#!/usr/bin/env python3
"""One blocking reattachment after a chat interruption; no experiment is relaunched."""
import json
import argparse
import os
import signal
from pathlib import Path
import time

from common import config,log_run,save_json

p=argparse.ArgumentParser();p.add_argument('--next',action='store_true');p.add_argument('--shuffle',action='store_true');args=p.parse_args()
c=config();t=Path(c['task_root']);state=t/'analysis/runs/R33_wait/delivered.json'
connection=t/'analysis/runs/R44_wait_connections'/f'{os.getpid()}.json'
connection_state={'pid':os.getpid(),'started_unix':time.time(),'status':'waiting','experiment_restarted':False}
save_json(connection,connection_state)


def connection_terminated(signum,_frame):
    connection_state.update(status='connection_terminated',signal=signum,ended_unix=time.time())
    save_json(connection,connection_state)
    raise SystemExit(128+signum)


signal.signal(signal.SIGTERM,connection_terminated)
if not state.exists():log_run(c,33,'对话中断后的单命令阻塞接续',[
 'CUDA_VISIBLE_DEVICES=\'\' '+c['reproduction_environment']+' -u analysis/wait_round2.py'],
 '对话中断后原V8 exec cell已不存在，但H2、完成owner和R32恢复子进程仍活着。只附着等待已有完整receipt，不重新启动推理。'
 '文件等待和存活检查全部在本命令内部执行；不会在模型端反复调用ps/tail/nvidia-smi。')
events=[('context','analysis/runs/R23_context/result.json'),
        ('V1','analysis/runs/R24_v1_calibration/result.json'),
        ('H2','analysis/runs/R17_h2/result.json'),
        ('error_images','analysis/errors/manifest.json'),
        ('split_regression','analysis/runs/R19c_split_regression/result.json'),
        ('all_frame_scores','analysis/runs/R22_full_scores/frame_complete.json'),
        ('calibration','analysis/runs/R27_calibration/result.json'),
        ('all_frame_video_scores','analysis/runs/R22_full_scores/result.json'),
        ('newborn_scores','analysis/runs/R26_birth_scores/result.json'),
        ('TRP','analysis/runs/R28_trp/result.json'),
        ('SoM','analysis/runs/R25_som/result.json'),
        ('complete','analysis/runs/R30_completion/result.json')]
if args.shuffle:events=[('shuffled_SoM','analysis/runs/R47_shuffled_som/controller_complete.json')]
delivered=set(json.loads(state.read_text())) if args.next and state.exists() else set()


def alive(pid):
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False


while True:
    for name,relative in events:
        file=t/relative
        if name in delivered or not file.exists():continue
        r=json.loads(file.read_text());brief={'stage':name,'receipt':str(file)}
        if name=='H2':brief['metrics']={k:r['metrics'][k] for k in ('HOTA','DetA','AssA')}
        elif name=='context':brief['F1']={g:{m:v['f1'] for m,v in ms.items()} for g,ms in r['groups'].items()}
        elif name=='calibration':brief.update(ECE=r['frame_calibration']['ECE'],source_best=r['V1_best'],target_transfer=r['V2_at_V1_configuration'])
        elif name=='TRP':brief['error_rates']={d:{k:rs[k]['error_rate'] for k in ('overall','near','far')} for d,rs in r['delta'].items()}
        elif name=='error_images':brief['images']=r['images']
        else:
            for k in ('complete','candidate_rows','tasks','expressions','seconds','elapsed_seconds','max_score_difference'):
                if k in r:brief[k]=r[k]
        print(json.dumps(brief,ensure_ascii=False),flush=True);delivered.add(name)
        state.parent.mkdir(parents=True,exist_ok=True);state.write_text(json.dumps(sorted(delivered)))
        connection_state.update(status='receipt_delivered',stage=name,ended_unix=time.time())
        save_json(connection,connection_state)
        if args.next:raise SystemExit(0)
    failure=t/('analysis/runs/R47_shuffled_som/failure.json' if args.shuffle else 'analysis/runs/R30_completion/failure.json')
    if failure.exists():raise RuntimeError(failure.read_text())
    if ('shuffled_SoM' if args.shuffle else 'complete') in delivered:break
    ownerfile=t/'analysis/process_owners.json'
    owners=json.loads(ownerfile.read_text()) if ownerfile.exists() else {'H2':2291654}
    if not alive(owners['H2']) and not (t/'analysis/runs/R17_h2/result.json').exists():
        raise RuntimeError('H2 owner exited without complete result; inspect R17_h2/inference.log and preserve completed units.')
    if not alive(2520228) and not (t/'analysis/runs/R22_full_scores/result.json').exists():
        raise RuntimeError('R22 queue exited without complete result; inspect R32_sigterm_recovery/queue_resumed.log.')
    if args.shuffle:
        owner=json.loads((t/'analysis/runs/R47_shuffled_som/owner.json').read_text())
        if not alive(owner['pid']) and not (t/'analysis/runs/R47_shuffled_som/controller_complete.json').exists():
            raise RuntimeError('R47 owner exited without complete result; inspect R47_shuffled_som/controller.log.')
    time.sleep(15)
