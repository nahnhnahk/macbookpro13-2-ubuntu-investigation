import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import unittest.mock
from types import SimpleNamespace

import mbp_t1_guard as guard


class BuildGuardTests(unittest.TestCase):
    def setUp(self):
        # /tmp is intentionally shared/writable, so trust checks are mocked
        # separately here; the corruption, identity, and hash checks stay real.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        hashes = {}
        for name in guard.SOURCE_FILES:
            path = self.source / name
            path.write_text('validated source ' + name)
            hashes[name] = guard.digest(path)
        self.approval = self.root / 'approval.json'
        self.approval.write_text(json.dumps({'schema': 1, 'source_files': hashes}))
        self.state = self.root / 'state'
        self.sysmodules = self.root / 'sysmodules'
        self.trust = unittest.mock.patch.object(guard, 'trusted', side_effect=lambda p, owner=0: p.resolve(strict=True))
        self.trust.start()
        self.addCleanup(self.trust.stop)

    def approve(self, kernel, version):
        modules = {}
        for module in guard.MODULES:
            p = self.root / (kernel + module + '.ko')
            p.write_text('compiled module ' + kernel + module)
            modules[module] = {'path': str(p), 'sha256': guard.digest(p),
                               'srcversion': version, 'vermagic': kernel + ' SMP'}
            loaded = self.sysmodules / module
            loaded.mkdir(parents=True, exist_ok=True)
            (loaded / 'srcversion').write_text(version)
        return guard.record_installed(kernel, self.approval, self.source, self.state,
                                      probe=lambda k: modules)

    def validate(self, kernel):
        return guard.validate_running_build(kernel, self.approval, self.source,
                                             self.state, self.sysmodules)

    def test_rebuilt_module_with_new_srcversion_is_accepted_for_new_kernel(self):
        self.approve('stock-kernel', 'A' * 24)
        self.validate('stock-kernel')
        self.approve('upgraded-kernel', 'B' * 24)
        self.validate('upgraded-kernel')

    def test_unknown_kernel_is_blocked(self):
        self.approve('stock-kernel', 'A' * 24)
        with self.assertRaisesRegex(guard.BuildGuardError, 'No approved'):
            self.validate('unknown-kernel')

    def test_changed_source_is_blocked(self):
        self.approve('kernel', 'A' * 24)
        (self.source / 'apple-touchbar.c').write_text('unreviewed modification')
        with self.assertRaisesRegex(guard.BuildGuardError, 'source changed'):
            self.validate('kernel')

    def test_changed_installed_module_is_blocked(self):
        record = self.approve('kernel', 'A' * 24)
        Path(record['modules']['apple_touchbar']['path']).write_text('different module')
        with self.assertRaisesRegex(guard.BuildGuardError, 'changed after approval'):
            self.validate('kernel')

    def test_stale_loaded_module_is_blocked(self):
        self.approve('kernel', 'A' * 24)
        (self.sysmodules / 'apple_touchbar/srcversion').write_text('B' * 24)
        with self.assertRaisesRegex(guard.BuildGuardError, 'Loaded apple_touchbar'):
            self.validate('kernel')

    def test_manifest_for_other_kernel_is_blocked(self):
        self.approve('kernel', 'A' * 24)
        path = self.state / 'kernel.json'
        record = json.loads(path.read_text())
        record['kernel'] = 'another-kernel'
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(guard.BuildGuardError, 'does not match'):
            self.validate('kernel')

    def test_missing_second_module_is_blocked(self):
        with self.assertRaisesRegex(guard.BuildGuardError, 'Both T1 modules'):
            guard.record_installed('kernel', self.approval, self.source, self.state,
                                   probe=lambda k: {})

    def test_unverified_installed_build_requires_fresh_rebuild(self):
        record = self.approve('kernel', 'A' * 23)
        (self.state / 'kernel.json').unlink()
        builder = unittest.mock.Mock()
        result = guard.approve_installed('kernel', self.approval, self.source, self.state,
                                         baseline=self.root / 'none.json',
                                         probe=lambda k: record['modules'], builder=builder)
        builder.assert_called_once_with('kernel')
        self.assertEqual(result['verification'], 'verified-source-build')
        self.validate('kernel')

    def test_unchanged_approved_build_does_not_rebuild_again(self):
        record = self.approve('kernel', 'A' * 23)
        builder = unittest.mock.Mock()
        result = guard.approve_installed('kernel', self.approval, self.source, self.state,
                                         baseline=self.root / 'none.json',
                                         probe=lambda k: record['modules'], builder=builder)
        builder.assert_not_called()
        self.assertEqual(result, record)

    def test_exact_validated_stock_proof_can_be_adopted(self):
        record = self.approve('stock-kernel', 'A' * 23)
        (self.state / 'stock-kernel.json').unlink()
        proof = self.root / 'baseline.json'
        proof.write_text(json.dumps(record))
        builder = unittest.mock.Mock()
        result = guard.approve_installed('stock-kernel', self.approval, self.source, self.state,
                                         baseline=proof, probe=lambda k: record['modules'],
                                         builder=builder)
        builder.assert_not_called()
        self.assertEqual(result['verification'], 'validated-stock-checkpoint')
        self.validate('stock-kernel')

    def test_other_kernel_baseline_does_not_skip_rebuild(self):
        record = self.approve('kernel', 'A' * 23)
        (self.state / 'kernel.json').unlink()
        proof = self.root / 'baseline.json'
        proof.write_text(json.dumps({**record, 'kernel': 'other-kernel'}))
        builder = unittest.mock.Mock()
        guard.approve_installed('kernel', self.approval, self.source, self.state,
                                baseline=proof, probe=lambda k: record['modules'], builder=builder)
        builder.assert_called_once_with('kernel')

    def test_source_change_during_rebuild_does_not_create_approval(self):
        record = self.approve('kernel', 'A' * 23)
        (self.state / 'kernel.json').unlink()
        def mutate_source(kernel):
            (self.source / 'apple-touchbar.c').write_text('changed during build')
        with self.assertRaisesRegex(guard.BuildGuardError, 'source changed'):
            guard.approve_installed('kernel', self.approval, self.source, self.state,
                                    baseline=self.root / 'none.json',
                                    probe=lambda k: record['modules'], builder=mutate_source)
        self.assertFalse((self.state / 'kernel.json').exists())


class TrustTests(unittest.TestCase):
    def test_current_23_digit_module_fingerprint_is_valid(self):
        self.assertTrue(guard.valid_metadata('kernel', 'D521E1602E61EB9488ED344', 'kernel SMP'))

    def test_missing_or_other_kernel_metadata_is_rejected(self):
        self.assertFalse(guard.valid_metadata('kernel', '', 'kernel SMP'))
        self.assertFalse(guard.valid_metadata('kernel', 'A' * 24, 'other-kernel SMP'))

    def fake(self, file_uid=0, file_mode=0o100644, parent_mode=0o40755):
        parent = unittest.mock.Mock()
        parent.stat.return_value = SimpleNamespace(st_uid=0, st_mode=parent_mode)
        path = unittest.mock.Mock()
        path.resolve.return_value = path
        path.parents = [parent]
        path.stat.return_value = SimpleNamespace(st_uid=file_uid, st_mode=file_mode)
        return path

    def test_root_owned_readonly_to_other_users_is_accepted(self):
        path = self.fake()
        self.assertIs(guard.trusted(path), path)

    def test_nonroot_owner_is_rejected(self):
        with self.assertRaises(guard.BuildGuardError):
            guard.trusted(self.fake(file_uid=1000))

    def test_group_writable_manifest_is_rejected(self):
        with self.assertRaises(guard.BuildGuardError):
            guard.trusted(self.fake(file_mode=0o100664))

    def test_writable_parent_is_rejected(self):
        with self.assertRaises(guard.BuildGuardError):
            guard.trusted(self.fake(parent_mode=0o40777))


if __name__ == '__main__':
    unittest.main()
