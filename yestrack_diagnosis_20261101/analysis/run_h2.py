#!/usr/bin/env python3
"""H2: run the original referring controller on complete released-coordinate GT tracks."""
import json
import argparse
import math
import os
from pathlib import Path
import shlex
import subprocess
import time

from common import config, log_run, official_eval, run_logged, save_json, summary

p = argparse.ArgumentParser();p.add_argument('--resume',action='store_true');options=p.parse_args()
c = config()
t = Path(c["task_root"])
official = t / c["upstream"]
baseline = json.loads((t / "analysis/local_baseline.json").read_text())
manifest = json.loads((t / "analysis/resources/gt_candidates_v2/manifest.json").read_text())
protocol = baseline["protocol"]
gpus = "3,4"
assert os.environ.get("CUDA_VISIBLE_DEVICES") == gpus
out = t / "analysis/runs/R17_h2"
out.mkdir(parents=True, exist_ok=True)
infer = [c["reproduction_environment"], "-u", "-m", "torch.distributed.run", "--standalone",
         "--nproc_per_node", "2", str(t / "analysis/observed_inference.py"),
         "--seed", str(c["seed"]), "--script", str(official / "refer_llm/llm_eval_from_mot.py"),
         "--trace-root", str(out / "raw_scores"), "--",
         "--model_name", c["base_model"], "--lora_path", c["official_v2_adapter"],
         "--data_root", c["dataset_root"], "--results_root", manifest["candidate_root"],
         "--mot_input_type", "results_root", "--mot_filename", "predict.txt",
         "--mot_frame_start_one", "1", "--image_frame_start_one", "0", "--frame_offset", "0",
         "--image_size", "320", "--margin_ratio", "0.2", "--video_n_frames", "4",
         "--re_refer_lower", "0.2", "--re_refer_thresh", "0.8", "--stability_enable",
         "--stability_window", "3", "--stability_thresh", "0.4", "--stability_boost", "0.3",
         "--infer_every_n_frames", "10", "--preprocess_workers", "4", "--vis_every", "0",
         "--output_root", str(out / "predictions")]
if options.resume:infer+=['--resume']
evaluate = official_eval(c, out / "predictions", out / "evaluation", [baseline["gamma"]])
estimate = 2.2 * manifest["candidate_rows"] / 1850576
log_run(c, 17, "H2：GT tracks + 官方 YesTrack referring", [
    "CUDA_VISIBLE_DEVICES=3,4 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false "
    + shlex.join([c["reproduction_environment"], "-u", "analysis/run_h2.py",*(['--resume'] if options.resume else [])]),
    "# 官方子进程工作目录：" + str(official),
    "# " + shlex.join(infer), "# " + shlex.join(evaluate)],
    f"GPU 阶段开始前预计 {estimate:.2f} 小时（保守范围 3–6 小时，低于 8 小时）；"
    "依据 R09 的 2.2 小时按完整候选数比例估算。物理 GPU 3、4；资源注册允许，启动前均空闲。"
    "同一发布 V2 权重、γ=0.6、TCP=3/.4/.3、TRP=10、video=4、refine=[.2,.8)。"
    "分析 wrapper 只记录官方 helper 原样返回的 frame/video 概率，不修改推理值或顺序。")
save_json(out / "commands.json", {"seed": c["seed"], "protocol": protocol, "inference": infer,
          "evaluation": evaluate, "cwd": str(official), "physical_gpus": [3, 4],
          "estimated_hours": estimate, "reference": "相对本地基线"})
started = time.time()
failures = []
with (out / "inference.log").open("w") as f:
    proc = subprocess.Popen(infer, cwd=official, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        f.write(line)
        f.flush()
        if "[ERR]" in line or "Traceback" in line:
            failures.append(line.strip())
            print(line, end="", flush=True)
    rc = proc.wait()
if rc or failures:
    raise RuntimeError(f"H2 inference failed: exit={rc}, first={failures[:1]}; see {out/'inference.log'}")
actual = {f"{f.parent.parent.name}__{f.parent.name}"
          for f in (out / "predictions").glob("*/*/predict_with_conf.txt")}
assert actual == {e["name"] for e in manifest["expressions"]}
total = 0
for entry in manifest["expressions"]:
    seq, expr = entry["name"].split("__", 1)
    lines = (out / "predictions" / seq / expr / "predict_with_conf.txt").read_text().splitlines()
    assert len(lines) == entry["candidate_rows"], entry["name"]
    for line in lines:
        row = line.split(",")
        assert len(row) == 7 and math.isfinite(float(row[6])) and 0 <= float(row[6]) <= 1
    total += len(lines)
assert total == manifest["candidate_rows"]
save_json(out / "coverage.json", {"complete": True, "expressions": len(actual), "candidate_rows": total})
print("[H2] Complete inference validated; evaluating with official TrackEval", flush=True)
run_logged(evaluate, official, out / "trackeval.log")
metrics = summary(out / f"evaluation/tracker/default_t{baseline['gamma']:.2f}".replace(".", "p")
                  / "pedestrian_summary.txt")
save_json(out / "result.json", {"metrics": metrics, "seed": c["seed"], "protocol": protocol,
                              "elapsed_seconds": time.time()-started, "reference": "相对本地基线"})
with (t / "analysis/runs.md").open("a") as f:
    f.write(f"\nR17 完成：HOTA={metrics['HOTA']:.3f}，DetA={metrics['DetA']:.3f}，"
            f"AssA={metrics['AssA']:.3f}；耗时 {(time.time()-started)/3600:.3f} 小时。\n")
print(json.dumps(metrics, ensure_ascii=False), flush=True)
