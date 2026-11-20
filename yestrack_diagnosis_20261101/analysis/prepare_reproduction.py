#!/usr/bin/env python3
"""Connect the released V2 resources to an isolated, read-only dataset view."""
import argparse
import csv
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, default=Path("analysis/config.json"))
a = p.parse_args()
c = json.loads(a.config.read_text())
t = Path(c["task_root"])
r = t / "analysis/resources/release/yestrack"
c.update(official_v2_adapter=str(r / "v2bestweight"),
         temprmot_star_candidates=str(r / "v2best_track_result"),
         released_v2_gt=str(r / "refer_kitti_motc_gt_v2"),
         released_v2_seqmap=str(r / "refer_kitti_motc_gt_v2/seqmaps/val.txt"),
         reproduction_physical_gpus=[3, 4])
adapter = json.loads((Path(c["official_v2_adapter"]) / "adapter_config.json").read_text())
assert adapter["base_model_name_or_path"] == "Qwen/Qwen3-VL-2B-Instruct"
assert (Path(c["official_v2_adapter"]) / "adapter_model.safetensors").is_file()
d = t / "analysis/resources/dataset_v2"
links = {
    d / "KITTI/training/image_02": Path(c["image_root"]),
    d / "KITTI/labels_with_ids/image_02": Path(c["labels_root"]),
    d / "expression": Path(c["expression_root"]),
}
for dst, src in links.items():
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.is_symlink():
        dst.symlink_to(src, target_is_directory=True)
    assert dst.resolve() == src.resolve()
c["dataset_root"] = str(d)
seqmap = list(csv.reader(Path(c["released_v2_seqmap"]).open()))
assert seqmap[0] == ["name"]
names = [",".join(x).strip() for x in seqmap[1:] if x]
assert len(names) == len(set(names)) == 862
inputs = Path(c["temprmot_star_candidates"])
actual = {f"{p.parent.parent.name}__{p.parent.name}" for p in inputs.glob("*/*/predict.txt")}
assert actual == set(names), "Released inputs must cover the complete official seqmap"
lengths = {s: len(list((Path(c["image_root"]) / s).glob("*.png"))) for s in c["val_sequences"]}
rows = []
for name in names:
    seq, expr = name.split("__", 1)
    f = inputs / seq / expr / "predict.txt"
    lines = f.read_text().splitlines()
    frames = [int(float(line.split(",", 1)[0])) for line in lines if line.strip()]
    if frames:
        assert min(frames) >= 1 and max(frames) <= lengths[seq], name
    gt = Path(c["released_v2_gt"]) / name / "gt/gt.txt"
    assert gt.is_file(), str(gt)
    rows.append({"name": name, "candidate_rows": len(frames),
                 "min_mot_frame": min(frames) if frames else None,
                 "max_mot_frame": max(frames) if frames else None,
                 "sequence_images": lengths[seq]})
report = {"released_seqmap_entries": len(names), "candidate_tasks": len(rows),
          "candidate_rows": sum(r["candidate_rows"] for r in rows),
          "mot_frame_start_one": 1, "image_frame_start_one": 0, "frame_offset": 0,
          "dataset_root": str(d), "tasks": rows}
(t / "analysis/reproduction_inputs.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
a.config.write_text(json.dumps(c, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({k: v for k, v in report.items() if k != "tasks"}, ensure_ascii=False, indent=2))
