#!/usr/bin/env python3
"""Pause this experiment's process tree when measured runtime exceeds authorization."""
import json
import os
from pathlib import Path
import signal
import time

from common import config,save_json

c=config();root=Path(c['task_root']);out=root/'analysis/runs/R53_native_trace'
owner=json.loads((out/'owner.json').read_text());owner_pid=owner['pid']
assert not (out/'budget_pause.json').exists(),'Budget pause already recorded'
# This is a single process-tree snapshot for an operational pause, not polling.
children={}
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        lines=(p/'status').read_text().splitlines()
        ppid=int(next(x.split(':',1)[1] for x in lines if x.startswith('PPid:')))
        children.setdefault(ppid,[]).append(int(p.name))
    except (FileNotFoundError,PermissionError,ProcessLookupError):continue
tree=[]
def descend(pid):
    tree.append(pid)
    for child in children.get(pid,[]):descend(child)
descend(owner_pid)
# Parent first prevents supervision from restarting stopped workers.
for pid in tree:os.kill(pid,signal.SIGSTOP)
paused=time.time();elapsed=paused-owner['started_unix']
tasks={r['name']:r for r in json.loads((root/'analysis/reproduction_inputs.json').read_text())['tasks']}
completed=[]
for line in (out/'inference.log').read_text().splitlines():
    if line.startswith('[OK] '):
        s=line.split(' ->',1)[0][5:];seq,expr=s.split('/',1);completed.append(seq+'__'+expr)
assert len(completed)==len(set(completed))
done_rows=sum(tasks[n]['candidate_rows'] for n in completed)
done_frames=sum(tasks[n]['sequence_images'] for n in completed)
total_rows=sum(r['candidate_rows'] for r in tasks.values())
total_frames=sum(r['sequence_images'] for r in tasks.values())
# Subtract an intentionally generous two-minute initialization allowance. These
# are workload-proxy extrapolations, not new model probes or exact guarantees.
steady=max(0.,elapsed-120.)
est_frame=(120+steady*total_frames/done_frames)/3600
est_row=(120+steady*total_rows/done_rows)/3600
receipt={'paused':True,'reason':'Measured shared-GPU throughput no longer supports the user automatic-execution estimate<8h condition',
    'owner_pid':owner_pid,'paused_pids':tree,'paused_unix':paused,'elapsed_wall_seconds_before_pause':elapsed,
    'completed_expressions':len(completed),'total_expressions':len(tasks),'completed_names':completed,
    'completed_candidate_rows':done_rows,'total_candidate_rows':total_rows,
    'completed_expression_image_frames':done_frames,'total_expression_image_frames':total_frames,
    'initialization_allowance_seconds':120,'estimated_total_hours_frame_proxy':est_frame,
    'estimated_total_hours_candidate_proxy':est_row,'old_prelaunch_estimate_hours':owner['estimated_hours'],
    'estimate_limitations':'Workload-proxy estimates using early sequence0005; future routing, sequence mix and foreign GPU load can change. Both proxies now exceed8h even after a generous warm-up subtraction.',
    'physical_GPUs':owner['physical_GPUs'],'other_users_processes_signaled':False,
    'model_and_seed_changed':False,'in_memory_state_preserved':True,'GPU_memory_still_reserved':True,
    'fullframe_cache_run':False,'requires_user_decision_before_SIGCONT':True}
save_json(out/'budget_pause.json',receipt)
state=json.loads((root/'analysis/round3_state.json').read_text())
state.update({'R53_GPU_paused_for_budget':True,'R51_next_action':'await_user_decision_on_revised_native_trace_budget',
              'R51_awaiting_approval':True,'R53_budget_pause':'analysis/runs/R53_native_trace/budget_pause.json'})
save_json(root/'analysis/round3_state.json',state)
print(json.dumps({k:v for k,v in receipt.items() if k!='completed_names'},ensure_ascii=False,indent=2),flush=True)
