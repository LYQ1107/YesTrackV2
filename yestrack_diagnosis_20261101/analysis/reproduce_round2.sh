#!/usr/bin/env bash
# Full replay. Requires the already-recovered official assets and explicit >8h approval.
# Approximate total wall time exceeds one workday; see individual GPU budgets in runs.md.
set -euo pipefail
cd /data2/user/LocateMOT_GroundJEV/yestrack_diagnosis_20261101
task_python=analysis/.venv-yestrack/bin/python
export OMP_NUM_THREADS=2
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/r13_diagnostics.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/r14_thresholds.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/r15_coordinates.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/prepare_gt_candidates.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/build_labels.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/freeze_semantic_review.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/build_labels.py --review analysis/labels/llm_review.json
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/label_groups.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/plan_probes.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/plan_som_and_births.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/prepare_v1_plan.py
CUDA_VISIBLE_DEVICES=6 "$task_python" analysis/cache_scores.py --plan analysis/plans/R19_timing.json --out analysis/runs/R19_timing --video
CUDA_VISIBLE_DEVICES=6 "$task_python" analysis/cache_scores.py --plan analysis/plans/R19_timing.json --out analysis/runs/R19b_frame_timing
CUDA_VISIBLE_DEVICES=3,4 "$task_python" analysis/run_h2.py &
task_h2_pid=$!
CUDA_VISIBLE_DEVICES=6 "$task_python" analysis/context_probe.py &
task_context_pid=$!
CUDA_VISIBLE_DEVICES=5 "$task_python" analysis/run_v1_calibration.py &
task_v1_pid=$!
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/prepare_oracles.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/quantization_sanity.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/empty_frame_oracle.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/empty_frame_examples.py
wait "$task_h2_pid"
wait "$task_context_pid"
wait "$task_v1_pid"
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/calibration_source.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/threshold_transfer_actual.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/analyze_context.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/decompose.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/error_examples.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/heuristic_diagnostics.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/trace_tcp_examples.py
CUDA_VISIBLE_DEVICES=3,4,5,6 "$task_python" analysis/run_score_cache.py --plan analysis/plans/calibration_full.json --out analysis/runs/R22_full_scores --gpus 3,4,5,6 --run-number 22 --estimated-hours 13 --video --over8-authorized
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/frame_score_stats.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/class_base_rates.py
CUDA_VISIBLE_DEVICES=3,4,5,6 "$task_python" analysis/run_score_cache.py --plan analysis/plans/trp_births.json --out analysis/runs/R26_birth_scores --gpus 3,4,5,6 --run-number 26 --estimated-hours 1 --video
CUDA_VISIBLE_DEVICES=6 "$task_python" analysis/som_probe.py &
task_som_pid=$!
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/calibration.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/trp_probe.py
wait "$task_som_pid"
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/analyze_som.py
CUDA_VISIBLE_DEVICES=6 "$task_python" analysis/launch_shuffled_som.py
CUDA_VISIBLE_DEVICES='' "$task_python" -u analysis/wait_round2.py --next --shuffle
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/render_report.py
CUDA_VISIBLE_DEVICES='' "$task_python" analysis/final_validation.py
