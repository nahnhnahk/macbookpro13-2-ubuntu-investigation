"""Normalize and audit permissions for locally built, root-owned packages."""
from pathlib import PurePosixPath
import os
import stat
import subprocess
import tarfile


def normalize(root):
    for path in [root, *root.rglob('*')]:
        if path.is_symlink():
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        path.chmod(mode & ~0o022)


def validate_member(member):
    if member.uid != 0 or member.gid != 0:
        raise RuntimeError('Package member is not root-owned: ' + member.name)
    if not member.issym() and member.mode & 0o022:
        raise RuntimeError('Package member permits group/other writes: ' + member.name)


def audit(package):
    directories = set()
    process = subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(package)],
                               stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                validate_member(member)
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts:
                    raise RuntimeError('Unsafe package path: ' + member.name)
                if member.isdir():
                    if member.mode != 0o755:
                        raise RuntimeError('Unexpected package directory mode: ' + member.name)
                    directories.add(path)
        if process.wait() != 0:
            raise RuntimeError('Cannot read package payload: ' + str(package))
        return directories
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()


def repair_directories(roots, declared, owner=0):
    """Repair dpkg-preserved 0775 modes only inside the supplied package trees.

    `declared` must come from audited package payloads. No files, shared system
    ancestors, symlinks, ownership, or unrelated paths are changed.
    """
    roots = tuple(roots)
    declared = set(declared)
    if any(root not in declared for root in roots):
        raise RuntimeError('Repair root is not declared in the packages')
    canonical = {}
    for root in roots:
        if not stat.S_ISDIR(root.lstat().st_mode):
            raise RuntimeError('Repair root is not a real directory: ' + str(root))
        canonical[root] = root.resolve(strict=True)
    targets = []
    for path in sorted(declared):
        root = next((root for root in roots if path.is_relative_to(root)), None)
        if root is None:
            continue
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise RuntimeError('Package directory is missing or a symlink: ' + str(path))
        if path.resolve(strict=True) != canonical[root] / path.relative_to(root):
            raise RuntimeError('Package directory has a redirected parent: ' + str(path))
        if info.st_uid != owner or info.st_gid != owner:
            raise RuntimeError('Unexpected package directory ownership: ' + str(path))
        if stat.S_IMODE(info.st_mode) not in (0o755, 0o775):
            raise RuntimeError('Unexpected package directory mode: ' + str(path))
        targets.append((path, info.st_dev, info.st_ino))
    # Validate the complete set before changing anything, then recheck each
    # opened directory's identity. Never follow a replacement leaf symlink.
    repaired = []
    for path, device, inode in targets:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if ((info.st_dev, info.st_ino) != (device, inode)
                    or info.st_uid != owner or info.st_gid != owner
                    or stat.S_IMODE(info.st_mode) not in (0o755, 0o775)):
                raise RuntimeError('Package directory changed during repair: ' + str(path))
            if stat.S_IMODE(info.st_mode) == 0o775:
                os.fchmod(fd, 0o755)
                repaired.append(path)
        finally:
            os.close(fd)
    return repaired
