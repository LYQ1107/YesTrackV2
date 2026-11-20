#!/usr/bin/env python3
"""Run the already-defined full GPU phase, then CPU analyses, after its budget gate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
TASK=Path(__file__).resolve().parents[1];OUT=TASK/'analysis/runs/R58_calibration'
def save(obj):
 (OUT/'pipeline_status.json').write_text(json.dumps(obj,indent=2)+'\n')
try:
 assert (OUT/'full_budget_approval.json').exists(),'The user four-hour budget gate is still pending'
 subprocess.run([sys.executable,'-u','analysis/r58_owner.py','--stage','full'],cwd=TASK,check=True)
 pilot=json.loads((OUT/'pilot_owner_result.json').read_text())
 full=json.loads((OUT/'full_owner_result.json').read_text())
 done={r['model']:r for r in full['models']}
 incomplete=[r['model'] for r in pilot['models'] if r['status']=='complete'
             and (done[r['model']]['status']!='complete' or done[r['model']]['checkpoint_repo']!=r['checkpoint_repo'])]
 assert not incomplete,('Incomplete full caches: resume these models before CPU publication',incomplete)
 save({'status':'CPU_analysis_running','GPU_full_complete':True})
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='')
 subprocess.run([str(TASK/'analysis/.venv-yestrack/bin/python'),'-u','analysis/r58_cpu_owner.py'],cwd=TASK,env=env,check=True)
 save({'status':'complete','GPU_full_complete':True,'CPU_report_complete':True})
except Exception as e:
 save({'status':'failed','exception':repr(e),'traceback':traceback.format_exc()})
 raise
