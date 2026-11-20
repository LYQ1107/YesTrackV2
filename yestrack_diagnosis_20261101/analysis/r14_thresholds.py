#!/usr/bin/env python3
"""R14: official evaluation only; choose only between fixed gamma .4 and README .6."""
from pathlib import Path
import json
import os
from common import config, official_eval, run_logged, summary, save_json, log_run

c = config()
root = Path(c["task_root"])
out = root / "analysis/runs/R14"
out.mkdir(parents=True, exist_ok=True)
pred = root / "analysis/runs/temprmot_star_paper_v2/predictions"
assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
upstream = root / c["upstream"]
source = (upstream / "refer_llm/llm_eval_from_mot.py").read_text()
assert '"--gamma"' not in source and '"--thresholds"' not in source
recommended = official_eval(c, pred, out / "recommended", [0.6])
scan = official_eval(c, pred, out / "sensitivity", [0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
log_run(c, 14, "发布推荐 γ=0.6 重评测及固定附表扫描", [
    "CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 " + c["reproduction_environment"] + " -u analysis/r14_thresholds.py"],
    "CPU only。γ 仅在 eval_refer_kitti_mot.py:206、229–255 和 13–30 的结果过滤生效；推理入口无 γ 参数，1183 行原样保存连续分数。只在 0.4/预给定 0.6 之间按授权选择；扫描不用于选基线。预计约 15–30 分钟。")
save_json(out / "commands.json", {"cwd": str(upstream), "recommended": recommended, "sensitivity": scan,
                                   "environment": {"CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "2"}})
print("[R14] Evaluate pre-specified README gamma=0.6", flush=True)
run_logged(recommended, upstream, out / "recommended.log")
m06 = summary(out / "recommended/tracker/default_t0p60/pedestrian_summary.txt")
print("[R14] gamma=0.6:", json.dumps({k:m06[k] for k in ("HOTA","DetA","AssA")}), flush=True)
print("[R14] Sensitivity appendix 0.3..0.8", flush=True)
run_logged(scan, upstream, out / "sensitivity.log")
scanned = {str(g): summary(out / "sensitivity/tracker" / ("default_t"+f"{g:.2f}".replace(".","p")) / "pedestrian_summary.txt")
           for g in [0.3,0.4,0.5,0.6,0.7,0.8]}
m04 = summary(root / "analysis/runs/temprmot_star_paper_v2/evaluation/tracker/default_t0p40/pedestrian_summary.txt")
assert all(scanned["0.4"][k] == m04[k] and scanned["0.6"][k] == m06[k] for k in ("HOTA","DetA","AssA"))
gamma = 0.6 if m06["HOTA"] > m04["HOTA"] else 0.4
baseline = {"gamma": gamma, "rule": "README .6 if HOTA exceeds fixed .4; sensitivity grid never selects gamma",
            "label": "发布权重推荐值" if gamma == 0.6 else "原本地固定值",
            "reference": "相对本地基线", "seed": c["seed"], "tracker": "TempRMOT_star",
            "predictions": str(pred), "metrics": m06 if gamma == 0.6 else m04,
            "evaluation": str(out / "recommended" if gamma == 0.6 else root / "analysis/runs/temprmot_star_paper_v2/evaluation"),
            "protocol": {**c["paper_protocol"], "gamma": gamma}}
save_json(root / "analysis/local_baseline.json", baseline)
save_json(out / "result.json", {"baseline": baseline, "recommended": m06, "sensitivity_appendix_only": scanned,
                                "code_evidence": {"threshold_argument": "eval_refer_kitti_mot.py:206",
                                                  "score_filter": "eval_refer_kitti_mot.py:13-30",
                                                  "threshold_loop": "eval_refer_kitti_mot.py:229-255",
                                                  "continuous_output": "refer_llm/llm_eval_from_mot.py:1183"}})
with (root / "analysis/runs.md").open("a") as f:
    f.write(f"\nR14 完成：γ=.4 HOTA={m04['HOTA']:.3f}；预指定 γ=.6 HOTA={m06['HOTA']:.3f}。冻结本地 γ={gamma}（{baseline['label']}）。扫描结果仅附表，见 R14/result.json。\n")
print(json.dumps({"gamma06": {k:m06[k] for k in ("HOTA","DetA","AssA")}, "local_baseline_gamma": gamma,
                  "sensitivity": {g:{k:m[k] for k in ("HOTA","DetA","AssA")} for g,m in scanned.items()}}, indent=2), flush=True)
