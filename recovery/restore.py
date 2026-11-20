#!/usr/bin/env python3
"""Restore the selected, frozen YesTrack source without copying large payloads."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NAS = Path('/data3/liuyeqiang/nas/A800')
OLD = '/data2/user/LocateMOT_GroundJEV/'
TASK = ROOT / 'yestrack_diagnosis_20261101'
SOURCE = NAS / 'data2/user/LocateMOT_GroundJEV'


def main():
    wanted = {}
    with (NAS / 'project_snapshot_20261113/code_snapshot_manifest.csv').open() as f:
        for row in csv.DictReader(f):
            path = row['path']
            if not path.startswith(OLD):
                continue
            rel = path[len(OLD):]
            if rel.startswith(('yestrack_diagnosis_20261101/', 'external/OneJev/')):
                wanted[path.lstrip('/')] = row
    restored = []
    with tarfile.open(NAS / 'project_snapshot_20261113/code_snapshot.tar', 'r|') as archive:
        for member in archive:
            key = member.name.removeprefix('./').lstrip('/')
            row = wanted.get(key)
            if row is None:
                continue
            assert member.isfile(), member.name
            content = archive.extractfile(member).read()
            assert len(content) == int(row['bytes']), member.name
            assert hashlib.sha256(content).hexdigest() == row['sha256'], member.name
            rel = row['path'][len(OLD):]
            out = ROOT / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
            out.chmod(0o755 if member.mode & 0o111 else 0o644)
            restored.append({'original': row['path'], 'local': str(out),
                             'bytes': len(content), 'sha256': row['sha256']})
    assert len(restored) == len(wanted), (len(restored), len(wanted))
    # These logs include the later successful November 15 backup closeout.
    for rel in ['research_log.md', 'yestrack_diagnosis_20261101/analysis/runs.md',
                'yestrack_diagnosis_20261101/analysis/research_log.md']:
        out = ROOT / rel
        shutil.copyfile(SOURCE / rel, out)
    (ROOT / 'recovery/source_files.json').write_text(json.dumps(restored, indent=2) + '\n')
    shutil.copyfile(SOURCE / 'AGENTS.md', ROOT / 'recovery/AGENTS.a800.md')
    print(json.dumps({'restored_source_files': len(restored),
                      'source_bytes': sum(r['bytes'] for r in restored)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
