#!/usr/bin/env python3
"""Audit completed local artifacts and emit the installer integrity manifest."""
import hashlib
import json
from pathlib import Path
import subprocess
from package_permissions import audit

BASE = Path(__file__).resolve().parent
RELEASE = '7.0.14-mbp132-tb1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = BASE / 'build'
    if (build / 'include/config/kernel.release').read_text().strip() != RELEASE:
        raise RuntimeError('Unexpected built kernel release')
    changes = json.loads((BASE / 'source-changes.json').read_text())
    for name, expected in changes.items():
        if sha(BASE / 'linux-source-7.0.0' / name) != expected['after']:
            raise RuntimeError('Patched source changed during build: ' + name)
    module = build / 'drivers/thunderbolt/thunderbolt.ko'
    data = module.read_bytes()
    for marker in [b'SXFP', b'tb_acpi_force_power', b'tb_switch_set_bit26']:
        if marker not in data:
            raise RuntimeError('Built Thunderbolt module lacks ' + marker.decode())
    driver = json.loads((BASE / 'test-driver-build.json').read_text())
    if set(driver) != {'apple-ibridge', 'apple-touchbar'}:
        raise RuntimeError('External-driver header build was not validated')
    client = BASE / 't1-upgrade/acpidbg'
    approval = json.loads((BASE / 't1-upgrade/acpidbg.json').read_text())
    if (approval.get('schema') != 1
            or approval.get('path') != '/usr/local/libexec/mbp-t1/acpidbg'
            or sha(client) != approval.get('sha256')
            or sha(BASE / 'linux-source-7.0.0' / approval['source']) != approval['source_sha256']):
        raise RuntimeError('Standalone debugger client/source approval mismatch')
    help_text = subprocess.check_output([str(client), '-h'], text=True, timeout=5)
    if 'Specify command to be executed in batch mode' not in help_text:
        raise RuntimeError('Standalone debugger client readiness check failed')
    dynamic = subprocess.check_output(['readelf', '-d', str(client)], text=True)
    if 'RPATH' in dynamic or 'RUNPATH' in dynamic:
        raise RuntimeError('Standalone debugger client has an unexpected library path')
    packages = []
    for kind in ['headers', 'image']:
        candidates = list((BASE / 'packages').glob('linux-' + kind + '-' + RELEASE + '_*.deb'))
        if len(candidates) != 1:
            raise RuntimeError('Expected one ' + kind + ' package')
        package = candidates[0]
        audit(package)
        name = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Package'], text=True).strip()
        if name != 'linux-' + kind + '-' + RELEASE:
            raise RuntimeError('Unexpected package name')
        listing = subprocess.check_output(['dpkg-deb', '--contents', str(package)], text=True)
        (BASE / 'logs' / (kind + '-package-contents.txt')).write_text(listing)
        if kind == 'headers' and ('usr/src/linux-headers-' + RELEASE + '/Module.symvers') not in listing:
            raise RuntimeError('Exported header package lacks symbol versions')
        if kind == 'image' and ('boot/vmlinuz-' + RELEASE) not in listing:
            raise RuntimeError('Image package lacks the kernel image')
        packages.append(str(package.relative_to(BASE)))
    required = [
        'install-test-kernel.py', 'package_permissions.py',
        'rollback-test-kernel.py', 'verify-test-kernel.py',
        'promote-test-kernel.py', 't1-upgrade/mbp_t1_guard.py',
        't1-upgrade/mbp-t1-record-build', 't1-upgrade/approved-source.json',
        't1-upgrade/validated-baseline.json',
        't1-upgrade/zz-mbp-t1-verify', 't1-upgrade/header-zz-mbp-t1-verify',
        't1-upgrade/mbp-t1-s3-handshake.py',
        't1-upgrade/acpidbg', 't1-upgrade/acpidbg.json', 'repair-acpidbg.py',
        'patches/ubuntu-7.0.0-43-mbp132-backport.patch', 'source-changes.json',
    ] + packages
    manifest = {'schema': 1, 'kernel': RELEASE,
                'base_package': 'linux-source-7.0.0=7.0.0-43.43',
                'packages': packages,
                'files': {name: sha(BASE / name) for name in required},
                'test_driver_build': driver,
                'thunderbolt_srcversion': subprocess.check_output(
                    ['modinfo', '-F', 'srcversion', str(module)], text=True).strip()}
    (BASE / 'artifact-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Artifact source, module markers, package identity, and header checks passed.')
    print('Installer manifest:', BASE / 'artifact-manifest.json')


if __name__ == '__main__':
    main()
