#!/usr/bin/env python3
"""R58 CPU-only discovery: pinned official cards/code and train-only text inventory."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/runs/R58_calibration'
C = json.loads((ROOT / 'analysis/config.json').read_text())
MODELS = ['vllm-sr/d3-mini', 'vllm-sr/d3-flash', 'vllm-sr/d3-turbo',
          'OmniJev/OneJev1.5-9B', 'perplexity-ai/pplx-decider-v1.2',
          'Qwen/Qwen3-VL-2B-Instruct', 'Qwen/Qwen3-VL-8B-Instruct']


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def fetch(url):
    with urllib.request.urlopen(url, timeout=90) as r:
        return r.read()


def model(repo):
    dest = OUT / 'model_cards' / repo.replace('/', '__')
    dest.mkdir(parents=True, exist_ok=True)
    try:
        info = (json.loads((dest / 'api.json').read_text()) if (dest / 'api.json').exists()
                else json.loads(fetch(f'https://huggingface.co/api/models/{repo}')))
        write(dest / 'api.json', info)
        rev = info['sha']
        files = [x['rfilename'] for x in info.get('siblings', [])]
        selected = [s for s in files if (s.endswith(('.py', '.md', '.json', '.toml')) or 'requirements' in s)
                    and not s.endswith(('tokenizer.json', 'vocab.json', 'model.safetensors.index.json'))]
        for name in selected:
            p = dest / name
            if p.exists():
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(fetch(f'https://huggingface.co/{repo}/resolve/{rev}/{name}'))
        row = {'repo': repo, 'revision': rev, 'files': files, 'metadata_downloaded': selected,
               'status': 'official_metadata_retrieved'}
    except Exception as e:
        row = {'repo': repo, 'status': 'metadata_failed', 'reason': repr(e)}
    write(dest / 'discovery.json', row)
    print(json.dumps({k: v for k, v in row.items() if k not in ['files', 'metadata_downloaded']}), flush=True)
    return row


def text_inventory():
    rows = []
    for seq in C['train_sequences']:
        for p in sorted((Path(C['expression_root']) / seq).glob('*.json')):
            d = json.loads(p.read_text())
            rows.append({'sequence': seq, 'file': p.name, 'sentence': d.get('sentence', ''),
                         'raw_sentence': d.get('raw_sentence', d.get('sentence', '')),
                         'frames': len(d['label']),
                         'ids': sorted({int(i) for ids in d['label'].values() for i in ids})})
    write(OUT / 'train_expression_inventory.json', rows)
    unique = {}
    for r in rows:
        raw = r['raw_sentence'].lower().strip()
        u = unique.setdefault(raw, {'raw_sentence': raw, 'sequences': set(), 'count': 0})
        u['count'] += 1
        u['sequences'].add(r['sequence'])
    us = [{**r, 'sequences': sorted(r['sequences'])} for r in unique.values()]
    write(OUT / 'train_raw_sentences.json', sorted(us, key=lambda x: x['raw_sentence']))
    (OUT / 'train_raw_sentences.txt').write_text('\n'.join(sorted(unique)) + '\n')
    print(json.dumps({'train_expressions': len(rows), 'unique_raw_sentences': len(unique),
                      'sequences': dict(Counter(r['sequence'] for r in rows))}), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['models', 'texts'])
    ap.add_argument('--repo', nargs='*')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == 'models':
        with ThreadPoolExecutor(max_workers=7) as pool:
            res = list(pool.map(model, args.repo or MODELS))
        if args.repo:
            previous = json.loads((OUT / 'model_inventory.json').read_text())
            replacements = {r['repo']: r for r in res}
            res = [replacements.get(r['repo'], r) for r in previous]
            res.extend(r for key, r in replacements.items() if key not in {x['repo'] for x in previous})
        write(OUT / 'model_inventory.json', res)
    else:
        text_inventory()
