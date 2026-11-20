#!/usr/bin/env python3
"""Observe raw scores returned by official helpers; never change their return values."""
import argparse
import gzip
import inspect
import json
import os
from pathlib import Path
import random
import runpy
import sys

import numpy as np
import torch

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--seed", type=int, required=True)
p.add_argument("--script", type=Path, required=True)
p.add_argument("--trace-root", type=Path, required=True)
p.add_argument("script_args", nargs=argparse.REMAINDER)
a = p.parse_args()
random.seed(a.seed)
np.random.seed(a.seed)
torch.manual_seed(a.seed)
torch.cuda.manual_seed_all(a.seed)
sys.path.insert(0, str(a.script.resolve().parent))
namespace = runpy.run_path(str(a.script.resolve()), run_name="yestrack_observed")
main = namespace["main"]
g = main.__globals__
a.trace_root.mkdir(parents=True, exist_ok=True)
trace = gzip.open(a.trace_root / f"rank{os.environ.get('RANK', '0')}.jsonl.gz", "wt")


def observe(original, mode):
    def wrapped(*args, **kwargs):
        caller = inspect.currentframe().f_back.f_locals
        if mode == "frame":
            indices = (range(len(caller["dets_one"])) if caller["do_full_infer"]
                       else caller["new_indices"])
        else:
            indices = caller["refine_indices"]
        ids = [int(caller["dets_one"][i][0]) for i in indices]
        result = original(*args, **kwargs)
        assert len(ids) == len(result)
        trace.write(json.dumps({"name": f"{caller['seq']}__{caller['expr_dirname']}",
                                "frame": int(caller["frame"]), "ids": ids,
                                "mode": mode, "p": result}) + "\n")
        return result
    return wrapped


for helper, mode in (("_forward_probs_for_patches", "frame"),
                     ("_forward_probs_for_detections_video", "video")):
    g[helper] = observe(g[helper], mode)
script_args = a.script_args[1:] if a.script_args[:1] == ["--"] else a.script_args
sys.argv = [str(a.script.resolve())] + script_args
try:
    main()
finally:
    trace.close()
