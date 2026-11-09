#!/usr/bin/env python3
"""Install the standalone recovery client; never suspend or invoke firmware."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

BASE = Path(__file__).resolve().parent
HELPER = Path('/usr/local/sbin/mbp-t1-s3-handshake')
PREVIOUS_HELPER = 'ee1094ee338f06bd690317f384b423690bf32327ab81a47e486f054e5d44e424'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(source, destination, mode):
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    from mbp_t1_guard import trusted
    trusted(destination.parent)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(source.read_bytes())
            file.flush()
            os.fsync(file.fileno())
            os.fchmod(file.fileno(), mode)
            os.fchown(file.fileno(), 0, 0)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run this script with sudo')
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MacBookPro13,2':
        raise RuntimeError('Unsupported machine')
    if os.uname().release not in ('7.0.0-43-generic', '7.0.14-mbp132-tb1'):
        raise RuntimeError('Run from the approved stock or test kernel')
    manifest = json.loads((BASE / 'artifact-manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if sha(BASE / name) != expected:
            raise RuntimeError('Reviewed artifact changed: ' + name)
    sys.path.insert(0, '/usr/local/lib/mbp-t1')
    from mbp_t1_guard import trusted, validate_running_build
    trusted(HELPER)
    desired = BASE / 't1-upgrade/mbp-t1-s3-handshake.py'
    if sha(HELPER) not in (PREVIOUS_HELPER, sha(desired)):
        raise RuntimeError('Installed helper is not the expected reviewed version')
    with open('/run/lock/mbp-t1-firmware-test.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if Path('/run/mbp-t1-s3-handshake/pending.json').exists():
            raise RuntimeError('A firmware wake is pending; refusing changes')
        validate_running_build()
        for source, destination in (
                ('t1-upgrade/acpidbg', '/usr/local/libexec/mbp-t1/acpidbg'),
                ('t1-upgrade/acpidbg.json', '/etc/mbp-t1/acpidbg.json')):
            path = Path(destination)
            if path.is_symlink() or (path.exists() and sha(path) != sha(BASE / source)):
                raise RuntimeError('Unexpected existing destination: ' + destination)
        backup = Path('/var/lib/mbp-t1/test-kernel-backup/mbp-t1-s3-handshake.pre-acpidbg-fix')
        if not backup.exists():
            if sha(HELPER) != PREVIOUS_HELPER:
                raise RuntimeError('Previous helper backup is missing')
            shutil.copy2(HELPER, backup)
        elif sha(backup) != PREVIOUS_HELPER:
            raise RuntimeError('Previous helper backup has changed')
        install(BASE / 't1-upgrade/acpidbg', Path('/usr/local/libexec/mbp-t1/acpidbg'), 0o755)
        install(BASE / 't1-upgrade/acpidbg.json', Path('/etc/mbp-t1/acpidbg.json'), 0o644)
        # Validate the staged helper and installed client before switching the
        # systemd entry point. validate() does not evaluate any ACPI method.
        staged = runpy.run_path(str(desired), run_name='mbp_t1_staged')
        staged['validate']()
        install(desired, HELPER, 0o755)
        active = runpy.run_path(str(HELPER), run_name='mbp_t1_installed')
        active['validate']()
        if active['planned_mode']() != 'deep':
            raise RuntimeError('Effective sleep setting is not deep')
    print('Recovery client and helper installed; all read-only readiness checks passed.')
    print('No firmware call, suspend, reboot, or live module reload was performed.')
    print('No reboot is required. Run verify-test-kernel.py, then an explicit controlled sleep test.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('REPAIR STOPPED: ' + str(error))
