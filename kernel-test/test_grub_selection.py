import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'installer', Path(__file__).with_name('install-test-kernel.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

SUBMENU = 'gnulinux-advanced-test-uuid'
STOCK = 'gnulinux-7.0.0-43-generic-advanced-test-uuid'
TEST = 'gnulinux-7.0.14-mbp132-tb1-advanced-test-uuid'
DECLARATIONS = f'''submenu 'Advanced options for Ubuntu' $menuentry_id_option '{SUBMENU}' {{
    menuentry 'Ubuntu, with Linux 7.0.14-mbp132-tb1' --class ubuntu $menuentry_id_option '{TEST}' {{
        linux /boot/vmlinuz-7.0.14-mbp132-tb1
    }}
    menuentry 'Ubuntu, with Linux 7.0.0-43-generic' $menuentry_id_option '{STOCK}' {{
        linux /boot/vmlinuz-7.0.0-43-generic
    }}
}}
'''


class GrubSelectionTests(unittest.TestCase):
    def test_pinned_default_is_not_mistaken_for_submenu(self):
        config = f'set default="{SUBMENU}>{STOCK}"\n' + DECLARATIONS
        result = installer.entry_from_config(config, installer.TEST)
        self.assertEqual(result, SUBMENU + '>' + TEST)
        self.assertEqual(len(result.split('>')), 2)
        self.assertEqual(installer.entry_from_config(config, installer.STOCK),
                         SUBMENU + '>' + STOCK)

    def test_initial_numeric_default(self):
        self.assertEqual(installer.entry_from_config('set default="0"\n' + DECLARATIONS,
                                                     installer.TEST), SUBMENU + '>' + TEST)

    def test_only_references_do_not_count_as_declarations(self):
        with self.assertRaisesRegex(RuntimeError, 'unique explicit'):
            installer.entry_from_config(f'set default="{SUBMENU}>{TEST}"\n'
                                        + '# ' + DECLARATIONS, installer.TEST)

    def test_missing_or_duplicate_entries_are_rejected(self):
        for config in (DECLARATIONS.replace(TEST, 'other-entry'),
                       DECLARATIONS + DECLARATIONS):
            with self.subTest(config=config), self.assertRaises(RuntimeError):
                installer.entry_from_config(config, installer.TEST)

    def test_mismatched_device_identifiers_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'different device'):
            installer.entry_from_config(DECLARATIONS.replace(TEST, TEST + '-other'),
                                        installer.TEST)


if __name__ == '__main__':
    unittest.main()
