"""Approve per-kernel DKMS builds of the validated T1 source checkpoint.

This module never evaluates firmware methods. Approval requires unchanged
reviewed source, an installed DKMS build, and matching installed artifacts.
Running validation additionally checks the loaded modules' srcversions.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

APPROVAL = Path('/etc/mbp-t1/approved-source.json')
SOURCE = Path('/usr/src/apple-ib-drv-0.1')
STATE = Path('/var/lib/mbp-t1/approved-builds')
BASELINE = Path('/etc/mbp-t1/validated-baseline.json')
MODULES = ('apple_ibridge', 'apple_touchbar')
SOURCE_FILES = {'Makefile', 'dkms.conf', 'apple-ibridge.c', 'apple-ibridge.h',
                'apple-touchbar.c', 'hid-ids.h'}


class BuildGuardError(RuntimeError):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trusted(path, owner=0):
    """Reject editable trust records and source/artifact files."""
    p = path.resolve(strict=True)
    for item in (p, *p.parents):
        s = item.stat()
        if s.st_uid != owner or s.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise BuildGuardError(f'Untrusted ownership/permissions: {item}')
    return p


def check_source(approval=APPROVAL, source=SOURCE, owner=0):
    trusted(approval, owner)
    record = json.loads(approval.read_text())
    files = record.get('source_files', {})
    if record.get('schema') != 1 or set(files) != SOURCE_FILES:
        raise BuildGuardError('Invalid approved-source manifest')
    for name, expected in files.items():
        path = trusted(source / name, owner)
        if digest(path) != expected:
            raise BuildGuardError(f'T1 source changed and requires review: {name}')
    return digest(approval)


def kernel_name(kernel):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+\-]*', kernel):
        raise BuildGuardError('Invalid kernel release')
    return kernel


def valid_metadata(kernel, version, vermagic):
    # Current installed DKMS modules expose 23 hex digits; do not assume
    # srcversion has a fixed printable width. Artifact SHA256 is checked too.
    words = vermagic.split()
    return bool(re.fullmatch(r'[A-Fa-f0-9]{1,64}', version) and words and words[0] == kernel)


def probe_installed(kernel):
    kernel_name(kernel)
    r = subprocess.run(['/usr/sbin/dkms', 'status', '-m', 'apple-ib-drv',
                        '-v', '0.1', '-k', kernel], text=True, capture_output=True,
                       timeout=30, check=True)
    status = re.compile(r'apple-ib-drv/0\.1, ' + re.escape(kernel)
                        + r', x86_64: installed(?:\s+\(.*\))?')
    if not any(status.fullmatch(line.strip()) for line in r.stdout.splitlines()):
        raise BuildGuardError(f'T1 DKMS build is not installed for {kernel}')
    root = (Path('/lib/modules') / kernel / 'updates' / 'dkms').resolve()
    dkms = Path('/var/lib/dkms/apple-ib-drv/0.1') / kernel / 'x86_64/module'
    result = {}
    for module in MODULES:
        def info(field):
            return subprocess.check_output(['/usr/sbin/modinfo', '-k', kernel,
                                            '-F', field, module], text=True, timeout=10).strip()
        path = Path(info('filename')).resolve(strict=True)
        if not path.is_relative_to(root):
            raise BuildGuardError(f'{module} did not resolve to the DKMS module directory')
        trusted(path)
        original = trusted(dkms / path.name)
        if digest(path) != digest(original):
            raise BuildGuardError(f'{module} does not match its DKMS build artifact')
        version = info('srcversion')
        vermagic = info('vermagic')
        if not valid_metadata(kernel, version, vermagic):
            raise BuildGuardError(f'Invalid module metadata for {module}')
        result[module] = {'path': str(path), 'sha256': digest(path),
                          'srcversion': version, 'vermagic': vermagic}
    return result


def record_installed(kernel, approval=APPROVAL, source=SOURCE, state=STATE,
                     owner=0, probe=probe_installed, verification='verified-source-build'):
    kernel_name(kernel)
    approved = check_source(approval, source, owner)
    modules = probe(kernel)
    if set(modules) != set(MODULES):
        raise BuildGuardError('Both T1 modules must be verified')
    state.mkdir(parents=True, exist_ok=True, mode=0o755)
    trusted(state, owner)
    data = {'schema': 1, 'kernel': kernel, 'approval_sha256': approved,
            'modules': modules, 'verification': verification}
    with tempfile.NamedTemporaryFile(mode='w', dir=state, delete=False) as f:
        json.dump(data, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
        temporary = Path(f.name)
    try:
        os.replace(temporary, state / (kernel + '.json'))
        directory = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def rebuild_dkms(kernel):
    # A DKMS version may have old artifacts for an older kernel even though its
    # global source directory has since changed. Establish fresh provenance.
    for action in ('build', 'install'):
        subprocess.run(['/usr/sbin/dkms', action, '--force', '-m', 'apple-ib-drv',
                        '-v', '0.1', '-k', kernel], check=True)


def approve_installed(kernel, approval=APPROVAL, source=SOURCE, state=STATE,
                      baseline=BASELINE, owner=0, probe=probe_installed,
                      builder=rebuild_dkms):
    kernel_name(kernel)
    source_digest = check_source(approval, source, owner)
    try:
        modules = probe(kernel)
    except (BuildGuardError, subprocess.CalledProcessError, FileNotFoundError):
        modules = None
    if modules:
        path = state / (kernel + '.json')
        if path.exists():
            trusted(path, owner)
            existing = json.loads(path.read_text())
            if (existing.get('schema') == 1 and existing.get('kernel') == kernel
                    and existing.get('approval_sha256') == source_digest
                    and existing.get('modules') == modules
                    and existing.get('verification') in
                    ('verified-source-build', 'validated-stock-checkpoint')):
                return existing
        if baseline.exists():
            trusted(baseline, owner)
            proof = json.loads(baseline.read_text())
            if (proof.get('kernel') == kernel and proof.get('modules') == modules
                    and proof.get('approval_sha256') == source_digest):
                return record_installed(kernel, approval, source, state, owner,
                                        probe=lambda k: modules,
                                        verification='validated-stock-checkpoint')
    builder(kernel)
    if check_source(approval, source, owner) != source_digest:
        raise BuildGuardError('Source approval changed during the DKMS rebuild')
    return record_installed(kernel, approval, source, state, owner, probe=probe)


def validate_running_build(kernel=None, approval=APPROVAL, source=SOURCE,
                           state=STATE, sysmodules=Path('/sys/module'), owner=0):
    kernel = kernel_name(kernel or os.uname().release)
    approved = check_source(approval, source, owner)
    path = state / (kernel + '.json')
    if not path.exists():
        raise BuildGuardError(f'No approved T1 DKMS build for kernel {kernel}; deep sleep is blocked')
    trusted(path, owner)
    record = json.loads(path.read_text())
    if (record.get('schema') != 1 or record.get('kernel') != kernel
            or record.get('approval_sha256') != approved
            or record.get('verification') not in
            ('verified-source-build', 'validated-stock-checkpoint')
            or set(record.get('modules', {})) != set(MODULES)):
        raise BuildGuardError('Kernel/source approval does not match the running system')
    for module, info in record['modules'].items():
        path = trusted(Path(info['path']), owner)
        if digest(path) != info['sha256'] or info['vermagic'].split()[0] != kernel:
            raise BuildGuardError(f'Installed {module} changed after approval')
        loaded = (sysmodules / module / 'srcversion').read_text().strip()
        if loaded != info['srcversion']:
            raise BuildGuardError(f'Loaded {module} does not match the approved build; reboot or investigate')
    return record
