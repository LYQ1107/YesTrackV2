#!/usr/bin/env python3
"""Cache official frame/video helper scores for explicitly frozen GT candidate units."""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch
from PIL import Image
from common import config, mot, save_json

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--plan", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
p.add_argument("--rank", type=int, default=0)
p.add_argument("--world-size", type=int, default=1)
p.add_argument("--video", action="store_true")
p.add_argument("--video-only", action="store_true")
p.add_argument("--resume", action="store_true")
p.add_argument("--dynamic-shards", action="store_true")
a = p.parse_args()
c = config()
t = Path(c["task_root"])
plan = json.loads(a.plan.read_text())
random.seed(c["seed"])
np.random.seed(c["seed"])
torch.manual_seed(c["seed"])
torch.cuda.manual_seed_all(c["seed"])
sys.path.insert(0, str(t / c["upstream"]))
from refer_llm import llm_eval_from_mot as off
from transformers.utils.logging import disable_progress_bar
disable_progress_bar()

a.out.mkdir(parents=True, exist_ok=True)
started = time.monotonic()
device = torch.device("cuda:0")
torch.cuda.set_device(device)
model, processor, ids = off.build_model_and_processor_for_eval(
    model_name=c["base_model"], lora_path=c["official_v2_adapter"], bf16=True, use_4bit=False)
model.to(device)
model.eval()
load_seconds = time.monotonic()-started
tpl = "The normalized position of the car or person in the picture is <{coord}>.Determine whether this description matches this image: {sentence}. Answer Yes or No."
vtpl = "This is a short video clip of a car or person at <{coord}> across frames. The target may include motion cues; consider background and temporal context when deciding if the description matches this target: {sentence}. Answer Yes or No."
count = video_count = frames = completed = 0
assigned_names=[]
frame_seconds = video_seconds = 0.0
claim_phase='video' if a.video_only else ('joint' if a.video else 'frame')
claim_root=a.out/('claims_'+claim_phase)
if a.dynamic_shards:claim_root.mkdir(parents=True,exist_ok=True)
manifest = json.loads(Path(plan.get("tracks_manifest", t / "analysis/resources/gt_candidates_v2/manifest.json")).read_text())
tracks = {seq: mot(r["track_file"]) for seq, r in manifest["sequences"].items()}
with torch.inference_mode():
    for task_index, task in enumerate(plan["tasks"]):
        if a.dynamic_shards:
            try:(claim_root/task['name']).mkdir()
            except FileExistsError:continue
        elif task_index % a.world_size != a.rank:
            continue
        assigned_names.append(task['name'])
        target = a.out / (task["name"] + ".npz")
        if a.resume and target.exists():
            saved = np.load(target)
            assert len(saved["row_index"]) == task["candidate_rows"], task["name"]
            eligible=(saved['p_frame']>=.2)&(saved['p_frame']<.8)
            if not a.video or np.isfinite(saved['p_video'][eligible]).all():
                completed += 1
                continue
        seq, expr = task["name"].split("__", 1)
        tr = tracks[seq]
        trajectory = {int(oid): np.flatnonzero(tr[:, 1] == oid) for oid in np.unique(tr[:, 1])}
        born = {oid: int(tr[ix[0],0]) for oid,ix in trajectory.items()}
        existing=None
        if a.video_only:
            assert a.video
            saved=np.load(target)
            existing=np.full(len(tr),np.nan,dtype=np.float32)
            existing[saved['row_index']]=saved['p_frame']
        row_indices, ps, pv = [], [], []
        sentence = off._natural_sentence_from_dirname(expr)
        for frame in task["frames"]:
            indices = np.flatnonzero(tr[:, 0] == frame)
            if plan.get("births_only", False):
                indices = np.array([i for i in indices if born[int(tr[i,1])] == frame],dtype=np.int64)
            if not len(indices):
                continue
            frame_start = time.monotonic()
            image = str(Path(c["image_root"]) / seq / f"{frame-1:06d}.png")
            boxes = [tuple(b) for b in tr[indices, 2:6]]
            if a.video_only:
                with Image.open(image) as header:w,h=header.size
            else:
                patches, w, h = off._prepare_patches_for_frame(image, boxes, 320, .2, None, 8,
                    preprocess_workers=4, context=task["name"])
            coords = [f"{np.clip((x+.5*bw)/w,0,1):.3f} {np.clip((y+.5*bh)/h,0,1):.3f}"
                      for x,y,bw,bh in boxes]
            prompts = [tpl.format(coord=coord, sentence=sentence) for coord in coords]
            if a.video_only:
                prob=existing[indices]
                assert np.isfinite(prob).all()
            else:
                prob = np.array(off._forward_probs_for_patches(model, processor, device,
                    patches, prompts, ids[0], ids[1], context=task["name"]), dtype=np.float32)
            video = np.full(len(indices), np.nan, dtype=np.float32)
            eligible = np.flatnonzero((prob >= .2) & (prob < .8))
            frame_seconds += time.monotonic()-frame_start
            if a.video and len(eligible):
                video_start = time.monotonic()
                paths_per, boxes_per, video_prompts = [], [], []
                for k in eligible:
                    index = indices[k]
                    traj = trajectory[int(tr[index, 1])]
                    pos = int(np.flatnonzero(traj == index)[0])
                    previous = traj[max(0,pos-3):pos+1]
                    paths_per.append([str(Path(c["image_root"]) / seq / f"{int(tr[j,0])-1:06d}.png") for j in previous])
                    boxes_per.append([tuple(tr[j, 2:6]) for j in previous])
                    video_prompts.append(vtpl.format(coord=coords[k], sentence=sentence))
                video[eligible] = off._forward_probs_for_detections_video(
                    model=model, processor=processor, device=device, image_paths_per_sample=paths_per,
                    dets_per_sample=boxes_per, prompts=video_prompts, yes_id=ids[0], no_id=ids[1],
                    image_size=320, margin_ratio=.2, margin_px=None, min_side=8,
                    preprocess_workers=4, context=task["name"])
                video_count += len(eligible)
                video_seconds += time.monotonic()-video_start
            row_indices.extend(indices)
            ps.extend(prob)
            pv.extend(video)
            count += len(indices)
            frames += 1
        assert len(row_indices) == task["candidate_rows"], task["name"]
        temporary=target.with_suffix('.tmp.npz')
        np.savez_compressed(temporary, row_index=np.asarray(row_indices,dtype=np.int32),
                            p_frame=np.asarray(ps,dtype=np.float32), p_video=np.asarray(pv,dtype=np.float32))
        temporary.replace(target)
        completed += 1
elapsed = time.monotonic()-started
result = {"rank": a.rank, "seed": c["seed"], "plan": str(a.plan), "complete": True,
          "tasks": completed, "frame_samples": count, "video_samples": video_count,
          "assigned_expression_names": assigned_names, "dynamic_shards": a.dynamic_shards,
          "frames": frames, "load_seconds": load_seconds, "seconds": elapsed,
          "inference_seconds": elapsed-load_seconds,
          "frame_seconds": frame_seconds, "video_seconds": video_seconds,
          "frame_samples_per_second": count/max(elapsed-load_seconds,1e-9),
          "peak_cuda_bytes": torch.cuda.max_memory_allocated()}
save_json(a.out / f"receipt_rank{a.rank}.json", result)
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
