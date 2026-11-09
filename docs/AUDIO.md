# Internal speakers

**Status (2026-11-08):** fixed on the running `7.0.14-mbp132-tb1` kernel with a manually installed, Apple-patched CS8409 driver. The user confirmed the speakers play. The stock fallback kernels still use the in-tree driver and remain silent until the DKMS setup below is completed. Evidence: [`evidence/audio-2026-11-08/`](../evidence/audio-2026-11-08/README.md).

## Symptom

After Ubuntu was installed, the internal speakers made no sound. Everything in userspace looked normal: ALSA listed `CS8409 Analog`, PipeWire showed `Built-in Audio Analog Stereo` at full volume, and playback reported no errors. The new Thunderbolt/PCI/ACPICA kernel did not change this.

## Cause

The MacBookPro13,2 audio codec is a Cirrus Logic CS8409 (`0x10138409`) with Apple subsystem ID `0x106b3600`. On this machine the codec does not drive the speakers directly. It sends digital audio to separate speaker amplifier chips, which have to be powered and configured over an I²C bus behind the codec.

Mainline/Ubuntu `snd_hda_codec_cs8409` only has fixups for Dell designs that use this chip. For Apple IDs it falls back to the generic HDA parser (`autoconfig for CS8409 … type:speaker`). That parser creates PCM devices and a mixer but never initializes the amplifiers, so the audio reaches the codec and stops there. macOS has the Apple-specific setup built in; stock Linux does not.

Two further problems kept the known fix from taking effect:

1. **The community driver was registered but never built.** [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro) had been added to DKMS (`snd_hda_macbookpro/0.1: added`). Its pre-build script needs Ubuntu's kernel source tarball (`/usr/src/linux-source-7.0.0.tar.bz2`), which was not installed, so the script exited before compiling and the failure went unnoticed.
2. **The custom kernel's release name breaks the source lookup.** The script derives the tarball name from the kernel release: `7.0.14-mbp132-tb1` → `linux-source-7.0.14`. Ubuntu only publishes `linux-source-X.Y.0`. The custom kernel's own in-tree module was unchanged (same `srcversion` as stock), because the backport touches no sound code.

## Fix applied

1. The source used was `linux-source-7.0.0=7.0.0-43.43`, the exact package the custom kernel was built from.
2. The patched driver was built rootless against `/lib/modules/7.0.14-mbp132-tb1/build` from driver commit `89b22ff`. The patches applied, with a "later than implemented version" warning. It compiled without errors and includes explicit `0x106b3600` handling.
3. It was installed with [`audio/install-cs8409-apple.sh`](../audio/install-cs8409-apple.sh) into `/lib/modules/7.0.14-mbp132-tb1/updates/cirrus/`, which modprobe prefers over `kernel/`. `depmod` was run and the machine rebooted.

**How to verify:** the kernel log contains `snd_hda_intel: Primary patch_cs8409 NOT FOUND trying APPLE`. The `autoconfig for CS8409` lines also appear with the patched driver, so they do not tell you which driver is active. [`audio/verify-speaker-driver.sh`](../audio/verify-speaker-driver.sh) is a read-only check that reports which module each installed kernel will load and whether the Apple path ran this boot.

## Keeping it working across kernel upgrades

The manual module is tied to one kernel release. Any other kernel (a stock Ubuntu update, the stock fallback, or a future rebuilt custom kernel) loads the in-tree driver and is silent. To make the fix follow kernel installs automatically, finish the DKMS setup.

> The DKMS steps were exercised through the same pre_build and `make` sequence without root, for both installed kernels (see evidence). The root `dkms install` and playback on the stock kernel have **not** yet been run on this machine. Run `verify-speaker-driver.sh` after doing so and record the result.

### One-time DKMS setup

`/usr/src/snd_hda_macbookpro-0.1` is the DKMS source. On this machine it is a symlink to a local clone of the upstream repository at `89b22ff`.

```sh
# 1. Let the DKMS hook find Ubuntu's source tarball for custom kernel names
cd /home/example/snd_hda_macbookpro
git apply /home/example/macbookpro13-2-ubuntu-investigation/audio/ubuntu-base-source-fallback.patch

# 2. Install the kernel source tarball the hook extracts sound/hda from.
#    apt keeps this package in step with stock 7.0.0-N kernels.
sudo apt install linux-source-7.0.0      # provides /usr/src/linux-source-7.0.0.tar.bz2

# 3. Remove the manual copy so only one patched module exists in updates/
sudo rm /lib/modules/7.0.14-mbp132-tb1/updates/cirrus/snd-hda-codec-cs8409.ko

# 4. Build and install for every installed kernel
for k in 7.0.14-mbp132-tb1 7.0.0-43-generic; do
  sudo dkms install snd_hda_macbookpro/0.1 -k "$k" --force
done
dkms status snd_hda_macbookpro          # expect "installed" for each kernel

# 5. Check, reboot, check again
./audio/verify-speaker-driver.sh
```

`dkms.conf` has `AUTOINSTALL="yes"`, so later kernel installs build the module automatically, the same way the T1 `apple-ib-drv` driver is maintained.

### After each kernel upgrade

1. Run `audio/verify-speaker-driver.sh`. Every kernel you might boot should show `patched (Apple)`.
2. If a kernel shows `IN-TREE ONLY`, check `/var/lib/dkms/snd_hda_macbookpro/0.1/build/make.log`, then run `sudo dkms install snd_hda_macbookpro/0.1 -k <release> --force`.
3. After rebooting into it, the verifier should report the Apple code path, and the speakers should play.

Known ways this can break:

| Situation | What happens | Action |
|---|---|---|
| Stock `7.0.0-N` update | apt updates `linux-source-7.0.0` together with the kernel. If DKMS runs before the new source is unpacked, the module is built from the previous point release's `sound/hda`. This usually still works. | After `apt` finishes, rerun `dkms install … -k <new> --force` if `linux-source-7.0.0` was upgraded in the same transaction. |
| New Ubuntu base series (e.g. 7.1, or after a distribution upgrade) | Needs `linux-source-7.1.0`. The driver's `.diff` files may no longer apply or compile. The kernel installs fine, but the speakers go silent. | `sudo apt install linux-source-7.1.0`; `git pull` the driver (keep or rebase the fallback patch); rebuild; record the result here. |
| Rebuilt custom kernel (`*-mbp132-*`) | DKMS builds against whichever `linux-source-X.Y.0` is installed. It should match the source the kernel was built from. | Build the kernel and the driver from the same `linux-source` version. Verify before promotion, alongside the existing T1/sleep checks in [UPGRADES-AND-ROLLBACK.md](UPGRADES-AND-ROLLBACK.md). |
| HWE kernel | Ubuntu publishes no matching `linux-source` package. The upstream script notes it does not support HWE kernels. | Not supported by this setup. |
| Upstream accepts Apple CS8409 support | The in-tree driver would handle `0x106b3600` itself. | Check whether a new kernel's in-tree module plays sound before relying on it. If it does, remove the DKMS module (`sudo dkms remove snd_hda_macbookpro/0.1 --all`). |

### Undo

- **Manual install:** `sudo rm /lib/modules/<release>/updates/cirrus/snd-hda-codec-cs8409.ko && sudo depmod -a <release>`, then reboot.
- **DKMS install:** `sudo dkms remove snd_hda_macbookpro/0.1 --all`.

Either way, the in-tree (silent) driver loads on the next boot.

## Not yet validated

Only internal-speaker playback on `7.0.14-mbp132-tb1` was confirmed. Not yet checked with this driver:

- the 3.5 mm headphone jack and plug detection
- the internal and headset microphones
- speaker behavior after deep-sleep resume
- the stock kernel

The upstream driver keeps an `INTERNAL_MIKE_ONLY` build flag disabled by default because it breaks headset microphones.
