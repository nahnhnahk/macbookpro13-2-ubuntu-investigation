# Attribution and source terms

Original copyright and SPDX notices in copied code remain intact. The GPL v2 text is included in `LICENSE`. Existing source licenses govern their respective portions; publication does not remove original rights or notices.

- Linux/Ubuntu kernel: exact source package `linux-source-7.0.0=7.0.0-43.43`; the repository contains selected patches, not the full kernel. [Linux COPYING](https://github.com/torvalds/linux/blob/master/COPYING).
- PCI prerequisite and related submissions: public author attribution/sign-offs are retained in the individual patch files. See [source references](docs/REPRODUCING.md).
- Thunderbolt suspend proposal: original public v3/v4 patch attribution and sign-offs are retained. The local consolidated patch is a backport/adaptation, not an upstream acceptance claim.
- ACPICA: PRs [1235](https://github.com/open-acpica/acpica/pull/1235) and [1236](https://github.com/open-acpica/acpica/pull/1236); original project terms remain applicable to upstream portions. [ACPICA source license notices](https://github.com/open-acpica/acpica/blob/master/source/include/acpi.h).
- Apple iBridge/Touch Bar source: Ronald Tschalär's copyright and GPL source notices are preserved in `kernel-test/apple-ib-driver/`; the reviewed checkpoint includes local integration/protection and lifecycle changes.
- Apple CS8409 audio: [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro) (GPL), commit `89b22ff`, is used unmodified apart from `audio/ubuntu-base-source-fallback.patch` to its install script. The driver source is not copied into this repository.
- `applespi` Fn device patch: `touchbar-fn/applespi-separate-fn-device.patch` modifies the in-tree driver by Federico Lorenzi and Ronald Tschalär (GPL-2.0). Only the patch is included; `prepare-dkms-source.sh` takes the original files from Ubuntu's `linux-source`. keyd ([rvaiya/keyd](https://github.com/rvaiya/keyd)) is configured, not copied.
- Corroborating firmware report: [AJ-dev-i60/t1-touchbar issue 4](https://github.com/AJ-dev-i60/t1-touchbar/issues/4). The repository summarizes the finding and links its source rather than copying the discussion.

New documentation and supporting scripts authored for this archive use GPL-2.0-only unless a file states otherwise. Files retaining another SPDX expression remain under that expression.
