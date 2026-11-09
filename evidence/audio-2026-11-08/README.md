# Internal speaker evidence — 2026-11-08

Selected excerpts captured on the MacBookPro13,2. The host name is replaced with `example-MacBookPro13-2`; times are America/Los_Angeles. Full journals remain local.

## Codec identity

From `/proc/asound/card0/codec#0` (same on all kernels):

```text
Codec: Cirrus Logic CS8409
Vendor Id: 0x10138409
Subsystem Id: 0x106b3600
```

`aplay -l` listed `card 0: PCH [HDA Intel PCH], device 0: CS8409 Analog`. PipeWire/WirePlumber exposed `Built-in Audio Analog Stereo` at volume 1.00. The only ALSA simple control on the codec was `PCM`, with no `Master`, `Speaker` or `Headphone` control. Userspace looked healthy, but the internal speakers made no sound.

## Before: stock `7.0.0-43-generic` (boot starting Nov 7 22:51)

```text
snd_hda_codec_cs8409 hdaudioC0D0: autoconfig for CS8409: line_outs=2 (0x24/0x25/0x0/0x0/0x0) type:speaker
snd_hda_codec_cs8409 hdaudioC0D0:    speaker_outs=0 (0x0/0x0/0x0/0x0/0x0)
snd_hda_codec_cs8409 hdaudioC0D0:    hp_outs=1 (0x2c/0x0/0x0/0x0/0x0)
```

Module: `/lib/modules/7.0.0-43-generic/kernel/sound/hda/codecs/cirrus/snd-hda-codec-cs8409.ko.zst`, `srcversion FB741A9D2CA2F92E375CC5E`.

## Driver registered but never built (Nov 8 00:24)

`dkms status` reported `snd_hda_macbookpro/0.1: added` (not `installed`). `/var/lib/dkms/snd_hda_macbookpro/0.1/build/make.log`:

```text
DKMS (dkms-3.2.2) make.log for snd_hda_macbookpro/0.1 for kernel 7.0.0-43-generic (x86_64)
Running the pre_build script
# command: cd /var/lib/dkms/snd_hda_macbookpro/0.1/build/ && /var/lib/dkms/snd_hda_macbookpro/0.1/build/install.cirrus.driver.sh -k 7.0.0-43-generic --dkms
Ubuntu linux kernel source not found in /usr/src: /usr/src/linux-source-7.0.0.tar.bz2
assuming the linux kernel source package is not installed
# exit code: 1
```

## Still silent: patched `7.0.14-mbp132-tb1` before the fix (boot starting Nov 8 14:04)

```text
2026-11-08T14:04:27-08:00 example-MacBookPro13-2 kernel: snd_hda_codec_cs8409 hdaudioC0D0: autoconfig for CS8409: line_outs=2 (0x24/0x25/0x0/0x0/0x0) type:speaker
```

The custom kernel's in-tree module had the same `srcversion FB741A9D2CA2F92E375CC5E` as stock. The Thunderbolt/PCI/ACPICA backport changed no sound code (`kernel-test/source-changes.json` lists no `sound/` path). For this release, the unpatched driver script would have looked for a `linux-source-7.0.14.tar.bz2` that Ubuntu does not publish.

## Rootless build test

- Source: Ubuntu `linux-source-7.0.0_7.0.0-43.43_all.deb`, the same hash-checked package the custom kernel was built from.
- Driver: davidjo/snd_hda_macbookpro at `89b22ff`.
- Patch output: `cs8409.c` 3/3 hunks applied (offset 159); `cs8409.h` 4/4 applied (2 with fuzz 2). The script warned "Kernel version later than implemented version - there may be build problems". Compilation finished with no errors.
- Result: `snd-hda-codec-cs8409.ko`, `vermagic 7.0.14-mbp132-tb1`, `srcversion D6CED27E5D3E21C955AD8D8`.
- The patched source has explicit `0x106b3600` handling in `cirrus_apple.h` and `patch_cirrus_new84.h`.

## After: manual install into `updates/`, reboot (boot starting Nov 8 17:59)

`modinfo -n snd_hda_codec_cs8409` → `/lib/modules/7.0.14-mbp132-tb1/updates/cirrus/snd-hda-codec-cs8409.ko`

```text
2026-11-08T17:59:58-08:00 example-MacBookPro13-2 kernel: snd_hda_intel: Primary cs8409
2026-11-08T17:59:58-08:00 example-MacBookPro13-2 kernel: snd_hda_intel: Primary patch_cs8409 NOT FOUND trying APPLE
2026-11-08T17:59:58-08:00 example-MacBookPro13-2 kernel: snd_hda_codec_cs8409 hdaudioC0D0: autoconfig for CS8409: line_outs=2 (0x24/0x25/0x0/0x0/0x0) type:speaker
2026-11-08T17:59:58-08:00 example-MacBookPro13-2 kernel: snd_hda_intel: hda_generic_check_dyn_adc_switch shrinking
```

The user reported that the internal speakers play sound. The `autoconfig` lines appear both before and after the fix, so they do not show which driver is active. The marker is `patch_cs8409 NOT FOUND trying APPLE`.

## DKMS hook test (patched script, rootless)

This used `audio/ubuntu-base-source-fallback.patch` with `CIRRUS_LINUX_SOURCE_DIR` pointing at the extracted source package. It ran the same `install.cirrus.driver.sh -k <release> --dkms` and `make KERNELRELEASE=<release>` steps that DKMS runs:

| Kernel | pre_build | make | Module |
|---|---|---|---|
| `7.0.14-mbp132-tb1` | 0 ("Using Ubuntu base source …linux-source-7.0.0.tar.bz2") | 0 | `srcversion D6CED27E5D3E21C955AD8D8`, identical to the validated module |
| `7.0.0-43-generic` | 0 | 0 | built; compiler/pahole version-difference warnings only |
| no tarball present | 1, clear "source not found" message | n/a | n/a |

The root `dkms install` step and hardware playback on the stock kernel were **not** run in this session.
