#!/usr/bin/env python3
"""Infrastructure-only NCCL timeout for the unchanged score observer and model."""
import datetime
from pathlib import Path
import runpy

import torch.distributed as dist


def install_timeout():
    original = dist.init_process_group

    def initialize(*args, **kwargs):
        kwargs.setdefault('timeout', datetime.timedelta(hours=8))
        return original(*args, **kwargs)

    dist.init_process_group = initialize


if __name__ == '__main__':
    install_timeout()
    runpy.run_path(str(Path(__file__).with_name('observed_inference.py')), run_name='__main__')
