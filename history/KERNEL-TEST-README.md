> Historical working notes, sanitized for publication. Early statements describe the state at that stage and may have been superseded by later entries. Use [current state](../docs/CURRENT-STATE.md) for the final configuration. Paths, MACs, IPs, UUIDs and boot IDs are examples or redacted.

# MacBookPro13,2 Thunderbolt/S3 test kernel

Build, packaging and installation completed successfully on 2026-11-08. Three measured closed-lid cycles passed, including an uninterrupted 2-hour-45-minute sleep and a test with Ethernet on the opposite USB-C controller side. Ethernet and T1 recovery passed afterward. The validation threshold is met; the promotion script is ready. Stock remains the persistent boot default until that script runs.

## Source and patches

- Exact Ubuntu source package: `linux-source-7.0.0=7.0.0-43.43`, downloaded using APT and independently checked against the archive SHA256 `208b9997b555c9494535edd0dee6f0ee67a7ccddc180fb40c30218f06bd2dc59`.
- That source has upstream version `7.0.14`. The separate build release is `7.0.14-mbp132-tb1`.
- Prerequisite PCI helper: upstream commit `e18d1abc3bff` (Farhan Ali), followed by the author's PCI saved-state and inaccessible-link checks.
- ACPICA: port the shared functional correction in PRs 1235/1236 to Linux's lower-case ACPICA implementation. Apply it once.
- Thunderbolt: port the tested v3 callback placement to the older NHI layout. Keep the domain mutex held while clearing the controller bit and calling SXFP, then suspend the control channel. This preserves the older driver's NULL/optional operations semantics. The v4 author's newly described unlocked ordering window is avoided by retaining the v3 placement.
- Consolidated backport: `patches/ubuntu-7.0.0-43-mbp132-backport.patch`; original author submissions/signatures remain in `patches/`. Changed-file before/after hashes are in `source-changes.json`; pristine changed files are preserved under `pristine-files/`.
- This is experimental on MacBookPro13,2. The source author's tests were on MacBookPro14,3. Compilation does not establish hardware reliability.

Source references:

- https://lists.openwall.net/linux-kernel/2026/10/21/1796
- https://lists.openwall.net/linux-kernel/2026/10/19/3216
- https://lists.openwall.net/linux-kernel/2026/10/19/3211
- https://github.com/torvalds/linux/commit/e18d1abc3bff
- https://github.com/open-acpica/acpica/pull/1235
- https://github.com/open-acpica/acpica/pull/1236

## Build and configuration

`build/` is separate from installed kernels. The build command is:

```bash
bash with-build-tools.sh nice -n 10 make -C linux-source-7.0.0 O="$PWD/build" -j3 bzImage modules
```

Do not start another build in the same output directory while this command is active. Progress and compiler output are in `logs/build.log`.

The stock configuration is the starting point. Critical boot, storage, graphics, Wi-Fi, Ethernet, Thunderbolt, suspend and ACPI-debugger settings were compared with stock and match. To build with available tools and manageable debug-artifact size, this test disables DWARF/BTF and Rust; dependent optional BPF scheduling/debug features and a Rust PHY driver are consequently unavailable. The complete differences are in `logs/config-diff.txt`. None of those removed optional drivers is required by the hardware being tested. The test uses its own generated module-signing key and does not embed Canonical's unavailable certificate files. This machine does not support Secure Boot.

Build tools and development headers are extracted locally under `build-tools/`; no system build packages have been installed. Host runtime libraries match the installed distribution versions. Packaging removes workspace-specific runtime library paths from exported host tools.

The first full build finished compiling the modules but stopped during image generation because `gawk` was missing. Its log is preserved as `logs/build-attempt2-missing-gawk.log`. A hash-checked Ubuntu `gawk` package was extracted locally, and the incremental build completed successfully. The image package accepts the existing `dracut` setup (or `initramfs-tools` on machines using that alternative); it uses the provider's `update-initramfs` command.

After a complete kernel/modules build, `stage-packages.py` stages the modules and exports standalone build headers. It then builds the current Touch Bar/iBridge source against those exported headers without the local tool wrapper, matching normal DKMS conditions. Only after those checks pass are image/header Debian packages generated.

## Preserve deep-sleep recovery across kernel upgrades

The original tested Touch Bar/iBridge source remains registered in DKMS with `AUTOINSTALL=yes`. The existing systemd deep-sleep configuration, SOCW arguments/order, single-attempt behavior, delay, and probe-time `skip_acpi_power=1` protection are retained.

The helper's fixed compiled Touch Bar srcversion is replaced by a per-kernel build registry:

1. Root-owned approval records pin the reviewed C/header/Makefile/DKMS source checkpoint.
2. The existing hardware-validated stock build is adopted only when its exact artifact hashes and metadata match the captured baseline. An unverified kernel gets a fresh, forced DKMS build/install from the pinned source; matching installed source alone is not accepted as proof that an older cached DKMS artifact used that source. The recorder checks the target kernel, module metadata, and installed hashes against the DKMS outputs, and records both modules. A verified unchanged build is reused on subsequent image/header hooks.
3. Before any firmware action, the recovery helper checks the source checkpoint, installed artifact hashes, target release, and loaded module srcversions against that record.
4. Kernel-image and header post-install hooks handle either installation order. When image headers have not arrived, approval is deferred; the header hook checks after DKMS builds. Changed source, missing/failed builds, stale loaded modules, and unknown kernels block deep sleep with an explicit error before a firmware call.

This permits trusted rebuilds to have different compiled srcversions on newer kernels. A kernel upgrade alone does not require editing a hard-coded fingerprint. Driver-source changes still require review; an API break that prevents DKMS building cannot be treated as successful recovery support.

The recovery client is also independent of kernel release names. A standalone `acpidbg`, built from the same Ubuntu source, is installed at `/usr/local/libexec/mbp-t1/acpidbg` with a root-owned hash approval. The helper verifies its ownership/hash and runs only `-h` (which exits before opening the debugger) during preflight, before creating a firmware-pending marker. It uses that client directly for the unchanged SOCW command pair. Ubuntu's `/usr/bin/acpidbg` dispatcher requires per-kernel tool directories and failed on the custom kernel; module/source verification alone did not catch that dependency. The read-only verifier and installer now include client readiness.

For an existing installation with that missing-client failure, while running the approved stock or test kernel:

```bash
sudo python3 /home/example/macbookpro-ubuntu/kernel-test/repair-acpidbg.py
```

The repair backs up the prior helper, installs the reviewed client/approval and helper, and validates readiness. It holds the existing recovery lock and refuses a pending firmware wake. It never evaluates firmware, suspends, reloads drivers, or reboots. No reboot is needed. Run the read-only verifier, then explicitly request a controlled 60-second test as described below. Initial system-menu attempts on the test kernel were cancelled in ExecStartPre; suspend success/failure counters remained zero and the kernel did not enter sleep.

The full Thunderbolt/PCI/ACPICA patchset is kernel code, so DKMS alone cannot carry it into arbitrary stock kernel updates. During initial testing, GRUB keeps the stock kernel as default and selects the test build for one boot. After successful hardware validation and promotion, GRUB explicitly keeps the patched kernel as default. Newly installed kernels can be staged and given verified T1 rebuilds, but do not silently replace that working default. A newer base kernel still needs source/patch review, rebuilding where required, and hardware tests before promotion. This also means kernel security updates need timely review/rebuild; an unvalidated kernel is not automatically selected.

## Installation and first boot

When the artifacts are ready, from the known stock `7.0.0-43-generic` kernel:

```bash
sudo python3 /home/example/macbookpro-ubuntu/kernel-test/install-test-kernel.py
```

The installer verifies artifact hashes and unchanged DKMS source; backs up the current helper under `/var/lib/mbp-t1/test-kernel-backup/`; installs the upgrade-safe guard/hooks; records the stock build; protects the stock image/headers from automatic removal; installs the separate test image/headers; builds and approves the test kernel's DKMS modules; generates its initramfs; and schedules one test boot. It never reboots, suspends, reloads a live module, or calls firmware. No permanent USB-autosuspend workaround is installed.

The initial installation stopped after unpacking because build-workspace directory modes (0775) had been retained in the packages. The recovery guard correctly refused the group-writable module parent, so no test initramfs was generated or test boot scheduled. Both packages have been corrected to remove group/other write permissions; every archived payload member is now checked for root ownership and safe modes before finalization. Eight regression tests cover normalization and scoped repair. A real isolated dpkg upgrade reproduced preservation of existing 0775 directories despite a corrected archive; the installer now explicitly repairs only root-owned, package-declared directories under this test kernel's module/header trees from 0775 to 0755. It refuses symlinks, redirected parents, unexpected owners or unexpected modes before any repair. Shared system directories, files, and other kernels are excluded. The earlier archive-extraction test did not model dpkg's preservation behavior. Re-run the installer above to finish an interrupted installation. Wait for its final `Installed.` message before restarting; it now explicitly checks configured package states and both boot artifacts before scheduling a test boot.

Save work and restart normally when ready. If the test boot fails, the subsequent boot defaults to the retained stock kernel. The stock kernel is also selectable in GRUB's Advanced options.

### Repairing the initial one-time boot selection

After installation completed, the first requested test boot still used stock. The installer had matched a quoted `set default="submenu>stock"` reference as if it were the submenu declaration, producing the invalid path `submenu>stock>test`. The parser now matches actual submenu/menuentry declarations, requires unique matching device identifiers, and reads back the scheduled entry after `grub-reboot`. Five regression tests and the copied installed configuration confirm the corrected two-component paths; promotion and rollback share this corrected parser.

For that already completed installation, do not reinstall. Schedule the existing test entry directly:

```bash
sudo grub-reboot 'Advanced options for Ubuntu>Ubuntu, with Linux 7.0.14-mbp132-tb1'
sudo grub-editenv /boot/grub/grubenv list
```

The output must contain `next_entry=Advanced options for Ubuntu>Ubuntu, with Linux 7.0.14-mbp132-tb1`. Then save work and restart normally. Check `uname -r` before running the verifier. This selects one test boot and retains the stock default.

## Hardware validation

Leave the EDUP adapter connected with working Ethernet, and boot the test kernel. First run the read-only verifier:

```bash
sudo python3 /home/example/macbookpro-ubuntu/kernel-test/verify-test-kernel.py
```

Then explicitly request one controlled cycle:

```bash
sudo python3 /home/example/macbookpro-ubuntu/kernel-test/verify-test-kernel.py --suspend-seconds 60
```

The test requires the correct kernel and approved loaded drivers, healthy USB 3 controllers and Ethernet routing, no existing RTC alarm, no pending T1 wake, and no attached Thunderbolt storage. It enables only the relevant dynamic-debug messages, arms one RTC alarm, and suspends through systemd. It waits for the kernel counters and the T1 post-resume service before clearing its own alarm/restoring debug state. It does not call SOCW or SXFP from a shell and does not repeat firmware calls.

Results include kernel/service logs, pre/post hardware and routing checks, evidence that both controller callbacks ran, T1 sleep/wake acknowledgments, and Ethernet-bound HTTPS. Check the actual Touch Bar display/touch input, keyboard/trackpad, Wi-Fi, and camera manually. Repeat across both USB-C sides and include a longer lid-closed interval. The RTC test deliberately leaves the lid open; real lid-close/open behavior should also be checked separately. Battery behavior needs a longer unplugged measurement; short resume samples can have gauge settling.

The verifier now measures actual suspended time using the change in `CLOCK_BOOTTIME - CLOCK_MONOTONIC`, excluding active preparation and the 15-second post-resume recovery delay. A 60-second alarm allows up to 15 seconds of suspend-entry overhead; less than 45 seconds actually suspended fails `sleep_duration_met`. Wake-source/interrupt snapshots are saved as `wake-before.json` and `wake-after.json`, with ACPI GPE deltas in the result. Wake settings are not changed. An in-progress suspend service blocks another test before it touches the RTC alarm.

The first short tests after repairing acpidbg woke early: the latest kernel suspend entry/exit spanned roughly three seconds, followed by the 15-second recovery delay. Ethernet retained its 5 Gbit/s USB transport, 1 Gbit/s link and working HTTPS, but this does not establish sustained sleep. The original verifier incorrectly returned success because it did not validate duration. Those older reports cannot qualify for promotion. The user confirmed that the open lid and input devices were untouched. The wake source is still unconfirmed; prior spurious lid/EC evidence is only a candidate, and lid-opening wake remains enabled.

Promotion requires three distinct, duration-verified successful cycles, including one with at least 900 measured seconds asleep, and manual device checks. Timed RTC tests qualify when all checks and measured duration pass. Manual closed-lid comparisons also qualify when the folder contains preserved `lid-comparison-before.json`, `lid-comparison-after.json`, `closed-lid-kernel.log`, and `closed-lid-services.log`, plus a passing post-wake verifier result. Promotion recomputes actual suspended time from the clocks, requires the same boot and exactly one success-counter increment with no failure increment, one deep entry/exit, one lid close/open, and both T1 acknowledgments. Manual trials shorter than 30 measured seconds are rejected. Repeated captures of the same boot/counter cycle count only once. A read-only verification alone cannot qualify.

Three manual trials qualify: `validation-5yac3kyp` (99.261 seconds), `validation-3mtfzxvb` (9908.864 seconds), and `validation-n689igio` (104.941 seconds). The long trial stayed asleep from about 14:27:47 until lid opening at 17:12:57, without intermediate resume. The final trial used the opposite controller `0000:7c:00.0`; earlier trials used `0000:06:00.0`. Post-wake Ethernet was 1000 Mbps over 5000 Mbps USB, with working bound HTTPS and valid PCI config for both xHCI controllers. The unused controller reinitializes on resume; this moved from 7c to 06 when the adapter moved, while the active side retained Ethernet. Open-lid early wake remains an unresolved lid/firmware candidate and lid-opening wake remains enabled.

After a third qualified cycle and manual device checks:

```bash
sudo python3 /home/example/macbookpro-ubuntu/kernel-test/promote-test-kernel.py
```

This makes the patched kernel the explicit default while retaining the stock rollback entry.

## Kernel rollback

Boot `7.0.0-43-generic`, then run:

```bash
sudo python3 /home/example/macbookpro-ubuntu/kernel-test/rollback-test-kernel.py
```

This removes only the test image/headers and selects stock. The independently tested upgrade-safe T1 integration is retained. The original helper backup remains available if a separate rollback of that guard migration is needed. No rollback command initiates a reboot or firmware operation.
