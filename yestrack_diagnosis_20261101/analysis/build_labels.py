#!/usr/bin/env python3
"""Keyword proposal, frozen LLM semantic review, and annotation-derived F/G labels."""
import argparse
import csv
import json
from pathlib import Path
import re

import numpy as np
from common import config, log_run, mot, names, save_json

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--review", type=Path)
a = p.parse_args()
c = config()
t = Path(c["task_root"])
out = t / "analysis/labels"
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads((t / "analysis/resources/gt_candidates_v2/manifest.json").read_text())
tracks = {seq: mot(row["track_file"]) for seq, row in manifest["sequences"].items()}
rules = {
    "A": r"\b(car|cars|vehicle|vehicles|automobile|automobiles|auto|autos|sedan|sedans|truck|trucks|van|vans|suv|suvs|bus|buses|pedestrian|pedestrians|person|people|man|men|woman|women|black|white|red|blue|green|silver|gray|grey|light|dark|taxi)\b",
    "B": r"\b(left|right|leftside|rightside|opposite lane|oncoming lane|front|behind|ahead|near|far|side|across|center|middle|intersection|crossroad)\b",
    "C": r"\b(ego|our|us|ours|own|my|me|camera|another|other car|other vehicle|other automobile|other pedestrian|each other|following|follow|beside|between|alongside|adjacent|next to|relative to)\b",
    "D": r"\b(leftmost|rightmost|closest|nearest|farthest|furthest|fastest|slowest|biggest|largest|smallest|tallest|shortest|most|least|closer|further|farther|nearer|faster|slower|bigger|larger|smaller|more|less|first|second|third|last|frontmost|rearmost)\b",
    "E": r"\b(mov\w*|driv\w*|travel\w*|turn\w*|park\w*|stop\w*|accelerat\w*|decelerat\w*|run\w*|walk\w*|stand\w*|wait\w*|go|going|goes|head\w*|coming|approach\w*|stationary|motion\w*|transit|proceed\w*|overtak\w*|follow\w*|speed\w*|cross\w*|pass\w*|depart\w*)\b",
    "H": r"\b(all|both|two|three|four|five|six|seven|eight|nine|ten|several|multiple|group|groups|pair|pairs|couple|cluster|line of|row of|at least|at most)\b|\b[2-9]\b",
}
compiled = {k: re.compile(v, re.I) for k, v in rules.items()}
review = json.loads(a.review.read_text()) if a.review else None
if review:
    assert review["seed"] == c["seed"]
    assert set(review["reviewed_names"]) == set(names(c))
    overrides = review["overrides"]
else:
    overrides = {}
rows = []
switches = []
for i, name in enumerate(names(c)):
    seq, expr = name.split("__", 1)
    record = json.loads((Path(c["expression_root"]) / seq / f"{expr}.json").read_text())
    sentence = re.sub(r"[_-]+", " ", expr)
    mask = {int(f)+1: {int(x) for x in ids} for f, ids in record["label"].items()}
    tr = tracks[seq]
    y = np.array([int(row[1]) in mask.get(int(row[0]), set()) for row in tr])
    positives = int(y.sum())
    gt_rows = mot(Path(c["released_v2_gt"]) / name / "gt/gt.txt")
    assert positives == len(gt_rows), name
    local_switches = []
    for oid in np.unique(tr[:, 1]):
        indices = np.flatnonzero(tr[:, 1] == oid)
        order = indices[np.argsort(tr[indices, 0])]
        changed = np.flatnonzero(y[order][1:] != y[order][:-1]) + 1
        for j in changed:
            old, new = order[j-1], order[j]
            local_switches.append({"name": name, "id": int(oid),
                "previous_frame": int(tr[old, 0]), "frame": int(tr[new, 0]),
                "gap": int(tr[new, 0]-tr[old, 0]), "from": int(y[old]), "to": int(y[new])})
    keyword = sorted(k for k, rule in compiled.items() if rule.search(sentence))
    semantic = overrides.get(name, {}).get("labels", keyword)
    assert set(semantic) <= set("ABCDEH"), (name, semantic)
    labels = sorted(set(semantic) | ({"F"} if local_switches else set()) | ({"G"} if not positives else set()))
    row = {"index": i, "name": name, "sequence": seq, "sentence": sentence,
           "keyword_labels": keyword, "labels": labels, "candidate_rows_gt": len(tr),
           "positive_object_frames": positives, "positive_image_frames": len(np.unique(gt_rows[:, 0])) if positives else 0,
           "sequence_frames": manifest["sequences"][seq]["frames"],
           "switch_count": len(local_switches), "contiguous_switch_count": sum(s["gap"] == 1 for s in local_switches),
           "review_note": overrides.get(name, {}).get("note", "")}
    rows.append(row)
    switches.extend(local_switches)
save_json(out / ("expressions.json" if review else "keyword_proposals.json"), rows)
save_json(out / "truth_switches.json", switches)
if not review:
    (out / "semantic_review_input.txt").write_text("\n".join(
        f"{r['index']:03d}\t{r['name']}\t{''.join(r['keyword_labels'])}" for r in rows)+"\n")
else:
    rng = np.random.default_rng(c["seed"])
    selected = rng.choice(len(rows), 100, replace=False)
    with (t / "analysis/label_audit.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "sentence", "keyword_labels", "final_labels", "positive_object_frames",
                         "truth_switches", "llm_note", "human_labels", "human_notes"])
        for i in selected:
            r = rows[i]
            writer.writerow([r["name"], r["sentence"], ";".join(r["keyword_labels"]),
                ";".join(r["labels"]), r["positive_object_frames"], r["switch_count"], r["review_note"], "", ""])
total_positive = sum(r["positive_object_frames"] for r in rows)
distribution = {}
for cat in "ABCDEFGH":
    subset = [r for r in rows if cat in r["labels"]]
    distribution[cat] = {"expressions": len(subset), "expression_share": len(subset)/len(rows),
        "positive_object_frames": sum(r["positive_object_frames"] for r in subset),
        "positive_object_frame_share": sum(r["positive_object_frames"] for r in subset)/total_positive,
        "positive_image_frames": sum(r["positive_image_frames"] for r in subset),
        "expression_image_frames": sum(r["sequence_frames"] for r in subset)}
save_json(out / ("distribution.json" if review else "keyword_distribution.json"), distribution)
print(json.dumps({"expressions": len(rows), "positive_object_frames": total_positive,
                  "distribution": distribution, "switches": len(switches)}, ensure_ascii=False, indent=2))
if review:
    log_run(c,18,"表达式多标签与 100 条人工审计样本",[[c["reproduction_environment"],
        "analysis/build_labels.py", "--review", str(a.review)]],
        "先跑关键词规则，再由当前 Codex LLM 逐条语义审核；冻结审核输出可重放。"
        "F 仅由同一可见 GT ID 的真值切换得到（跨可见性空档的切换另记 gap）；G 从发布 GT 空集合得到。"
        "A 含明确类别约束；H 只标明示群体/数量，不把普通复数一律当作计数。")
