> Historical working notes, sanitized for publication. Early statements describe the state at that stage and may have been superseded by later entries. Use [current state](../docs/CURRENT-STATE.md) for the final configuration. Paths, MACs, IPs, UUIDs and boot IDs are examples or redacted.

# T1 S3 firmware wake investigation

Offline analysis only. No ACPI methods have been evaluated.

## Captured firmware

Model MacBookPro13,2, Apple firmware 529.120.1.0.0. Tables are from the affected laptop. `iasl` 20251212 was extracted from Ubuntu's acpica-tools package into this workspace, not installed system-wide.

SSDT6 was disassembled using DSDT and SSDT5 for external references. DSDT disassembly had unresolved externals in the initial all-table pass; conclusions below concern the explicitly visible, named methods, not a complete execution proof of every firmware path. Re-disassembly with selective external tables produced `SSDT6.dsl` successfully.

## Firmware mechanism

- `SSDT6.dsl`: `\\_SB.PCI0.XHC1.RHUB.ASOC.SOCW(0)` invokes `\\_SB.MBOX(1)`.
- `SOCW(1)` invokes `MBOX(6)` followed by `MBOX(2)` on success.
- DSDT `MBOX` writes embedded-controller `INDX`, `DATA`, and `CMDS`, polls EC status, and coordinates GPIOs. Its explicit polling deadlines are approximately one second and four seconds per mailbox invocation. EC/AML execution itself is not protected by a userspace timeout.
- DSDT `_WAK` calls `SWAK` for S3/S4. `SWAK` pulses a wake GPIO; it does not issue the SOCW mailbox commands.
- No explicit SOCW/MBOX calls were found in the inspected `_PTS`/`_WAK` methods.
- ASOC also exposes reset, GPIO and DFU-related helpers. None should be invoked as an experiment.

## Corroborating primary report

https://github.com/AJ-dev-i60/t1-touchbar/issues/4

An October 16, 2026 report on MacBookPro14,3 describes the same signature: Touch Bar stays dark despite successful USB/HID transfers and resume logging; reauthorization and reload do not recover it; restart does. It reports recovery using SOCW sleep/wake notifications, with probe-time protection retained. The report identifies the same apple-ibridge.c SHA256 as this laptop: `96fc45f6ab17a01a1472e180ad7ff36648188db7a65dfc6712cf24eb7b09952d`.

This is strong corroboration of a missing T1 firmware sleep/wake handshake, not proof that the proposed SOCW workaround is safe on MacBookPro13,2. The report's kernel patch is described as hardware-untested, and its ordering differs from the reported working userspace hook. Another model's success does not override this session's explicit instruction to avoid SOCW(1).

## Conclusion and limits

The firmware handshake skipped by `skip_acpi_power=1` is now the leading evidence-supported explanation of the persistent dark Touch Bar after S3. The USB persistence experiment and lifecycle patch did not recover display/input. The lifecycle patch separately removed a verified reconnect registration failure.

No safe S3 Touch Bar recovery has been validated on this laptop under the current no-SOCW constraint. Do not set skip_acpi_power=0, install a resume hook that calls SOCW, invoke reset/DFU helpers, or claim that executing SOCW in a worker/userspace with timeout prevents a hard freeze. Existing protections remain active. Any further firmware-level experiment would require an explicit change to the user's constraint, concrete recovery planning, and machine-specific validation.

## Authorized firmware recovery result

The user explicitly relaxed the no-unsafe-ACPI constraint to test a fix. A one-shot `SOCW(1)` was then invoked outside suspend and driver probe using the kernel's existing `acpidbg` interface. Capture: `t1-firmware-wake-SjQDJQWV`. AML evaluation returned Integer 0, acpidbg exited 0, and the user confirmed immediate recovery of both display and touch input without reboot. Loaded lifecycle-fix module and HID bindings did not change; skip_acpi_power stayed 1. This validates the missing firmware-wake mechanism on this machine, but not yet a complete sleep/wake cycle or overnight reliability. The user has not authorized permanent hooks. A temporary one-minute sleep/wake-pair test is prepared but not run by the agent.

## Complete cycle and automatic integration

`t1-deep-handshake-KVqgvbLu` subsequently validated one complete S3 cycle with SOCW(0) before suspend and delayed SOCW(1) after resume. Both returned 0; display and touch worked afterward. The user then installed the guarded systemd integration. `deep-60s-I7G4eLKN` validates that automatic path: one SOCW(0), true S3, a 15-second post-resume delay, one SOCW(1), both Integer 0, unchanged HID bindings, and working Touch Bar, keyboard/trackpad and Wi-Fi reported by the user. Probe protection remains active and the default still selects s2idle. Long-duration reliability and battery savings remain unmeasured.
