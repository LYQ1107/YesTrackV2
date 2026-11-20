#!/usr/bin/env python3
"""Seed the process, then execute an unmodified official entry point."""
import argparse
from pathlib import Path
import random
import runpy
import sys

import numpy as np
import torch

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--seed", type=int, required=True)
p.add_argument("--script", type=Path, required=True)
p.add_argument("script_args", nargs=argparse.REMAINDER)
a = p.parse_args()
random.seed(a.seed)
np.random.seed(a.seed)
torch.manual_seed(a.seed)
torch.cuda.manual_seed_all(a.seed)
script_args = a.script_args[1:] if a.script_args[:1] == ["--"] else a.script_args
if "--lora_path" in script_args:
    adapter = Path(script_args[script_args.index("--lora_path")+1])
    assert (adapter / "adapter_config.json").is_file()
    assert (adapter / "adapter_model.safetensors").is_file()
sys.path.insert(0, str(a.script.resolve().parent))
sys.argv = [str(a.script.resolve())] + script_args
runpy.run_path(str(a.script.resolve()), run_name="__main__")
