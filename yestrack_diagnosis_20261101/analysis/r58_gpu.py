#!/usr/bin/env python3
"""R58 official-interface inference, immutable question bank, resumable complete requests."""
import argparse
import copy
import gc
import json
import os
from pathlib import Path
import random
import sys
import time
import traceback

import numpy as np
from PIL import Image
import torch

TASK = Path(__file__).resolve().parents[1]
OUT = TASK / 'analysis/runs/R58_calibration'
PLAN = json.loads((TASK / 'analysis/plans/r58.json').read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def questions_for(setting):
    result = {}
    mapping = {}
    for q in PLAN['questions']['bank']:
        word = setting['wording']
        orders = q['orders']
        order = orders[setting['permutation']] if q['type'] == 'choice' else orders[0]
        options = [q['options'][i] for i in order]
        qq = {'type': q['type'], 'instructions': q['instructions'][word]}
        if q['type'] == 'choice':
            qq['criteria'] = {o['labels'][word]: None for o in options}
        result[q['id']] = qq
        mapping[q['id']] = [(o['id'], o['labels'][word]) for o in options]
    return result, mapping


def payload(sample, setting, pil=False):
    images = sample['input_images'] if setting['images'] == 'crop+frame' else sample['input_images'][:1]
    state = sample['state']
    if setting['images'] == 'crop':
        state = state.replace('Image 2 is the full-frame thumbnail; the red box marks the same target. ', '')
    qs, mapping = questions_for(setting)
    return state, [Image.open(x).convert('RGB') for x in images] if pil else images, qs, mapping


def canonical_probs(answer, mapping):
    result = {}
    for qid, options in mapping.items():
        a = answer[qid]
        if 'noul' in a:
            result[qid] = {'no': 1 - float(a['noul']), 'yes': float(a['noul'])}
        else:
            result[qid] = {key: float(a['probabilities'][label]) for key, label in options}
    return result


class Decision:
    def __init__(self, repo, path):
        self.repo = repo
        self.path = path
        self.parity = None
        if repo.startswith('vllm-sr/') and repo.endswith(('-FP8', '-INT4')):
            sys.path.insert(0, str(path))
            from d3q.load import load_d3
            self.model = load_d3(str(path), device='cuda:0')
        elif repo.startswith('vllm-sr/'):
            from transformers import AutoModel
            self.model = AutoModel.from_pretrained(str(path), trust_remote_code=True, device='cuda:0')
        elif repo.startswith('OmniJev/'):
            sys.path.insert(0, PLAN['onejev_code']['path'])
            from qev.mm_engine import MMDecisionEngine
            self.model = MMDecisionEngine(str(path), device='cuda:0', fork_mode='auto')
        else:
            sys.path.insert(0, str(path / 'source/src'))
            from pplx_decider import Decider
            self.model = Decider.from_pretrained(path, device='cuda:0', fast=False)

    def predict(self, sample, setting):
        state, images, questions, mapping = payload(sample, setting)
        if self.repo.startswith('vllm-sr/'):
            answer = self.model.system_one(state=state, images=images, questions=questions)
            p = canonical_probs(answer['answers'], mapping)
            return p, {'usage': answer.get('usage')}
        if self.repo.startswith('OmniJev/'):
            from qev.schema import SystemOneRequest
            from qev.media import data_uri
            media = [{'type': 'image', 'data': data_uri(p)} for p in images]
            refs = ' '.join(f'<image:{j+1}>' for j in range(len(images)))
            req = SystemOneRequest.model_validate({'state': refs + ' ' + state, 'questions': questions})
            response, meta = self.model.decide(req, media=media, debias=1, debug=False)
            return canonical_probs(response.model_dump()['answers'], mapping), {'official_meta': meta}
        # Public raw logits interface avoids applying the checkpoint's saved temperature twice.
        logits = self.model.logits([{'state': state, 'images': images, 'questions': questions}])[0]
        result = {}
        for qid, values in logits.items():
            p = torch.tensor(values, dtype=torch.float64).softmax(-1).tolist()
            if questions[qid]['type'] == 'noul':
                # Official protocol.py:68,82: false then true, Noul is values[1].
                result[qid] = {'no': p[0], 'yes': p[1]}
            else:
                result[qid] = {key: p[i] for i, (key, label) in enumerate(mapping[qid])}
        return result, {'raw_readout_logits': logits, 'saved_temperature': self.model.temperature}


def reuse_qwen_pilot_cache_decision(model, model_key, checkpoint_repo, revision):
    """The frozen cache gate is evaluated on the first pilot sample, never a new full sample."""
    pilot_path = OUT / 'status' / (model_key + '_pilot.json')
    pilot = json.loads(pilot_path.read_text())
    assert pilot['status'] == 'complete'
    assert pilot['checkpoint_repo'] == checkpoint_repo and pilot['revision'] == revision
    assert pilot['cache_parity'] is not None, 'The frozen pilot cache gate has not been measured'
    model.cache_ok = bool(pilot['cache_parity']['cache_used'])
    model.parity = {**pilot['cache_parity'], 'decision_source': 'frozen first-pilot-sample gate',
                    'source_status': str(pilot_path)}


class Qwen:
    """Teacher-forced full-option scoring with an optional validated shared-prefix cache."""
    def __init__(self, repo, path):
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.processor = AutoProcessor.from_pretrained(str(path))
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(path), dtype=torch.bfloat16, device_map={'': 'cuda:0'}, attn_implementation='sdpa').eval()
        self.tokenizer = self.processor.tokenizer
        self.cache_ok = True
        self.parity = None

    def inputs(self, sample, setting):
        state, images, qs, mapping = payload(sample, setting, pil=True)
        lines = [state, 'Answer every numbered question independently. Output the complete option text.']
        for qid, q in qs.items():
            text = f'{qid}: {q["instructions"]}'
            opts = [label for key, label in mapping[qid]]
            lines.append(text + '\nOptions: ' + ' | '.join(opts))
        content = [{'type': 'image', 'image': image} for image in images]
        content.append({'type': 'text', 'text': '\n'.join(lines)})
        inputs = self.processor.apply_chat_template([{'role': 'user', 'content': content}],
            tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt')
        return inputs.to(self.model.device), mapping

    def candidates(self, mapping):
        result = []
        for qid, opts in mapping.items():
            prefix = self.tokenizer.encode(qid + ':', add_special_tokens=False)
            for key, label in opts:
                tokens = self.tokenizer.encode(' ' + label, add_special_tokens=False)
                result.append((qid, key, prefix, tokens))
        return result

    def normalize(self, mapping, scores):
        result = {}
        for qid, opts in mapping.items():
            z = torch.tensor([scores[(qid, key)] for key, label in opts], dtype=torch.float64)
            result[qid] = dict(zip([key for key, label in opts], z.softmax(-1).tolist()))
        return result

    def fresh(self, inputs, mapping):
        scores = {}
        prefix_length = inputs['input_ids'].shape[1]
        for qid, key, prefix, tokens in self.candidates(mapping):
            suffix = torch.tensor([prefix + tokens], device=self.model.device)
            kw = dict(inputs)
            kw['input_ids'] = torch.cat([inputs['input_ids'], suffix], -1)
            kw['attention_mask'] = torch.ones_like(kw['input_ids'])
            if 'mm_token_type_ids' in kw:
                kw['mm_token_type_ids'] = torch.cat([kw['mm_token_type_ids'], torch.zeros_like(suffix)], -1)
            if 'token_type_ids' in kw:
                kw['token_type_ids'] = torch.cat([kw['token_type_ids'], torch.zeros_like(suffix)], -1)
            # Keep only suffix logits to avoid a full context*vocabulary tensor.
            out = self.model(**kw, use_cache=False, logits_to_keep=len(prefix) + len(tokens))
            start = len(prefix) - 1
            lp = out.logits[0, start:start + len(tokens)].float().log_softmax(-1)
            score = lp[torch.arange(len(tokens), device=lp.device), torch.tensor(tokens, device=lp.device)].sum()
            scores[(qid, key)] = float(score)
        return self.normalize(mapping, scores)

    def cached(self, inputs, mapping):
        base = self.model(**inputs, use_cache=True, logits_to_keep=1)
        cache = base.past_key_values
        length = inputs['input_ids'].shape[1]
        candidates = self.candidates(mapping)
        scores = {}
        pad = self.tokenizer.pad_token_id or self.tokenizer.eos_token_id
        for first in range(0, len(candidates), 4):
            batch = candidates[first:first + 4]
            width = max(len(p) + len(t) for _, _, p, t in batch)
            ids = torch.full((len(batch), width), pad, dtype=torch.long, device=self.model.device)
            am = torch.zeros_like(ids)
            for j, (_, _, p, t) in enumerate(batch):
                ids[j, :len(p) + len(t)] = torch.tensor(p + t, device=ids.device)
                am[j, :len(p) + len(t)] = 1
            branch = copy.deepcopy(cache)
            if len(batch) > 1:
                branch.batch_repeat_interleave(len(batch))
            mask = torch.cat([torch.ones((len(batch), length), dtype=am.dtype, device=am.device), am], -1)
            # Use the installed official generation helpers to slice suffix M-RoPE positions.
            # Passing only the full attention mask to forward() builds full-length positions
            # for suffix-only embeddings in Transformers 5.17 and causes a shape mismatch.
            position_ids = self.model._prepare_position_ids_for_generation(
                ids, {'attention_mask': mask, 'past_key_values': branch})
            prepared = self.model.prepare_inputs_for_generation(
                ids, past_key_values=branch, attention_mask=mask,
                position_ids=position_ids, use_cache=True)
            out = self.model(**prepared)
            for j, (qid, key, p, tokens) in enumerate(batch):
                lp = out.logits[j, len(p)-1:len(p)+len(tokens)-1].float().log_softmax(-1)
                score = lp[torch.arange(len(tokens), device=lp.device), torch.tensor(tokens, device=lp.device)].sum()
                scores[(qid, key)] = float(score)
            del branch, out
        del base, cache
        return self.normalize(mapping, scores)

    def predict(self, sample, setting):
        inputs, mapping = self.inputs(sample, setting)
        if self.parity is None:
            try:
                p = self.cached(inputs, mapping)
                reference = self.fresh(inputs, mapping)
                delta = max(abs(p[q][k] - reference[q][k]) for q in p for k in p[q])
                self.cache_ok = delta <= .005
                self.parity = {'probability_max_abs_error': delta, 'tolerance': .005, 'cache_used': self.cache_ok}
            except Exception as e:
                self.cache_ok = False
                self.parity = {'cache_used': False, 'cache_exception': repr(e), 'fallback': 'fresh full-option reference'}
                torch.cuda.empty_cache()
                reference = self.fresh(inputs, mapping)
            return p if self.cache_ok else reference, {'cache_parity': self.parity}
        p = self.cached(inputs, mapping) if self.cache_ok else self.fresh(inputs, mapping)
        return p, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--checkpoint-repo')
    ap.add_argument('--stage', choices=['pilot', 'full'], required=True)
    args = ap.parse_args()
    if args.model.startswith('perplexity'):
        # Its exact Python3.12/torch2.14 requirements are isolated from the main Python3.10 overlay.
        sys.path = [p for p in sys.path if p != '/home/user/.cache/r58_calibration/extra310']
        os.environ.pop('PYTHONPATH', None)
    assert PLAN['seed'] == 2025 and PLAN['status'] == 'FROZEN_BEFORE_ANY_MODEL_INFERENCE'
    assert len(os.environ['CUDA_VISIBLE_DEVICES'].split(',')) == 1
    visible = int(os.environ['CUDA_VISIBLE_DEVICES'])
    assert visible in PLAN['resources']['allowed_gpus']
    random.seed(2025)
    np.random.seed(2025)
    torch.manual_seed(2025)
    torch.cuda.manual_seed_all(2025)
    torch.set_num_threads(4)
    info = next(x for x in PLAN['models'] if x['repo'] == args.model)
    checkpoint_repo = args.checkpoint_repo or args.model
    if checkpoint_repo != args.model:
        assert any(x['repo'] == checkpoint_repo for x in info.get('memory_fallbacks', []))
    model_key = checkpoint_repo.replace('/', '__')
    path = OUT / 'models' / model_key
    checkpoint_info = info if checkpoint_repo==args.model else next(x for x in info['memory_fallbacks'] if x['repo']==checkpoint_repo)
    assert path.resolve().name == checkpoint_info['revision'], 'Checkpoint revision differs from frozen plan'
    status = OUT / 'status' / (model_key + '_' + args.stage + '.json')
    samples = json.loads((OUT / 'samples.json').read_text())
    index = {r['id']: r for r in samples}
    settings = PLAN['questions']['settings']
    outputs = OUT / 'predictions' / model_key
    outputs.mkdir(parents=True, exist_ok=True)
    if args.stage == 'full':
        approval = OUT / 'full_budget_approval.json'
        if not approval.exists():
            raise RuntimeError('Full inference requires the budget gate/explicit authorization artifact')
        authorization=json.loads(approval.read_text())
        if authorization.get('authorization')=='user automatic <=4h rule':
            assert json.loads((OUT/'budget.json').read_text())['gate']=='within_user_automatic_budget'
    state = json.loads((OUT / 'protocol_status.json').read_text())
    state['inference_started'] = True
    if args.stage=='full':state['full_inference_started']=True
    save(OUT / 'protocol_status.json', state)
    t0 = time.monotonic()
    try:
        model = Qwen(checkpoint_repo, path) if args.model.startswith('Qwen/') else Decision(checkpoint_repo, path)
        if args.stage == 'full' and args.model.startswith('Qwen/'):
            reuse_qwen_pilot_cache_decision(model, model_key, checkpoint_repo, checkpoint_info['revision'])
        torch.cuda.synchronize()
        load_time = time.monotonic() - t0
        timing = []
        for setting in settings:
            ids = PLAN['pilot']['sample_ids'] if args.stage == 'pilot' else list(index)
            if args.stage == 'pilot' and setting['id'] != 'main':
                ids = ids[:10]
            dest = outputs / (setting['id'] + '.jsonl')
            done = set()
            if dest.exists():
                for line in dest.read_text().splitlines():
                    r = json.loads(line)
                    assert r['checkpoint_repo'] == checkpoint_repo
                    done.add(r['sample_id'])
            n = 0
            elapsed = 0
            with dest.open('a') as f:
                for sample_id in ids:
                    if sample_id in done:
                        continue
                    start = time.monotonic()
                    with torch.inference_mode():
                        probs, meta = model.predict(index[sample_id], setting)
                    torch.cuda.synchronize()
                    seconds = time.monotonic() - start
                    for q, pp in probs.items():
                        a = np.array(list(pp.values()))
                        assert np.isfinite(a).all() and np.all(a >= 0) and abs(a.sum()-1) < 1e-5, (q, pp)
                    assert len(probs) == len(PLAN['questions']['bank'])
                    rec = {'sample_id': sample_id, 'setting': setting['id'], 'checkpoint_repo': checkpoint_repo,
                           'seed': 2025, 'probabilities': probs, 'seconds': seconds, 'meta': meta}
                    f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                    f.flush()
                    n += 1
                    elapsed += seconds
                    if n == 1 or n % 20 == 0:
                        print(json.dumps({'model': checkpoint_repo, 'setting': setting['id'], 'new_requests': n,
                                          'planned_requests': len(ids), 'seconds': elapsed}), flush=True)
            timing.append({'setting': setting['id'], 'new_requests': n, 'seconds': elapsed,
                           'total_records': len(done) + n, 'planned_stage_requests': len(ids)})
        save(status, {'status': 'complete', 'model': args.model, 'checkpoint_repo': checkpoint_repo,
                      'revision':checkpoint_info['revision'],'python':sys.version,
                      'gpu_name':torch.cuda.get_device_name(0),'compute_capability':torch.cuda.get_device_capability(0),
                      'stage': args.stage, 'load_seconds': load_time, 'timing': timing,
                      'cache_parity': model.parity, 'physical_gpu': visible,
                      'wall_seconds': time.monotonic() - t0, 'torch': torch.__version__})
    except Exception as e:
        save(status, {'status': 'failed', 'model': args.model, 'checkpoint_repo': checkpoint_repo,
                      'stage': args.stage, 'exception': repr(e), 'traceback': traceback.format_exc(),
                      'physical_gpu': visible, 'wall_seconds': time.monotonic() - t0})
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
