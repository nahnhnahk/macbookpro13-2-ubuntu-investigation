import copy
import unittest
from test_suspend_wait import module as verifier


class SleepDurationTests(unittest.TestCase):
    def test_early_wake_with_recovery_delay_is_not_a_full_test(self):
        result = verifier.sleep_timing({'boottime': 100, 'monotonic': 100},
                                      {'boottime': 123, 'monotonic': 120}, 60)
        self.assertEqual(result['system_suspended_seconds'], 3)
        self.assertEqual(result['awake_seconds'], 20)
        self.assertFalse(result['duration_met'])

    def test_normal_alarm_with_entry_overhead_and_recovery_passes(self):
        result = verifier.sleep_timing({'boottime': 100, 'monotonic': 100},
                                      {'boottime': 176, 'monotonic': 119}, 60)
        self.assertEqual(result['system_suspended_seconds'], 57)
        self.assertTrue(result['duration_met'])

    def test_promotion_requires_measured_duration(self):
        old = {'passed': True, 'suspend_requested': 900,
               'after': {'kernel': verifier.RELEASE}}
        self.assertFalse(verifier.qualified_cycle(old, verifier.RELEASE))
        valid = copy.deepcopy(old)
        valid['checks'] = {'sleep_duration_met': True}
        valid['timing'] = {'schema': 1, 'duration_met': True,
                           'system_suspended_seconds': 897}
        self.assertTrue(verifier.qualified_cycle(valid, verifier.RELEASE))
        valid['timing']['system_suspended_seconds'] = 3
        self.assertFalse(verifier.qualified_cycle(valid, verifier.RELEASE))

    def lid_fixture(self):
        before = {'boot_id': 'same-boot', 'suspend_stats': {'success': 1, 'fail': 0},
                  'clocks': {'monotonic': 10, 'boottime': 10}}
        after = {'boot_id': 'same-boot', 'suspend_stats': {'success': 2, 'fail': 0},
                 'clocks': {'monotonic': 40, 'boottime': 1040}}
        verification = {'passed': True, 'suspend_requested': None,
                        'before': {'kernel': verifier.RELEASE, 'errors': []}}
        kernel = 'PM: suspend entry (deep)\nPM: suspend exit\n'
        services = 'Lid closed.\nfirmware sleep acknowledged\nLid opened.\nfirmware wake acknowledged\n'
        return [before, after, verification, kernel, services, verifier.RELEASE]

    def test_manual_cycle_requires_independent_timing_and_journal_evidence(self):
        args = self.lid_fixture()
        result = verifier.qualified_lid_comparison(*args)
        self.assertEqual(result['timing']['system_suspended_seconds'], 1000)
        self.assertEqual(result['success_index'], 2)
        self.assertEqual(result['trigger'], 'manual-lid')
        args[3] = ''
        self.assertIsNone(verifier.qualified_lid_comparison(*args))

    def test_manual_cycle_rejects_reboot_multiple_cycles_and_failed_recovery(self):
        for field in ('reboot', 'multiple', 'failure', 'missing_wake', 'bad_hardware'):
            args = self.lid_fixture()
            if field == 'reboot': args[1]['boot_id'] = 'another-boot'
            elif field == 'multiple': args[1]['suspend_stats']['success'] = 3
            elif field == 'failure': args[1]['suspend_stats']['fail'] = 1
            elif field == 'missing_wake': args[4] = args[4].replace('firmware wake acknowledged', '')
            else: args[2]['passed'] = False
            with self.subTest(field=field):
                self.assertIsNone(verifier.qualified_lid_comparison(*args))

    def test_manual_early_wake_does_not_qualify(self):
        args = self.lid_fixture()
        args[1]['clocks']['boottime'] = 43
        self.assertIsNone(verifier.qualified_lid_comparison(*args))


if __name__ == '__main__':
    unittest.main()
