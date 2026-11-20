#!/usr/bin/env python3
"""Make candidate-preserving referring oracles and a perfect-GT sanity evaluation."""
import json
from pathlib import Path
import shlex
import time

import numpy as np
from scipy.optimize import linear_sum_assignment
from common import config, log_run, mot, names, official_eval, run_logged, save_json, summary

c = config()
t = Path(c["task_root"])
baseline = json.loads((t / "analysis/local_baseline.json").read_text())
manifest = json.loads((t / "analysis/resources/gt_candidates_v2/manifest.json").read_text())
tracks = {seq: mot(r["track_file"]) for seq, r in manifest["sequences"].items()}
out = t / "analysis/runs/R20_oracles"
out.mkdir(parents=True, exist_ok=True)
log_run(c,20,"候选保持不变的 referring oracle 与 H3 sanity",[
    "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 " + shlex.join([c["reproduction_environment"],
    "-u", "analysis/prepare_oracles.py"])],
    "CPU；全 862 表达式；候选框/轨迹 ID/帧不变，逐帧 Hungarian 最大 IoU 匹配完整 GT，IoU>=0.5 后按表达式真值赋 oracle 0/1。"
    "H3 复制发布 GT 的原始小数框而非推理入口的整数框，仍使用官方 area>=20、统一类别和完整 seqmap。"
    "分类别 ΔHOTA 将用官方 HOTA.combine_sequences 替换对应独立表达式结果后精确重聚合。")


def ious(a, b):
    lo = np.maximum(a[:, None, :2], b[None, :, :2])
    hi = np.minimum(a[:, None, :2]+a[:, None, 2:4], b[None, :, :2]+b[None, :, 2:4])
    inter = np.prod(np.maximum(0, hi-lo), axis=-1)
    area_a = a[:, 2]*a[:, 3]
    area_b = b[:, 2]*b[:, 3]
    return inter / np.maximum(area_a[:, None]+area_b[None, :]-inter, 1e-12)


mapping = {}
for seq in c["val_sequences"]:
    first = next(n for n in names(c) if n.startswith(seq+"__"))
    expr = first.split("__", 1)[1]
    rows = mot(Path(baseline["predictions"]) / seq / expr / "predict_with_conf.txt")
    truth = tracks[seq]
    ids = np.full(len(rows), -1, dtype=np.int64)
    match_iou = np.zeros(len(rows))
    for frame in np.unique(rows[:, 0]):
        ix = np.flatnonzero(rows[:, 0] == frame)
        gt = truth[truth[:, 0] == frame]
        if not len(gt):
            continue
        sims = ious(rows[ix, 2:6], gt[:, 2:6])
        rr, cc = linear_sum_assignment(-sims)
        keep = sims[rr, cc] >= 0.5
        ids[ix[rr[keep]]] = gt[cc[keep], 1].astype(int)
        match_iou[ix[rr[keep]]] = sims[rr[keep], cc[keep]]
    mapping[seq] = (rows[:, :6], ids, match_iou)

counts = {"expressions": 0, "candidate_rows": 0, "candidate_positive_rows": 0,
          "unmatched_candidate_rows": 0, "gt_rows": 0, "gt_rows_below_min_area": 0}
for name in names(c):
    seq, expr = name.split("__", 1)
    base = mot(Path(baseline["predictions"]) / seq / expr / "predict_with_conf.txt")
    boxes, ids, quality = mapping[seq]
    assert np.array_equal(base[:, :6], boxes), name
    js = json.loads((Path(c["expression_root"]) / seq / f"{expr}.json").read_text())
    mask = {int(f)+1: {int(x) for x in v} for f, v in js["label"].items()}
    y = np.array([oid >= 0 and int(oid) in mask.get(int(f), set()) for f, oid in zip(base[:, 0], ids)])
    oracle = base.copy()
    oracle[:, 6] = y
    target = out / "tracker_oracle" / seq / expr / "predict_with_conf.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(target, oracle, delimiter=",", fmt=["%d"]*6+["%.6f"])
    label_file = out / "candidate_labels" / seq / f"{expr}.npz"
    label_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(label_file, y=y, matched_gt_id=ids, matched_iou=quality)
    gt = mot(Path(c["released_v2_gt"]) / name / "gt/gt.txt")
    perfect = np.column_stack([gt[:, :6], np.ones(len(gt))])
    target = out / "h3" / seq / expr / "predict_with_conf.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(target, perfect, delimiter=",", fmt=["%d", "%d"]+["%.3f"]*4+["%.6f"])
    counts["expressions"] += 1
    counts["candidate_rows"] += len(base)
    counts["candidate_positive_rows"] += int(y.sum())
    counts["unmatched_candidate_rows"] += int((ids < 0).sum())
    counts["gt_rows"] += len(gt)
    counts["gt_rows_below_min_area"] += int((gt[:, 4]*gt[:, 5] < 20).sum())
save_json(out / "counts.json", counts)
results = {}
commands = []
for stage, pred in (("tracker_oracle", out / "tracker_oracle"), ("h3", out / "h3")):
    command = official_eval(c, pred, out / f"eval_{stage}", [baseline["gamma"]])
    commands.append(command)
    print(f"[R20] Official TrackEval {stage}", flush=True)
    run_logged(command, t / c["upstream"], out / f"{stage}_trackeval.log")
    tag = f"default_t{baseline['gamma']:.2f}".replace(".", "p")
    results[stage] = summary(out / f"eval_{stage}" / "tracker" / tag / "pedestrian_summary.txt")
save_json(out / "commands.json", {"commands": commands, "seed": c["seed"]})
save_json(out / "result.json", {"metrics": results, "coverage": counts,
                              "reference": "相对本地基线", "matching_iou": 0.5})
print(json.dumps({"coverage": counts, "metrics": {k: {m:v[m] for m in ('HOTA','DetA','AssA')}
                                               for k,v in results.items()}}, indent=2), flush=True)
