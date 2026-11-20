#!/usr/bin/env python3
"""R13: compare existing metrics and correctly combine expression HOTA by video."""
from pathlib import Path
import json
from common import config, summary, hota_rows, combine_hota, save_json, log_run

c = config()
root = Path(c["task_root"])
d = root / "analysis/runs/temprmot_star_paper_v2/evaluation/tracker/default_t0p40"
local = summary(d / "pedestrian_summary.txt")
metric, rows = hota_rows(d / "pedestrian_detailed.csv", c)
assert len(rows) == 862
combined = combine_hota(metric, rows)
assert all(abs(combined[k]-local[k]) < 0.0006 for k in combined)
paper = {"HOTA": 41.78, "DetA": 32.69, "AssA": 53.75,
         "DetRe": 41.37, "DetPr": 58.10, "AssRe": 59.98, "AssPr": 81.07, "LocA": 87.17}
report = {"source": str(d), "gamma": 0.4, "seed": c["seed"], "expressions": len(rows),
          "comparison": {k: {"paper": p, "local": local[k], "difference_points": local[k]-p}
                         for k, p in paper.items()},
          "per_video": {s: combine_hota(metric, {n: r for n, r in rows.items() if n.startswith(s+"__")})
                        for s in c["val_sequences"]},
          "finding": "Detection precision is lower while detection recall is higher; the gap is primarily precision/false positives, not reduced detection recall.",
          "aggregation": "Official HOTA.combine_sequences over per-expression alpha arrays; not a mean of sequence HOTA."}
log_run(c, 13, "已有结果的精度/召回归因与逐视频 HOTA", [[c["reproduction_environment"], "analysis/r13_diagnostics.py"]],
        "CPU；不做新推理或新 TrackEval。论文附加对照数字由第二轮用户给定。")
save_json(root / "analysis/runs/R13/result.json", report)
print(json.dumps(report, ensure_ascii=False, indent=2))
