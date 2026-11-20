#!/usr/bin/env python3
"""Audit reproduction provenance and annotation alignment without another model/metric run."""
import argparse
from collections import Counter
import configparser
import importlib.util
import json
from pathlib import Path
import subprocess

from PIL import Image

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, default=Path("analysis/config.json"))
p.add_argument("--output", type=Path, default=Path("analysis/reproduction_diagnosis.json"))
a = p.parse_args()
c = json.loads(a.config.read_text())
root = Path(c["task_root"])
upstream = root / c["upstream"]
result = json.loads((root / "analysis/runs/temprmot_star_paper_v2/result.json").read_text())
inputs = json.loads((root / "analysis/reproduction_inputs.json").read_text())
spec = importlib.util.spec_from_file_location("official_gt_parser", upstream / "tools/prepare_refer_kitti_motc_gt.py")
official = importlib.util.module_from_spec(spec)
spec.loader.exec_module(official)
boxes = {}
sequence_info = {}
geometry_issues = []
issues = []
local_rows = released_rows = 0
for entry in inputs["tasks"]:
    name = entry["name"]
    seq, expr = name.split("__", 1)
    released = Path(c["released_v2_gt"]) / name
    if seq not in boxes:
        ini = configparser.ConfigParser()
        ini.read(released / "seqinfo.ini")
        w, h = ini.getint("Sequence", "imWidth"), ini.getint("Sequence", "imHeight")
        length = ini.getint("Sequence", "seqLength")
        sizes = Counter()
        for image_path in sorted((Path(c["image_root"]) / seq).glob("*.png")):
            with Image.open(image_path) as im:
                sizes[im.size] += 1
        actual_sizes = [{"width": size[0], "height": size[1], "frames": n}
                        for size, n in sizes.items()]
        if set(sizes) != {(w, h)}:
            geometry_issues.append({"sequence": seq, "released_gt_size": [w, h],
                                    "actual_image_sizes": actual_sizes})
        assert length == entry["sequence_images"], (seq, length)
        boxes[seq] = official.read_labels_with_ids_boxes(c["labels_root"], seq, w, h)
        sequence_info[seq] = {"released_gt_width": w, "released_gt_height": h,
                              "frames": length, "actual_image_sizes": actual_sizes}
    expression = json.loads((Path(c["expression_root"]) / seq / f"{expr}.json").read_text())
    expected = {}
    for frame0, dets in boxes[seq].items():
        targets = {int(i) for i in expression["label"].get(str(frame0), [])}
        for oid, x, y, w, h in dets:
            if oid in targets:
                key = (frame0 + 1, oid)
                assert key not in expected, (name, key)
                expected[key] = tuple(f"{v:.3f}" for v in (x, y, w, h))
    observed = {}
    for line in (released / "gt/gt.txt").read_text().splitlines():
        if not line.strip():
            continue
        r = line.split(",")
        key = (int(float(r[0])), int(float(r[1])))
        assert key not in observed, (name, key)
        assert int(r[6]) == 1 and int(r[7]) == 1, (name, r)
        observed[key] = tuple(f"{float(v):.3f}" for v in r[2:6])
    local_rows += len(expected)
    released_rows += len(observed)
    if expected != observed:
        changed = sorted(k for k in expected.keys() | observed.keys() if expected.get(k) != observed.get(k))
        issues.append({"expression": name, "mismatched_object_frames": len(changed),
                       "examples": [{"frame1": k[0], "id": k[1], "local": expected.get(k),
                                     "released": observed.get(k)} for k in changed[:3]]})

adapter = json.loads((Path(c["official_v2_adapter"]) / "adapter_config.json").read_text())
changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=upstream, text=True).splitlines()
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip()
diagnosis = {
    "reproduction_gate_passed": result["within_tolerance"],
    "metrics": {k: result["metrics"][k] for k in ("HOTA", "DetA", "AssA")},
    "paper_gap_points": {k: result["metrics"][k] - result["paper"][k] for k in ("HOTA", "DetA", "AssA")},
    "upstream_commit": sha, "changed_upstream_tracked_files": changed,
    "seed": c["seed"], "protocol": c["paper_protocol"],
    "public_adapter": {"path": c["official_v2_adapter"],
                       "base_model": adapter["base_model_name_or_path"],
                       "r": adapter["r"], "lora_alpha": adapter["lora_alpha"],
                       "official_release_downloaded": True},
    "released_weight_configuration_note": c["released_weight_note"],
    "dataset_version": c["dataset_version"], "sequences": sequence_info,
    "image_geometry_matches_released_gt": not geometry_issues,
    "geometry_issues": geometry_issues,
    "expression_count": len(inputs["tasks"]), "candidate_rows": inputs["candidate_rows"],
    "annotation_alignment": {"local_positive_object_frames": local_rows,
                             "released_positive_object_frames": released_rows,
                             "mismatched_expressions": len(issues), "issues": issues,
                             "exact_at_released_box_precision": not issues,
                             "coordinate_reference": "Released seqinfo dimensions, matching the official GT conversion; image dimensions are audited separately."},
    "scope": "Provenance and annotation audit only. No new inference, threshold sweep, category analysis, or TrackEval run.",
    "causality": "Released V2 threshold calibration differs from the paper; the current run does not establish this as the unique cause of the HOTA discrepancy.",
}
a.output.write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in diagnosis.items() if k != "annotation_alignment"}, ensure_ascii=False, indent=2))
print(json.dumps({"annotation_alignment": {k: v for k, v in diagnosis["annotation_alignment"].items() if k != "issues"}}, indent=2))
assert sha == c["upstream_commit"] and not changed
assert local_rows == released_rows == int(result["metrics"]["GT_Dets"])
assert not issues, f"{len(issues)} expressions differ from released GT; see {a.output}"
if geometry_issues:
    raise SystemExit(2)
