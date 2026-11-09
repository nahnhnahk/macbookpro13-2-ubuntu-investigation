#!/usr/bin/env python3
"""Apply reviewed upstream changes to the exact downloaded Ubuntu source.

The older driver keeps its PCI table in nhi.c. Use v3's mutex-held callback
placement, which was hardware-tested by the author, and preserve the old
driver's optional-operations semantics. No installed files are touched.
"""
from pathlib import Path
from email import policy
from email.parser import BytesParser
import difflib
import hashlib
import json
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parent
SRC = BASE / 'linux-source-7.0.0'
PATCHES = BASE / 'patches'
FILES = ['drivers/pci/pci.c', 'drivers/acpi/acpica/hwpci.c'] + [
    'drivers/thunderbolt/' + p for p in
    ['acpi.c', 'domain.c', 'nhi.c', 'nhi.h', 'switch.c', 'tb.h', 'tb_regs.h']]


def replace(name, before, after):
    path = SRC / name
    text = path.read_text()
    assert text.count(before) == 1, (name, before[:100], text.count(before))
    path.write_text(text.replace(before, after, 1))


def added_code(patch, name):
    chunk = patch.split('diff --git a/' + name + ' b/' + name + '\n', 1)[1]
    chunk = chunk.split('\ndiff --git ', 1)[0]
    return '\n'.join(line[1:] for line in chunk.splitlines()
                     if line.startswith('+') and not line.startswith('+++')) + '\n'


def main():
    original = BASE / 'pristine-files'
    if original.exists():
        assert sys.argv[1:] == ['--retry'], 'Pristine backup exists; use --retry to restore these files and reapply.'
        for name in FILES:
            shutil.copy2(original / name, SRC / name)
    for name in FILES:
        dest = original / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(SRC / name, dest)

    # These PCI changes are absent in this Ubuntu source. The first is the
    # upstream helper commit required by the author's system-suspend guard.
    for name in ['pci-config-accessible.patch', 'pci-save-state.patch', 'pci-link-status.patch']:
        cmd = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCHES / name)]
        subprocess.run(cmd[:1] + ['--dry-run'] + cmd[1:], cwd=SRC, check=True)
        subprocess.run(cmd, cwd=SRC, check=True)

    # Linux's ACPICA copy uses lower-case identifiers. Port the functional
    # change shared by ACPICA PRs 1235/1236, not both equivalent patches.
    replace('drivers/acpi/acpica/hwpci.c',
            '#define PCI_CFG_PRIMARY_BUS_NUMBER_REG      0x18\n', '')
    replace('drivers/acpi/acpica/hwpci.c',
            '\t/* Bridge: Get the Primary bus_number */\n\n'
            '\tstatus = acpi_os_read_pci_configuration(pci_id,\n'
            '\t\t\t\t\t\tPCI_CFG_PRIMARY_BUS_NUMBER_REG,\n'
            '\t\t\t\t\t\t&pci_value, 8);\n'
            '\tif (ACPI_FAILURE(status)) {\n\t\treturn (status);\n\t}\n\n'
            '\t*is_bridge = TRUE;\n\tpci_id->bus = (u16)pci_value;\n',
            '\t/*\n'
            '\t * Keep the bus inherited from the parent bridge. Its primary bus\n'
            '\t * register can still hold its reset value before PCI state has\n'
            '\t * been restored during resume. Using it would cache a wrong\n'
            '\t * address for the PCI_Config region and the following read.\n'
            '\t */\n\t*is_bridge = TRUE;\n')

    message = BytesParser(policy=policy.default).parsebytes((PATCHES / 'thunderbolt-v3.mbox').read_bytes())
    patch = message.get_body(preferencelist=('plain',)).get_content()
    (PATCHES / 'thunderbolt-v3.patch').write_text(patch)

    acpi = added_code(patch, 'drivers/thunderbolt/acpi.c')
    acpi = acpi[acpi.index('/**'):].replace('ACPI_COMPANION(tb->nhi->dev)',
                                         'ACPI_COMPANION(&tb->nhi->pdev->dev)')
    replace('drivers/thunderbolt/acpi.c', '#include <linux/pm_runtime.h>\n',
            '#include <linux/pm_runtime.h>\n#include <linux/suspend.h>\n')
    replace('drivers/thunderbolt/acpi.c', 'static bool tb_acpi_bus_match(struct device *dev)',
            acpi + 'static bool tb_acpi_bus_match(struct device *dev)')

    switch = added_code(patch, 'drivers/thunderbolt/switch.c')
    replace('drivers/thunderbolt/switch.c',
            '/**\n * tb_switch_xhci_disconnect() - Disconnect internal xHCI',
            switch + '/**\n * tb_switch_xhci_disconnect() - Disconnect internal xHCI')
    replace('drivers/thunderbolt/tb_regs.h',
            '#define TB_PLUG_EVENTS_PCIE_WR_DATA\t\t0x1b',
            '#define TB_PLUG_EVENTS_CS_20\t\t\t0x14\n'
            '#define TB_PLUG_EVENTS_CS_20_BIT26\t\tBIT(26)\n\n'
            '#define TB_PLUG_EVENTS_PCIE_WR_DATA\t\t0x1b')
    replace('drivers/thunderbolt/tb.h',
            'void tb_switch_xhci_disconnect(struct tb_switch *sw);',
            'void tb_switch_xhci_disconnect(struct tb_switch *sw);\n'
            'int tb_switch_set_bit26(struct tb_switch *sw, bool value);')
    replace('drivers/thunderbolt/tb.h', 'void tb_acpi_exit(void);',
            'void tb_acpi_exit(void);\nvoid tb_acpi_force_power(struct tb *tb);')
    replace('drivers/thunderbolt/tb.h', 'static inline void tb_acpi_exit(void) { }',
            'static inline void tb_acpi_exit(void) { }\n'
            'static inline void tb_acpi_force_power(struct tb *tb) { }')
    replace('drivers/thunderbolt/nhi.h',
            ' * @init: NHI specific initialization\n',
            ' * @init: NHI specific initialization\n'
            ' * @pre_suspend_noirq: Called before the domain is suspended, with tb->lock held\n')
    replace('drivers/thunderbolt/nhi.h', '\tint (*init)(struct tb_nhi *nhi);',
            '\tint (*init)(struct tb_nhi *nhi);\n'
            '\tvoid (*pre_suspend_noirq)(struct tb_nhi *nhi);')
    replace('drivers/thunderbolt/domain.c',
            '\tmutex_lock(&tb->lock);\n\tif (tb->cm_ops->suspend_noirq)',
            '\tmutex_lock(&tb->lock);\n'
            '\tif (tb->nhi->ops && tb->nhi->ops->pre_suspend_noirq)\n'
            '\t\ttb->nhi->ops->pre_suspend_noirq(tb->nhi);\n'
            '\tif (tb->cm_ops->suspend_noirq)')
    replace('drivers/thunderbolt/nhi.c', '#include <linux/pm_runtime.h>\n',
            '#include <linux/pm_runtime.h>\n#include <linux/platform_data/x86/apple.h>\n')
    replace('drivers/thunderbolt/nhi.c', 'static struct pci_device_id nhi_ids[] = {',
            '/* Apple Alpine Ridge firmware preparation for system suspend. */\n'
            'static void ar_nhi_pre_suspend_noirq(struct tb_nhi *nhi)\n{\n'
            '\tif (x86_apple_machine)\n'
            '\t\ttb_acpi_force_power(pci_get_drvdata(nhi->pdev));\n}\n\n'
            'static const struct tb_nhi_ops ar_nhi_ops = {\n'
            '\t.pre_suspend_noirq = ar_nhi_pre_suspend_noirq,\n};\n\n'
            'static struct pci_device_id nhi_ids[] = {')
    for name in ['2C_NHI', '4C_NHI', 'USBONLY_NHI', 'LP_NHI', 'LP_USBONLY_NHI',
                 'C_2C_NHI', 'C_4C_NHI', 'C_USBONLY_NHI']:
        key = 'PCI_DEVICE_ID_INTEL_ALPINE_RIDGE_' + name
        replace('drivers/thunderbolt/nhi.c',
                '\t{ PCI_VDEVICE(INTEL, ' + key + ') },',
                '\t{ PCI_VDEVICE(INTEL, ' + key + '),\n'
                '\t  .driver_data = (kernel_ulong_t)&ar_nhi_ops },')

    changes = []
    hashes = {}
    for name in FILES:
        before = (original / name).read_bytes()
        after = (SRC / name).read_bytes()
        hashes[name] = {'before': hashlib.sha256(before).hexdigest(),
                        'after': hashlib.sha256(after).hexdigest()}
        changes.append('diff --git a/' + name + ' b/' + name + '\n')
        changes.extend(difflib.unified_diff(before.decode().splitlines(True),
                                          after.decode().splitlines(True),
                                          fromfile='a/' + name, tofile='b/' + name))
    description = ('Subject: [PATCH] Restore Apple Alpine Ridge controllers across S3\n\n'
                   'Backport the tested Thunderbolt suspend preparation and its\n'
                   'PCI state and ACPICA address-resolution prerequisites to\n'
                   'Ubuntu source package 7.0.0-43.43. The old NHI optional-ops\n'
                   'layout is retained; the callback runs with the domain lock held.\n\n'
                   'Original author submissions and signatures are retained separately.\n\n---\n')
    (PATCHES / 'ubuntu-7.0.0-43-mbp132-backport.patch').write_text(description + ''.join(changes))
    (BASE / 'source-changes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print('Backport applied and consolidated patch generated.')


if __name__ == '__main__':
    main()
