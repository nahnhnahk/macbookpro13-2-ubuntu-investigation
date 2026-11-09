#!/usr/bin/env python3
"""Package a completed build without writing installed system directories."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
from package_permissions import normalize, audit

BASE = Path(__file__).resolve().parent
SRC = BASE / 'linux-source-7.0.0'
BUILD = BASE / 'build'
TOOLS = BASE / 'build-tools'
RELEASE = '7.0.14-mbp132-tb1'
VERSION = '7.0.14-1+mbp132tb1'


def run(cmd, log, local_tools=False):
    if local_tools:
        cmd = ['bash', str(BASE / 'with-build-tools.sh'), *cmd]
    with (BASE / 'logs' / log).open('a') as f:
        subprocess.run(cmd, cwd=BASE, stdout=f, stderr=subprocess.STDOUT, check=True)


def control(root, package, description, dependencies):
    directory = root / 'DEBIAN'
    directory.mkdir(parents=True, exist_ok=True)
    size = sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) // 1024
    (directory / 'control').write_text(
        f'Package: {package}\nVersion: {VERSION}\nArchitecture: amd64\n'
        f'Maintainer: Local MacBook test build <root@localhost>\n'
        f'Section: kernel\nPriority: optional\nInstalled-Size: {size}\n'
        f'Depends: {dependencies}\nDescription: {description}\n'
        ' Locally built Ubuntu-source test kernel for Apple Alpine Ridge S3 recovery.\n')


def script(root, name, body):
    path = root / 'DEBIAN' / name
    path.write_text('#!/bin/sh\nset -eu\n' + body)
    path.chmod(0o755)


def main():
    assert (BUILD / 'include/config/kernel.release').read_text().strip() == RELEASE
    assert (BUILD / 'arch/x86/boot/bzImage').is_file()
    assert (BUILD / 'Module.symvers').is_file()
    staging = BASE / 'package-roots'
    staging.mkdir(exist_ok=False)
    image = staging / 'image'
    headers = staging / 'headers'
    image.mkdir()
    headers.mkdir()
    run(['make', '-C', str(SRC), 'O=' + str(BUILD), '-j3',
         'INSTALL_MOD_PATH=' + str(image), 'INSTALL_MOD_STRIP=1', 'modules_install'],
        'modules-install.log', local_tools=True)
    module_dir = image / 'lib/modules' / RELEASE
    for name in ['build', 'source']:
        path = module_dir / name
        if path.is_symlink():
            path.unlink()
    boot = image / 'boot'
    boot.mkdir()
    for source, name, mode in [(BUILD / 'arch/x86/boot/bzImage', 'vmlinuz', 0o600),
                               (BUILD / 'System.map', 'System.map', 0o600),
                               (BUILD / '.config', 'config', 0o644)]:
        path = boot / (name + '-' + RELEASE)
        shutil.copy2(source, path)
        path.chmod(mode)

    header_dir = headers / 'usr/src' / ('linux-headers-' + RELEASE)
    command = '+$(srctree)/scripts/package/install-extmod-build ' + str(header_dir)
    run(['make', '-C', str(SRC), 'O=' + str(BUILD), 'run-command',
         'KBUILD_RUN_COMMAND=' + command], 'headers-export.log', local_tools=True)
    header_link = headers / 'lib/modules' / RELEASE / 'build'
    header_link.parent.mkdir(parents=True)
    header_link.symlink_to('/usr/src/linux-headers-' + RELEASE)

    # Host utilities must resolve distribution libraries on the installed system,
    # not a writable build-tools directory in this workspace.
    for p in sorted((BASE / 'downloads').glob('chrpath_*.deb')):
        subprocess.run(['dpkg-deb', '-x', str(p), str(TOOLS)], check=True)
    chrpath = TOOLS / 'usr/bin/chrpath'
    for path in header_dir.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as f:
            head = f.read(20)
        if len(head) < 20 or head[:4] != b'\x7fELF':
            continue
        endian = '<' if head[5] == 1 else '>'
        if struct.unpack(endian + 'H', head[16:18])[0] not in (2, 3):
            continue
        result = subprocess.run([str(chrpath), '-l', str(path)], capture_output=True, text=True)
        if result.returncode == 0:
            subprocess.run([str(chrpath), '-d', str(path)], check=True)

    # Prove that the exported headers can build the current DKMS source without
    # the workspace tool wrapper, as a normal post-upgrade DKMS build would.
    driver = BASE / 'driver-header-check'
    driver.mkdir()
    for path in (BASE / 'apple-ib-driver').iterdir():
        if path.is_file():
            shutil.copy2(path, driver / path.name)
    run(['make', '-C', str(header_dir), 'M=' + str(driver), '-j3', 'modules'],
        'touchbar-build.log')
    metadata = {}
    for module in ['apple-ibridge', 'apple-touchbar']:
        path = driver / (module + '.ko')
        fields = {}
        for field in ['srcversion', 'vermagic']:
            fields[field] = subprocess.check_output(['modinfo', '-F', field, str(path)], text=True).strip()
        assert fields['vermagic'].split()[0] == RELEASE
        fields['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata[module] = fields
    (BASE / 'test-driver-build.json').write_text(json.dumps(metadata, indent=2) + '\n')

    control(image, 'linux-image-' + RELEASE, 'MacBookPro13,2 Alpine Ridge S3 test kernel',
            'kmod, dracut | initramfs-tools, linux-base')
    control(headers, 'linux-headers-' + RELEASE, 'Build headers for the MacBook S3 test kernel',
            'libc6, libelf1t64 (>= 0.194), libssl3t64 (>= 3.5), libzstd1, zlib1g, gcc-15, make')
    script(image, 'postinst', f'''if [ "${{1:-}}" = configure ]; then
    depmod -a {RELEASE}
    if [ -e /boot/initrd.img-{RELEASE} ]; then
        update-initramfs -u -k {RELEASE}
    else
        update-initramfs -c -k {RELEASE}
    fi
    update-grub
fi
''')
    script(image, 'prerm', f'''if [ "$(uname -r)" = {RELEASE} ]; then
    echo 'Boot the stock kernel before removing this running test kernel.' >&2
    exit 1
fi
''')
    script(image, 'postrm', f'''case "${{1:-}}" in
remove|purge)
    if [ -e /boot/initrd.img-{RELEASE} ]; then
        update-initramfs -d -k {RELEASE}
    fi
    update-grub
    ;;
esac
''')
    packages = BASE / 'packages'
    packages.mkdir()
    hashes = {}
    for root, kind in [(headers, 'headers'), (image, 'image')]:
        normalize(root)
        path = packages / f'linux-{kind}-{RELEASE}_{VERSION}_amd64.deb'
        run(['dpkg-deb', '--root-owner-group', '-Zzstd', '-z6', '--build',
             str(root), str(path)], 'packages.log')
        audit(path)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (packages / 'SHA256SUMS').write_text(''.join(f'{h}  {name}\n' for name, h in hashes.items()))
    print('Kernel, modules, headers, and external-driver compatibility checks packaged successfully.')


if __name__ == '__main__':
    main()
