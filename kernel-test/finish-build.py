#!/usr/bin/env python3
"""Wait for the active compile, then stage/audit artifacts; never install."""
from pathlib import Path
import re
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
log = BASE / 'logs/build.log'
ending = "make: Leaving directory '" + str(BASE / 'linux-source-7.0.0') + "'"
while True:
    text = log.read_text(errors='replace')
    lines = text.splitlines()
    if lines and lines[-1] == ending:
        if re.search(r'^make[^\n]*\*\*\*', text, re.MULTILINE):
            raise SystemExit('Kernel compile failed; inspect logs/build.log. No packaging or installation attempted.')
        break
    print('Compile active: ' + (lines[-1] if lines else 'starting'), flush=True)
    time.sleep(45)
print('Compile finished; staging modules, standalone headers, and packages.', flush=True)
for script in ['stage-packages.py', 'finalize-artifacts.py']:
    with (BASE / 'logs' / (script + '.log')).open('a') as output:
        result = subprocess.run([sys.executable, str(BASE / script)], cwd=BASE,
                                stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(script + ' failed; inspect its log. No installation attempted.')
    print(script + ' passed.', flush=True)
print('Artifacts ready for review. No installed system files or boot settings were changed.', flush=True)
