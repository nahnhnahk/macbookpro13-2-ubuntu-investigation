# Wi-Fi after battery deep sleep — evidence, 2026-11-23 to 2026-11-25

Machine: MacBookPro13,2, kernel `7.0.14-mbp132-tb1`, BCM43602 `14e4:43ba` rev 02, subsystem `106b:0157`, firmware `7.35.177.61 (r598657)`. Times are America/Los_Angeles. Host name, network names, access point and client MAC addresses, and boot IDs are omitted. Raw journals stay in the private workspace.

## Failure signature (stock driver)

```
kernel: PM: suspend entry (deep)
kernel: brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM43602/2 wl0: Nov 10 2015 06:38:10 version 7.35.177.61 (r598657)
kernel: PM: suspend exit
wpa_supplicant: wlp2s0: CTRL-EVENT-ASSOC-REJECT bssid=<all zeros> status_code=16
wpa_supplicant: wlp2s0: CTRL-EVENT-ASSOC-REJECT bssid=<all zeros> status_code=16
...                                  (repeats against every 5 GHz access point until reboot)
```

The firmware line inside the suspend window is `brcmfmac` re-probing the chip during resume. It appeared on every resume, on AC and on battery, so the chip's firmware never survives S3 on this machine.

## Battery vs AC (UPower history from 2026-11-18, every deep-sleep resume)

| Power when the sleep started | Resumes | Reconnected | Stuck until reboot or next sleep |
|---|---:|---:|---:|
| Battery | 20 | 2 | 18 |
| AC | 43 | 41 | 2 |

Power swapped during the sleep (2026-11-24, about 16 s each): sleep on AC and wake on battery got stuck; sleep on battery with the charger plugged in before wake got stuck.

## Tests while stuck that did not recover

Driver reload; driver unloaded across S3; PCI remove/rescan; restarting wpa_supplicant and NetworkManager; EC power cut of the Wi-Fi chip (EC 0x03 bit 3, config space confirmed reset); EC power cut of the Bluetooth chip (bit 4); both together for 5.6 s; kexec into the same kernel; plugging in the charger; a further sleep on AC; wake-on-WLAN set before sleep (wiped by the re-probe). A normal reboot always recovered.

An experimental sleep hook that cut the Wi-Fi chip's power before S3 made a sleep on AC fail (one trial), consistent with a power-on reset being the trigger.

## Wrong-password band probe (2026-11-25 00:00)

The firmware runs the 4-way handshake, so a wrong password also returns status 16, but with the access point's real BSSID. Control (working state): both bands returned a real BSSID. Stuck state: the 2.4 GHz access point returned its real BSSID (it answered); the 5 GHz network only returned the all-zero BSSID (no association). The 5 GHz wrong-password attempt did not run separately in the stuck trial, so this is indicative, not exact.

## Fix verification (patched driver, 2026-11-25)

```
12:01:04 kernel: brcmfmac 0000:02:00.0: femctrl: chipcontrol 0x01400090, discrete FEM control mode already set
12:01:21 kernel: PM: suspend entry (deep)                                  # on battery
12:01:25 kernel: brcmfmac 0000:02:00.0: femctrl: chipcontrol 0x00000000 was CLEARED, restored to 0x00000010
12:02:33 kernel: PM: suspend entry (deep)                                  # on battery
12:02:41 kernel: brcmfmac 0000:02:00.0: femctrl: chipcontrol 0x00000000 was CLEARED, restored to 0x00000010
```

Wi-Fi reconnected after both battery sleeps (user-confirmed; one status-16 attempt in the whole boot, against a dozen or more per stuck wake before). Only bit 4 is restored; the other bits seen after boot (`0x01400080`) stay clear, and 5 GHz works without them.

Build reproducibility: `wifi/build.sh` from the source directory and from a tarball both produced `srcversion 71DDA38F45F749CA5900327`, identical to the loaded module. `wifi/verify-femctrl.sh` reported the patched module for `7.0.14-mbp132-tb1` and the in-tree driver for the stock kernels.

## Not yet validated

Longer battery sleeps (minutes to hours), overnight sleep, more cycles, AC sleeps with the patched driver, stock fallback kernels (no fix installed), and other access points or networks.
