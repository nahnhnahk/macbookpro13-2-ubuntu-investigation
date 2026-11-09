# Configuration examples

These files describe the validated machine's installed arrangement. No file in this directory is automatically installed by cloning or CI.

- `90-mbp132-deep.conf`: systemd deep-sleep selection.
- `99-mbp132-suspend.cfg`: retained PCIe and initial sleep-mode boot arguments.
- `apple-touchbar.conf`: retained probe-time protection.
- `90-mbp-t1-handshake.conf`: guarded ordinary systemd suspend recovery phases.
- `98-mbp132-test-kernel.cfg.example`: promoted patched-kernel default, with a synthetic disk UUID. Generate entries from actual GRUB declarations on the intended machine; never copy this UUID verbatim.

The iBridge source approval, verified kernel builds and standalone debugger client must be installed and validated before the systemd firmware helper is usable. See the current-state and reproduction documents.
