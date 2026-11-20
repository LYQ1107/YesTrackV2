#!/usr/bin/env python3
"""One real frame through the official verifier and official crop/forward helpers."""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, default=Path("analysis/config.json"))
a = p.parse_args()
c = json.loads(a.config.read_text())
t = Path(c["task_root"])
random.seed(c["seed"])
np.random.seed(c["seed"])
torch.manual_seed(c["seed"])
torch.cuda.manual_seed_all(c["seed"])
sys.path.insert(0, str(t / c["upstream"]))
from refer_llm import llm_eval_from_mot as official

adapter = Path(c["official_v2_adapter"])
assert (adapter / "adapter_model.safetensors").is_file()
start = time.perf_counter()
model, processor, tokens = official.build_model_and_processor_for_eval(
    model_name=c["base_model"], lora_path=str(adapter), bf16=True, use_4bit=False)
device = torch.device("cuda:0")
torch.cuda.set_device(device)
model.to(device)
model.eval()
file = sorted(Path(c["temprmot_star_candidates"]).glob("0005/*/predict.txt"))[0]
seq, expr = file.parent.parent.name, file.parent.name
dets = official._load_mot_file(str(file), frame_offset=0)
frame = min(dets)
selected = dets[frame][:2]
img = Path(c["image_root"]) / seq / f"{frame-1:06d}.png"
patches, w, h = official._prepare_patches_for_frame(
    img_path=str(img), dets_xywh=[tuple(r[1:5]) for r in selected], image_size=320,
    margin_ratio=0.2, margin_px=None, min_side=8, preprocess_workers=0, context="stage0 smoke")
sentence = official._natural_sentence_from_dirname(expr)
tpl = "The normalized position of the car or person in the picture is <{coord}>.Determine whether this description matches this image: {sentence}. Answer Yes or No."
prompts = [tpl.format(coord=f"{min(1,max(0,(x+0.5*bw)/w)):.3f} {min(1,max(0,(y+0.5*bh)/h)):.3f}", sentence=sentence)
           for _, x, y, bw, bh, _ in selected]
probs = official._forward_probs_for_patches(model=model, processor=processor, device=device,
    patches=patches, prompts=prompts, yes_id=tokens[0], no_id=tokens[1], context="stage0 smoke")
assert len(probs) == len(selected)
assert all(np.isfinite(v) and 0 <= v <= 1 for v in probs)
out = {"seed": c["seed"], "sequence": seq, "expression": sentence, "mot_frame": frame,
       "image_index": frame-1, "candidate_count": len(selected), "probs": probs,
       "adapter_loaded": hasattr(model, "peft_config"), "yes_no_token_ids": tokens,
       "seconds": time.perf_counter()-start,
       "max_memory_allocated_bytes": torch.cuda.max_memory_allocated()}
assert out["adapter_loaded"]
(t / "analysis/runtime_smoke.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(out, ensure_ascii=False, indent=2))
