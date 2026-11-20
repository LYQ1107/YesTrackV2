#!/usr/bin/env python3
"""Launch archived analysis code with A800 path names translated at runtime.

Source, frozen JSON files and numeric results retain their original bytes.
Only explicitly recorded filesystem prefixes are translated. Official upstream
modules are loaded normally. Use a new run number for new experiments.
"""
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'yestrack_diagnosis_20261101'
ANALYSIS = TASK / 'analysis'
PATHS = json.loads((ROOT / 'recovery/runtime_paths.json').read_text())
PREFIXES = sorted(PATHS, key=len, reverse=True)
ORIGINAL_LOADS = json.loads


def relocate(value):
    if isinstance(value, dict):
        return {k: relocate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v) for v in value]
    if isinstance(value, str):
        for old in PREFIXES:
            if value == old or value.startswith(old + '/'):
                return PATHS[old] + value[len(old):]
    return value


def source_at(path):
    source = path.read_text()
    for old in PREFIXES:
        source = source.replace(old, PATHS[old])
    return compile(source, str(path), 'exec')


class AnalysisLoader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):
        return source_at(Path(self.path))


class AnalysisFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if '.' not in fullname:
            candidate = ANALYSIS / (fullname + '.py')
            if candidate.is_file():
                return importlib.util.spec_from_loader(fullname, AnalysisLoader(fullname, str(candidate)))
        return None


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: recovery/run.py analysis/SCRIPT.py [arguments]')
    script = Path(sys.argv[1])
    if not script.is_absolute():
        script = TASK / script
    sys.argv = [str(script), *sys.argv[2:]]
    sys.path.insert(0, str(ANALYSIS))
    sys.meta_path.insert(0, AnalysisFinder())
    json.loads = lambda *args, **kwargs: relocate(ORIGINAL_LOADS(*args, **kwargs))
    os.chdir(TASK)
    exec(source_at(script), {'__name__': '__main__', '__file__': str(script)})


if __name__ == '__main__':
    main()
