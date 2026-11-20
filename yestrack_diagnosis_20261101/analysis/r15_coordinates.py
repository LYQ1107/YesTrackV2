#!/usr/bin/env python3
"""R15: released candidate/GT extents and crop coordinate deltas, without inference."""
from pathlib import Path
import importlib.util
import json
import numpy as np
from common import config, names, mot, save_json, log_run

c = config()
root = Path(c["task_root"])
spec = importlib.util.spec_from_file_location("official_crop", root/c["upstream"]/"refer_llm/crop_utils.py")
crop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crop)
nominal = np.array([1242,375,1242,375],dtype=float)
native = np.array([1238,374,1238,374],dtype=float)
scale = native/nominal
data = {"candidates": {}, "gt": {}}
for name in names(c):
    seq, expr = name.split("__",1)
    if seq != "0019":
        continue
    for key,path in [("candidates",Path(c["temprmot_star_candidates"])/seq/expr/"predict.txt"),
                     ("gt",Path(c["released_v2_gt"])/name/"gt/gt.txt")]:
        for row in mot(path):
            data[key][tuple(row[:6])] = row[2:6]
report = {"seed":c["seed"], "nominal_size":[1242,375], "native_size":[1238,374], "box_sources":{}}
for key, items in data.items():
    boxes = np.array(list(items.values()))
    ends = boxes[:,:2]+boxes[:,2:]
    shifts = []
    bounds_only = []
    raw_shift = []
    for b in boxes:
        a = np.array(crop.xywh_to_xyxy_with_margin(tuple(b),(1242,375),margin_ratio=.2,min_side=8))
        b_native = b*scale
        z = np.array(crop.xywh_to_xyxy_with_margin(tuple(b_native),(1238,374),margin_ratio=.2,min_side=8))
        same = np.array(crop.xywh_to_xyxy_with_margin(tuple(b),(1238,374),margin_ratio=.2,min_side=8))
        shifts.append(a-z)
        bounds_only.append(a-same)
        raw = np.array([b[0],b[1],b[0]+b[2],b[1]+b[3]])
        raw_shift.append(raw*(1-scale))
    shifts=np.array(shifts); bounds_only=np.array(bounds_only); raw_shift=np.array(raw_shift)
    report["box_sources"][key] = {"unique_frame_id_box_rows":len(boxes), "max_x2":float(ends[:,0].max()),
        "max_y2":float(ends[:,1].max()),
        "beyond_native_x2":int(np.sum(ends[:,0]>1238+.002)), "beyond_native_y2":int(np.sum(ends[:,1]>374+.002)),
        "beyond_nominal_x2":int(np.sum(ends[:,0]>1242+.002)), "beyond_nominal_y2":int(np.sum(ends[:,1]>375+.002)),
        "scaled_crop_max_abs_edge_shift_px":float(np.abs(shifts).max()),
        "scaled_crop_max_corner_shift_l2_px":float(np.linalg.norm(shifts.reshape(-1,2),axis=1).max()),
        "same_box_clip_only_max_abs_edge_shift_px":float(np.abs(bounds_only).max()),
        "unclipped_box_max_abs_edge_shift_px":float(np.abs(raw_shift).max())}
report["max_crop_shift_px"] = max(v["scaled_crop_max_corner_shift_l2_px"] for v in report["box_sources"].values())
report["correction_required_by_user_rule"] = report["max_crop_shift_px"]>10
report["correction_applied"] = False
report["interpretation_note"] = "Maxima alone cannot identify coordinates for unclipped boxes; compare extents and the known GT conversion, while recording both scaling and clipping-only crop shifts."
log_run(c,15,"0019 候选/GT 坐标与 crop 偏移核对",[[c["reproduction_environment"],"analysis/r15_coordinates.py"]],
        "CPU；不做新推理。对各表达式发布框取唯一(frame,id,bbox)，不重复计相同候选；GT 同样去重。使用官方 crop 坐标函数，margin=.2/min_side=8；报告缩放、仅裁剪边界和未裁剪框三种差值。")
save_json(root/"analysis/runs/R15/result.json",report)
print(json.dumps(report,ensure_ascii=False,indent=2))
