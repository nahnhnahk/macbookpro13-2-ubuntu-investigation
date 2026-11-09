#!/usr/bin/env python3
"""Remove only the test kernel; retain upgrade-safe T1 recovery support."""
import os
from pathlib import Path
import subprocess
from importlib.util import spec_from_file_location, module_from_spec

base = Path(__file__).resolve().parent
spec = spec_from_file_location('installer', base / 'install-test-kernel.py')
installer = module_from_spec(spec)
spec.loader.exec_module(installer)

if os.geteuid() != 0:
    raise SystemExit('Run with sudo after booting the stock kernel.')
if os.uname().release != installer.STOCK:
    raise SystemExit('Boot ' + installer.STOCK + ' before removing the test kernel.')
installer.write_pin(installer.entries(installer.STOCK))
subprocess.run(['grub-editenv', '/boot/grub/grubenv', 'unset', 'next_entry'], check=True)
subprocess.run(['dpkg', '--purge', 'linux-image-' + installer.TEST,
                'linux-headers-' + installer.TEST], check=True)
subprocess.run(['update-grub'], check=True)
print('Test kernel removed. Stock kernel selected. Upgrade-safe T1 integration retained.')
