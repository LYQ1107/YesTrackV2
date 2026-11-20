#!/usr/bin/env python3
"""Prepare GT candidate tracks for stage 0 using the official GT box parser."""
import argparse
import configparser
import importlib.util
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, default=Path("analysis/config.json"))
a = p.parse_args()
c = json.loads(a.config.read_text())
root = Path(c["task_root"])

parser_path = root / c["upstream"] / "tools/prepare_refer_kitti_motc_gt.py"
spec = importlib.util.spec_from_file_location("yestrack_official_gt_parser", parser_path)
official = importlib.util.module_from_spec(spec)
spec.loader.exec_module(official)
inputs = json.loads((root / "analysis/reproduction_inputs.json").read_text())
out = root / "analysis/resources/gt_candidates_v2"
out.mkdir(parents=True, exist_ok=True)
sequence_boxes = {}
sequence_files = {}
summary = {"seed": c["seed"], "source_parser": str(parser_path), "frame_base": 1,
           "box_decimals": 3, "positive_mask_source": c["released_v2_gt"],
           "sequences": {}, "expressions": [], "candidate_rows": 0}


def link_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == source.resolve():
        return
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    target.symlink_to(source)


for entry in inputs["tasks"]:
    name = entry["name"]
    seq, expr = name.split("__", 1)
    gt_seq = Path(c["released_v2_gt"]) / name
    info = configparser.ConfigParser()
    info.read(gt_seq / "seqinfo.ini")
    width = info.getint("Sequence", "imWidth")
    height = info.getint("Sequence", "imHeight")
    length = info.getint("Sequence", "seqLength")
    if seq not in sequence_boxes:
        frames = official.read_labels_with_ids_boxes(c["labels_root"], seq, width, height)
        boxes = {}
        for frame0, dets in sorted(frames.items()):
            assert 0 <= frame0 < length, (seq, frame0, length)
            for oid, x, y, w, h in dets:
                key = (frame0 + 1, oid)
                assert key not in boxes, (seq, key)
                boxes[key] = tuple(f"{v:.3f}" for v in (x, y, w, h))
        file = out / "tracks" / f"{seq}.txt"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("".join(f"{f},{oid},{','.join(box)},1.0\n" for (f, oid), box in boxes.items()))
        sequence_boxes[seq] = boxes
        sequence_files[seq] = file
        summary["sequences"][seq] = {"width": width, "height": height, "frames": length,
                                      "candidate_rows": len(boxes), "track_file": str(file)}
    else:
        previous = summary["sequences"][seq]
        assert (width, height, length) == (previous["width"], previous["height"], previous["frames"])

    boxes = sequence_boxes[seq]
    positive = {}
    for line in (gt_seq / "gt/gt.txt").read_text().splitlines():
        if not line.strip():
            continue
        row = line.split(",")
        key = (int(row[0]), int(row[1]))
        box = tuple(f"{float(v):.3f}" for v in row[2:6])
        assert key not in positive, (name, key)
        assert key in boxes and boxes[key] == box, (name, key, box, boxes.get(key))
        positive[key] = box

    expression = json.loads((Path(c["expression_root"]) / seq / f"{expr}.json").read_text())
    labels = expression["label"]
    ids_by_frame = {int(f) + 1: {int(i) for i in ids} for f, ids in labels.items()}
    local_positive = {key for key in boxes if key[1] in ids_by_frame.get(key[0], set())}
    assert local_positive == set(positive), (name, "expression mask differs from released GT")
    link_file(sequence_files[seq], out / "results" / seq / expr / "predict.txt")
    link_file(gt_seq / "gt/gt.txt", out / "results" / seq / expr / "gt.txt")
    summary["expressions"].append({"name": name, "candidate_rows": len(boxes),
                                   "positive_rows": len(positive)})
    summary["candidate_rows"] += len(boxes)

assert len(summary["expressions"]) == len(inputs["tasks"]) == 862
summary["complete"] = True
summary["candidate_root"] = str(out / "results")
(out / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"expressions": len(summary["expressions"]), "candidate_rows": summary["candidate_rows"],
                  "candidate_root": summary["candidate_root"], "released_gt_match": True}, indent=2))
