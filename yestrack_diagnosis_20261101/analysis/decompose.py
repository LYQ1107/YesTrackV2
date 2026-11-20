#!/usr/bin/env python3
"""Official HOTA recombination, classwise counterfactuals and referring confusion."""
import csv
import json
from pathlib import Path

import numpy as np
from common import combine_hota, config, confusion, hota_rows, log_run, mot, save_json

c = config()
t = Path(c["task_root"])
b = json.loads((t / "analysis/local_baseline.json").read_text())
labels = json.loads((t / "analysis/labels/expressions.json").read_text())
gamma = b["gamma"]
tag = f"default_t{gamma:.2f}".replace(".","p")
metric, h1 = hota_rows(Path(b["evaluation"])/"tracker"/tag/"pedestrian_detailed.csv",c)
_, oracle = hota_rows(t/"analysis/runs/R20_oracles/eval_tracker_oracle/tracker"/tag/"pedestrian_detailed.csv",c)
_, h3 = hota_rows(t/"analysis/runs/R20_oracles/eval_h3/tracker"/tag/"pedestrian_detailed.csv",c)
h2_path = t/"analysis/runs/R17_h2/evaluation/tracker"/tag/"pedestrian_detailed.csv"
h2 = hota_rows(h2_path,c)[1] if (t/"analysis/runs/R17_h2/result.json").exists() else None
h1_total = combine_hota(metric,h1)
conf_tracker, conf_gt = {}, {}
empty_frames = empty_exprs = predicted_empty_frames = 0
empty_fp = empty_n = 0
empty_gt_alarms=empty_gt_fp=empty_gt_n=0
manifest = json.loads((t/"analysis/resources/gt_candidates_v2/manifest.json").read_text())
gt_tracks = {seq:mot(r["track_file"]) for seq,r in manifest["sequences"].items()}

for row in labels:
    name = row["name"]
    seq,expr = name.split("__",1)
    p = mot(Path(b["predictions"])/seq/expr/"predict_with_conf.txt")
    y = np.load(t/"analysis/runs/R20_oracles/candidate_labels"/seq/f"{expr}.npz")["y"]
    conf_tracker[name] = confusion(y,p[:,6],gamma)
    js = json.loads((Path(c["expression_root"])/seq/f"{expr}.json").read_text())
    mask = {int(f)+1:{int(x) for x in v} for f,v in js["label"].items()}
    gt_positive = mot(Path(c["released_v2_gt"])/name/"gt/gt.txt")
    frames_empty = set(range(1,row["sequence_frames"]+1)) - set(gt_positive[:,0].astype(int))
    empty_frames += len(frames_empty)
    empty_exprs += bool(frames_empty)
    sub = p[np.isin(p[:,0],list(frames_empty))]
    predicted_empty_frames += len(np.unique(sub[sub[:,6]>=gamma,0]))
    empty_fp += int((sub[:,6]>=gamma).sum())
    empty_n += len(sub)
    if h2 is not None:
        gt_p = mot(t/"analysis/runs/R17_h2/predictions"/seq/expr/"predict_with_conf.txt")
        tr = gt_tracks[seq]
        assert np.array_equal(gt_p[:,:2],tr[:,:2])
        gt_y = [int(r[1]) in mask.get(int(r[0]),set()) for r in tr]
        conf_gt[name] = confusion(gt_y,gt_p[:,6],gamma)
        gt_empty=gt_p[np.isin(gt_p[:,0],list(frames_empty))]
        empty_gt_alarms+=len(np.unique(gt_empty[gt_empty[:,6]>=gamma,0]))
        empty_gt_fp+=int((gt_empty[:,6]>=gamma).sum());empty_gt_n+=len(gt_empty)


def aggregate_conf(source, subset):
    if not source or not subset:
        return None
    totals={k:sum(source[n][k] for n in subset) for k in ("tp","fp","fn","tn","n")}
    tp,fp,fn,tn=[totals[k] for k in ("tp","fp","fn","tn")]
    return {**totals,"accuracy":(tp+tn)/(tp+fp+fn+tn),
            "precision":tp/(tp+fp) if tp+fp else None,
            "recall":tp/(tp+fn) if tp+fn else None,
            "f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


results={}
for cat in ["overall",*"ABCDEFGH"]:
    subset=[r["name"] for r in labels if cat=="overall" or cat in r["labels"]]
    a1=combine_hota(metric,{n:h1[n] for n in subset})
    a2=combine_hota(metric,{n:h2[n] for n in subset}) if h2 else None
    a3=combine_hota(metric,{n:h3[n] for n in subset})
    replaced={n:(oracle[n] if n in set(subset) else v) for n,v in h1.items()}
    total_replaced=combine_hota(metric,replaced)
    results[cat]={"expressions":len(subset),"expression_share":len(subset)/len(labels),
        "H1":a1,"H2":a2,"H3":a3,
        "H2_minus_H1":a2["HOTA"]-a1["HOTA"] if a2 and subset else None,
        "H3_minus_H2":a3["HOTA"]-a2["HOTA"] if a2 and subset else None,
        "oracle_referring_total":total_replaced,
        "delta_HOTA":total_replaced["HOTA"]-h1_total["HOTA"],
        "tracker_candidate_conditional_referring":aggregate_conf(conf_tracker,subset),
        "gt_track_referring":aggregate_conf(conf_gt,subset)}
out=t/"analysis/runs/R21_decomposition"
out.mkdir(parents=True,exist_ok=True)
save_json(out/"per_expression_confusion.json",{"tracker_candidates":conf_tracker,"gt_tracks":conf_gt})
subsets={
    "C_or_D":[r["name"] for r in labels if set(r["labels"]) & set("CD")],
    "F_without_C_D":[r["name"] for r in labels if "F" in r["labels"] and not set(r["labels"]) & set("CD")],
    "A_without_other_text_labels":[r["name"] for r in labels if "A" in r["labels"] and not set(r["labels"]) & set("BCDEH")],
    "C_scene":[r["name"] for r in labels if "C" in r["labels"] and any(x in r["sentence"] for x in ("bike","bicycle"))],
    "C_viewpoint":[r["name"] for r in labels if "C" in r["labels"] and not any(x in r["sentence"] for x in ("bike","bicycle"))]}
extra={}
for group,subset in subsets.items():
    changed=combine_hota(metric,{n:oracle[n] if n in set(subset) else v for n,v in h1.items()})
    extra[group]={"expressions":len(subset),"delta_HOTA":changed["HOTA"]-h1_total["HOTA"],
        "H1":combine_hota(metric,{n:h1[n] for n in subset}),
        "H2":combine_hota(metric,{n:h2[n] for n in subset}) if h2 else None,
        "gt_track_referring":aggregate_conf(conf_gt,subset)}
save_json(out/"result.json",{"reference":"相对本地基线","gamma":gamma,"categories":results,
    "additional_subsets":extra,
    "empty_frame_control":{"expressions_with_empty_frames":empty_exprs,"empty_expression_frames":empty_frames,
        "frames_with_false_alarm":predicted_empty_frames,"frame_false_alarm_rate":predicted_empty_frames/empty_frames,
        "false_positive_candidate_rows":empty_fp,"candidate_rows_on_empty_frames":empty_n,
        "candidate_false_positive_rate":empty_fp/empty_n if empty_n else None,
        "GT_candidate_frames_with_false_alarm":empty_gt_alarms if h2 else None,
        "GT_candidate_empty_frame_false_alarm_rate":empty_gt_alarms/empty_frames if h2 else None,
        "GT_candidate_FP_rows_on_empty_frames":empty_gt_fp if h2 else None,
        "GT_candidate_rows_on_empty_frames":empty_gt_n if h2 else None,
        "scope":"GT empty at a frame; not G expression (there are zero whole-video empty expressions)."},
    "method":"Native HOTA.combine_sequences; replace independent expression results with candidate-preserving Hungarian-IoU>=.5 referring oracle; overlapping class gains are not additive.",
    "h2_complete":h2 is not None})
with (out/"categories.csv").open("w") as f:
    w=csv.writer(f)
    w.writerow(["category","expressions","share","H1","H2","H3","delta_HOTA","tracker_P","tracker_R","tracker_F1","GT_P","GT_R","GT_F1"])
    for cat,r in sorted(results.items(),key=lambda kv:-kv[1]["delta_HOTA"]):
        ct=r["tracker_candidate_conditional_referring"] or {};cg=r["gt_track_referring"] or {}
        w.writerow([cat,r["expressions"],r["expression_share"],r["H1"]["HOTA"],
            r["H2"]["HOTA"] if r["H2"] else None,r["H3"]["HOTA"],r["delta_HOTA"],
            *[ct.get(k) for k in ("precision","recall","f1")],*[cg.get(k) for k in ("precision","recall","f1")]])
if not (out/"logged.txt").exists():
    log_run(c,21,"分类误差分解与候选保持的 ΔHOTA",[
        "CUDA_VISIBLE_DEVICES='' "+c["reproduction_environment"]+" analysis/decompose.py"],
        "从完整官方 TrackEval detailed CSV 调用原生 HOTA.combine_sequences 精确重算；"
        "H2 完成后同一命令更新 H2 及 GT tracks Acc/P/R。未按表达式 HOTA 做简单平均；重叠类别收益不可相加。")
    (out/"logged.txt").write_text("logged\n")
print(json.dumps({cat:{"n":r["expressions"],"delta_HOTA":r["delta_HOTA"],"H1":r["H1"]["HOTA"],
    "H2":r["H2"]["HOTA"] if r["H2"] else None} for cat,r in results.items()},indent=2))
