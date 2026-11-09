#!/usr/bin/env python3
"""Install reviewed test artifacts, preserve the stock default, schedule one test boot.

Requires administrator execution in the user's terminal. Never suspends,
reboots, reloads a module, or evaluates an ACPI method.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parent
STOCK = '7.0.0-43-generic'
TEST = '7.0.14-mbp132-tb1'
BACKUP = Path('/var/lib/mbp-t1/test-kernel-backup')
PIN = Path('/etc/default/grub.d/98-mbp132-test-kernel.cfg')
OLD_HELPER = '07c44563fb9ebd75884762d9dadce2ff0c2982bfcb9b0301881777fc60cb35ac'
PRE_ACPIDBG_HELPER = 'ee1094ee338f06bd690317f384b423690bf32327ab81a47e486f054e5d44e424'
FILES = {
    't1-upgrade/mbp_t1_guard.py': ('/usr/local/lib/mbp-t1/mbp_t1_guard.py', 0o644),
    't1-upgrade/mbp-t1-record-build': ('/usr/local/sbin/mbp-t1-record-build', 0o755),
    't1-upgrade/approved-source.json': ('/etc/mbp-t1/approved-source.json', 0o644),
    't1-upgrade/validated-baseline.json': ('/etc/mbp-t1/validated-baseline.json', 0o644),
    't1-upgrade/zz-mbp-t1-verify': ('/etc/kernel/postinst.d/zz-mbp-t1-verify', 0o755),
    't1-upgrade/header-zz-mbp-t1-verify': ('/etc/kernel/header_postinst.d/zz-mbp-t1-verify', 0o755),
    't1-upgrade/acpidbg': ('/usr/local/libexec/mbp-t1/acpidbg', 0o755),
    't1-upgrade/acpidbg.json': ('/etc/mbp-t1/acpidbg.json', 0o644),
    't1-upgrade/mbp-t1-s3-handshake.py': ('/usr/local/sbin/mbp-t1-s3-handshake', 0o755),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    print('+', ' '.join(args), flush=True)
    subprocess.run(args, check=True)


def entry_from_config(config, release):
    # Match declarations, never references inside `set default`. Once stock
    # is pinned, that reference contains a complete submenu>entry path.
    # Treating it as a submenu produces an invalid three-component path.
    suffix = r'[A-Za-z0-9_.+\-]+'
    submenus = re.findall(
        r'''(?m)^[ \t]*submenu[ \t]+[^\n]*?['"](gnulinux-advanced-'''
        + suffix + r''')['"][ \t]*\{[ \t]*$''', config)
    entries = re.findall(
        r'''(?m)^[ \t]*menuentry[ \t]+[^\n]*?['"](gnulinux-'''
        + re.escape(release) + '-advanced-' + suffix
        + r''')['"][ \t]*\{[ \t]*$''', config)
    if len(submenus) != 1 or len(entries) != 1:
        raise RuntimeError(f'Cannot find unique explicit GRUB declarations for {release}')
    if submenus[0].removeprefix('gnulinux-advanced-') != entries[0].removeprefix(
            'gnulinux-' + release + '-advanced-'):
        raise RuntimeError('GRUB submenu and kernel entry use different device identifiers')
    return submenus[0] + '>' + entries[0]


def entries(release):
    return entry_from_config(Path('/boot/grub/grub.cfg').read_text(), release)


def write_pin(entry):
    if not re.fullmatch(r'[A-Za-z0-9_.+\-]+>[A-Za-z0-9_.+\-]+', entry):
        raise RuntimeError('Unexpected characters in GRUB entry identifier')
    PIN.parent.mkdir(parents=True, exist_ok=True)
    PIN.write_text('# Managed MacBook test-kernel boot selection.\nGRUB_DEFAULT="' + entry + '"\n')
    PIN.chmod(0o644)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run: sudo python3 kernel-test/install-test-kernel.py')
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MacBookPro13,2':
        raise RuntimeError('Unsupported machine')
    if os.uname().release != STOCK:
        raise RuntimeError('Install from the known stock kernel ' + STOCK)
    if Path('/run/mbp-t1-s3-handshake/pending.json').exists():
        raise RuntimeError('A T1 firmware wake is pending; resolve that before installation')
    manifest = json.loads((BASE / 'artifact-manifest.json').read_text())
    if manifest['kernel'] != TEST:
        raise RuntimeError('Wrong artifact release')
    for name, expected in manifest['files'].items():
        if sha(BASE / name) != expected:
            raise RuntimeError('Reviewed artifact changed: ' + name)
    source = json.loads((BASE / 't1-upgrade/approved-source.json').read_text())
    for name, expected in source['source_files'].items():
        if sha(Path('/usr/src/apple-ib-drv-0.1') / name) != expected:
            raise RuntimeError('Installed DKMS source changed: ' + name)
    if not Path('/boot/vmlinuz-' + STOCK).is_file():
        raise RuntimeError('Stock rollback kernel is missing')
    stock_entry = entries(STOCK)
    if PIN.exists() and not PIN.read_text().startswith('# Managed MacBook test-kernel boot selection.\n'):
        raise RuntimeError('Refusing to overwrite an existing GRUB drop-in')
    # Validate every destination before modifying any of them.
    for relative, (name, mode) in FILES.items():
        path = Path(name)
        if path.is_symlink():
            raise RuntimeError('Unexpected symlink: ' + name)
        if path.exists():
            allowed = {sha(BASE / relative)}
            if name == '/usr/local/sbin/mbp-t1-s3-handshake':
                allowed.add(OLD_HELPER)
                allowed.add(PRE_ACPIDBG_HELPER)
            if sha(path) not in allowed:
                raise RuntimeError('Existing managed destination differs: ' + name)
    BACKUP.mkdir(parents=True, exist_ok=True, mode=0o700)
    old = BACKUP / 'mbp-t1-s3-handshake.original'
    helper = Path('/usr/local/sbin/mbp-t1-s3-handshake')
    if not old.exists():
        if sha(helper) != OLD_HELPER:
            raise RuntimeError('Original helper backup is missing and current helper is unexpected')
        shutil.copy2(helper, old)
    elif sha(old) != OLD_HELPER:
        raise RuntimeError('Original helper backup changed; refusing to overwrite or rely on it')
    if not (BACKUP / 'sleep-unit.txt').exists():
        text = subprocess.check_output(['systemctl', 'cat', 'systemd-suspend.service'], text=True)
        (BACKUP / 'sleep-unit.txt').write_text(text)
    # Install the library and recorder first; approve the current build before
    # replacing the helper that depends on those records.
    for relative, (name, mode) in FILES.items():
        if name == '/usr/local/sbin/mbp-t1-s3-handshake':
            run('/usr/local/sbin/mbp-t1-record-build', STOCK)
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE / relative, path)
        path.chmod(mode)
        os.chown(path, 0, 0)
    # Pin the stock entry before installing a numerically newer test kernel.
    write_pin(stock_entry)
    run('apt-mark', 'manual', 'linux-image-' + STOCK, 'linux-headers-' + STOCK)
    packages = [str(BASE / name) for name in manifest['packages']]
    # Audit the corrected payloads and use their directory declarations to
    # scope repairs. dpkg preserves modes on existing package directories.
    from package_permissions import audit, repair_directories
    directories = set()
    for package in packages:
        directories.update(Path('/') / path for path in audit(package))
    run('dpkg', '--unpack', *packages)
    repaired = repair_directories(
        (Path('/lib/modules') / TEST,
         Path('/usr/src') / ('linux-headers-' + TEST)), directories)
    print(f'Repaired {len(repaired)} existing test-kernel directory permissions.', flush=True)
    for path in (Path('/lib/modules') / TEST,
                 Path('/usr/src') / ('linux-headers-' + TEST)):
        mode = path.stat()
        if mode.st_uid != 0 or mode.st_mode & 0o022:
            raise RuntimeError('Unsafe installed package directory permissions: ' + str(path))
    run('depmod', '-a', TEST)
    run('/usr/local/sbin/mbp-t1-record-build', TEST)
    run('dpkg', '--configure', 'linux-headers-' + TEST, 'linux-image-' + TEST)
    for package in ('linux-headers-' + TEST, 'linux-image-' + TEST):
        status = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${db:Status-Status}', package], text=True).strip()
        if status != 'installed':
            raise RuntimeError(package + ' was not fully configured: ' + status)
    for prefix in ('vmlinuz-', 'initrd.img-'):
        path = Path('/boot') / (prefix + TEST)
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError('Missing or empty boot artifact: ' + str(path))
    # Check the existing T1 recovery integration without invoking its phases.
    sys.path.insert(0, '/usr/local/lib/mbp-t1')
    from mbp_t1_guard import validate_running_build
    validate_running_build()
    helper = runpy.run_path('/usr/local/sbin/mbp-t1-s3-handshake', run_name='mbp_t1_preflight')
    helper['validate']()
    run('grub-script-check', '/boot/grub/grub.cfg')
    test_entry = entries(TEST)
    run('grub-reboot', test_entry)
    environment = subprocess.check_output(
        ['grub-editenv', '/boot/grub/grubenv', 'list'], text=True).splitlines()
    if 'next_entry=' + test_entry not in environment:
        raise RuntimeError('GRUB did not retain the requested one-time kernel selection')
    print('\nInstalled. No suspend, reboot, firmware call, or live module reload was performed.')
    print('The next normal reboot will use ' + TEST + ' once.')
    print('Subsequent boots default to ' + STOCK + ' until validation promotes the test kernel.')
    print('The T1 source/build guards and DKMS upgrade hooks are installed.')
    print('Save your work and restart normally when ready, then run the verification script.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('INSTALL STOPPED: ' + str(error)
                         + '\nInstallation is incomplete. Do not reboot for testing until this installer prints "Installed."'
                         + '\nThe stock kernel remains available; no automatic reboot was requested.')
