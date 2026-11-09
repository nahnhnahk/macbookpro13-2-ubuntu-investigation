# MacBookPro13,2 Ubuntu suspend, Ethernet, audio and Touch Bar investigation

Current state, investigation history, source changes, and measured validation for a 2016 Touch Bar MacBook Pro running Ubuntu. Snapshot: **2026-11-08**; dates and human-readable log times use America/Los_Angeles unless marked UTC.

The machine now boots **7.0.14-mbp132-tb1**, a separate kernel built from Ubuntu `linux-source-7.0.0=7.0.0-43.43`. Three closed-lid trials preserved Ethernet and T1 recovery, including **2 hours 45 minutes of uninterrupted deep sleep** and use of both USB-C controller sides. GRUB's promoted default was verified locally. The stock `7.0.0-43-generic` fallback remains installed.

**Internal speakers** were silent after the Ubuntu install because the in-tree CS8409 driver never initializes Apple's speaker amplifiers, and the community driver had been registered with DKMS but never built. An Apple-patched driver now plays sound on the running kernel. DKMS setup for automatic rebuilds on kernel upgrades is documented but not yet completed: see [Internal speakers](docs/AUDIO.md).

**The Touch Bar Fn key** did not switch the bar to F1–F12 because keyd's exclusive grab of the built-in keyboard hid Fn from the Touch Bar driver. A small `applespi` patch now reports Fn on a separate device that keyd leaves alone; the pinned T1 driver is unchanged. See [Touch Bar Fn key](docs/TOUCHBAR-FN.md).

**Open-lid suspend can still wake after about three seconds.** Lid events and firmware interrupt GPE `6F` are the leading evidence; the exact cause is unresolved. Lid-opening wake remains enabled.

| Validated cycle | Actually asleep | Ethernet controller | After resume |
|---|---:|---|---|
| Short closed-lid trial | 99.261 s | `0000:06:00.0` | USB 3, 1 Gbps Ethernet, HTTPS passed |
| Extended closed-lid trial | 9908.864 s | `0000:06:00.0` | No intermediate wake; Ethernet and T1 recovery passed |
| Opposite-side trial | 104.941 s | `0000:7c:00.0` | USB 3, 1 Gbps Ethernet, HTTPS passed |

## Read the record

- [Current state](docs/CURRENT-STATE.md): installed configuration and practical limits.
- [Investigation](docs/INVESTIGATION.md): symptoms, evidence, unsuccessful hypotheses, and fixes.
- [Timeline](docs/TIMELINE.md): chronological decisions, implementation mistakes, and corrections.
- [Validation](docs/VALIDATION.md): timing method, evidence bundles, and what “passed” means.
- [Internal speakers](docs/AUDIO.md): cause, applied fix and how to keep it through kernel upgrades.
- [Touch Bar Fn key](docs/TOUCHBAR-FN.md): keyd grab diagnosis, the `applespi` fix, install and undo.
- [Kernel upgrades and rollback](docs/UPGRADES-AND-ROLLBACK.md): what is automatic and what still requires maintenance.
- [Reproducing the build](docs/REPRODUCING.md): exact source, patch provenance, configuration differences, and archive limitations.
- [Open questions](docs/OPEN-QUESTIONS.md) and [maintenance workflow](docs/MAINTENANCE.md).
- [Historical working notes](history/): preserved and sanitized; early conclusions were superseded as evidence improved.

## Source and evidence

`kernel-test/` preserves the kernel preparation, packaging, verification, promotion/rollback and T1 upgrade-support source. `kernel-test/apple-ib-driver/` contains the reviewed driver checkpoint. The consolidated kernel backport is [here](kernel-test/patches/ubuntu-7.0.0-43-mbp132-backport.patch); the independent Touch Bar lifecycle patch is [here](patches/touchbar-lifecycle.patch).

`touchbar-fn/` contains the `applespi` Fn device patch, the DKMS source preparation script and install/uninstall helpers. `audio/` contains the CS8409 driver source-lookup patch, the manual install helper and a read-only speaker-driver check. `configuration/` contains reviewed configuration examples. `evidence/` contains sanitized build records and selected validation captures. The original `result.json` files are retained: a read-only post-wake pass is separate from independent proof of sleep duration. One older false-positive report is retained and explicitly identified in the validation document.

This is a **machine-specific source and evidence archive**. Installation requires locally built artifacts, regenerated integrity records and review of hardware-specific assumptions. Runtime binaries, kernel packages and build directories are excluded. Public interface names, home paths, network addresses, UUIDs and boot IDs use placeholders; see [publication handling](docs/PUBLICATION.md).

## Upgrade behavior

DKMS and post-install hooks rebuild and verify the reviewed T1 drivers for newer kernels. The firmware recovery helper uses a standalone, approved `acpidbg` client so Ubuntu's per-kernel tool dispatcher does not break it.

The core Thunderbolt/PCI/ACPICA fixes require a reviewed kernel rebuild unless an incoming kernel already includes them. GRUB deliberately keeps the validated patched kernel as its default. **Installing a new kernel does not apply its security fixes to the running kernel until a tested replacement is selected.** See the upgrade document before maintaining this setup.

Existing copyright and SPDX notices are preserved. The included source is distributed under its original applicable terms; [LICENSE](LICENSE) provides GPL v2, and [THIRD-PARTY.md](THIRD-PARTY.md) records upstream provenance. Newly written documentation and supporting scripts in this archive use GPL-2.0-only unless a file states otherwise.
