#!/usr/bin/env python3
"""Check restored I/O and recompute saved metrics without running new experiments."""
import csv
import importlib.metadata
import json
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'yestrack_diagnosis_20261101'
A = TASK / 'analysis'
sys.path.insert(0, str(A))
from common import combine_hota, hota_rows, names
from r58_metrics import Data, ece


def main():
    c = json.loads((A / 'config.json').read_text())
    detail = A / 'runs/R14/recommended/tracker/default_t0p60/pedestrian_detailed.csv'
    metric, rows = hota_rows(detail, c)
    scores = combine_hota(metric, rows)
    assert len(rows) == len(names(c)) == 862
    assert abs(scores['HOTA'] - 40.427) < .0006
    baseline = {'expressions': len(rows), **scores}
    image_root = Path(c['image_root'])
    expr_root = Path(c['expression_root'])
    sequences = c['train_sequences'] + c['val_sequences']
    data = {}
    for seq in sorted(sequences):
        frames = sorted((image_root / seq).glob('*.png'))
        expressions = list((expr_root / seq).glob('*.json'))
        assert frames and expressions, seq
        with Image.open(frames[0]) as image:
            image.load()
            dimensions = list(image.size)
        data[seq] = {'image_files': len(frames), 'expressions': len(expressions),
                     'first_image_size': dimensions}
    assert sum(data[s]['expressions'] for s in c['val_sequences']) == 862
    weights = {}
    for name, path in [('base', Path(c['base_model']) / 'model.safetensors'),
                       ('V2_LoRA', Path(c['official_v2_adapter']) / 'adapter_model.safetensors')]:
        with path.open('rb') as f:
            length = struct.unpack('<Q', f.read(8))[0]
            header = json.loads(f.read(length))
        weights[name] = {'path': str(path), 'bytes': path.stat().st_size,
                         'tensors': len(header) - int('__metadata__' in header)}
    recovered = []
    integrity = json.loads((A / 'runs/R58_calibration/final_integrity.json').read_text())
    for model in integrity['models']:
        key = model['model'].replace('/', '__')
        d = Data(key, require_full=True)
        p, temperatures = d.oof()
        attrs = d.plan['samples']['main_attributes']
        macro = float(np.mean([ece(p[d.attr == attr], d.y[d.attr == attr]) for attr in attrs]))
        saved = json.loads((A / 'runs/R58_calibration/metrics' / key / 'P1_P2.json').read_text())
        expected = saved['global_T_LOSO']['main_attribute_macro']['ECE_mass15']
        assert abs(macro - expected) < 1e-6, (key, macro, expected)
        requests = sum(len(v) for v in d.pred.values())
        assert requests == 12864 and len(d.samples) == 2144
        recovered.append({'model': model['model'], 'requests': requests,
                          'binary_rows': d.n, 'global_T_macro_ECE': macro,
                          'saved_macro_ECE': expected})
    links = json.loads((ROOT / 'recovery/storage_links.json').read_text())
    broken = [r for r in links if not Path(r['local']).exists()]
    assert not broken, broken[:5]
    packages = ['torch', 'torchvision', 'transformers', 'peft', 'numpy', 'scipy',
                'pandas', 'matplotlib', 'pillow', 'pycocotools']
    result = {'status': 'PASS', 'baseline_reaggregated_with_official_TrackEval': baseline,
              'NAS_dataset_inventory': data, 'NAS_weight_headers': weights,
              'R58_recomputed_from_raw_probabilities': recovered,
              'R58_total_requests': sum(r['requests'] for r in recovered),
              'storage_links_checked': len(links), 'broken_storage_links': broken,
              'environment': {'python': sys.version, 'executable': sys.executable,
                              'packages': {k: importlib.metadata.version(k) for k in packages}},
              'limitations': ['R58 GPU environment is not restored; its six-model CPU cache analysis is verified.',
                             'Five public R58 model weight sets were deferred in the backup; only the Qwen2 baseline is available.',
                             'Large NAS datasets/checkpoints were inventoried and sampled, not fully rehashed.']}
    (ROOT / 'recovery/verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'baseline': baseline,
                      'R58_models': len(recovered), 'R58_requests': result['R58_total_requests'],
                      'storage_links': len(links), 'dataset_images': sum(v['image_files'] for v in data.values()),
                      'dataset_expressions': sum(v['expressions'] for v in data.values())}, indent=2), flush=True)


if __name__ == '__main__':
    main()
