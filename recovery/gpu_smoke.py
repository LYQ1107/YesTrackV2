#!/usr/bin/env python3
"""Run the archived two-crop verifier check, using RAM for remote weight I/O."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'yestrack_diagnosis_20261101'
NAS = Path('/data3/liuyeqiang/nas/A800')


def ram_view(source, dest, descriptors):
    """Pinned SFTP sequential read into anonymous RAM; no local weight file."""
    dest.mkdir()
    for file in source.iterdir():
        if not file.is_file():
            continue
        if file.suffix != '.safetensors':
            (dest / file.name).symlink_to(file)
            continue
        fd = os.memfd_create('yestrack-smoke-' + file.name)
        descriptors.append(fd)
        remote = '/home/A800/' + file.resolve().relative_to(NAS).as_posix()
        command = ['sftp', '-P', '24557', '-B', '262144', '-R', '64',
                   '-i', '/data3/liuyeqiang/.ssh/id_ed25519_nas_readwrite',
                   '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=nas-readwrite',
                   '-o', 'UserKnownHostsFile=/data3/liuyeqiang/.ssh/known_hosts_nas_readwrite',
                   '-b', '-', 'Valadmin@127.0.0.1']
        print('Loading NAS weight into anonymous RAM:', file.name, flush=True)
        subprocess.run(command, input=f'get "{remote}" "/proc/self/fd/{fd}"\n',
                       text=True, check=True, pass_fds=(fd,))
        assert os.fstat(fd).st_size == file.stat().st_size
        (dest / file.name).symlink_to(f'/proc/{os.getpid()}/fd/{fd}')


def main():
    start = time.perf_counter()
    config = json.loads((TASK / 'analysis/config.json').read_text())
    descriptors = []
    try:
        with tempfile.TemporaryDirectory(prefix='smoke-ram-', dir=ROOT / 'recovery') as temp:
            temp = Path(temp)
            ram_view(Path(config['base_model']), temp / 'base', descriptors)
            ram_view(Path(config['official_v2_adapter']), temp / 'adapter', descriptors)
            config.update(base_model=str(temp / 'base'), official_v2_adapter=str(temp / 'adapter'))
            config_path = temp / 'config.json'
            config_path.write_text(json.dumps(config))
            source_path = TASK / 'analysis/smoke_runtime.py'
            source = source_path.read_text()
            original_output = '(t / "analysis/runtime_smoke.json").write_text'
            assert original_output in source
            source = source.replace(original_output,
                '(Path(' + repr(str(ROOT / 'recovery/gpu_smoke.json')) + ')).write_text')
            sys.argv = [str(source_path), '--config', str(config_path)]
            exec(compile(source, str(source_path), 'exec'), {'__name__': '__main__', '__file__': str(source_path)})
            out = ROOT / 'recovery/gpu_smoke.json'
            result = json.loads(out.read_text())
            reference = json.loads((TASK / 'analysis/runtime_smoke.json').read_text())
            result.update(weight_storage='NAS; sequential SFTP into anonymous RAM for this check only',
                          physical_GPU=os.environ.get('CUDA_VISIBLE_DEVICES'),
                          total_seconds_including_NAS_read=time.perf_counter() - start,
                          local_persistent_weight_bytes=0,
                          archived_A800_reference_probabilities=reference['probs'],
                          max_probability_difference_from_A800=max(abs(a-b) for a,b in zip(result['probs'],reference['probs'])))
            out.write_text(json.dumps(result, indent=2) + '\n')
    finally:
        for fd in descriptors:
            os.close(fd)


if __name__ == '__main__':
    main()
