# Investigation and findings

## 1. Suspend, battery drain and T1 recovery

The initial s2idle setup consumed substantial battery and sometimes woke periodically. A roughly 40-minute wake pattern implicated ACPI non-EC GPE `6D`. Offline firmware analysis mapped the PCH USB controller's wake resource to that GPE. Keeping the Touch Bar off did not eliminate the wakes. One combined Touch Bar-off/USB-remote-wake-disabled trial lasted 88 minutes, but retained substantial drain; it did not isolate remote wake as the sole cause or establish an efficient final configuration.

True S3 deep sleep resumed the machine but left the Touch Bar dark and unresponsive even when HID control transfers succeeded. Device reauthorization, reload, display/mode commands and targeted interface rebinding did not establish recovery. Successful USB transfers were therefore insufficient evidence of functioning T1 firmware state.

## 2. Independent driver lifecycle bug

An experiment with USB persistence disabled forced rediscovery during resume. The driver then logged a double list addition in `input_register_handler`. Its `active` flag represented run/suspend state but also controlled removal cleanup; a disconnect while suspended could skip teardown and then register the same input handler again.

The lifecycle patch separates registration lifetime with `initialized`, clears it during cleanup and guards a missing display interface. A hardware rediscovery test removed the duplicate-registration warnings. The Touch Bar still failed after S3, proving that lifecycle cleanup and firmware recovery were distinct problems. The lifecycle change remains in the validated source checkpoint.

## 3. Missing firmware handshake

Offline DSDT/SSDT analysis identified `\_SB.PCI0.XHC1.RHUB.ASOC.SOCW`:

- `SOCW(0)` calls the embedded-controller mailbox sleep sequence.
- `SOCW(1)` invokes the mailbox wake/reinitialization sequence.
- The inspected ordinary wake methods did not supply this complete handshake.

A [matching primary report](https://github.com/AJ-dev-i60/t1-touchbar/issues/4) supported the hypothesis. Initial experiments deliberately avoided these firmware operations. The user later explicitly authorized a targeted test; a one-shot wake call returned Integer 0 and restored display and touch without restarting. Complete sleep/wake pairs, automatic integration, longer trials and a closed-lid overnight run then established the practical recovery sequence on this machine.

The installed integration retains probe-time ACPI protection, avoids invoking the sequence inside driver suspend/probe callbacks, waits 15 seconds after resume and makes only one wake attempt. A userspace timeout does not make an arbitrary firmware method safe. This archive contains source and historical evidence, rather than a recommendation to issue raw firmware commands on another machine.

## 4. Ethernet detection failure below the network layer

The EDUP adapter sometimes exposed only its USB 2 hub. The RTL8153 chip was absent, so NetworkManager had no Ethernet interface to display even though its driver was already loaded.

At first, a lid cycle restored Ethernet on a 480 Mbps USB 2 fallback. Later, a fresh-boot capture directly established the deeper fault: a working SuperSpeed adapter was attached to the Alpine Ridge tree, then S3 resume made both bridge/controller trees inaccessible. PCI reads reported unusable headers, bridges entered D3cold, xHCI buses were removed, and the Ethernet device disconnected with its parent bus.

This explains how a later replug or sleep cycle could restore reduced-speed USB 2 Ethernet without recovering the missing USB 3 controllers.

### Autosuspend hypothesis tested

The remaining Genesys USB 2 hub was suspended with `power/control=auto`. A first unplug/replug test did not reproduce the failure and never exercised the hold-awake branch. The subsequent failed-state test held only that hub awake for 15 seconds. It became active, but all child ports stayed unattached and RTL8153 did not return. The setting was restored.

A permanent hub-autosuspend rule was therefore unsupported for the demonstrated controller-loss failure. The Ethernet chip already had its USB no-LPM quirk; adding the same quirk again would not address a missing parent controller.

## 5. Separate DHCP/address conflict

After enumeration recovered, the DHCP server repeatedly offered an address claimed by another device. An ARP test performed without owning that address confirmed an independent claim; the machine's vendor database identified the claimant's original OUI as LG Innotek. The user has LG TVs, but the exact claimant was not conclusively identified.

A temporary connection with a distinct DHCP identity obtained a different address and passed interface-bound connectivity tests. The exact tested identity was applied to the original wired profile, preserving its other settings. It survived reconnect and reboot. This avoids the observed lease conflict; it does not repair the router's underlying reservation/static-address situation.

Additional cross-interface ARP replies occurred with Wi-Fi and Ethernet both active under default Linux ARP settings. These were kept separate from the independently verified other-device conflict. No ARP sysctl workaround was installed.

## 6. Kernel repair

A matching Thunderbolt patch proposed an Apple Alpine Ridge pre-suspend sequence: clear controller CS_20 bit 26, then call the controller's `SXFP(0)` while the control channel is still available. Its PCI/ACPICA prerequisites matter as well.

The local backport uses the tested v3 mutex-held placement in the older Ubuntu NHI layout. It retains the optional-operations checks, Apple guard, firmware-suspend restriction and ICM exclusion. It includes the prerequisite PCI config-accessibility helper, saved-state protection, inaccessible-link checks and ACPICA inherited-bus fix. The exact source, references and implementation choices are in [reproduction notes](REPRODUCING.md).

The original generic kernel remains installed for rollback. The separate kernel's build success was followed by hardware tests, rather than treated as proof of recovery.

## 7. Upgrade preservation and validation corrections

The original T1 helper accepted a fixed compiled driver fingerprint. Per-kernel trusted build records now permit verified DKMS rebuilds with different fingerprints. A fresh build is required for an unverified kernel unless it exactly matches the known validated stock checkpoint; a global source directory alone does not prove an old cached binary's provenance.

Testing also exposed missing setup assumptions and validation bugs: retained directory modes during package upgrades, a GRUB parser matching a default reference as a declaration, Ubuntu's per-kernel `acpidbg` dispatcher, and a verifier that did not check actual sleep duration. Each was corrected and tested; see [timeline](TIMELINE.md).

Normal closed-lid trials now pass on both controller sides, including an uninterrupted multi-hour interval. Open-lid premature waking remains separately documented. No lid-wake suppression was installed to obtain these successful closed-lid results.
