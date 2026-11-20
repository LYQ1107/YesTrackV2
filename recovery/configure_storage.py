#!/usr/bin/env python3
"""Create local metadata views and explicit pointers to read-only NAS assets."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
NAS = Path('/data3/liuyeqiang/nas/A800')
OLD = '/data2/user/LocateMOT_GroundJEV'
TASK_NAME = 'yestrack_diagnosis_20261101'
TASK = ROOT / TASK_NAME
A = TASK / 'analysis'
SOURCE = NAS / 'data2/user/LocateMOT_GroundJEV' / TASK_NAME / 'analysis'
SELECTED = NAS / 'selected_checkpoints/LocateMOT_20261112/files'
RUNTIME = Path('/data3/liuyeqiang/nas/A100/YesTrackV2_runtime')
LINKS = []


def link(out, target):
    out = Path(out)
    target = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_symlink():
        if out.readlink() != target:
            out.unlink()
    if not out.exists() and not out.is_symlink():
        out.symlink_to(target)
    LINKS.append({'local': str(out), 'NAS': str(target)})


def shallow_view(source, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if source.name == 'R58_calibration' and item.name in {'models', 'predictions'}:
            continue
        out = dest / item.name
        if item.is_symlink():
            continue  # Absolute A800 links are rebuilt explicitly below.
        if item.is_file() and item.suffix in {'.json', '.csv', '.md', '.log', '.txt'} and item.stat().st_size < 2 * 1024**2:
            if not out.exists():
                shutil.copyfile(item, out)
        else:
            link(out, item)


def main():
    for name in ['plans', 'labels']:
        shutil.copytree(SOURCE / name, A / name, dirs_exist_ok=True)
    link(A / 'errors', SOURCE / 'errors')
    for run in (SOURCE / 'runs').iterdir():
        if run.is_dir() and not run.is_symlink():
            shallow_view(run, A / 'runs' / run.name)
        elif run.is_file():
            shutil.copyfile(run, A / 'runs' / run.name)
    resources = A / 'resources'
    resources.mkdir(exist_ok=True)
    for name in ['gt_candidates_v1', 'gt_candidates_v2', 'yestrack.zip', 'yestrack_arxiv_source.tar']:
        link(resources / name, SOURCE / 'resources' / name)
    for version in ['v1', 'v2']:
        data = NAS / ('data2/user/LocateMOT/data/refer_kitti_' + version)
        view = resources / ('dataset_' + version)
        link(view / 'expression', data / 'expression')
        link(view / 'KITTI/labels_with_ids', data / 'labels_with_ids')
        link(view / 'KITTI/training/image_02', NAS / 'data2/user/LocateMOT/data/kitti_tracking/training/image_02')
    release = resources / 'release/yestrack'
    release.mkdir(parents=True, exist_ok=True)
    for name in ['refer_kitti_motc_gt', 'refer_kitti_motc_gt_v2', 'v1best_track_result', 'v2best_track_result']:
        link(release / name, SOURCE / 'resources/release/yestrack' / name)
    for name in ['v1bestweight', 'v2bestweight']:
        chosen = SELECTED / ('data2/user/LocateMOT_GroundJEV/' + TASK_NAME + '/analysis/resources/release/yestrack/' + name)
        # Recreate the directory locally if code metadata was already selected.
        out = release / name
        if out.is_dir() and not out.is_symlink():
            for f in chosen.iterdir():
                link(out / f.name, f)
        else:
            link(out, chosen)
    base = SELECTED / 'data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct'
    link(ROOT / 'assets/Qwen3-VL-2B-Instruct', base)
    link(ROOT / 'assets/data', NAS / 'data2/user/LocateMOT/data')
    link(ROOT / 'assets/kitti_tracking_labels.zip', NAS / 'data2/user/reference_envs/kitti_tracking_labels_20261001/data_tracking_label_2.zip')
    link(ROOT / 'assets/research_evidence', NAS / 'research_evidence_20261115')
    link(ROOT / 'assets/checkpoints', NAS / 'selected_checkpoints')
    r58 = A / 'runs/R58_calibration'
    (r58 / 'models').mkdir(exist_ok=True)
    link(r58 / 'models/Qwen__Qwen3-VL-2B-Instruct', base)
    link(r58 / 'predictions', RUNTIME / 'r58_calibration/predictions')
    original = json.loads((A / 'config.json').read_text())
    (ROOT / 'recovery/config.a800.json').write_text(json.dumps(original, indent=2) + '\n')
    mapping = {
        OLD: str(ROOT),
        '/data2/user/LocateMOT/data': str(ROOT / 'assets/data'),
        '/data2/user/TTA-RMOT-assets/teacher-p1/models/Qwen3-VL-2B-Instruct': str(base),
    }
    def relocate(value):
        if isinstance(value, dict):
            return {k: relocate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocate(v) for v in value]
        if isinstance(value, str):
            for old, new in mapping.items():
                if value == old or value.startswith(old + '/'):
                    return new + value[len(old):]
        return value
    config = relocate(original)
    config['reproduction_environment'] = '/data3/liuyeqiang/.venvs/fgrefmot-rmot-sports-20261019/bin/python'
    config['candidate_environment'] = config['reproduction_environment']
    config['base_model'] = str(base)
    config['local_search_roots'] = [str(ROOT), str(NAS)]
    config['reproduction_physical_gpus'] = []
    config['allocated_gpus_for_preflight'] = []
    (A / 'config.json').write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n')
    link(A / '.venv-yestrack', Path(config['reproduction_environment']).parent.parent)
    (ROOT / 'recovery/storage_links.json').write_text(json.dumps(LINKS, indent=2) + '\n')
    (ROOT / 'recovery/runtime_paths.json').write_text(json.dumps({**mapping,
        '/data2/user/nas/A800': str(NAS),
        '/home/user/.cache/r58_calibration': str(RUNTIME / 'r58_calibration'),
        '/data2/user/reference_envs/kitti_tracking_labels_20261001/data_tracking_label_2.zip': str(ROOT / 'assets/kitti_tracking_labels.zip')}, indent=2) + '\n')
    print(json.dumps({'storage_links': len(LINKS), 'config': str(A / 'config.json')}), flush=True)


if __name__ == '__main__':
    main()
