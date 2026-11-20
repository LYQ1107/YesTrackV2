#!/usr/bin/env python3
"""Run the unmodified V2 TempRMOT* referring entry point and its TrackEval gate."""
import argparse
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, default=Path("analysis/config.json"))
a = p.parse_args()
c = json.loads(a.config.read_text())
t = Path(c["task_root"])
official = t / c["upstream"]
python = c["reproduction_environment"]
gpus = ",".join(str(g) for g in c["reproduction_physical_gpus"])
assert os.environ.get("CUDA_VISIBLE_DEVICES") == gpus
assert len(c["reproduction_physical_gpus"]) <= c["max_project_physical_gpus"]
out = t / "analysis/runs/temprmot_star_paper_v2"
out.mkdir(parents=True, exist_ok=True)
protocol = c["paper_protocol"]
infer = [python, "-u", "-m", "torch.distributed.run", "--standalone", "--nproc_per_node",
         str(len(c["reproduction_physical_gpus"])), str(t / "analysis/seeded_run.py"),
         "--seed", str(c["seed"]), "--script", str(official / "refer_llm/llm_eval_from_mot.py"), "--",
         "--model_name", c["base_model"], "--lora_path", c["official_v2_adapter"],
         "--data_root", c["dataset_root"], "--results_root", c["temprmot_star_candidates"],
         "--mot_input_type", "results_root", "--mot_filename", "predict.txt",
         "--mot_frame_start_one", "1", "--image_frame_start_one", "0", "--frame_offset", "0",
         "--image_size", str(protocol["image_size"]), "--margin_ratio", str(protocol["margin_ratio_from_official_code"]),
         "--video_n_frames", str(protocol["video_n_frames"]),
         "--re_refer_lower", str(protocol["re_refer_lower"]), "--re_refer_thresh", str(protocol["re_refer_thresh"]),
         "--stability_enable", "--stability_window", str(protocol["stability_window"]),
         "--stability_thresh", str(protocol["stability_thresh"]), "--stability_boost", str(protocol["stability_boost"]),
         "--infer_every_n_frames", str(protocol["infer_every_n_frames"]),
         "--preprocess_workers", "4", "--vis_every", "0", "--output_root", str(out / "predictions")]
evaluate = [python, "-u", str(official / "eval_refer_kitti_mot.py"),
            "--refer-root", str(out / "predictions"), "--refer-structure", "nested",
            "--gt-folder", c["released_v2_gt"], "--seqmap-file", c["released_v2_seqmap"],
            "--out-dir", str(out / "evaluation"), "--split", "val", "--offset", "0",
            "--min-area", "20.0", "--classes", "pedestrian", "--thresholds", str(protocol["gamma"])]
commands = {"inference": infer, "evaluation": evaluate, "cwd": str(official),
            "CUDA_VISIBLE_DEVICES": gpus, "seed": c["seed"], "configuration": c}
(out / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2)+"\n")
with (t / "analysis/runs.md").open("a") as f:
    f.write("\n## R09：TempRMOT* V2 完整论文参数复现\n\n")
    f.write(f"GPU={gpus}，seed={c['seed']}，所有 862 个官方 seqmap 条目。控制器命令见下；实际子进程从官方仓库目录执行，命令展开如下。\n\n```bash\n")
    f.write(f"cd {shlex.quote(str(official))}\n")
    for cmd in (infer, evaluate):
        f.write("CUDA_VISIBLE_DEVICES="+gpus+" OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false "+shlex.join(cmd)+"\n")
    f.write("```\n\n结果：待控制器完成。官方入口、权重和推理逻辑不修改，失败任务及输出缺失会使控制器失败；不使用 subset seqmap。\n")


def run(cmd, log):
    print("[stage0] Running:", shlex.join(cmd), flush=True)
    last_notice = 0.0
    failures = []
    with log.open("w") as f:
        proc = subprocess.Popen(cmd, cwd=official, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            f.write(line)
            f.flush()
            now = time.monotonic()
            if "[ERR]" in line:
                failures.append(line.strip())
                print(line, end="", flush=True)
            elif line.startswith(("[OK]", "[TIME]")) and now-last_notice > 30:
                print(line, end="", flush=True)
                last_notice = now
        status = proc.wait()
    if status:
        raise RuntimeError(f"Command exited {status}; full output: {log}")
    if failures:
        raise RuntimeError(f"Official inference failed on {len(failures)} tasks; first: {failures[0]}")


started = time.time()
run(infer, out / "inference.log")
inputs = json.loads((t / "analysis/reproduction_inputs.json").read_text())
pred = out / "predictions"
actual = {f"{f.parent.parent.name}__{f.parent.name}" for f in pred.glob("*/*/predict_with_conf.txt")}
assert actual == {r["name"] for r in inputs["tasks"]}
total = 0
for entry in inputs["tasks"]:
    seq, expr = entry["name"].split("__", 1)
    path = pred / seq / expr / "predict_with_conf.txt"
    lines = [line.split(",") for line in path.read_text().splitlines() if line.strip()]
    assert len(lines) == entry["candidate_rows"], str(path)
    assert all(len(r) == 7 and math.isfinite(float(r[6])) and 0 <= float(r[6]) <= 1 for r in lines), str(path)
    total += len(lines)
assert total == inputs["candidate_rows"]
coverage = {"tasks": len(actual), "candidate_rows": total, "complete": True}
(out / "coverage.json").write_text(json.dumps(coverage, indent=2)+"\n")
print("[stage0] Full output coverage validated:", coverage, flush=True)
run(evaluate, out / "trackeval.log")
summary = out / "evaluation/tracker/default_t0p40/pedestrian_summary.txt"
rows = summary.read_text().splitlines()
metrics = {k: float(v) for k, v in zip(rows[0].split(), rows[1].split())}
paper = c["paper_v2_results"]["TempRMOT_star"]
gap = metrics["HOTA"] - paper["HOTA"]
result = {"tracker": "TempRMOT_star", "protocol": "paper_v2_gamma0.4",
          "seed": c["seed"], "coverage": coverage, "metrics": metrics, "paper": paper,
          "HOTA_gap_points": gap, "tolerance_points": c["hota_stop_tolerance_points"],
          "within_tolerance": abs(gap) <= c["hota_stop_tolerance_points"],
          "elapsed_seconds": time.time()-started, "other_tracker_gate_complete": False}
(out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
with (t / "analysis/runs.md").open("a") as f:
    f.write(f"\nR09 完成：HOTA={metrics['HOTA']:.5f}，DetA={metrics['DetA']:.5f}，AssA={metrics['AssA']:.5f}；论文 HOTA 差={gap:+.5f}，是否通过 1.5 门槛={result['within_tolerance']}。完整结果：`analysis/runs/temprmot_star_paper_v2/result.json`。\n")
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
if not result["within_tolerance"]:
    print("[stage0] STOP: paper HOTA discrepancy exceeds 1.5; no downstream analysis launched.", flush=True)
