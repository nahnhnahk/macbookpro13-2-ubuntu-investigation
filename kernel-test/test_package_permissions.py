from pathlib import Path
import os
import stat
import tarfile
import tempfile
import unittest

from package_permissions import normalize, validate_member, repair_directories


class PackagePermissionsTests(unittest.TestCase):
    def test_build_workspace_modes_are_normalized_without_following_links(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'package'
            root.mkdir(mode=0o775)
            root.chmod(0o775)
            tool = root / 'tool'
            tool.write_text('executable')
            tool.chmod(0o775)
            outside = base / 'outside'
            outside.write_text('unmanaged')
            outside.chmod(0o666)
            (root / 'link').symlink_to(outside)
            normalize(root)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(tool.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o666)

    def test_group_writable_directory_is_rejected(self):
        member = tarfile.TarInfo('./lib/modules/test')
        member.type = tarfile.DIRTYPE
        member.mode = 0o775
        with self.assertRaisesRegex(RuntimeError, 'group/other writes'):
            validate_member(member)

    def test_non_root_ownership_is_rejected(self):
        member = tarfile.TarInfo('./file')
        member.uid = 1000
        member.mode = 0o644
        with self.assertRaisesRegex(RuntimeError, 'root-owned'):
            validate_member(member)

    def test_normal_symlink_permissions_are_accepted(self):
        member = tarfile.TarInfo('./lib/modules/test/build')
        member.type = tarfile.SYMTYPE
        member.mode = 0o777
        validate_member(member)

    def test_repairs_only_declared_directories_inside_test_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'test-kernel'
            child = root / 'kernel'
            child.mkdir(parents=True)
            unrelated = base / 'other-kernel'
            unrelated.mkdir()
            undeclared = root / 'unmanaged'
            undeclared.mkdir()
            for path in (root, child, unrelated, undeclared):
                path.chmod(0o775)
            module = child / 'driver.ko'
            module.write_text('module bytes')
            module.chmod(0o664)
            repaired = repair_directories((root,), {root, child, unrelated}, os.getuid())
            self.assertEqual(set(repaired), {root, child})
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(child.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), 0o775)
            self.assertEqual(stat.S_IMODE(undeclared.stat().st_mode), 0o775)
            self.assertEqual(stat.S_IMODE(module.stat().st_mode), 0o664)
            self.assertEqual(module.read_text(), 'module bytes')
            self.assertEqual(repair_directories((root,), {root, child}, os.getuid()), [])

    def test_symlink_is_rejected_before_any_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'test-kernel'
            root.mkdir()
            root.chmod(0o775)
            outside = Path(directory) / 'outside'
            outside.mkdir()
            link = root / 'link'
            link.symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, 'symlink'):
                repair_directories((root,), {root, link}, os.getuid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o775)

    def test_redirected_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'test-kernel'
            root.mkdir()
            root.chmod(0o775)
            outside = base / 'outside'
            (outside / 'child').mkdir(parents=True)
            (root / 'redirect').symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, 'redirected parent'):
                repair_directories((root,), {root, root / 'redirect/child'}, os.getuid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o775)

    def test_unexpected_ownership_or_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o775)
            with self.assertRaisesRegex(RuntimeError, 'ownership'):
                repair_directories((root,), {root}, os.getuid() + 1)
            root.chmod(0o777)
            with self.assertRaisesRegex(RuntimeError, 'mode'):
                repair_directories((root,), {root}, os.getuid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o777)


if __name__ == '__main__':
    unittest.main()
