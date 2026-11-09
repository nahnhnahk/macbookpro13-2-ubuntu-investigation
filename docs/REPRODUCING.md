# Source provenance and reproduction notes

## Exact base

- Package: `linux-source-7.0.0=7.0.0-43.43`.
- Independently checked package SHA256: `208b9997b555c9494535edd0dee6f0ee67a7ccddc180fb40c30218f06bd2dc59`.
- Source Makefile version: 7.0.14; local release: `7.0.14-mbp132-tb1`.
- The original stock configuration was `/boot/config-7.0.0-43-generic`.
- Changed-file before/after hashes are preserved in `kernel-test/source-changes.json`.
- The consolidated source backport is `kernel-test/patches/ubuntu-7.0.0-43-mbp132-backport.patch`.

The public repository excludes source tarballs, compiled kernel/modules, Debian packages, private signing keys and installed runtime binaries. Fetch the exact source from the Ubuntu archive, verify its hash, review/apply the backport and regenerate local build/approval manifests. Do not use the original artifact manifest as an installation approval for modified source copies.

## Upstream changes

| Change | Primary reference |
|---|---|
| PCI config-accessibility prerequisite | [Linux commit e18d1abc3bff](https://github.com/torvalds/linux/commit/e18d1abc3bff) |
| Preserve PCI saved state when inaccessible | [Author submission](https://lists.openwall.net/linux-kernel/2026/10/19/3216) |
| Reject all-ones PCI link status | [Author submission](https://lists.openwall.net/linux-kernel/2026/10/19/3211) |
| ACPICA inherited PCI bus resolution | [ACPICA PR 1235](https://github.com/open-acpica/acpica/pull/1235), [PR 1236](https://github.com/open-acpica/acpica/pull/1236) |
| Thunderbolt v3 suspend preparation | [Author submission](https://lists.openwall.net/linux-kernel/2026/10/21/1796) |
| Later v4 discussion | [Author submission](https://lore-kernel.gnuweeb.org/linux-usb/20261103115104.13845-1-fbeltranmillalen@gmail.com/) |

The older driver keeps its PCI table in `nhi.c`. The local adaptation retains the v3 pre-suspend callback under the existing domain mutex before the control channel is suspended, preserves optional/NULL NHI operations and uses the older `pdev` device layout. It clears CS_20 bit 26 before SXFP, restricts the operation to Apple Alpine Ridge firmware-managed system suspend and excludes ICM. ACPICA's functional correction is applied once, not twice through equivalent PRs. The original author's other-model test is not substituted for the local model's hardware tests.

## Configuration and tools

The build starts from stock, disables DWARF/BTF and Rust for available tooling/size, and consequently omits dependent optional BPF scheduler/debug features and a Rust PHY driver. Critical boot, storage, graphics, Wi-Fi, Ethernet, Thunderbolt, ACPI and deep-sleep settings were checked against stock. Full differences are in `evidence/build/config-diff.txt`.

Unavailable Canonical trusted/revocation certificate paths were cleared; the build used its own generated module-signing key. This machine has no Secure Boot support. The private key is excluded from publication.

Local extracted build tools supplied flex, bison, gawk and development headers without installing system build dependencies. The first full compile needed a final incremental retry after adding gawk. Exported header host tools were checked free of workspace-specific RPATH/RUNPATH. Both T1 modules compiled against exported headers without the local build wrapper.

The standalone acpidbg client is built by the upstream target:

```sh
make -C linux-source-7.0.0/tools/power/acpi acpidbg
```

Its source path and source/binary hashes are preserved in `kernel-test/t1-upgrade/acpidbg.json`. The `-h` branch exits before opening debugfs. A local rebuild must receive a newly reviewed binary hash; no executable is shipped here.

## Archived tooling

`prepare-backport.py`, `stage-packages.py`, `finalize-artifacts.py`, the installer and recovery scripts preserve the implementation used in this investigation. The retained v3 email keeps its public attribution/body while routing headers are omitted. `PUBLIC-SNAPSHOT.json` records original and sanitized source-file hashes. Network interface defaults and home paths were replaced for publication, so those public copies deliberately differ from machine-local source.

`evidence/build/original-artifact-manifest.json` describes the original local artifacts. The public layout does not place an installable `artifact-manifest.json` or package directory beside the installer. A fresh, reviewed build and matching integrity records are prerequisites for installing elsewhere. Installation does not automatically reboot, suspend or reload a live module.
