#!/usr/bin/env python3
"""End the user-superseded stopped TCP run, preserving files and releasing GPUs."""
import json
import os
from pathlib import Path
import signal
import time

from common import config,save_json

c=config();root=Path(c['task_root']);out=root/'analysis/runs/R53_native_trace'
pause=json.loads((out/'budget_pause.json').read_text());pids=pause['paused_pids']
live=[]
for pid in pids:
    path=Path('/proc')/str(pid)
    if not path.exists():continue
    command=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    assert str(root) in command,(pid,'not the recorded experiment process')
    live.append(pid)
workers=[pid for pid in live if pid not in pids[:2]]
# Queue interruption before unfreezing workers. SIGCONT is solely to deliver
# pending SIGINT and allow the passive recorder's finally: trace.close().
for pid in workers:os.kill(pid,signal.SIGINT)
for pid in workers:os.kill(pid,signal.SIGCONT)
def alive(pid):
    p=Path('/proc')/str(pid)/'status'
    if not p.exists():return False
    state=next(x for x in p.read_text().splitlines() if x.startswith('State:'))
    return '\tZ' not in state
deadline=time.monotonic()+30
while any(alive(pid) for pid in workers) and time.monotonic()<deadline:time.sleep(.25)
for pid in live:
    if alive(pid):
        os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
deadline=time.monotonic()+10
while any(alive(pid) for pid in live) and time.monotonic()<deadline:time.sleep(.25)
assert not any(alive(pid) for pid in live),'Own native trace processes did not exit'
receipt={'status':'cancelled_and_superseded_by_user','stopped_pids':live,
    'reason':'User requested a fresh official no-TCP run; old TCP trace must not resume',
    'GPU_memory_released_via_process_exit':True,'old_outputs_preserved':True,
    'completed_expression_files':len(list((out/'predictions').glob('*/*/predict_with_conf.txt'))),
    'other_users_processes_signaled':False,'continue_old_inference':False}
save_json(out/'superseded.json',receipt)
state=json.loads((root/'analysis/round3_state.json').read_text())
state.update({'R53_GPU_paused_for_budget':False,'R53_status':'superseded_no_resume_GPU_released',
    'R51_awaiting_approval':False,'R51_next_action':'CPU_gamma_LOSO_then_wait_for_low_load_noTCP_inference',
    'new_noTCP_run_authorized_when_estimate_below8h':True})
save_json(root/'analysis/round3_state.json',state)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
