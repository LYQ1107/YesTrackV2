#!/usr/bin/env python3
"""Unpack the frozen probability records on NAS, retaining their original bytes."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/data3/liuyeqiang/nas/A800/research_evidence_20261115')
DEST = Path('/data3/liuyeqiang/nas/A100/YesTrackV2_runtime/r58_calibration/predictions')
PREFIX = '/home/user/.cache/r58_calibration/predictions/'


def main():
    expected = {r['path'].lstrip('/'): r for r in
                map(json.loads, (SOURCE / '01_R58_raw_predictions_01.manifest.jsonl').read_text().splitlines())}
    checked = []
    with tarfile.open(SOURCE / '01_R58_raw_predictions_01.tar.gz', 'r|gz') as archive:
        for member in archive:
            key = member.name.removeprefix('./').lstrip('/')
            if key not in expected:
                continue
            row = expected[key]
            assert member.isfile() and row['path'].startswith(PREFIX), member.name
            content = archive.extractfile(member).read()
            assert len(content) == row['bytes']
            assert hashlib.sha256(content).hexdigest() == row['sha256'], member.name
            out = DEST / row['path'][len(PREFIX):]
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                assert hashlib.sha256(out.read_bytes()).hexdigest() == row['sha256'], out
            else:
                partial = out.with_suffix(out.suffix + '.partial')
                partial.write_bytes(content)
                assert hashlib.sha256(partial.read_bytes()).hexdigest() == row['sha256']
                partial.rename(out)
            checked.append({**row, 'restored_NAS': str(out)})
    assert len(checked) == len(expected), (len(checked), len(expected))
    (ROOT / 'recovery/r58_predictions_receipt.json').write_text(json.dumps(checked, indent=2) + '\n')
    print(json.dumps({'files': len(checked), 'bytes': sum(r['bytes'] for r in checked),
                      'destination': str(DEST), 'sha256': 'all members verified'}), flush=True)


if __name__ == '__main__':
    main()
