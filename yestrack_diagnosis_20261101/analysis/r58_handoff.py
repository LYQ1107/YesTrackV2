#!/usr/bin/env python3
"""Stop this R58 owner tree for a recorded, cache-preserving GPU handoff."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import time

TASK = Path(__file__).resolve().parents[1]
OUT = TASK / 'analysis/runs/R58_calibration'


def exited(pid):
    p = Path('/proc') / str(pid) / 'stat'
    return not p.exists() or p.read_text().split()[2] == 'Z'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pipeline', type=int, required=True)
    ap.add_argument('--owner', type=int, required=True)
    ap.add_argument('--worker', type=int, required=True)
    args = ap.parse_args()
    jobs = {}
    for pid, script in [(args.pipeline, 'r58_pipeline.py'),
                        (args.owner, 'r58_owner.py'), (args.worker, 'r58_gpu.py')]:
        p = Path('/proc') / str(pid)
        command = (p / 'cmdline').read_bytes().split(b'\0')
        assert (p / 'cwd').resolve() == TASK and ('analysis/' + script).encode() in command
        jobs[script] = {'pid': pid, 'command': [x.decode() for x in command if x]}
    assert b'Qwen/Qwen3-VL-8B-Instruct' in (Path('/proc') / str(args.worker) / 'cmdline').read_bytes().split(b'\0')
    ticks = int((Path('/proc') / str(args.worker) / 'stat').read_text().split()[21])
    elapsed = float(Path('/proc/uptime').read_text().split()[0]) - ticks / os.sysconf('SC_CLK_TCK')
    record = {'time_UTC': datetime.now(timezone.utc).isoformat(), 'seed': 2025,
              'reason': 'GPU6 shared compute; observed 25.4 s/request versus pilot about 7; resume unchanged unfinished requests on lower-utilization allowed GPU',
              'jobs': jobs, 'interrupted_worker_elapsed_seconds': elapsed,
              'prior_launch': json.loads((OUT / 'full_pipeline_launch.json').read_text()),
              'inference_definitions_changed': False, 'weights_changed': False,
              'cache_rows_deleted_or_rewritten': 0}
    destination = OUT / 'resource_handoff_Qwen8.json'
    destination.write_text(json.dumps(record, indent=2) + '\n')
    # Freeze the two owners so neither can advance while the worker exits.
    for pid in [args.pipeline, args.owner]:
        os.kill(pid, signal.SIGSTOP)
    os.kill(args.worker, signal.SIGINT)
    deadline = time.monotonic() + 120
    while not exited(args.worker) and time.monotonic() < deadline:
        time.sleep(1)
    assert exited(args.worker), 'R58 worker has not exited; do not start a replacement'
    for pid in [args.owner, args.pipeline]:
        os.kill(pid, signal.SIGTERM)
        os.kill(pid, signal.SIGCONT)
    while not all(exited(pid) for pid in [args.owner, args.pipeline]):
        time.sleep(1)
    folder = OUT / 'predictions/Qwen__Qwen3-VL-8B-Instruct'
    counts = {}
    for path in folder.glob('*.jsonl'):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == len({r['sample_id'] for r in rows})
        assert all(r['seed'] == 2025 and r['checkpoint_repo'] == 'Qwen/Qwen3-VL-8B-Instruct' for r in rows)
        counts[path.stem] = len(rows)
    record.update(status='stopped_for_cache_resume', cached_requests=counts,
                  previous_processes_exited=True)
    destination.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
