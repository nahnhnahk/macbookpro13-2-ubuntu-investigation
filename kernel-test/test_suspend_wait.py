import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('verification', Path(__file__).with_name('verify-test-kernel.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SuspendWaitTests(unittest.TestCase):
    def test_waits_for_kernel_and_post_recovery_after_queued_request(self):
        before = {'success': 2, 'fail': 0}
        after = {'success': 3, 'fail': 0}
        stats = Mock(side_effect=[before, before, after])
        service = Mock(side_effect=[{'stdout': s} for s in
                                    ['activating', 'activating', 'activating', 'inactive']])
        pause = Mock()
        result = module.wait_for_suspend(before, read_stats=stats, run=service,
                                          pause=pause, clock=lambda: 0)
        self.assertEqual(result, after)
        self.assertEqual(pause.call_count, 3)
        self.assertEqual(service.call_count, 4)

    def test_pre_suspend_service_failure_is_reported(self):
        before = {'success': 2, 'fail': 0}
        with self.assertRaisesRegex(RuntimeError, 'before a kernel cycle'):
            module.wait_for_suspend(before, read_stats=lambda: before,
                                    run=lambda cmd: {'stdout': 'failed'}, clock=lambda: 0)

    def test_failed_kernel_cycle_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, 'exactly one successful'):
            module.wait_for_suspend({'success': 2, 'fail': 0},
                                    read_stats=lambda: {'success': 2, 'fail': 1}, clock=lambda: 0)


if __name__ == '__main__':
    unittest.main()
