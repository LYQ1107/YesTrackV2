#!/usr/bin/env python3
"""Try Perplexity's exact official runtime in an isolated environment, without loading weights."""
import json
import os
from pathlib import Path
import subprocess
import traceback

TASK = Path(__file__).resolve().parents[1]
OUT = TASK / 'analysis/runs/R58_calibration'
ENV = Path('/home/user/.cache/r58_calibration/env-pplx')
REQ = OUT / 'model_cards/perplexity-ai__pplx-decider-v1.2/requirements.txt'


def main():
    result = {'repo': 'perplexity-ai/pplx-decider-v1.2', 'environment': str(ENV),
              'requirements': str(REQ), 'model_loaded': False, 'model_inference': False}
    try:
        if not (ENV / 'bin/python').exists():
            subprocess.run(['/home/user/.local/bin/python3.12', '-m', 'venv', str(ENV)], check=True)
        with (OUT / 'perplexity_environment_install.log').open('w') as f:
            subprocess.run([str(ENV / 'bin/python'), '-m', 'pip', 'install', '--no-cache-dir', '-r', str(REQ)],
                           check=True, stdout=f, stderr=subprocess.STDOUT)
        probe = '''import json,sys,torch,torchvision,transformers
print(json.dumps({'python':sys.version,'torch':torch.__version__,'torchvision':torchvision.__version__,
 'transformers':transformers.__version__,'cuda_build':torch.version.cuda}),flush=True)
torch.cuda.init()
print(json.dumps({'cuda_initialized':True,'gpu':torch.cuda.get_device_name(0)}),flush=True)
'''
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='5')
        r = subprocess.run([str(ENV / 'bin/python'), '-c', probe], env=env, text=True, capture_output=True)
        (OUT / 'perplexity_cuda_probe.log').write_text(r.stdout + r.stderr)
        result.update({'returncode': r.returncode, 'probe_output': r.stdout, 'probe_error': r.stderr,
                       'status': 'runtime_ready' if r.returncode == 0 else 'runtime_unavailable'})
    except Exception as e:
        result.update({'status': 'runtime_install_failed', 'exception': repr(e), 'traceback': traceback.format_exc()})
    (OUT / 'perplexity_runtime.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
