# Change log

## Internal speaker fix — 2026-11-08

- Found why the internal speakers were silent: the in-tree CS8409 driver has no Apple (`0x106b3600`) support, the community driver's DKMS build had failed for lack of `linux-source-7.0.0`, and the custom kernel's release name broke the source lookup.
- Recorded the working manual fix on `7.0.14-mbp132-tb1`, as confirmed by the user, with sanitized kernel-log evidence.
- Added a source-lookup patch so the driver's DKMS hook builds for stock and custom kernel names, plus a manual install helper and a read-only verification script.
- Documented DKMS setup, per-upgrade checks, failure modes and rollback. The root DKMS install and other audio paths remain unvalidated.

## Initial public snapshot — 2026-11-08

- Recorded the final promoted-kernel state and retained stock fallback.
- Preserved dated suspend, driver-lifecycle, T1 firmware, Ethernet enumeration and DHCP investigations, including failed hypotheses and corrections.
- Archived the exact-source kernel backport, reviewed T1 source/support tools and machine-specific configuration examples.
- Published selected sanitized validation evidence: early-wake failure plus three successful closed-lid comparisons, including multi-hour and opposite-controller use.
- Recorded upgrade behavior, security-maintenance obligation, rollback, open-lid wake limitations and future work.
- Added regression tests, publication checks, integrity records and an ongoing update workflow.

This change log is maintained alongside Git commits. Later results should be added as new dated entries with their evidence and practical limits.
