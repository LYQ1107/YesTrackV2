#!/usr/bin/env python3
"""Lock the official inference software before the first R58 model forward."""
from importlib.metadata import version
import json
from pathlib import Path
import sys

import torch
import transformers
import cv2
import einops
import fla

out=Path(__file__).resolve().parent/'runs/R58_calibration'
assert not json.loads((out/'protocol_status.json').read_text())['inference_started']
packages=['torch','torchvision','transformers','accelerate','safetensors','huggingface_hub',
          'pillow','einops','opencv-python-headless','flash-linear-attention','fla-core','triton','compressed-tensors','socksio']
result={'python':sys.version,'executable':sys.executable,'cuda_build':torch.version.cuda,
        'packages':{p:version(p) for p in packages},'overlay':sys.path,
        'model_inference_performed':False}
(out/'environment.lock.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
