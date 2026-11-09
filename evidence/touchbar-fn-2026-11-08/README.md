# Touch Bar Fn key evidence — 2026-11-08

Selected excerpts captured on the MacBookPro13,2 running `7.0.14-mbp132-tb1`. The host name is replaced with `example-MacBookPro13-2`; times are America/Los_Angeles. Full journals remain local.

## Before the fix

`/proc/bus/input/devices` showed that the Touch Bar handler (`tbkbd`) was attached to the SPI keyboard, and that the keyboard advertised `KEY_FN` (bit 464, the `10000` in the highest word):

```text
N: Name="Apple SPI Keyboard"
H: Handlers=sysrq kbd event4 tbkbd leds
B: KEY=10000 0 0 0 6300001000 3800000000 710effd063c0001f ff7ffffffffffffe
N: Name="Apple SPI Touchpad"
H: Handlers=mouse0 event5 tbtpad
N: Name="keyd virtual keyboard"
H: Handlers=sysrq rfkill kbd event8 leds
B: KEY=10000000000000 0 ffffffffffffff0f ffffffffffffffff ffffffffffffffff fffffffffffffffe
```

The keyd virtual keyboard's bitmap covers only key codes 0–383, so it cannot emit `KEY_FN` (464).

Module parameters: `apple_touchbar fnmode=1 idle_timeout=300 dim_timeout=-2`; `applespi fnmode=1 fnremap=0`.

keyd configuration (`/etc/keyd/default.conf`, before):

```ini
[ids]
*

[main]
leftmeta = layer(mac)
```

keyd journal at boot (keyd v2.5.0):

```text
Nov 08 17:59:57 example-MacBookPro13-2 keyd.rvaiya[1155]: DEVICE: match    0000:0006:bdb72f48  /etc/keyd/default.conf        (Video Bus)
Nov 08 17:59:57 example-MacBookPro13-2 keyd.rvaiya[1155]: DEVICE: match    1d6b:0301:347e2a02  /etc/keyd/default.conf        (iBridge Virtual HID 0003:05AC:8600.0001/1d6b:0301)
Nov 08 17:59:57 example-MacBookPro13-2 keyd.rvaiya[1155]: DEVICE: ignoring 06cb:0557:81c82bfc  (Apple SPI Touchpad)
Nov 08 17:59:57 example-MacBookPro13-2 keyd.rvaiya[1155]: DEVICE: match    0000:0000:caea9b11  /etc/keyd/default.conf        (Apple SPI Keyboard)
```

Kernel source (`linux-source-7.0.0=7.0.0-43.43`, `drivers/input/input.c`): when `dev->grab` is set, `input_pass_values()` calls only the grabbing handle's `handle_events` and returns, skipping every other handler in `dev->h_list`.

Not run: a direct `EVIOCGRAB` probe of `/dev/input/event4`, which needed root. Stopping keyd as a confirmation test was suggested but not recorded. The grab is inferred from keyd's `match` line and its documented behavior, together with the kernel code above.

## Build

The patched module was built rootless against `/lib/modules/7.0.14-mbp132-tb1/build` with no compiler warnings. `prepare-dkms-source.sh` was checked against both an extracted `linux-source-7.0.0` tree and a tarball with Ubuntu's layout. Both produced source byte-identical to the installed `/usr/src/applespi-fn-0.1`. A build from that source has the same `srcversion` as the loaded module.

## After the fix (Nov 8 20:58)

```text
applespi-fn/0.1, 7.0.14-mbp132-tb1, x86_64: installed (Original modules exist)
modinfo -n applespi: /lib/modules/7.0.14-mbp132-tb1/updates/dkms/applespi.ko
/sys/module/applespi/srcversion: 515D8FC66CE6568552A3E4F
```

```text
I: Bus=001c Vendor=0000 Product=0000 Version=0000
N: Name="Apple SPI Keyboard"
P: Phys=applespi/input0
H: Handlers=sysrq kbd event4 leds
B: KEY=6300001000 3800000000 710effd063c0001f ff7ffffffffffffe
I: Bus=001c Vendor=0000 Product=0001 Version=0000
N: Name="Apple SPI Fn Key"
P: Phys=applespi/input2
H: Handlers=event5 tbkbd
B: EV=13
B: KEY=10000 0 0 0 0 0 0 0
B: MSC=10
I: Bus=001c Vendor=06cb Product=0557 Version=0000
N: Name="Apple SPI Touchpad"
P: Phys=applespi/input1
H: Handlers=mouse0 event15 tbtpad
```

keyd configuration (after):

```ini
[ids]
-0000:0001
*
```

keyd journal after the reload. The new Fn-only device does not appear at all, neither as `match` nor as `ignoring`:

```text
Nov 08 20:58:55 example-MacBookPro13-2 keyd.rvaiya[11895]: DEVICE: ignoring 06cb:0557:81c82bfc  (Apple SPI Touchpad)
Nov 08 20:58:55 example-MacBookPro13-2 keyd.rvaiya[11895]: DEVICE: match    0000:0000:caea9b11  /etc/keyd/default.conf        (Apple SPI Keyboard)
Nov 08 20:58:55 example-MacBookPro13-2 keyd.rvaiya[11895]: DEVICE: match    0000:0006:bdb72f48  /etc/keyd/default.conf        (Video Bus)
Nov 08 20:58:55 example-MacBookPro13-2 keyd.rvaiya[11895]: DEVICE: match    1d6b:0301:347e2a02  /etc/keyd/default.conf        (iBridge Virtual HID 0003:05AC:8600.0001/1d6b:0301)
```

Result: with keyd running and still matching the main keyboard (above), the user confirmed the fix works: pressing Fn now switches the Touch Bar to the F-key row. The Cmd layer's behavior after the change was not separately recorded.

Not yet observed: typing keeping the bar awake past 300 s, behavior after reboot or deep-sleep resume, and the stock fallback kernels.
