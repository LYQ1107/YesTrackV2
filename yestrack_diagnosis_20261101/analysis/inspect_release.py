#!/usr/bin/env python3
"""Inspect and extract the official YesTrack resource archive."""
import argparse
from collections import Counter
import json
from pathlib import Path
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--archive", type=Path, required=True)
p.add_argument("--extract-to", type=Path, required=True)
p.add_argument("--output", type=Path, default=Path("analysis/release_inventory.json"))
a = p.parse_args()
with zipfile.ZipFile(a.archive) as z:
    bad = z.testzip()
    if bad is not None:
        raise RuntimeError(f"Archive CRC failure: {bad}")
    files = [m for m in z.infolist() if not m.is_dir()]
    report = {
        "archive": str(a.archive.resolve()),
        "archive_bytes": a.archive.stat().st_size,
        "members": len(files),
        "uncompressed_bytes": sum(m.file_size for m in files),
        "groups": dict(Counter("/".join(Path(m.filename).parts[:2]) for m in files)),
        "adapter_configs": [m.filename for m in files if m.filename.endswith("adapter_config.json")],
        "seqmaps": [m.filename for m in files if "seqmap" in m.filename.lower()],
        "all_member_names": [m.filename for m in files],
        "crc_passed": True,
        "extract_to": str(a.extract_to.resolve()),
    }
    z.extractall(a.extract_to)
a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "all_member_names"}, ensure_ascii=False, indent=2))
