#!/usr/bin/env python3
"""Freeze data-independent selections and budgets before probing the verifier."""
import json
from pathlib import Path

import numpy as np
from common import config, log_run, mot, save_json

c = config()
t = Path(c["task_root"])
out = t / "analysis/plans"
out.mkdir(parents=True, exist_ok=True)
rows = json.loads((t / "analysis/labels/expressions.json").read_text())
manifest = json.loads((t / "analysis/resources/gt_candidates_v2/manifest.json").read_text())
tracks = {seq: mot(r["track_file"]) for seq,r in manifest["sequences"].items()}
rng = np.random.default_rng(c["seed"])


def task(row, frames):
    frames = sorted(map(int,frames))
    tr = tracks[row["sequence"]]
    return {"name": row["name"], "frames": frames,
            "candidate_rows": int(np.isin(tr[:,0],frames).sum())}


pilot = []
for seq in c["val_sequences"]:
    pool = [r for r in rows if r["sequence"] == seq and "F" in r["labels"]]
    selected = [pool[i] for i in rng.choice(len(pool),2,replace=False)]
    for row in selected:
        fs = np.unique(tracks[seq][:,0]).astype(int)
        pilot.append(task(row,rng.choice(fs,min(16,len(fs)),replace=False)))
save_json(out / "R19_timing.json", {"seed": c["seed"], "tasks": pilot,
    "scope": "128 real frames, eight expressions, all four sequences; frame + selective video, same per-frame batching as official."})
fullf = [task(r,np.unique(tracks[r["sequence"]][:,0])) for r in rows if "F" in r["labels"]]
save_json(out / "trp_full_f.json", {"seed":c["seed"],"tasks":fullf,"scope":"all F expressions and visible GT frames"})
full = [task(r,np.unique(tracks[r["sequence"]][:,0])) for r in rows]
save_json(out / "calibration_full.json", {"seed":c["seed"],"tasks":full,"scope":"all GT track object-frames"})
cd = [r for r in rows if "C" in r["labels"] or "D" in r["labels"]]
control=[]
for seq in c["val_sequences"]:
    needed=sum(r["sequence"]==seq for r in cd)
    controls=[r for r in rows if r["sequence"]==seq and "A" in r["labels"] and not set(r["labels"]) & set("CD")]
    assert len(controls)>=needed
    control.extend(controls[i] for i in rng.choice(len(controls),needed,replace=False))
context = []
for row in cd+control:
    fs = np.unique(tracks[row["sequence"]][:,0]).astype(int)
    context.append({**task(row,rng.choice(fs,min(24,len(fs)),replace=False)),
                    "group":"CD" if row in cd else "A_control"})
save_json(out / "context.json", {"seed":c["seed"],"tasks":context,
    "scope":"Every C/D expression plus equally many random A controls excluding C/D, matched by sequence; other labels may overlap; 24 uniform frames per expression, all GT candidates; frozen paired frames."})
print(json.dumps({"timing_pilot_rows":sum(x["candidate_rows"] for x in pilot),
                  "full_F_rows":sum(x["candidate_rows"] for x in fullf),
                  "full_GT_rows":sum(x["candidate_rows"] for x in full),
                  "context_CD_expressions":len(cd),"A_control_expressions":len(control),
                  "context_rows_per_variant":sum(x["candidate_rows"] for x in context)},indent=2))
