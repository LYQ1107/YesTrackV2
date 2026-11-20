#!/usr/bin/env python3
"""Keep the pilot owner alive across terminal loss; wait in one blocking command."""
import json
from pathlib import Path
import subprocess
import sys
import time
TASK=Path(__file__).resolve().parents[1]
OUT=TASK/'analysis/runs/R58_calibration'
log=OUT/'pilot_owner_resumed.log'
offset=log.stat().st_size if log.exists() else 0
with log.open('a') as f:
 p=subprocess.Popen([sys.executable,'-u','analysis/r58_owner.py'],cwd=TASK,
   stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
(OUT/'pilot_owner_launch.json').write_text(json.dumps({'pid':p.pid,'log':str(log),'mode':'pilot only; detached from terminal signals'},indent=2)+'\n')
print(json.dumps({'event':'pilot_owner_resumed','pid':p.pid}),flush=True)
with log.open() as f:
 f.seek(offset)
 while True:
  text=f.read()
  if text:print(text,end='',flush=True)
  code=p.poll()
  if code is not None:
   text=f.read()
   if text:print(text,end='',flush=True)
   print(json.dumps({'event':'pilot_owner_exit','returncode':code}),flush=True)
   raise SystemExit(code)
  time.sleep(5)
