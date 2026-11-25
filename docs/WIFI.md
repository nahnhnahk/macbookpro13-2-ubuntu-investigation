# Wi-Fi after deep sleep on battery

**Status (2026-11-25):** fixed on the running `7.0.14-mbp132-tb1` kernel with a patched `brcmfmac` that backports the upstream fix "wifi: brcmfmac: pcie: restore FEM control pin mode on Apple BCM43602". The patched driver logged the cleared register being restored on two battery deep sleeps, and Wi-Fi reconnected both times. Stock fallback kernels still use the in-tree driver and keep the bug. Evidence: [`evidence/wifi-2026-11-25/`](../evidence/wifi-2026-11-25/README.md).

## Symptom

After some deep sleeps (S3), the BCM43602 Wi-Fi (`14e4:43ba`, subsystem `106b:0157`, firmware 7.35.177.61) could not rejoin the home network. Every attempt failed about 100 ms after it started:

```
wpa_supplicant: wlp2s0: CTRL-EVENT-ASSOC-REJECT bssid=<all zeros> status_code=16
```

The network was still visible in scans with strong signal. NetworkManager eventually gave up with a misleading `no-secrets` reason. Only a reboot fixed it.

**Trigger:** battery power during the sleep. From the UPower history, 18 of 20 deep sleeps that started on battery got stuck, against 2 of 43 that started plugged in. Swapping power during the sleep also got stuck: AC at entry and battery at wake failed, and battery at entry with the charger plugged in before wake failed. Every access point of the affected network was on 5 GHz.

## Cause

The board's 5 GHz path goes through a discrete front-end module (FEM). The BCM43602 only drives it when bit 4 (`DISCRETE_FEMCTRL_MODE`) of its ChipCommon `chipcontrol` register is set. Apple's boot firmware sets that bit. A power-on reset of the chip clears it, and neither Linux nor the Wi-Fi firmware sets it again. Without it, 5 GHz joins fail until the next reboot.

On battery the chip's power is removed during S3. Plugged in, it is kept (upstream testers measured the bit staying set across an AC sleep). On this machine `chipcontrol` read `0x01400090` after boot and `0x00000000` after each battery sleep.

This explains every earlier observation:

| Observation | Explanation |
|---|---|
| A reboot always fixed it | Boot firmware sets the bit again |
| Driver reloads, PCI remove/rescan, restarting wpa_supplicant/NetworkManager did not | Nothing in Linux sets the bit |
| Cutting the chip's power via the EC (`APWC`, EC 0x03 bit 3) did not; neither did kexec | A power cut clears the bit; kexec skips boot firmware |
| An experimental hook that cut the chip's power before sleep made an AC sleep fail too | The hook itself caused the power-on reset |
| The scan showed the network; joins never got as far as association | Receive works; transmit through the 5 GHz FEM does not |

### What status 16 means here

`brcmf_bss_connect_done()` in `cfg80211.c` reports `WLAN_STATUS_AUTH_TIMEOUT` (16) for **every** unsuccessful firmware join. Because this chip runs the WPA 4-way handshake in firmware (`4WAY_HANDSHAKE_STA_PSK`), a wrong password also shows up as status 16. The two can be told apart by the reported BSSID: a real address means the access point answered and the join failed later; an all-zero BSSID means no association happened. Status 16 does not mean the router refused the laptop.

## Fix applied

The upstream patch (v3, Sergey Armodin, posted 2026-11-01, Acked-by Arend van Spriel, Broadcom) reads `chipcontrol` before firmware download on the BCM43602 and sets bit 4 if it is clear. It is limited to Apple subsystem IDs `0x0157`, `0x015a` and `0x0173`; this machine is `0x0157`. Upstream testing covered MacBookPro14,2 (`0x0157`), MacBookPro13,3 (`0x015a`) and MacBookPro14,3 (`0x0173`).

[`wifi/brcmfmac-apple-43602-femctrl.patch`](../wifi/brcmfmac-apple-43602-femctrl.patch) is that patch with one local change: the value is always logged with `dev_info` (`femctrl: ...`) so the fix can be checked without dynamic debug. `brcmfmac` re-probes the chip after every resume on this machine (the firmware does not survive S3), so the fix runs on each wake before the firmware starts.

```sh
cd /home/example/macbookpro13-2-ubuntu-investigation/wifi
./build.sh /home/example/macbookpro-ubuntu/kernel-test/linux-source-7.0.0   # or a linux-source tarball; no root
sudo ./install.sh                                                           # updates/brcmfmac-femctrl, reloads driver
```

The build uses the exact `linux-source-7.0.0=7.0.0-43.43` source of the running kernel. Built from the directory or from a tarball, the module's `srcversion` matched the loaded module. The modules are unsigned; this kernel does not enforce module signatures. Undo with `sudo ./uninstall.sh`.

**How to verify:** run [`wifi/verify-femctrl.sh`](../wifi/verify-femctrl.sh) (read-only). After boot or an AC sleep it should log `discrete FEM control mode already set`. After a battery sleep it should log `chipcontrol 0x00000000 was CLEARED, restored to 0x00000010`, and Wi-Fi should reconnect.

## Kernel upgrades

The module in `updates/` is tied to `7.0.14-mbp132-tb1`. Any other kernel loads the in-tree driver and the bug returns, unless that kernel already contains the upstream patch. After installing a new kernel, rebuild with `build.sh` from its matching source, run `install.sh` with `KVERSION=<new release>`, and check `verify-femctrl.sh`. Once the patch is merged into an incoming kernel (look for `brcmf_pcie_43602_apple_femctrl` in its `pcie.c`), the local module should be removed.

## How it was found (and what did not work)

The investigation took two days and several wrong turns; they are kept here because they rule things out:

- **Treated status 16 as the router refusing the laptop.** This led to router/mesh and "clusters" theories. The clusters turned out to be periods on battery.
- **Firmware console reading (`debug=0x100000`) looked like a fix** (13 good wakes), but all those wakes were on AC. Disproved when the problem stayed away after it was removed.
- **No effect while stuck:** driver reload, unload across S3, PCI remove/rescan, EC power cut of the Wi-Fi chip, Bluetooth chip power cut (EC 0x03 bit 4), both chips together, kexec, plugging in the charger, a further sleep on AC, wake-on-WLAN (the chip still lost power and the setting was wiped by the re-probe).
- **Battery dependence** was noticed by the user and confirmed against UPower history.
- **A wrong-password probe** showed 2.4 GHz still associating while 5 GHz did not, pointing at the 5 GHz path.
- **A parallel Codex session found the upstream patch** by searching the linux-wireless list. A search for the chip, subsystem ID and symptom at the start would have found it on day one.

Lesson recorded for this archive: search upstream lists for the exact symptom early, and read the driver source for what an error code really means.
