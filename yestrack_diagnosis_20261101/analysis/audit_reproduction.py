#!/usr/bin/env python3
"""Read-only resource and protocol audit. Does not run a model or compute results."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo


def command(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(args, cwd=cwd, text=True, check=True, capture_output=True).stdout.strip()


def literal_defaults(path: Path) -> dict:
    result = {}
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument" or not node.args:
            continue
        for kw in node.keywords:
            if kw.arg == "default":
                try:
                    result[ast.literal_eval(node.args[0])] = ast.literal_eval(kw.value)
                except (ValueError, TypeError):
                    pass  # Other argument defaults are expressions, not literal values.
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("analysis/config.json"))
    parser.add_argument("--output", type=Path, default=Path("analysis/preflight.json"))
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    task = Path(cfg["task_root"])
    upstream = task / cfg["upstream"]
    result = {
        "checked_at_asia_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "seed": cfg["seed"],
        "project_root": cfg["project_root"],
        "upstream_commit": command(["git", "rev-parse", "HEAD"], upstream),
        "upstream_status": command(["git", "status", "--porcelain"], upstream),
        "gpu_processes_launched": 0,
        "inference_or_analysis_run": False,
    }
    assert result["upstream_commit"] == cfg["upstream_commit"]
    assert result["upstream_status"] == "", "Official source has local modifications"
    split_ast = ast.parse((upstream / "tools/prepare_refer_kitti_motc_gt.py").read_text())
    splits = next(ast.literal_eval(n.value) for n in split_ast.body
                  if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                  and t.id == "DATASET_SPLITS" for t in n.targets))
    assert [f"{s:04d}" for s in splits["v2"]["val"]] == cfg["val_sequences"]
    expr_root, image_root, labels_root = (
        Path(cfg[k]) for k in ("expression_root", "image_root", "labels_root"))
    dataset = []
    for seq in cfg["train_sequences"] + cfg["val_sequences"]:
        expr = sorted((expr_root / seq).glob("*.json"))
        images = sorted((image_root / seq).glob("*.png"))
        labels = sorted((labels_root / seq).glob("*.txt"))
        row = {"sequence": seq, "split": "val" if seq in cfg["val_sequences"] else "train",
               "expressions": len(expr), "images": len(images), "label_files": len(labels),
               "image_label_stems_equal": {p.stem for p in images} == {p.stem for p in labels},
               "first_image": images[0].name if images else None,
               "last_image": images[-1].name if images else None}
        dataset.append(row)
    result["dataset_inventory"] = sorted(dataset, key=lambda r: r["sequence"])
    result["dataset_totals"] = {split: {k: sum(r[k] for r in dataset if r["split"] == split)
                                        for k in ("expressions", "images", "label_files")}
                                for split in ("train", "val")}
    # Include ignored and hidden files: pretrained weights are commonly gitignored.
    files = command(["rg", "--files", "--hidden", "--no-ignore",
                     "-g", "adapter_config.json", "-g", "*[Yy]es[Tt]rack*.zip",
                     *cfg["local_search_roots"]]).splitlines()
    adapters = []
    archives = []
    for f in files:
        p = Path(f)
        if p.suffix == ".zip":
            archives.append({"path": f, "bytes": p.stat().st_size})
            continue
        c = json.loads(p.read_text())
        adapters.append({"path": f, "base_model_name_or_path": c.get("base_model_name_or_path"),
                         "official_v2_folder_name": "v2bestweight" in str(p).lower(),
                         "weight_files": [q.name for q in p.parent.glob("adapter_model.*")]})
    result["local_adapter_inventory"] = adapters
    result["local_yestrack_archives"] = archives
    result["local_v2_named_adapters"] = [a for a in adapters if a["official_v2_folder_name"]]
    result["local_qwen3_vl_2b_adapters"] = [a for a in adapters if
        "qwen3-vl-2b" in str(a["base_model_name_or_path"]).lower()]
    model = Path(cfg["base_model"])
    result["base_model"] = {"path": str(model), "config_present": (model / "config.json").is_file(),
                            "weight_bytes": (model / "model.safetensors").stat().st_size}
    env_python = Path(cfg["candidate_environment"])
    env_code = (
        "import importlib.metadata as m, json, sys\n"
        "names=['torch','transformers','peft','Pillow','numpy','scipy','accelerate']\n"
        "versions={}\n"
        "for n in names:\n"
        " try: versions[n]=m.version(n)\n"
        " except m.PackageNotFoundError: versions[n]=None\n"
        "print(json.dumps({'python':sys.version,'packages':versions}))\n"
    )
    result["candidate_environment"] = json.loads(command([str(env_python), "-c", env_code]))
    infer_defaults = literal_defaults(upstream / "refer_llm/llm_eval_from_mot.py")
    keys = ["--image_size", "--margin_ratio", "--video_n_frames", "--stability_window",
            "--stability_thresh", "--stability_boost", "--infer_every_n_frames",
            "--re_refer_lower", "--re_refer_thresh", "--mot_frame_start_one",
            "--image_frame_start_one", "--frame_offset", "--prompt_single_tpl", "--prompt_video_tpl"]
    result["upstream_inference_defaults"] = {k: infer_defaults.get(k) for k in keys}
    eval_defaults = literal_defaults(upstream / "eval_refer_kitti_mot.py")
    result["upstream_metric_defaults"] = {k: eval_defaults.get(k) for k in
                                         ("--min-area", "--offset", "--classes", "--thresholds")}
    result["paper_v2_results"] = cfg["paper_v2_results"]
    result["required_resources"] = {key: cfg[key] for key in (
        "official_v2_adapter", "temprmot_star_candidates", "yestrack_mot_candidates",
        "released_v2_gt", "released_v2_seqmap")}
    result["status"] = "REPRODUCTION_NOT_STARTED_MISSING_OFFICIAL_ASSETS"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "upstream_commit", "dataset_totals",
                      "local_v2_named_adapters", "local_yestrack_archives", "base_model",
                      "candidate_environment")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
