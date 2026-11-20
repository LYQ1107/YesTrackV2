#!/usr/bin/env python3
"""Freeze R58, including exact prompts, samples and all analyses, before model inference."""
import argparse
from collections import Counter, defaultdict
import itertools
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from r58_data import ATTRIBUTES, COLOURS, FINE_CLASSES, C, OUT, ROOT, SEED, write, csvwrite


def choice(qid, attr, prompts, options, values=None):
    opts = []
    for key, labels in options:
        assert len(labels) == 3
        opts.append({'id': key, 'labels': labels})
    return {'id': qid, 'attribute': attr, 'type': 'choice', 'instructions': prompts,
            'options': opts, 'value_options': values or {k: [k] for k, v in options}}


def binary(qid, attr, prompts, value='yes'):
    return {'id': qid, 'attribute': attr, 'type': 'noul', 'instructions': prompts,
            'options': [{'id': 'no', 'labels': ['No'] * 3}, {'id': 'yes', 'labels': ['Yes'] * 3}],
            'value_options': {value: ['yes']}}


def question_bank():
    synonym_classes = [
        ('Car', ['car', 'passenger automobile', 'passenger car']),
        ('Van', ['van', 'delivery van', 'minivan']),
        ('Truck', ['truck', 'lorry', 'cargo truck']),
        ('Pedestrian', ['pedestrian', 'person on foot', 'walking or standing person']),
        ('Person_sitting', ['seated person', 'sitting person', 'person who is sitting']),
        ('Cyclist', ['cyclist', 'bicycle rider', 'person riding a bicycle']),
        ('Tram', ['tram', 'streetcar', 'tramcar']),
        ('Misc', ['miscellaneous object', 'other labelled object', 'miscellaneous road object']),
        ('other', ['other', 'another category', 'none of these categories'])]
    qs = [choice('category', 'category', [
        'What is the category of the target object?',
        'Select the object class that best describes the marked target.',
        'Which kind of road object is shown in the target crop?'], synonym_classes)]
    colour_labels = {
        'black': ['black', 'black coloured', 'a black shade'],
        'white': ['white', 'white coloured', 'a white shade'],
        'silver': ['silver or grey', 'silver grey', 'grey or metallic silver'],
        'blue': ['blue', 'blue coloured', 'a blue shade'],
        'red': ['red', 'red coloured', 'a red shade'],
        'yellow': ['yellow', 'yellow coloured', 'a yellow shade'],
        'green': ['green', 'green coloured', 'a green shade'],
        'other': ['other or not applicable', 'another colour or inapplicable', 'none of these or no such item']}
    qs.append(choice('vehicle_colour', 'vehicle_colour', [
        'What is the body colour of the target vehicle? Choose other if it is not a vehicle.',
        'Select the main paint colour of the marked vehicle, or other when inapplicable.',
        'Which colour best describes the target vehicle exterior? Use other for a non-vehicle.'],
        list(colour_labels.items())))
    qs.append(choice('gender', 'gender', [
        'What is the perceived gender of the target person? Choose other when not applicable or indeterminate.',
        'Does the marked person appear male or female? Use other if inapplicable or unclear.',
        'Select the apparent gender presentation of the target human, or other if unknown.'],
        [('male', ['male', 'man', 'masculine person']), ('female', ['female', 'woman', 'feminine person']),
         ('other', ['other or indeterminate', 'unclear or not applicable', 'unknown or non-human'])]))
    qs.append(choice('upper_type', 'upper_type', [
        'Which of these upper garments is the target person wearing? Both is allowed.',
        'Select the visible upper clothing of the marked person: T-shirt, coat, both, or other.',
        'Identify whether the target wears a T-shirt, a coat, both garments, or neither.'],
        [('tshirt', ['T-shirt only', 'tee shirt without a coat', 'only a T-shirt']),
         ('coat', ['coat only', 'coat without a T-shirt', 'only a coat']),
         ('both', ['both a T-shirt and a coat', 'both garments', 'T-shirt plus coat']),
         ('other', ['other or not applicable', 'neither garment or unclear', 'another outfit or no person'])],
        {'tshirt': ['tshirt', 'both'], 'coat': ['coat', 'both']}))
    for garment, name in [('tshirt', 'T-shirt'), ('coat', 'coat')]:
        qs.append(choice('upper_colour_' + garment, 'upper_colour', [
            f'What colour is the target person\'s {name}? Choose other if no {name} is worn.',
            f'Select the main colour of the marked person\'s {name}, or other when absent.',
            f'Which colour describes the {name} worn by the target? Use other if inapplicable.'],
            list(colour_labels.items()), {garment + ':' + v: [v] for v in COLOURS}))
    qs.append(choice('lower_type', 'lower_type', [
        'What lower clothing is the target person wearing? Jeans are a type of pants.',
        'Select the marked person\'s lower garment. Distinguish denim jeans from other trousers.',
        'Which option describes the target\'s bottom clothing? Non-denim pants exclude jeans.'],
        [('jeans', ['jeans', 'denim trousers', 'denim jeans']),
         ('pants', ['non-denim pants', 'other trousers', 'trousers other than jeans']),
         ('other', ['other or not applicable', 'another garment or no person', 'neither jeans nor trousers'])],
        {'jeans': ['jeans'], 'pants': ['jeans', 'pants']}))
    qs.append(binary('bag', 'bag', [
        'Is the target person carrying or holding a bag?',
        'Does the marked person have a bag with them?',
        'Is a bag being carried by the person in the crop?']))
    qs.append(binary('bicycle', 'bicycle', [
        'Is the target person with a bicycle, pushing or riding it?',
        'Does the marked person accompany a bicycle, including pushing or riding?',
        'Is the person in the crop together with a bicycle?']))
    events = {
        'car': ['category', 'Car', 'a car'], 'person': ['category', 'Pedestrian', 'a pedestrian'],
        'white': ['vehicle_colour', 'white', 'white in vehicle body colour'],
        'black': ['vehicle_colour', 'black', 'black in vehicle body colour'],
        'male': ['gender', 'male', 'male'], 'female': ['gender', 'female', 'female'],
        'jeans': ['lower_type', 'jeans', 'wearing jeans'], 'bag': ['bag', 'yes', 'carrying a bag']}
    conjunctions = [('car', 'white'), ('car', 'black'), ('person', 'male'), ('person', 'female'),
                    ('male', 'jeans'), ('female', 'bag'), ('person', 'male', 'jeans'),
                    ('person', 'female', 'bag')]
    for items in conjunctions:
        ident = 'and_' + '_'.join(items)
        text = ' AND '.join(events[e][2] for e in items)
        q = binary(ident, 'conjunction', [
            f'Does the target satisfy every part of this description: {text}?',
            f'Are all these properties true of the marked target simultaneously: {text}?',
            f'Is this complete conjunction true for the object in the crop: {text}?'])
        q['events'] = [[events[e][0], events[e][1]] for e in items]
        qs.append(q)
    return qs


def render_images(samples):
    sys.path.insert(0, str(ROOT / C['upstream']))
    from refer_llm.crop_utils import crop_with_margin
    folder = OUT / 'inputs'
    folder.mkdir(exist_ok=True)
    for r in samples:
        name = r['id'].replace(':', '_')
        crop_path = folder / (name + '_crop.jpg')
        frame_path = folder / (name + '_frame.jpg')
        if not (crop_path.exists() and frame_path.exists()):
            with Image.open(r['image']) as source:
                image = source.convert('RGB')
                crop = crop_with_margin(image, tuple(r['box_xywh']), margin_ratio=.2, min_side=8)
                assert crop is not None, r['id']
                crop.resize((320, 320), Image.Resampling.BILINEAR).save(crop_path, quality=95)
                draw = ImageDraw.Draw(image)
                x, y, w, h = r['box_xywh']
                draw.rectangle((x, y, x + w, y + h), outline=(255, 0, 0), width=3)
                image.thumbnail((640, 640), Image.Resampling.LANCZOS)
                image.save(frame_path, quality=95)
        x,y,w,h = r['box_xywh']
        W, H = r['image_width'], r['image_height']
        r['input_images'] = [str(crop_path), str(frame_path)]
        r['state'] = ('Image 1 is the target crop. Image 2 is the full-frame thumbnail; the red box marks the same target. '
                      f'Target normalized top-left x={x/W:.6f}, y={y/H:.6f}, width={w/W:.6f}, height={h/H:.6f}. '
                      'Answer all questions about this same target. Choose other for an inapplicable Choice question, '
                      'and No for an inapplicable Yes/No question.')


def pilot_ids(samples):
    rng = np.random.default_rng(SEED)
    by_seq = defaultdict(list)
    for r in samples:
        by_seq[r['sequence']].append(r['id'])
    for s in by_seq:
        rng.shuffle(by_seq[s])
    chosen = []
    while len(chosen) < 200:
        for s in C['train_sequences']:
            if by_seq[s] and len(chosen) < 200:
                chosen.append(by_seq[s].pop())
    return chosen


def label_noise_images(samples):
    rng = np.random.default_rng(SEED)
    rows, quotas = [], []
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
    for attr in ATTRIBUTES:
        for y in [0, 1]:
            eligible = [(r, lab) for r in samples for lab in r['labels']
                        if lab['attribute'] == attr and lab['y'] == y]
            selected = rng.choice(len(eligible), min(50, len(eligible)), replace=False)
            quotas.append({'attribute': attr, 'y': y, 'available': len(eligible), 'exported': len(selected)})
            for j, index in enumerate(selected):
                r, lab = eligible[index]
                path = OUT / 'label_noise_audit' / attr / f'{y}_{j:03d}_{r["id"].replace(":", "_")}.jpg'
                path.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(r['image']) as im:
                    full = im.convert('RGB')
                canvas = Image.new('RGB', (full.width, full.height + 64), 'white')
                canvas.paste(full, (0, 64))
                d = ImageDraw.Draw(canvas)
                x, yy, w, h = r['box_xywh']
                d.rectangle((x, yy + 64, x + w, yy + h + 64), outline='red', width=3)
                d.text((8, 4), f'{attr} = {lab["value"]}; annotation y={y}; {r["id"]}', fill='black', font=font)
                d.text((8, 30), 'Human review: does the marked target satisfy the attribute?', fill='black', font=font)
                canvas.save(path, quality=92)
                rows.append({'attribute': attr, 'value': lab['value'], 'y': y, 'sample_id': r['id'],
                             'track': r['track'], 'image': str(path), 'human_y': '', 'human_notes': ''})
    csvwrite(OUT / 'label_noise_audit.csv', rows)
    write(OUT / 'label_noise_audit' / 'quotas.json', quotas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user-amendment', action='store_true')
    ap.add_argument('--reuse-prepared-inputs', action='store_true')
    ap.add_argument('--implementation-fix-before-inference', action='store_true')
    args = ap.parse_args()
    target = ROOT / 'analysis/plans/r58.json'
    if target.exists():
        if not (args.user_amendment or args.implementation_fix_before_inference):
            raise RuntimeError('R58 is already frozen; do not overwrite its definitions.')
        assert not list((OUT / 'predictions').glob('**/*.jsonl')), 'Model inference already started'
        assert not json.loads((OUT / 'protocol_status.json').read_text())['inference_started']
        old = OUT / 'protocol_revisions' / ('before_positive_domain_implementation_fix.json'
            if args.implementation_fix_before_inference else 'before_user_binary_ECE_amendment.json')
        old.parent.mkdir(exist_ok=True)
        if old.exists():
            raise RuntimeError('Do not silently repeat a protocol amendment')
        target.rename(old)
    samples = json.loads((OUT / ('samples.json' if args.reuse_prepared_inputs else 'samples_draft.json')).read_text())
    qs = question_bank()
    rng = np.random.default_rng(SEED)
    for q in qs:
        n = len(q['options'])
        base = list(range(n))
        orders = [base]
        if q['type'] == 'choice':
            while len(orders) < 3:
                order = rng.permutation(n).tolist()
                if order not in orders:
                    orders.append(order)
        q['orders'] = orders
    stats = json.loads((OUT / 'data_statistics_draft.json').read_text())
    # No model-dependent sampling, questions or eligibility changes after this point.
    if not args.reuse_prepared_inputs:
        render_images(samples)
        label_noise_images(samples)
    write(OUT / 'samples.json', samples)
    write(OUT / 'questions.json', qs)
    write(OUT / 'data_statistics.json', stats)
    model_info = json.loads((OUT / 'model_inventory.json').read_text())
    models = []
    for info in model_info:
        if info['repo'].endswith(('-FP8', '-INT4')):
            continue
        assert info['status'] == 'official_metadata_retrieved', info
        repo = info['repo']
        models.append({'repo': repo, 'revision': info['revision'],
            'role': 'control' if repo.startswith('Qwen/') else 'decision',
            'weights': 'published unmodified base checkpoint; no V2 LoRA or local training',
            'dtype': 'BF16 backbone; official head dtype',
            'official_card': f'https://huggingface.co/{repo}/blob/{info["revision"]}/README.md',
            'backend': 'official AutoModel.system_one' if repo.startswith('vllm-sr/') else
                       'official qev MMDecisionEngine.decide' if repo.startswith('OmniJev/') else
                       'official pplx_decider.Decider.logits, fast=False' if repo.startswith('perplexity') else
                       'official Qwen3VLForConditionalGeneration + AutoProcessor, conditional option-string log likelihood',
            'load_failure': 'record exact exception and skip; no substitution; full findings must state missing model',
            'public_temperature': 1.3823494677922652 if repo.startswith('perplexity') else 1.0})
        if repo == 'vllm-sr/d3-turbo':
            models[-1]['memory_fallbacks'] = [
                {'repo': x['repo'], 'revision': x['revision'],
                 'backend': 'official d3q.load.load_d3(...,device=cuda:0)',
                 'condition': 'BF16 OOM only; FP8 requires compute capability>=8.9; A800 sm80 uses INT4',
                 'report': 'label precision and exact checkpoint, not an unlabelled BF16 result'}
                for x in model_info if x['repo'].endswith(('-FP8', '-INT4'))]
    plan = {
        'run': 'R58', 'date_asia_shanghai': '2026-11-04', 'seed': SEED,
        'status': 'FROZEN_BEFORE_ANY_MODEL_INFERENCE',
        'user_amendment': 'binary one-vs-rest expression labels; static exclusions; image audits; >=2-value sensitivity; equal-mass binary ECE primary and equal-width cross-check; conflicting binning judgments partial; Brier decomposition and NLL diagnostic only',
        'outputs': str(OUT), 'split': 'V2 train only', 'sequences': C['train_sequences'],
        'samples': {'manifest': str(OUT / 'samples.json'), 'images': len(samples),
                    'tracks': stats['tracks'], 'max_frames_per_track': 8, 'minimum_frame_gap': 10,
                    'algorithm': 'earliest greedy >=10-frame spacing, evenly spaced rounded linspace subset if >8; no oversampling',
                    'main_attribute_minimum_images': 800,
                    'main_attributes': [a['attribute'] for a in stats['attributes'] if a['main_table']],
                    'small_attributes': 'retain all in a separate exploratory table; never pad/repeat to reach 800'},
        'labels': {'source': 'source raw_sentence templates reviewed by Codex; generated paraphrase is not the annotation meaning',
            'original_kitti': str(Path('/data2/user/reference_envs/kitti_tracking_labels_20261001/data_tracking_label_2.zip')),
            'matching': 'frame-wise Hungarian max summed IoU >=0.5, V2 top-left normalized xywh; unmatched original category/occlusion/truncation unknown',
            'positive': 'ID in a pure single-attribute expression GT on that explicitly annotated frame',
            'negative': 'visible same-category ID outside that expression GT, only at its explicitly annotated frames',
            'negative_category': 'same source class via independent pure cars/people expression GT when available; otherwise original KITTI Car for cars, original human classes for people; never turn Truck/Tram into car-colour negatives solely by grouping vehicles',
            'male_female_subjects': 'men/women + one clothing attribute yields all its GT positives; only negatives require independently known same gender',
            'upper_colour': 'garment-specific: all its GT positives retained; only negatives require independently known garment type; no generic-upper-colour inference from a black T-shirt',
            'nonexclusive_values': 'pants probability is marginal jeans + other pants; upper type permits both coat and T-shirt',
            'light_colour': 'not mapped to a unique hue; excluded from hue ground truth before results',
            'bicycle': 'with-bicycle expression is a proxy for pushing/riding together; cannot distinguish the two actions',
            'static_filter': 'if any value of a track/attribute has both 0 and 1 across source expressions/annotated visible frames, exclude whole track/attribute; no majority vote',
            'sensitivity': 'same video and same attribute question/garment has >=2 expression values; category uses original multiclass labels',
            'audit': {'expression_csv': str(OUT / 'label_audit.csv'), 'expression_n': 50,
                      'noise_csv': str(OUT / 'label_noise_audit.csv'), 'noise_each_attribute_each_sign': 50,
                      'shortage': 'export all available without duplication and report quotas',
                      'consensus_disagreement': 'all available completed decision models AND Qwen controls on the identical binary row predict the opposite at p>=0.5; reference noise upper bound requested by user, not a guaranteed bound; incomplete models explicitly listed'}},
        'inputs': {'crop': 'official crop_utils.crop_with_margin margin_ratio=.2,min_side=8; resize320x320 BILINEAR',
                   'frame': 'original full frame red3px target box, thumbnail max640 LANCZOS',
                   'text': 'normalized top-left x,y,width,height, six decimals; no ground-truth labels',
                   'all_questions': 'identical full question bank for every sample, irrespective of category or known labels, to prevent question selection leaking category',
                   'crop_ablation': 'same crop and coordinates, remove second image and its reference from state'},
        'questions': {'manifest': str(OUT / 'questions.json'), 'bank': qs,
                      'settings': [{'id': 'main', 'wording': 0, 'permutation': 0, 'images': 'crop+frame'},
                                   {'id': 'wording_1', 'wording': 1, 'permutation': 0, 'images': 'crop+frame'},
                                   {'id': 'wording_2', 'wording': 2, 'permutation': 0, 'images': 'crop+frame'},
                                   {'id': 'order_1', 'wording': 0, 'permutation': 1, 'images': 'crop+frame'},
                                   {'id': 'order_2', 'wording': 0, 'permutation': 2, 'images': 'crop+frame'},
                                   {'id': 'crop_only', 'wording': 0, 'permutation': 0, 'images': 'crop'}],
                      'other': 'Choice retains an other option to normalize its distribution, but no other ground-truth label or metric is derived'},
        'models': models,
        'onejev_code': {'repo': 'https://github.com/OmniJev/OneJev', 'revision': '2470c7595688c6a402560cf18b4753feb1fe290a',
                        'path': '/data2/user/LocateMOT_GroundJEV/external/OneJev', 'fork_mode': 'auto',
                        'debias': 1, 'checks': 'official synthetic fork self-check unchanged at tolerance .05'},
        'readout': {'decision': 'official unmodified inference; keep complete per-question option distribution in canonical semantic order',
                    'qwen': 'one shared prompt containing every question; for each question independently condition assistant on QID: and score every full visible option string token-by-token; sum conditional log probabilities then softmax, never supply labels/other answers',
                    'qwen_cache': 'optional shared-prefix KV cache; first pilot sample compare cached scoring to fresh full scoring for all options, max probability error <=0.005, otherwise use fresh reference; no post-result sampling changes',
                    'marginal': 'sum frozen value_options on the full normalized Choice distribution; Yes/No use P(Yes)',
                    'raw_probability': 'pre-extra-calibration official output; add a separate T=1 readout row for checkpoints with a saved non-unit temperature; LOSO global T relative to raw readout',
                    'epsilon_for_log': 1e-12},
        'metrics': {'unit': 'binary value-specific propositions, all P1-P6',
                    'aggregate': 'primary macro mean of per-attribute binary ECE over main-table attributes (>=800 images); also all-attribute macro and pooled binary propositions, explicitly separate',
                    'metrics': ['accuracy', 'macro_F1_binary', 'binary_NLL', 'Brier', 'ECE_width15', 'ECE_mass15', 'AUROC_when_two_classes'],
                    'ece': 'bin P(value) against binary truth, not top-label confidence; fixed equal-width15 and stable sorted equal-mass np.array_split15, empty bins ignored',
                    'Brier_decomposition': 'primary equal-mass15 bins: reliability=sum n/N*(mean(p)-mean(y))^2; resolution=sum n/N*(mean(y)-globalmean(y))^2; uncertainty=globalmean(y)*(1-globalmean(y)); report unbinned Brier and discretization residual; equal-width cross-check; diagnostic only',
                    'bootstrap': {'clusters': 'sequence:track_id', 'repetitions': 1000, 'ci': 'percentile95',
                                  'sampling': 'sample tracks with replacement within each train sequence; all their rows retained',
                                  'models_comparison': 'paired identical track resamples on common observed rows'},
                    'noise_floor': {'draws': 1000, 'labels': 'independent Bernoulli draws from each evaluated probability at identical N and binning',
                                    'report': 'mean and percentile95 interval alongside every ECE, including subgroups/conjunctions/K'},
                    'reliability': 'plot empirical positive rate vs mean P(value), histogram, track-bootstrap95 intervals'},
        'P2': {'folds': 'leave one of the 17 train sequences out; zero evaluation rows reported empty',
                'parameters': 'one scalar global logT per model/fold on all known training-fold atomic binary rows',
                'objective': 'pooled binary NLL of marginal probabilities after softmax(log_option_probability/T)',
                'bounds_T': [.05, 50.0], 'optimizer': 'scipy bounded minimize_scalar on logT, xatol1e-6',
                'secondary': 'one T per attribute and fold; training-fold attributes with no rows stay unestimable',
                'application': 'same global T to every wording/order/crop/direct conjunction; never fit on held-out sequence'},
        'P3': {'height_pixels': ['<40', '40<=h<=100', '>100'], 'occlusion': [0, 1, 2, 3],
                'truncation': ['0', '(0,0.5]', '>0.5'], 'category': FINE_CLASSES,
                'sequence': C['train_sequences'], 'unknown': 'separate unknown group; do not impute'},
        'P4': {'JS': 'mean of three pairwise natural-log JS over full canonical question distributions; also binary-event JS',
                'flip': 'mean of three pairwise argmax flip rates among wordings, with worst pair also reported',
                'order_flip': 'canonical vs each of two permuted orders, mean and worst, canonical semantic option mapping',
                'eligibility': 'atomic questions with at least one known event on that sample; identical cases across models'},
        'P5': {'conjunctions': [q for q in qs if q['attribute'] == 'conjunction'],
                'eligibility': 'all constituent binary labels known on same sample; include true and false, no model-based selection or balancing',
                'product': 'multiply constituent OOF global-T marginal probabilities',
                'direct': 'same model direct conjunction Noul with same OOF global T and identical image/prompt context',
                'report': ['ECE_mass15', 'ECE_width15', 'AUROC', 'binary_NLL_diagnostic_only', 'pairwise correctness Pearson/phi correlation'],
                'no_case': 'empty or one-class AUROC explicitly unavailable, not zero or silently omitted'},
        'P6': {'K': [1, 2, 4, 8], 'attributes': ATTRIBUTES,
                'unit': 'same track + same binary attribute value, truth constant after static consistency filtering',
                'frames': 'earliest K sampled frames with known label; compare each K to K=1 on the same eligible tracks; also common K=8 cohort',
                'input_probability': 'main setting OOF globally scaled probability',
                'fixed_rules': ['sigmoid(sum(logit(p)))', 'sigmoid(mean(logit(p)))'],
                'learned_rule': 'sigmoid(alpha*sum(logit(p)))',
                'alpha': {'parameters': 1, 'bounds': [0.0, 4.0], 'objective': 'binary NLL pooled over attributes and K=1,2,4,8 in training sequences',
                          'leakage_control': 'nested inner sequence-LOSO T within outer training sequences; no held-out labels in alpha or temperature'},
                'report': ['accuracy', 'ECE_width15', 'ECE_mass15', 'eligible_tracks', 'eligible_events']},
        'decision_utility': {'threshold_fixed': .5, 'threshold_grid': [round(x, 2) for x in np.linspace(0, 1, 101)],
                             'fit': 'one F1-optimal threshold per attribute on outer training-fold nested-OOF probabilities; ties closest .5 then smaller',
                             'report': 'held-out binary positive-class F1 difference vs fixed.5'},
        'criteria': {'user_thresholds_unchanged_except_explicit_binary_amendment': True,
                     'governing_ECE': 'binary mass15 is primary for every model/attribute and macro-attribute aggregate; width15 cross-check on identical rows; if pass/fail differs, criterion is partial rather than established',
                     'P2_aggregate': 'macro-attribute ECE <= max(2*same-binning Monte Carlo noise mean,.03); primary mass15; width15 cross-check',
                     'P2_main_attributes': 'each >=800-image main attribute binary mass15 ECE<=.05, width15 cross-check',
                     'T_stability': 'sample std(ddof=1)/mean across nonempty outer folds <=.15',
                     'P4': 'mean pairwise top-option flip rate across3wordings <=.10; worst pair and order flips also reported',
                     'P5': 'pooled product binary mass15 ECE<=.05, width15 cross-check; pairs/triples also reported; NLL/product-vs-direct diagnostic only under latest explicit user amendment',
                     'P6': 'at least one fixed rule and one K>1 improve main-attribute macro point accuracy over same-cohort K=1 while macro binary mass15 ECE<=.05, width15 cross-check',
                     'established': 'at least one decision model passes all the above',
                     'partial': 'only attribute-specific T or some attributes pass',
                     'not_established': 'remaining fully measured cases',
                     'missing': 'unassessable criteria/models are reported unassessable; never invent a failure/pass',
                     'unique': 'apply identical rules to Qwen; if any Qwen passes, state calibration is not a unique decision-model advantage; report paired bootstrap P4/P5 differences'},
        'pilot': {'sample_ids': pilot_ids(samples), 'n': 200, 'setting': 'main',
                  'additional_settings': 'same first10 pilot IDs for each remaining setting, no selection by results',
                  'timing': 'synchronized wall-time after load; keep first-call latency separately; inference+I/O included',
                  'full_estimate': 'remaining exact request counts per setting * measured seconds/request per model, plus model loading; sum physical GPU-hours and serial wall hours',
                  'budget': 'if estimated complete GPU time >4h, stop full inference and ask user; pilot records can be reused'},
        'resources': {'allowed_gpus': [3, 4, 5, 6, 7], 'max_all_GroundJEV_physical_gpus': 4,
                      'execution': 'sequential model workers, task-local CUDA_VISIBLE_DEVICES; respect other jobs; no U2 route',
                      'temporary_features_bytes_limit': 25 * 1024**3,
                      'checkpoint_cache': '/home/user/.cache/r58_calibration/models',
                      'checkpoint_location_note': 'raw weights outside nearly-full data2; per-model links and provenance in R58 output folder',
                      'main_environment': '/data2/user/LocateMOT_GroundJEV/.venv-onejev-py310/bin/python, Python3.10/torch2.10cu128/transformers5.17.0; unchanged existing environment',
                      'perplexity_environment': 'isolated Python3.12 with exact official requirements; if CUDA13/driver570 incompatible, record runtime failure and skip rather than use different torch/interface',
                      'long_wait': 'one blocking owner command; no agent-level process/load polling'}
    }
    target.parent.mkdir(exist_ok=True)
    with target.open('x') as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        f.write('\n')
    write(OUT / 'protocol_status.json', {'frozen': True, 'inference_started': False,
                                        'plan': str(target), 'questions': len(qs), 'samples': len(samples)})
    print(json.dumps({'plan': str(target), 'samples': len(samples), 'questions': len(qs),
                      'settings': 6, 'models': len(models)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
