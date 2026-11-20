#!/usr/bin/env python3
"""Frozen zero-shot SoM format probe on the same released V2 verifier."""
import gzip
import argparse
import json
import os
from pathlib import Path
import random
import shlex
import sys
import time

import numpy as np
from PIL import Image,ImageDraw,ImageFont
import torch
from common import config,log_run,mot,save_json

parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true')
parser.add_argument('--shuffle-candidates',action='store_true')
parser.add_argument('--out',type=Path,default=Path('analysis/runs/R25_som'));options_cli=parser.parse_args()
c=config();t=Path(c['task_root']);assert os.environ.get('CUDA_VISIBLE_DEVICES')=='6'
b=json.loads((t/'analysis/local_baseline.json').read_text())
plan=json.loads((t/'analysis/plans/som.json').read_text())
out=t/options_cli.out;out.mkdir(parents=True,exist_ok=True)
extra_args=(['--pilot'] if options_cli.pilot else [])+(['--shuffle-candidates','--out',str(options_cli.out)] if options_cli.shuffle_candidates else [])
log_run(c,47 if options_cli.shuffle_candidates else 25,'Set-of-Mark 固定seed随机编号对照' if options_cli.shuffle_candidates else 'Set-of-Mark 联合选择的小样本探针',[
 'CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false '+shlex.join([c['reproduction_environment'],'-u','analysis/som_probe.py',*extra_args])],
 ('GPU阶段开始前预计1–2小时，单GPU6；参考原同1704帧阶段实际3373.536秒及R09 2.2小时。'
  '每(sequence,frame)用seed=2025+100000*int(sequence)+frame固定随机排列，编号不依赖表达式或GT referring。'
  '原crop输入不变，其概率按GT ID重排复用R25；同一随机标号整帧上的独立二分类和联合选择均重新前向。' if options_cli.shuffle_candidates else
  'GPU阶段启动前预计2–4小时（参考R09 2.2小时及R19吞吐，计划仅1704帧左右）；')+
 '发布V2 LoRA与二分类使用完全相同权重，不增加训练/示例。D全21表达式；G全视频空表达式为0，以100条表达式的空GT帧作为另列对照。'
 '比较原crop二分类、同一整帧SoM图上的独立二分类、SoM联合单选+none。'
 'Qwen的10/11等为多token，故用完整选项串+换行的teacher-forced log概率之和再softmax，不错误地只读共享首token；不做长度归一化。'
 'SoM整帧保留原分辨率，二分类整帧控制使用完全相同图；联合单选对多目标帧有召回上限，分开报告。')
if options_cli.pilot:
    log_run(c,'25-pilot','单token/多token选项真实前向检查',[
        'CUDA_VISIBLE_DEVICES=6 OMP_NUM_THREADS=2 '+c['reproduction_environment']+' -u analysis/som_probe.py --pilot'],
        'GPU阶段启动前预计3–5分钟，依据R19加载/前向时间；原计划中各取一个N≤9和N≥10帧，完全相同输入。'
        '保存的两个真实帧结果供正式阶段复用，pilot不标为完整1704帧实验。')
random.seed(c['seed']);np.random.seed(c['seed']);torch.manual_seed(c['seed']);torch.cuda.manual_seed_all(c['seed'])
sys.path.insert(0,str(t/c['upstream']))
from refer_llm import llm_eval_from_mot as off
from transformers.utils.logging import disable_progress_bar
disable_progress_bar()
device=torch.device('cuda:0');torch.cuda.set_device(device)
model,processor,ids=off.build_model_and_processor_for_eval(c['base_model'],bf16=True,lora_path=c['official_v2_adapter'])
model.to(device);model.eval()
manifest=json.loads((t/'analysis/resources/gt_candidates_v2/manifest.json').read_text())
tracks={s:mot(r['track_file']) for s,r in manifest['sequences'].items()}
pilot_selection={}
if options_cli.pilot:
    for task in plan['tasks']:
        seq=task['name'].split('__',1)[0]
        for frame in task['frames']:
            n=int((tracks[seq][:,0]==frame).sum());stratum='single_token' if n<=9 else 'multi_token'
            pilot_selection.setdefault(stratum,(task['name'],frame,task['group']))
    assert len(pilot_selection)==2
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
tpl='The normalized position of the car or person in the picture is <{coord}>.Determine whether this description matches this image: {sentence}. Answer Yes or No.'
started=time.monotonic();records=0
original_records={}
if options_cli.shuffle_candidates:
    assert out!=t/'analysis/runs/R25_som'
    with gzip.open(t/'analysis/runs/R25_som/frames.jsonl.gz','rt') as source:
        for line in source:
            record=json.loads(line);original_records[(record['name'],record['frame'],record['group'])]=record
existing=set()
if (out/'frames.jsonl.gz').exists():
    with gzip.open(out/'frames.jsonl.gz','rt') as previous:
        for line in previous:
            record=json.loads(line);existing.add((record['name'],record['frame'],record['group']))
records=len(existing)
with gzip.open(out/'frames.jsonl.gz','at' if existing else 'wt') as output,torch.inference_mode():
 for task in plan['tasks']:
    seq,expr=task['name'].split('__',1);tr=tracks[seq]
    js=json.loads((Path(c['expression_root'])/seq/f'{expr}.json').read_text())
    sentence=off._natural_sentence_from_dirname(expr)
    for frame in task['frames']:
        if options_cli.pilot and (task['name'],frame,task['group']) not in set(pilot_selection.values()):continue
        if (task['name'],frame,task['group']) in existing:continue
        original_ix=np.flatnonzero(tr[:,0]==frame);n=len(original_ix)
        assert n
        permutation=(np.random.default_rng(c['seed']+100000*int(seq)+frame).permutation(n)
                     if options_cli.shuffle_candidates else np.arange(n))
        ix=original_ix[permutation]
        image=Image.open(Path(c['image_root'])/seq/f'{frame-1:06d}.png').convert('RGB');w,h=image.size
        marked=image.copy();draw=ImageDraw.Draw(marked)
        crop=[];prompts=[];global_prompts=[]
        y=[int(tr[i,1]) in {int(v) for v in js['label'].get(str(frame-1),[])} for i in ix]
        for j,i in enumerate(ix,1):
            x,y0,bw,bh=tr[i,2:6]
            draw.rectangle((x,y0,x+bw,y0+bh),outline='red',width=3)
            label=str(j);box=draw.textbbox((0,0),label,font=font);tw=box[2]-box[0]+6
            xx=min(max(0,x),w-tw);yy=max(0,y0-28)
            draw.rectangle((xx,yy,xx+tw,yy+28),fill='red');draw.text((xx+3,yy),label,font=font,fill='white')
            patch=off.crop_with_margin(image,(x,y0,bw,bh),margin_ratio=.2,min_side=8)
            assert patch is not None
            crop.append(patch.resize((320,320)))
            coord=f'{np.clip((x+.5*bw)/w,0,1):.3f} {np.clip((y0+.5*bh)/h,0,1):.3f}'
            prompt=tpl.format(coord=coord,sentence=sentence);prompts.append(prompt)
            global_prompts.append(f'The target is candidate {j}, marked by its number. '+prompt)
        if options_cli.shuffle_candidates:
            prior=original_records[(task['name'],frame,task['group'])]
            assert prior['ids']==tr[original_ix,1].astype(int).tolist()
            assert np.array_equal(np.array(prior['y'])[permutation],y)
            pcrop=np.array(prior['p_crop'])[permutation].tolist()
        else:pcrop=off._forward_probs_for_patches(model,processor,device,crop,prompts,ids[0],ids[1])
        pglobal=off._forward_probs_for_patches(model,processor,device,[marked]*n,global_prompts,ids[0],ids[1])
        options=[str(j) for j in range(1,n+1)]+['none']
        question=(f'The image shows candidate objects numbered 1 to {n}. Description: {sentence}. '
                  'Select the one candidate that best matches the description. If no candidate matches, select none. '
                  'Answer with exactly one candidate number or none, followed by a newline.')
        messages=[[{'role':'user','content':[{'type':'image','image':marked},{'type':'text','text':question}]}]
                  for _ in options]
        inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
                    return_dict=True,return_tensors='pt',padding=True).to(device)
        answers=[processor.tokenizer.encode(option+'\n',add_special_tokens=False) for option in options]
        maxlen=max(map(len,answers));pad=processor.tokenizer.pad_token_id
        suffix=torch.full((len(options),maxlen),pad,dtype=inputs['input_ids'].dtype,device=device)
        mask=torch.zeros_like(suffix)
        for j,tokens in enumerate(answers):
            suffix[j,:len(tokens)]=torch.tensor(tokens,device=device);mask[j,:len(tokens)]=1
        inputs['input_ids']=torch.cat([inputs['input_ids'],suffix],dim=1)
        inputs['attention_mask']=torch.cat([inputs['attention_mask'],mask],dim=1)
        logits=model(**inputs,use_cache=False,logits_to_keep=maxlen+1).logits.float()
        logp=torch.log_softmax(logits,dim=-1)
        scores=torch.stack([sum(logp[j,k,token] for k,token in enumerate(tokens))
                            for j,tokens in enumerate(answers)])
        probs=torch.softmax(scores,dim=0).cpu().tolist()
        chosen=int(torch.argmax(scores).item());none=chosen==n
        candidate_selected=[j+1 for j,v in enumerate(probs[:-1]) if v>=b['gamma']]
        single_ids=[processor.tokenizer.encode(option,add_special_tokens=False) for option in options]
        next_token_probs=None
        if all(len(tokens)==1 for tokens in single_ids):
            option_logits=torch.stack([logits[j,0,tokens[0]] for j,tokens in enumerate(single_ids)])
            next_token_probs=torch.softmax(option_logits,dim=0).cpu().tolist()
        output.write(json.dumps({'name':task['name'],'frame':frame,'group':task['group'],
             'row_index':ix.tolist(),'ids':tr[ix,1].astype(int).tolist(),'y':y,'p_crop':pcrop,
             'p_full_binary':pglobal,'option_log_likelihood':scores.cpu().tolist(),
             'option_probabilities':probs,'selected':None if none else chosen+1,
             'none':none,'n':n,'selected_at_frozen_gamma':candidate_selected,
             'none_at_frozen_gamma':not candidate_selected,
             'single_token_option_probabilities':next_token_probs,
             'candidate_permutation_from_original':permutation.tolist(),
             'candidate_ordering':'seeded_random_by_sequence_frame' if options_cli.shuffle_candidates else 'released_GT_order'})+'\n')
        records+=1
expected=len(pilot_selection) if options_cli.pilot else sum(len(x['frames']) for x in plan['tasks'])
receipt=out/('pilot_coverage.json' if options_cli.pilot else 'coverage.json')
save_json(receipt,{'complete':True,'seed':c['seed'],'expression_frames':records,
          'expected_expression_frames':expected,'pilot':options_cli.pilot,
          'candidate_ordering':'seeded_random_by_sequence_frame' if options_cli.shuffle_candidates else 'released_GT_order',
          'seconds':time.monotonic()-started})
assert records==expected
print(receipt.read_text(),flush=True)
