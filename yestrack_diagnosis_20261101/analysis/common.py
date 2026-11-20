"""Shared I/O and official TrackEval aggregation for the local-baseline analysis."""
import csv
import json
from pathlib import Path
import shlex
import subprocess
import sys

import numpy as np


def config(path="analysis/config.json"):
    return json.loads(Path(path).read_text())


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def names(c):
    with Path(c["released_v2_seqmap"]).open() as f:
        return [",".join(row).strip() for row in list(csv.reader(f))[1:] if row]


def mot(path):
    path = Path(path)
    if not path.read_text().strip():
        return np.empty((0, 7), dtype=np.float64)
    return np.loadtxt(path, delimiter=",", ndmin=2)


def summary(path):
    rows = Path(path).read_text().splitlines()
    return {k: float(v) for k, v in zip(rows[0].split(), rows[1].split())}


def hota_rows(path, c):
    sys.path.insert(0, str(Path(c["task_root"]) / c["upstream"] / "TrackEval"))
    from trackeval.metrics.hota import HOTA
    metric = HOTA()
    data = {}
    with Path(path).open() as f:
        for row in csv.DictReader(f):
            name = row["seq"]
            if "__" not in name:
                continue
            res = {field: np.array([float(row[f"{field}___{int(round(a*100))}"])
                                    for a in metric.array_labels])
                   for field in metric.float_array_fields + metric.integer_array_fields}
            res.update({field: float(row[field]) for field in metric.float_fields})
            data[name] = res
    return metric, data


def combine_hota(metric, data):
    if not data:
        return {k: None for k in ("HOTA", "DetA", "AssA", "DetRe", "DetPr", "AssRe", "AssPr", "LocA")}
    res = metric.combine_sequences(data)
    return {k: float(np.mean(res[k]) * 100) for k in
            ("HOTA", "DetA", "AssA", "DetRe", "DetPr", "AssRe", "AssPr", "LocA")}


def log_run(c, number, title, commands, note=""):
    with (Path(c["task_root"]) / "analysis/runs.md").open("a") as f:
        f.write(f"\n## R{number}：{title}\n\nseed={c['seed']}。{note}\n\n```bash\n")
        f.write("cd " + shlex.quote(c["task_root"]) + "\n")
        for cmd in commands:
            f.write((shlex.join(cmd) if isinstance(cmd, list) else cmd) + "\n")
        f.write("```\n")


def official_eval(c, predictions, out, thresholds):
    root = Path(c["task_root"])
    return [c["reproduction_environment"], "-u", str(root / c["upstream"] / "eval_refer_kitti_mot.py"),
            "--refer-root", str(predictions), "--refer-structure", "nested",
            "--gt-folder", c["released_v2_gt"], "--seqmap-file", c["released_v2_seqmap"],
            "--out-dir", str(out), "--split", "val", "--offset", "0", "--min-area", "20",
            "--classes", "pedestrian", "--thresholds", *map(str, thresholds)]


def run_logged(cmd, cwd, log):
    with Path(log).open("w") as f:
        subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, check=True)


def confusion(y, p, gamma):
    y = np.asarray(y, dtype=bool)
    pred = np.asarray(p) >= gamma
    tp, fp = int(np.sum(y & pred)), int(np.sum(~y & pred))
    fn, tn = int(np.sum(y & ~pred)), int(np.sum(~y & ~pred))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": len(y),
            "accuracy": (tp+tn)/len(y) if len(y) else None,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
