import importlib.util
from pathlib import Path
import tempfile
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('handshake', Path(__file__).with_name('mbp-t1-s3-handshake.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HandshakeScenarios(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name)
        self.check = Mock()
        self.call = Mock()
        self.pause = Mock()

    def phase(self, action, mode='deep'):
        return h.phase(action, self.state, mode, self.check, self.call, self.pause)

    def test_unapproved_kernel_build_blocks_real_validator_before_firmware(self):
        import mbp_t1_guard
        values = {
            '/sys/class/dmi/id/product_name': 'MacBookPro13,2',
            '/sys/module/apple_ibridge/parameters/skip_acpi_power': '1',
            '/sys/bus/acpi/devices/APP7777:00/path': r'\_SB_.PCI0.XHC1.RHUB.ASOC',
            '/proc/cmdline': 'pcie_port_pm=off',
        }
        def read(path, *args, **kwargs):
            return values[str(path)]
        with patch.object(Path, 'read_text', autospec=True, side_effect=read), \
                patch.object(h.os, 'access', return_value=True), \
                patch.object(mbp_t1_guard, 'validate_running_build',
                             side_effect=mbp_t1_guard.BuildGuardError('unapproved build')):
            with self.assertRaises(mbp_t1_guard.BuildGuardError):
                h.phase('pre', self.state, mode='deep', call=self.call, pause=self.pause)
        self.call.assert_not_called()
        self.assertFalse((self.state / 'pending.json').exists())

    def test_s2idle_never_calls_firmware(self):
        self.phase('pre', 's2idle')
        self.phase('post')
        self.call.assert_not_called()

    def test_configured_mode_overrides_current_kernel_selection(self):
        config = '[Sleep]\nMemorySleepMode=s2idle\n[Sleep]\nMemorySleepMode=deep\n'
        self.assertEqual(h.selected_mode(config, '[s2idle] deep'), 'deep')
        self.assertEqual(h.selected_mode('[Sleep]\nMemorySleepMode=\n', '[s2idle] deep'), 's2idle')

    def test_normal_cycle_and_stop_fallback_call_wake_only_once(self):
        self.phase('pre')
        self.phase('post')
        self.phase('post')
        self.assertEqual([c.args[0] for c in self.call.call_args_list], [0, 1])
        self.pause.assert_called_once_with(15)

    def test_failed_sleep_is_compensated_and_suspend_is_cancelled(self):
        self.call.side_effect = [h.HandshakeError('firmware sleep rejected'), None]
        with self.assertRaises(h.HandshakeError):
            self.phase('pre')
        self.phase('post')
        self.assertEqual([c.args[0] for c in self.call.call_args_list], [0, 1])

    def test_failed_wake_is_not_retried_by_stop_fallback(self):
        self.phase('pre')
        self.call.side_effect = h.HandshakeError('firmware wake rejected')
        with self.assertRaises(h.HandshakeError):
            self.phase('post')
        self.phase('post')
        self.assertEqual([c.args[0] for c in self.call.call_args_list], [0, 1])

    def test_guard_failure_makes_no_firmware_call(self):
        self.check.side_effect = h.HandshakeError('wrong machine or driver')
        with self.assertRaises(h.HandshakeError):
            self.phase('pre')
        self.call.assert_not_called()

    def test_unavailable_client_blocks_before_pending_marker_or_firmware(self):
        with patch.object(h, 'ACPIDBG_APPROVAL', self.state / 'missing-approval'):
            with self.assertRaises(FileNotFoundError):
                h.phase('pre', self.state, mode='deep', check=h.validate_acpidbg,
                        call=self.call, pause=self.pause)
        self.call.assert_not_called()
        self.assertFalse((self.state / 'pending.json').exists())

    def test_standalone_client_help_check_never_sends_a_debugger_command(self):
        import mbp_t1_guard
        binary = self.state / 'acpidbg'
        binary.write_bytes(b'\x7fELFtest-client')
        approval = self.state / 'acpidbg.json'
        approval.write_text(json.dumps({'schema': 1, 'path': str(binary),
            'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}))
        with patch.object(h, 'ACPIDBG', binary), patch.object(h, 'ACPIDBG_APPROVAL', approval), \
                patch.object(mbp_t1_guard, 'trusted', side_effect=lambda p: p), \
                patch.object(h.subprocess, 'run') as run:
            run.return_value = Mock(returncode=0,
                stdout='Specify command to be executed in batch mode')
            h.validate_acpidbg()
            self.assertEqual(run.call_args.args[0], [str(binary), '-h'])
            binary.write_bytes(b'\x7fELFchanged-client')
            run.reset_mock()
            with self.assertRaisesRegex(h.HandshakeError, 'approval'):
                h.validate_acpidbg()
            run.assert_not_called()

    def test_readiness_failure_blocks_before_firmware_pair(self):
        import mbp_t1_guard
        binary = self.state / 'acpidbg'
        binary.write_bytes(b'\x7fELFtest-client')
        approval = self.state / 'acpidbg.json'
        approval.write_text(json.dumps({'schema': 1, 'path': str(binary),
            'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}))
        with patch.object(h, 'ACPIDBG', binary), patch.object(h, 'ACPIDBG_APPROVAL', approval), \
                patch.object(mbp_t1_guard, 'trusted', side_effect=lambda p: p), \
                patch.object(h.subprocess, 'run', return_value=Mock(returncode=2, stdout='missing tool')):
            with self.assertRaisesRegex(h.HandshakeError, 'readiness'):
                h.phase('pre', self.state, mode='deep', check=h.validate_acpidbg,
                        call=self.call, pause=self.pause)
        self.call.assert_not_called()
        self.assertFalse((self.state / 'pending.json').exists())

    def test_firmware_command_uses_direct_client_and_preserves_arguments(self):
        with patch.object(h.subprocess, 'run', return_value=Mock(
                returncode=0, stdout='[Integer] = 0000000000000000\n')) as run:
            h.call_socw(0)
        self.assertEqual(run.call_args.args[0],
                         [str(h.ACPIDBG), '-b', f'execute {h.METHOD} 0'])


if __name__ == '__main__':
    unittest.main()
