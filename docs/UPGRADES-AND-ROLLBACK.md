# Kernel upgrades and rollback

## What the next upgrade does

Ubuntu can install its next stock kernel. DKMS and the installed image/header hooks rebuild and verify the reviewed T1 modules for that release. Missing headers defer image-hook approval; the header hook checks again. An unverified kernel gets a forced build/install from the approved source, rather than trusting an old cached binary under the same DKMS version.

The recovery helper, deep-sleep configuration and standalone acpidbg remain installed outside version-specific kernel directories. A build failure or changed source/artifact is reported; an unapproved running kernel is refused before firmware recovery starts.

GRUB continues to boot `7.0.14-mbp132-tb1`, which was explicitly promoted. A newly installed kernel does not silently replace that validated default. Its entry can still be selected for deliberate testing.

## Maintenance obligation

The Thunderbolt/PCI/ACPICA changes are core kernel code. DKMS preserves the separate T1 drivers and their recovery integration; it does not automatically backport those core changes onto every new Ubuntu kernel.

For each future base kernel:

1. Check whether its source already contains the necessary fixes and review upstream changes.
2. Adapt/rebuild where needed, using a separate release name and retaining a working fallback.
3. Build/export headers, verify the T1 modules and runtime client, then validate hardware and actual sleep duration.
4. Test ordinary lid-close/open behavior and both controller sides; promote the replacement only after evidence passes.
5. Record exact versions, patches, tests and limitations in this repository.

**Kernel security updates protect the running system only after a replacement containing them is built/tested and selected.** Keeping the working default avoids silent regression but requires timely maintenance. No automatic patched-kernel rebuilding service has been installed. A major distribution upgrade may also change driver APIs, boot or sleep infrastructure and requires review.

If a future Ubuntu kernel already includes the complete fixes, validate it and return to the distribution kernel update path.

## Rollback

The stock kernel remains selectable in GRUB's Advanced options. The archived rollback script requires booting that stock release first; it selects stock and removes only the separate test image/headers. Upgrade-safe T1 support is retained. The original firmware helper was backed up locally before migration.

Scripts in this public archive depend on machine-specific approval records and built artifacts, which must be reviewed/regenerated locally. Public example GRUB UUIDs and network interface names are placeholders. See [reproduction notes](REPRODUCING.md) before using archived installation or rollback source.
