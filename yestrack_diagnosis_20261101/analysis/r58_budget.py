#!/usr/bin/env python3
"""R58 pilot integrity, per-setting throughput and immutable four-hour full-run gate."""
import json
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
OUT = TASK / 'analysis/runs/R58_calibration'


def main():
    plan = json.loads((TASK / 'analysis/plans/r58.json').read_text())
    results = []
    total = 0
    pilot_gpu_seconds = 0
    family_status = json.loads((OUT / 'pilot_owner_result.json').read_text())
    for family in family_status['models']:
        if family['status'] != 'complete':
            results.append(family)
            continue
        repo = family['checkpoint_repo']
        key = repo.replace('/', '__')
        s = json.loads((OUT / 'status' / (key+'_pilot.json')).read_text())
        assert s['status'] == 'complete'
        settings = []
        estimate = s['load_seconds']  # restart cost for a separate full job
        realized = s['wall_seconds']
        for setting in plan['questions']['settings']:
            p = OUT / 'predictions' / key / (setting['id']+'.jsonl')
            cached = [json.loads(line) for line in p.read_text().splitlines()]
            expected = plan['pilot']['sample_ids'] if setting['id'] == 'main' else plan['pilot']['sample_ids'][:10]
            # Full inference appends to the same cache. Keep the original pilot measurement reproducible.
            expected_set=set(expected)
            rows=[r for r in cached if r['sample_id'] in expected_set]
            assert [r['sample_id'] for r in rows] == expected, (repo, setting['id'])
            assert all(len(r['probabilities']) == len(plan['questions']['bank']) for r in rows)
            # Keep the cold first request/cache-validation latency separate; extrapolate warm records.
            seconds = [r['seconds'] for r in rows]
            rate = sum(seconds[1:])/len(seconds[1:])
            remaining = plan['samples']['images']-len(rows)
            estimate += remaining*rate
            settings.append({'setting': setting['id'], 'pilot_requests': len(rows),
                'first_seconds': seconds[0], 'warm_seconds_per_request': rate,
                'warm_requests_per_second': 1/rate, 'remaining_requests': remaining,
                'remaining_seconds_estimate': remaining*rate})
        # First full-run request repeats backend warm-up / cache validation once after a new load.
        estimate += max(0, settings[0]['first_seconds']-settings[0]['warm_seconds_per_request'])
        result = {'model': family['model'], 'checkpoint_repo': repo, 'status': 'complete',
                  'pilot_gpu_stage_seconds': realized, 'remaining_gpu_stage_seconds': estimate,
                  'complete_study_gpu_stage_seconds': realized+estimate,
                  'settings': settings, 'load_seconds': s['load_seconds'], 'cache_parity': s.get('cache_parity')}
        results.append(result)
        total += realized+estimate
        pilot_gpu_seconds += realized
    measured=any(r['status']=='complete' for r in results)
    result = {'seed': 2025, 'sample_images': plan['samples']['images'], 'settings': 6,
              'pilot_primary_per_model': 200, 'pilot_other_per_setting_per_model': 10,
              'models': results, 'pilot_gpu_stage_hours': pilot_gpu_seconds/3600,
              'complete_study_gpu_stage_hours': total/3600 if measured else None,
              'remaining_gpu_stage_hours': (total-pilot_gpu_seconds)/3600 if measured else None,
              'execution': 'sequential one-GPU workers; sum stage wall time equals estimated reserved GPU-hours',
              'gate': 'unmeasured' if not measured else 'approval_required' if total > 4*3600 else 'within_user_automatic_budget',
              'full_inference_started': json.loads((OUT/'protocol_status.json').read_text()).get('full_inference_started',False)}
    (OUT / 'budget.json').write_text(json.dumps(result, indent=2)+'\n')
    approval=OUT/'full_budget_approval.json'
    if approval.exists() and (not measured or total>4*3600):
        previous=json.loads(approval.read_text())
        if previous.get('authorization')=='user automatic <=4h rule':
            history=OUT/'budget_history';history.mkdir(exist_ok=True)
            approval.rename(history/f'revoked_auto_approval_{len(list(history.glob("revoked_auto_approval_*.json")))}.json')
    with (TASK / 'analysis/runs.md').open('a') as f:
        f.write('\nR58 200 样本试跑测算（完整明细 `R58_calibration/budget.json`）：\n\n')
        f.write('| 模型 | 已测 GPU 阶段(h) | 预计剩余(h) | 完整预计(h) |\n|---|---:|---:|---:|\n')
        for r in results:
            if r['status'] == 'complete':
                f.write(f'| {r["checkpoint_repo"]} | {r["pilot_gpu_stage_seconds"]/3600:.3f} | {r["remaining_gpu_stage_seconds"]/3600:.3f} | {r["complete_study_gpu_stage_seconds"]/3600:.3f} |\n')
            else:
                f.write(f'| {r["model"]} | {r["status"]} | — | — |\n')
        if measured:
            f.write(f'\n总计约 {total/3600:.3f} GPU 阶段小时，其中试跑已用 {pilot_gpu_seconds/3600:.3f} 小时。所有估计按实际共享负载下吞吐计算，下载与纯CPU准备不计入。')
            f.write('超过用户4小时上限，**未启动全量**，等待批准。\n' if total > 4*3600 else '未超过4小时，可按用户授权启动同一冻结计划的全量。\n')
        else:
            f.write('\n没有成功的吞吐测量，预算为unmeasured，不是0小时；不自动放行全量。\n')
    if measured and total <= 4*3600 and pilot_gpu_seconds:
        (OUT / 'full_budget_approval.json').write_text(json.dumps({'authorization': 'user automatic <=4h rule',
            'estimated_total_gpu_hours': total/3600, 'plan': str(TASK/'analysis/plans/r58.json')}, indent=2)+'\n')
    print(json.dumps({'gate': result['gate'], 'total_gpu_hours': result['complete_study_gpu_stage_hours'],
                      'remaining_gpu_hours': result['remaining_gpu_stage_hours']}), flush=True)


if __name__ == '__main__':
    main()
