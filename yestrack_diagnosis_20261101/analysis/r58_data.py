#!/usr/bin/env python3
"""R58 train-only labels, single-attribute text audit and deterministic sampling."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/runs/R58_calibration'
C = json.loads((ROOT / 'analysis/config.json').read_text())
SEED = 2025
KITTI_ZIP = Path('/data2/user/reference_envs/kitti_tracking_labels_20261001/data_tracking_label_2.zip')
COLOURS = ['black', 'white', 'silver', 'blue', 'red', 'yellow', 'green']
ATTRIBUTES = ['category', 'vehicle_colour', 'gender', 'upper_colour', 'upper_type',
              'lower_type', 'bag', 'bicycle']
FINE_CLASSES = ['Car', 'Van', 'Truck', 'Pedestrian', 'Person_sitting', 'Cyclist', 'Tram', 'Misc']


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def csvwrite(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def norm(t):
    t = t.lower().replace('-', ' ')
    for a, b in [('pedestrain', 'pedestrian'), ('womem', 'women'), ('woth', 'with'),
                 ('thatse', 'whose'), ('t shirt', 'tshirt')]:
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip().strip('.')


def parse_single(raw):
    """Reviewed semantic templates; no compound-expression negatives are produced."""
    t = norm(raw)
    if re.search(r'\b(left|right|ahead|front|camera|ours|ego|direction|walking|standing|moving|'
                 r'parked|parking|braking|turning|faster|slower|back|bald|and)\b', t):
        return None
    if t in ['autos', 'cars']:
        return ('base_category', 'vehicle', 'vehicle', '')
    if t in ['people', 'persons', 'pedestrian', 'pedestrians']:
        return ('base_category', 'person', 'person', '')
    if t in ['men', 'males', 'women', 'females']:
        return ('gender', 'male' if t in ['men', 'males'] else 'female', 'person', '')
    m = re.fullmatch(r'(black|white|silver|blue|red|yellow|green) (autos|cars)', t)
    if not m:
        m = re.fullmatch(r'(?:autos|cars) in (black|white|silver|blue|red|yellow|green)', t)
    if m:
        return ('vehicle_colour', m[1], 'vehicle', '')
    # Light colour is not a mutually exclusive colour value: retain in text audit, exclude from labels.
    m = re.fullmatch(r'(people|persons|pedestrian|pedestrians|men|males|women|females) (.+)', t)
    if not m:
        return None
    subject, predicate = m.groups()
    gender = 'male' if subject in ['men', 'males'] else 'female' if subject in ['women', 'females'] else ''
    domain = 'person' + (':' + gender if gender else '')
    if predicate in ['with a bag', 'carrying a bag', 'holding a bag']:
        return ('bag', 'yes', domain, '')
    if predicate == 'with bicycle':
        return ('bicycle', 'yes', domain, '')
    m = re.fullmatch(r'(?:wearing|that are wearing|who are wearing) (jeans|pants|tshirt|coat)', predicate)
    if m:
        v = m[1]
        return ('lower_type' if v in ['jeans', 'pants'] else 'upper_type', v, domain, '')
    m = re.fullmatch(r'(?:wearing (?:a )?(black|white|green|red) (tshirt|coat)|'
                     r'whose (tshirt|coat) is (black|white|green|red))', predicate)
    if m:
        colour = m[1] or m[4]
        garment = m[2] or m[3]
        # Colour is conditional on independently labelled garment type. No clothing-type negatives from this text.
        return ('upper_colour', colour, domain, garment)
    return None


def ious(a, b):
    lo = np.maximum(a[:, None, :2], b[None, :, :2])
    hi = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.maximum(hi - lo, 0).prod(-1)
    aa = np.maximum(a[:, 2:] - a[:, :2], 0).prod(-1)
    bb = np.maximum(b[:, 2:] - b[:, :2], 0).prod(-1)
    return inter / np.maximum(aa[:, None] + bb[None, :] - inter, 1e-12)


def original_labels():
    by_seq = {}
    with zipfile.ZipFile(KITTI_ZIP) as z:
        for seq in C['train_sequences']:
            frames = defaultdict(list)
            for line in z.read(f'training/label_02/{seq}.txt').decode().splitlines():
                a = line.split()
                if int(a[1]) < 0 or a[2] == 'DontCare':
                    continue
                frames[int(a[0])].append({'id': int(a[1]), 'category': a[2],
                    'truncation': float(a[3]), 'occlusion': int(a[4]),
                    'box': list(map(float, a[6:10]))})
            by_seq[seq] = frames
    return by_seq


def align_boxes(original):
    frames, track_rows = {}, defaultdict(list)
    summary = []
    for seq in C['train_sequences']:
        n = matched = 0
        overlaps = []
        for p in sorted((Path(C['labels_root']) / seq).glob('*.txt')):
            if not p.read_text().strip():
                continue
            fr = int(p.stem)
            image = Path(C['image_root']) / seq / f'{fr:06d}.png'
            with Image.open(image) as im:
                width, height = im.size
            a = np.loadtxt(p, ndmin=2)
            xywh = a[:, 2:6] * [width, height, width, height]
            # Official data/refer_kitti_mot.py:200-210: normalized x,y are TOP LEFT.
            xyxy = xywh.copy()
            xyxy[:, 2:] += xyxy[:, :2]
            b = original[seq].get(fr, [])
            mapping = {}
            if b:
                overlap = ious(xyxy, np.array([r['box'] for r in b]))
                ri, ci = linear_sum_assignment(-overlap)
                for i, j in zip(ri, ci):
                    if overlap[i, j] >= .5:
                        mapping[int(i)] = (b[j], float(overlap[i, j]))
            rows = {}
            for i, row in enumerate(a):
                tid = int(row[1])
                source, overlap = mapping.get(i, ({}, None))
                r = {'id': f'{seq}:{tid}:{fr}', 'sequence': seq, 'track': f'{seq}:{tid}',
                     'track_id': tid, 'frame': fr, 'image': str(image), 'image_width': width,
                     'image_height': height, 'box_xywh': xywh[i].tolist(),
                     'category': source.get('category'), 'original_id': source.get('id'),
                     'truncation': source.get('truncation'), 'occlusion': source.get('occlusion'),
                     'original_iou': overlap}
                rows[tid] = r
                track_rows[r['track']].append(r)
                n += 1
                if source:
                    matched += 1
                    overlaps.append(overlap)
            frames[(seq, fr)] = rows
        summary.append({'sequence': seq, 'v2_rows': n, 'original_matched': matched,
                        'unmatched': n - matched,
                        'median_iou': float(np.median(overlaps)) if overlaps else None})
    return frames, track_rows, summary


def annotate_expressions():
    inventory = json.loads((OUT / 'train_expression_inventory.json').read_text())
    reviewed = []
    eligible = []
    for r in inventory:
        raw = parse_single(r['raw_sentence'])
        # raw_sentence carries the source annotation meaning; paraphrases can omit qualifiers.
        parsed = raw
        q = {**r, 'single_attribute': parsed is not None,
             'attribute': parsed[0] if parsed else '', 'value': parsed[1] if parsed else '',
             'domain': parsed[2] if parsed else '', 'garment': parsed[3] if parsed else '',
             'semantic_review': 'Codex reviewed source-language templates, not an evaluated vision model',
             'note': 'source raw_sentence used; generated sentence is only an audit field'}
        reviewed.append(q)
        if parsed:
            d = json.loads((Path(C['expression_root']) / r['sequence'] / r['file']).read_text())
            eligible.append((q, {int(f): {int(t) for t in ids} for f, ids in d['label'].items()}))
    csvwrite(OUT / 'expression_labels.csv', [{k: v for k, v in r.items() if k != 'ids'} for r in reviewed])
    # Audit 50 positives in the single-attribute-expression extraction, not 50 frame labels.
    candidates = [r for r in reviewed if r['single_attribute']]
    rng = np.random.default_rng(SEED)
    selection = rng.choice(len(candidates), min(50, len(candidates)), replace=False)
    audit = [{**{k: v for k, v in candidates[i].items() if k != 'ids'}, 'human_correct': '',
              'human_notes': ''} for i in sorted(selection)]
    csvwrite(OUT / 'label_audit.csv', audit)
    return eligible, reviewed


def within_domain(row, domain, gender, garment='', upper=None, base_domains=None):
    category = row['category']
    key = (row['sequence'],row['track_id'],row['frame'])
    coarse = domain.split(':')[0]
    explicit = (base_domains or {}).get((row['sequence'],row['frame'],coarse))
    if domain.startswith('vehicle'):
        # "cars" is V2's expression class, not an automatic Truck/Tram negative.
        return row['track_id'] in explicit if explicit is not None else category == 'Car'
    if explicit is not None:
        person = row['track_id'] in explicit
    else:
        person = category in ['Pedestrian', 'Person_sitting', 'Cyclist']
    if not person:
        return False
    if ':' in domain:
        value = domain.split(':')[1]
        if gender.get((row['sequence'], row['track_id'], row['frame']), {}).get(value) != {1}:
            return False
    if garment and (upper or {}).get((row['sequence'], row['track_id'], row['frame']), {}).get(garment) != {1}:
        return False
    return True


def build_labels(frames, eligible):
    # Every expression has its own annotated-frame mask; missing frame keys never mean negative.
    labels = defaultdict(lambda: defaultdict(set))
    provenance = defaultdict(lambda: defaultdict(set))
    genders = defaultdict(lambda: defaultdict(set))
    upper = defaultdict(lambda: defaultdict(set))
    base_domains = defaultdict(set)
    for q, gt in eligible:
        if q['attribute'] == 'base_category':
            for fr, ids in gt.items():
                base_domains[(q['sequence'],fr,q['value'])].update(ids)
    values = defaultdict(set)
    unknown_negative_domain = Counter()
    # Gender-neutral expressions first, gender-restricted clothes next, garment-conditional colour last.
    order = sorted(eligible, key=lambda x: (bool(x[0]['garment']), ':' in x[0]['domain']))
    for q, gt in order:
        attr, value = q['attribute'], q['value']
        if attr == 'base_category':
            continue
        seq = q['sequence']
        values[(seq, attr, q['garment'])].add(value)
        if attr == 'upper_colour':
            value = q['garment'] + ':' + value
        for fr, ids in gt.items():
            for tid, row in frames.get((seq, fr), {}).items():
                # GT membership is sufficient for positives. Independent same-category confirmation
                # is needed for NEGATIVES only, exactly as specified by the user.
                positive = tid in ids
                if not positive and not within_domain(row, q['domain'], genders, q['garment'], upper, base_domains):
                    unknown_negative_domain[(attr, row['category'])] += 1
                    continue
                key = (seq, tid, fr)
                label = int(positive)
                labels[key][(attr, value)].add(label)
                provenance[key][(attr, value)].add(q['file'])
                if attr == 'gender':
                    genders[key][value].add(label)
                if attr == 'upper_type':
                    upper[key][value].add(label)
    # Static attributes: reject an entire track/attribute if any value changes truth across observed frames
    # or if two source single-attribute expressions disagree at the same frame.
    histories = defaultdict(set)
    for (seq, tid, fr), attrs in labels.items():
        for (attr, value), ys in attrs.items():
            histories[(seq, tid, attr, value)].update(ys)
    bad = {(seq, tid, attr) for (seq, tid, attr, value), ys in histories.items() if len(ys) > 1}
    # Category is direct from original KITTI; track-category ambiguity is excluded by the same rule.
    cat_hist = defaultdict(set)
    for (seq, fr), rows in frames.items():
        for tid, row in rows.items():
            if row['category'] in FINE_CLASSES:
                cat_hist[(seq, tid)].add(row['category'])
    for (seq, tid), cs in cat_hist.items():
        if len(cs) > 1:
            bad.add((seq, tid, 'category'))
    dataset = {}
    for (seq, fr), rows in frames.items():
        for tid, row in rows.items():
            attrs = []
            if row['category'] in FINE_CLASSES and (seq, tid, 'category') not in bad:
                attrs.extend({'attribute': 'category', 'value': v, 'y': int(row['category'] == v),
                              'sensitivity_two_values': True, 'source': 'KITTI original class via frame-wise Hungarian IoU >= 0.5'}
                             for v in FINE_CLASSES)
            for (attr, value), ys in labels.get((seq, tid, fr), {}).items():
                if (seq, tid, attr) in bad:
                    continue
                assert len(ys) == 1
                attrs.append({'attribute': attr, 'value': value, 'y': next(iter(ys)),
                              'sensitivity_two_values': len(values[(seq, attr, value.split(':')[0] if attr == 'upper_colour' else '')]) >= 2,
                              'source': sorted(provenance[(seq, tid, fr)][(attr, value)])})
            if attrs:
                dataset[row['id']] = {**row, 'labels': attrs}
    denominator = {a: {(seq, tid) for seq, tid, attr, value in histories if attr == a} for a in ATTRIBUTES}
    denominator['category'] = set(cat_hist)
    exclusions = []
    for attr in ATTRIBUTES:
        removed = {(seq, tid) for seq, tid, a in bad if a == attr}
        exclusions.append({'attribute': attr, 'tracks_before_filter': len(denominator[attr]),
                           'inconsistent_tracks': len(removed),
                           'excluded_fraction': len(removed) / max(1, len(denominator[attr]))})
    return dataset, exclusions, values, unknown_negative_domain, bad


def select_samples(dataset):
    tracks = defaultdict(list)
    for r in dataset.values():
        tracks[r['track']].append(r)
    samples = []
    for track, rows in sorted(tracks.items()):
        rows.sort(key=lambda x: x['frame'])
        # Earliest-first spacing, followed by an evenly spread subset of at most eight frames.
        spaced = []
        for r in rows:
            if not spaced or r['frame'] - spaced[-1]['frame'] >= 10:
                spaced.append(r)
        if len(spaced) > 8:
            spaced = [spaced[i] for i in np.linspace(0, len(spaced) - 1, 8).round().astype(int)]
        samples.extend(spaced)
    return samples


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    eligible, reviewed = annotate_expressions()
    frames, tracks, alignment = align_boxes(original_labels())
    dataset, exclusions, values, rejects, bad = build_labels(frames, eligible)
    samples = select_samples(dataset)
    write(OUT / 'samples_draft.json', samples)
    write(OUT / 'original_alignment.json', {'source_zip': str(KITTI_ZIP),
        'method': 'per-frame Hungarian maximum summed IoU, accept IoU >= 0.5; unmatched class/occlusion unknown',
        'sequences': alignment})
    write(OUT / 'static_inconsistency.json', exclusions)
    write(OUT / 'excluded_tracks.json', [{'sequence':s,'track_id':t,'attribute':a} for s,t,a in sorted(bad)])
    counts = []
    for attr in ATTRIBUTES:
        rs = [r for r in samples if any(x['attribute'] == attr for x in r['labels'])]
        obs = [(r, x) for r in rs for x in r['labels'] if x['attribute'] == attr]
        counts.append({'attribute': attr, 'labelled_images': len(rs), 'binary_labels': len(obs),
            'tracks': len({r['track'] for r in rs}), 'positive': sum(x['y'] for r, x in obs),
            'negative': sum(1 - x['y'] for r, x in obs), 'main_table': len(rs) >= 800,
            'sequences': dict(Counter(r['sequence'] for r in rs)),
            'values': sorted({x['value'] for r, x in obs})})
    stats = {'seed': SEED, 'split': 'V2 train only', 'sequences': C['train_sequences'],
        'expressions': len(reviewed), 'single_attribute_expressions': len(eligible),
        'sample_images': len(samples), 'tracks': len({r['track'] for r in samples}),
        'attributes': counts, 'static_exclusions': exclusions,
        'per_sequence_expression_value_coverage': [
            {'sequence': seq, 'attribute': attr, 'garment': garment, 'values': sorted(vs), 'at_least_two': len(vs) >= 2}
            for (seq, attr, garment), vs in sorted(values.items())],
        'unknown_negative_domains': [{'attribute': a, 'original_class': k, 'expression_rows': v}
            for (a, k), v in rejects.items()]}
    write(OUT / 'data_statistics_draft.json', stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
