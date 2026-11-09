# Touch Bar Fn key

**Status (2026-11-08):** fixed on the running `7.0.14-mbp132-tb1` kernel with a patched `applespi` module installed through DKMS (`applespi-fn/0.1`). The user confirmed that holding Fn now switches the Touch Bar to the F-key row. Evidence: [`evidence/touchbar-fn-2026-11-08/`](../evidence/touchbar-fn-2026-11-08/README.md).

## Symptom

Holding Fn on the built-in keyboard did not switch the Touch Bar from media/brightness keys to F1–F12. The Touch Bar itself worked: it displayed, its keys produced events, and its `fnmode` was the normal `1` (media keys by default, F-keys while Fn is held).

## Cause

The Touch Bar driver works correctly. **keyd** takes exclusive control of the built-in keyboard, which hides the Fn key from the Touch Bar driver.

1. `apple-touchbar` (the T1 driver in [`kernel-test/apple-ib-driver/`](../kernel-test/apple-ib-driver/)) registers an in-kernel input handler named `appletb`. It attaches to any SPI-bus input device that has `KEY_FN` (the `tbkbd` handle) and switches the bar to F-keys on `KEY_FN` press. The same handler also refreshes the bar's idle timer on any keyboard event.
2. `applespi` reports `KEY_FN` on the "Apple SPI Keyboard" device, and `tbkbd` was attached to it (`Handlers=sysrq kbd event4 tbkbd leds`).
3. keyd was configured with `[ids] *` and a `leftmeta = layer(mac)` layer (Cmd+C/V-style shortcuts). It matched the Apple SPI Keyboard and took an exclusive `EVIOCGRAB` grab on it, which it needs in order to remap keys.
4. While a device is grabbed, the kernel's `input_pass_values()` (`drivers/input/input.c`) delivers its events **only** to the grabbing handle. Every other handler is skipped, including `tbkbd`. The `passive_observer` handler flag in 7.0 does not bypass a grab either.
5. keyd does not pass Fn back out. Its virtual keyboard does not even advertise `KEY_FN` (bit 464). So the Touch Bar driver never saw Fn from any device.

**Side effect of the same cause:** with `idle_timeout=300`, the bar could go dark after 5 minutes of typing, because typing no longer reached the driver. Only touchpad events, which keyd does not grab, kept it awake.

## Fix

[`touchbar-fn/applespi-separate-fn-device.patch`](../touchbar-fn/applespi-separate-fn-device.patch) changes only `applespi`:

- It registers a second input device, **"Apple SPI Fn Key"** (`BUS_SPI`, vendor `0000`, product `0001`, phys `applespi/input2`). That device carries only `KEY_FN` and `MSC_SCAN`.
- `KEY_FN` is removed from the main "Apple SPI Keyboard".
- The Touch Bar driver's existing id table (`BUS_SPI` + `KEY_FN`) attaches `tbkbd` to the new device without any change to the Touch Bar driver.
- Every keyboard report also sends `MSC_SCAN` on the new device as an activity pulse. A lone `EV_SYN` would be dropped by the input core; MSC events are not. This is meant to keep the bar's idle timer refreshed while typing.
- keyd keeps its grab on the main keyboard, so the Cmd layer is unaffected. As a precaution, the installer adds `-0000:0001` to keyd's `[ids]` section. In practice keyd 2.5.0 did not list the Fn-only device at all, even before that exclusion took effect, so the exclusion may not be strictly needed.

The pinned T1 driver sources (`apple-ib-drv`) are untouched. The deep-sleep guard verifies only those sources and artifacts, so its source approval and per-kernel build records are not affected.

Patching `apple-touchbar` instead (for example, a direct notifier from `applespi`) was rejected. It would change the approved T1 source checkpoint and block deep sleep until re-approval.

## Install

The repository contains the patch, not kernel source. `prepare-dkms-source.sh` takes `applespi.c`, `applespi.h` and `applespi_trace.h` from a kernel tree or Ubuntu's `linux-source` tarball and applies the patch. It also points the trace header at its own directory for out-of-tree builds and adds the DKMS `Makefile` and `dkms.conf`.

```sh
cd /home/example/macbookpro13-2-ubuntu-investigation/touchbar-fn
./prepare-dkms-source.sh /usr/src/linux-source-7.0.0.tar.bz2   # or an extracted tree; rootless
make -C src KVERSION="$(uname -r)" && make -C src clean        # optional rootless test build
sudo bash install.sh
```

`install.sh` does the following:

1. Copies `src/` to `/usr/src/applespi-fn-0.1` and runs `dkms add/build/install` for the running kernel. The module lands in `updates/dkms/`, which depmod prefers over the in-tree module.
2. Adds `-0000:0001` under keyd's `[ids]` (after a timestamped backup of `/etc/keyd/default.conf`).
3. Regenerates the initramfs only if it contains `applespi.ko`.
4. Reloads `applespi`, which drops the keyboard and touchpad for about 2 seconds. If the keyboard does not reappear within 10 seconds, it removes the DKMS module and loads the stock one again.
5. Restarts keyd.

**Check after installing:** `/proc/bus/input/devices` should show `tbkbd` on "Apple SPI Fn Key" and no `tbkbd` on "Apple SPI Keyboard". Holding Fn should show F1–F12 on the bar.

**Undo:** `sudo bash touchbar-fn/uninstall.sh`. This removes the DKMS package and the keyd exclusion, reloads the stock `applespi` and restarts keyd.

## Kernel upgrades

`dkms.conf` has `AUTOINSTALL="yes"`, so DKMS rebuilds the module on later kernel installs. The patch was written against `linux-source-7.0.0=7.0.0-43.43` (upstream 7.0.14). On a different base series, the `applespi` source used by DKMS may no longer match the kernel's own. To refresh it, rerun `prepare-dkms-source.sh` with the matching `linux-source` and reinstall.

If DKMS fails to build, the kernel's stock `applespi` loads. The keyboard keeps working; only the Fn → Touch Bar switching (and the typing keep-alive) is lost again while keyd is running.

The module was installed only for `7.0.14-mbp132-tb1`. The stock fallback kernels (`7.0.0-43-generic`, `7.0.0-30-generic`) still load the in-tree `applespi`, so Fn does not switch the bar there while keyd runs.

## Not yet validated

- That typing alone (without the touchpad) keeps the bar awake past `idle_timeout=300`.
- Behavior after a reboot (module loaded from boot rather than reloaded) and after deep-sleep resume.
- A build for, and behavior on, the stock fallback kernels.
- Desktop or userspace consumers of `KEY_FN` from the main keyboard. None are known on this machine; keyd did not forward it.
