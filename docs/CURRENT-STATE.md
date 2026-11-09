# Current state — 2026-11-08

This page supersedes historical “current status” paragraphs elsewhere in the archive.

## Machine and adapter

| Component | Observed |
|---|---|
| Computer | Apple MacBookPro13,2; T1/iBridge Touch Bar |
| Distribution | Ubuntu 26.04.1 |
| Running and promoted kernel | `7.0.14-mbp132-tb1` |
| Source package | `linux-source-7.0.0=7.0.0-43.43`; upstream version 7.0.14 |
| Stock fallback | `7.0.0-43-generic` |
| Adapter | EDUP; exact retail model unconfirmed |
| USB 2 hub | Genesys `05e3:0610` |
| USB 3 hub | Genesys `05e3:0626` |
| Ethernet | Realtek RTL8153 `0bda:8153`, existing `r8152` driver |
| Audio codec | Cirrus Logic CS8409 `0x10138409`, subsystem `0x106b3600` |
| Tested controller trees | Intel Alpine Ridge xHCI `8086:15d4`, `0000:06:00.0` and `0000:7c:00.0` |

## Installed behavior

- systemd selects `MemorySleepMode=deep` through `90-mbp132-deep.conf`.
- Kernel command line retains `pcie_port_pm=off mem_sleep_default=s2idle`. The systemd deep setting takes precedence for the configured suspend operation; a fresh boot may initially display `[s2idle] deep` in sysfs.
- `apple_ibridge skip_acpi_power=1` remains in place.
- The reviewed lifecycle-fixed T1 driver source is registered as DKMS `apple-ib-drv/0.1`, with `AUTOINSTALL=yes`.
- The systemd suspend drop-in runs one guarded `SOCW(0)` before deep sleep and one `SOCW(1)` after the validated 15-second post-resume delay. Pending markers and the shared lock prevent duplicate recovery attempts.
- Root-owned source approval and per-kernel build records verify both T1 modules before firmware actions. Unknown builds, changed source/artifacts, or mismatching loaded modules block deep sleep.
- The helper calls `/usr/local/libexec/mbp-t1/acpidbg` directly. Ownership, hash, native executable format and help/readiness are checked before a pending firmware marker is created.
- The original Ethernet profile uses a tested distinct DHCP identity to avoid a verified duplicate lease/address. The exact identity is omitted from this public archive. Router-side cleanup is still separate.
- Internal speakers use an Apple-patched `snd-hda-codec-cs8409` ([davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro) `89b22ff`). It is installed manually in `/lib/modules/7.0.14-mbp132-tb1/updates/cirrus/` and confirmed playing. DKMS `snd_hda_macbookpro/0.1` is still only `added`. Stock fallback kernels load the silent in-tree driver. See [AUDIO.md](AUDIO.md).
- GRUB's default explicitly selects the patched kernel. The machine's actual GRUB disk UUID is replaced in the public example. Promotion was independently confirmed by reading the installed configuration; some historical snapshots still say “not promoted.”

## Validated

Three distinct deep-sleep cycles with the lid closed: 99.261 seconds, 9908.864 seconds, and 104.941 seconds. Both physical controller sides were exercised. Each completed with accessible controller configuration space, a 5000 Mbps USB transport, 1000 Mbps Ethernet link, Ethernet default routing and successful interface-bound HTTPS. Both T1 firmware acknowledgments succeeded. The user reported normal device operation after the extended trial.

## Remaining limits

Open-lid suspend can wake prematurely. A 60-second RTC test measured only 3.196 seconds asleep; the alarm was still scheduled in the future. Lid event count and GPE `6F` increased while the USB/Ethernet/Wi-Fi wake-source counters did not. The firmware maps the lid's wake resource to `6F`. This implicates the lid/firmware path without proving its exact cause. Lid-opening wake has been preserved.

The inactive xHCI controller logs `USBSTS 0x401, Reinit` on resume. This moved from `7c` to `06` when the adapter moved to the opposite side; the active controller retained Ethernet in both tests. This reset observation should not be confused with the original complete removal of both USB 3 controller trees.

The patched kernel's battery efficiency has not been measured by a controlled long discharge trial. Earlier stock-kernel closed-lid overnight measurements belong to their original configuration and do not establish a new-kernel wattage. No hibernation solution is claimed.

The speaker fix is tied to `7.0.14-mbp132-tb1` until the DKMS setup in [AUDIO.md](AUDIO.md) is completed. Headphones, microphones and speaker behavior after deep-sleep resume have not been checked with the patched audio driver.
