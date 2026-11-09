#!/usr/bin/env python3
"""Select a validated patched kernel as the persistent GRUB default.

Requires three distinct duration-verified cycles, including one of at least
15 minutes, plus a current successful hardware/network/driver verification.
Run only after manually confirming Touch Bar display and touch recovery.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, base / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    installer = load('installer', 'install-test-kernel.py')
    verifier = load('verifier', 'verify-test-kernel.py')
    if os.geteuid() != 0 or os.uname().release != installer.TEST:
        raise SystemExit('Run with sudo while booted into the test kernel.')
    checks = verifier.collect('enx020000000001')
    if checks['errors']:
        raise SystemExit('Current verification failed: ' + '; '.join(checks['errors']))
    passed = []
    seen = set()
    for path in base.glob('validation-*/result.json'):
        data = json.loads(path.read_text())
        cycle = None
        if verifier.qualified_cycle(data, installer.TEST):
            cycle = {'trigger': 'rtc', 'timing': data['timing'],
                     'boot_id': data.get('boot_id'),
                     'success_index': data.get('suspend_stats_after', {}).get('success')}
        else:
            files = [path.parent / name for name in
                     ('lid-comparison-before.json', 'lid-comparison-after.json',
                      'closed-lid-kernel.log', 'closed-lid-services.log')]
            if all(file.is_file() for file in files):
                cycle = verifier.qualified_lid_comparison(
                    json.loads(files[0].read_text()), json.loads(files[1].read_text()),
                    data, files[2].read_text(), files[3].read_text(), installer.TEST)
        if cycle:
            key = ((cycle['boot_id'], cycle['success_index'])
                   if cycle['boot_id'] is not None and cycle['success_index'] is not None
                   else ('legacy-rtc', str(path)))
            if key not in seen:
                seen.add(key)
                cycle['capture'] = path.parent.name
                passed.append(cycle)
    for cycle in passed:
        print(f"Validated {cycle['capture']}: {cycle['timing']['system_suspended_seconds']} seconds asleep ({cycle['trigger']})")
    if len(passed) < 3 or not any(data['timing']['system_suspended_seconds'] >= 900 for data in passed):
        raise SystemExit('Need three distinct duration-verified passing cycles, including at least 900 measured seconds asleep. Preserved manual lid-cycle comparisons or timed RTC tests qualify.')
    installer.write_pin(installer.entries(installer.TEST))
    subprocess.run(['update-grub'], check=True)
    print('Patched kernel selected as default. Stock kernel remains in Advanced options.')
    print('Future kernel installs will not silently replace this selected kernel.')


if __name__ == '__main__':
    main()
