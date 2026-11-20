#!/usr/bin/env python3
"""Download exact published R58 checkpoints; no model load or inference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,'/home/user/.cache/r58_calibration/extra310')
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import snapshot_download

TASK = Path(__file__).resolve().parents[1]
OUT = TASK / 'analysis/runs/R58_calibration'
CACHE = Path('/home/user/.cache/r58_calibration/models')


def download(info):
    repo = info['repo']
    key = repo.replace('/', '__')
    dest = CACHE / key / info['revision']
    start = time.monotonic()
    print(json.dumps({'event':'download_start','repo':repo,'revision':info['revision']}),flush=True)
    try:
        path = snapshot_download(repo, revision=info['revision'], local_dir=dest, max_workers=4)
        target = OUT / 'models' / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(path, target_is_directory=True)
        result = {'repo': repo, 'revision': info['revision'], 'path': path,
                  'status': 'downloaded', 'seconds': time.monotonic() - start}
    except Exception as e:
        result = {'repo': repo, 'revision': info['revision'], 'status': 'download_failed',
                  'exception': repr(e), 'seconds': time.monotonic() - start}
    p = OUT / 'download_status' / (key + '.json')
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--repos', nargs='*')
    args = ap.parse_args()
    infos = json.loads((OUT / 'model_inventory.json').read_text())
    repos = args.repos or ['vllm-sr/d3-mini', 'vllm-sr/d3-flash', 'OmniJev/OneJev1.5-9B',
                           'Qwen/Qwen3-VL-2B-Instruct', 'Qwen/Qwen3-VL-8B-Instruct', 'vllm-sr/d3-turbo']
    selected = [next(x for x in infos if x['repo'] == r) for r in repos]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(download, selected))
    raise SystemExit(int(any(x['status'] != 'downloaded' for x in results)))
