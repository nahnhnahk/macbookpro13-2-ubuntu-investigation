> Historical working notes, sanitized for publication. Early statements describe the state at that stage and may have been superseded by later entries. Use [current state](../docs/CURRENT-STATE.md) for the final configuration. Paths, MACs, IPs, UUIDs and boot IDs are examples or redacted.

# USB Ethernet investigation — November 7, 2026

Initial investigation was read-only. The later DHCP investigation changed only the original wired profile's DHCP client ID; details and rollback are below. No driver, firmware, or persistent USB power change has been made.

Latest status (22:55–23:00, new boot): the reproduced failure is traced directly to the Apple Alpine Ridge Thunderbolt/USB 3 controller tree becoming inaccessible during deep-sleep resume. The working SuperSpeed Ethernet device was on that tree and disconnected when its controller was removed. A hold-awake test of the remaining USB 2 hub did not recover it. Ethernet is currently absent; Wi-Fi provides connectivity. The DHCP workaround survived reboot and obtained `.25` before sleep. A closely matching upstream kernel patch is identified below; no kernel/firmware change has been applied. Historical sections describe earlier failures and temporary recoveries.

## Current failure

- USB sees a Genesys Logic USB2.1 hub, `05e3:0610`, at `1-8`, but no Ethernet device downstream.
- All four hub ports report `state: not attached`, `disable: 0`, and zero overcurrent events. Hub and interface authorization are both enabled.
- The only network interfaces are loopback and Wi-Fi. NetworkManager therefore has no Ethernet interface to display.
- `r8152`, `r8153_ecm`, and their dependencies are already loaded. A missing Ethernet driver does not explain the absent USB device.

## Journal evidence (local time, America/Los_Angeles)

- 13:57:04: Genesys hub enumerated.
- 13:58:12, following deep-sleep resume: Realtek `0bda:8153`, product `USB 10/100/1000 LAN`, enumerated at `1-8.1`.
- 13:58:13: `r8152` created `enx020000000001`; carrier appeared at 13:58:28.
- 14:00:42: hub and Ethernet chip both enumerated again after a disconnect/reconnect.
- 14:02–14:03: NetworkManager activated the wired connection. Logs also show repeated Ethernet carrier changes and a separate DHCP address conflict for `192.0.2.28` with another MAC. That conflict could interfere with connectivity after detection, but cannot explain today's missing USB device.
- 14:56:53, during resume from deep sleep: hub and Ethernet chip disconnected.
- 14:56:58–14:57:11: hub enumeration failed repeatedly with `device descriptor read/64, error -71`, `Device not responding to setup address`, and `device not accepting address`.
- 18:36:28: hub reappeared after another resume, without the Ethernet chip.
- 18:40:10: another hub enumeration, again without the Ethernet chip.

The immediate cause is failure of USB enumeration of the Ethernet chip behind the hub. The logs support a sleep/resume or adapter power/state problem; they do not isolate adapter hardware/firmware, USB-C connection, or the host controller as the underlying cause. A full adapter power disconnect and reconnection to another physical USB-C port is the next isolation step. If the adapter also has external USB-C power, unplug that supply too when power-cycling it.

Kernel USB error documentation describes protocol errors as potentially caused by devices, firmware, or cables; the error alone does not establish defective hardware: https://www.kernel.org/doc/html/latest/driver-api/usb/error-codes.html

## Additional host-controller observation

At boot, the machine had Thunderbolt-side xHCI controllers `0000:06:00.0` and `0000:7c:00.0`. Both were removed during the first recorded deep-sleep resume at 00:51:14 with `Host not accessible, reset failed`; neither is currently present. Thunderbolt configuration-read warnings occur on resume, and several upstream bridges report D3cold. This is a separate resume anomaly worth investigating if another-port testing or a fresh boot changes behavior. It is not sufficient to explain this particular missing Ethernet chip: the chip successfully enumerated through the remaining Intel USB controller later in the same boot.

## Next verification

1. Compare USB journal and `lsusb -t` after a complete adapter power disconnect and reconnection to another physical USB-C port.
2. If `0bda:8153` returns, check `enx020000000001`, carrier, DHCP, and the earlier address conflict.
3. If only `05e3:0610` returns, compare the adapter on another computer or another adapter on this computer. A fresh-boot comparison can separately test the controller resume anomaly; no reboot was performed or scheduled.

The user identified the brand as EDUP. Exact model is not yet known.

## Different-port reconnection result

The user confirmed completion of the requested test. Journal shows the hub disconnected from `1-8` at 18:46:46 and appeared on a different physical USB path, `1-6`, at 18:47:08 (22 seconds later). Only the Genesys hub enumerated; `0bda:8153` did not return. No Ethernet interface was created. Both paths use the remaining Intel xHCI controller; this does not test a separate host controller. The replug rules out a single bad physical socket as the sole explanation, but does not distinguish an adapter problem from shared host-controller state.

A fresh boot with the adapter connected, before any suspend, is the next useful host-state comparison. Testing the adapter on another computer would independently check whether the chip fails to enumerate there too. No reboot or system modification has been performed.

## Recovery after lid-close sleep and wake

The user closed the lid for about ten seconds, reopened it, and reported Ethernet working. Kernel and network evidence:

- 18:48:17: entered deep sleep; 18:48:23: resumed from S3.
- 18:48:24–25: Ethernet chip `0bda:8153` newly enumerated at `1-6.1`, behind the same hub device 17 that had previously reported no children. The hub itself did not receive a new USB device number in this cycle.
- 18:48:26: existing `r8152` driver created `enx020000000001`.
- 18:48:39: carrier on and NetworkManager activated the wired profile. `ethtool` confirms 1000 Mb/s full duplex. USB transport remains high-speed USB 2 (480 Mb/s), rather than SuperSpeed.
- 18:48:39: NetworkManager again logged a conflict for `192.0.2.28` with `02:00:00:00:00:03`.
- At verification around 18:49, the Ethernet interface had `192.0.2.28`, but NetworkManager listed no IPv4 gateway/routes for it; `ip -4 route get 1.1.1.1` used Wi-Fi `wlp2s0`. Thus Ethernet recognition/link recovered, but ordinary IPv4 internet traffic still used Wi-Fi.

This supports an intermittent USB detection/power-management issue: the sleep/resume sequence made a previously invisible downstream device appear, using the already installed driver. The earlier 13:57 hub-only hotplug followed by 13:58 post-resume Ethernet enumeration shows the same pattern. The exact fault could be host USB handling or adapter hub/firmware behavior; existing logs cannot attribute it to one component or prove autosuspend is responsible. Unplug/replug and full system sleep execute different initialization/power sequences, so their different outcomes are not contradictory.

The separate inaccessible-PCI-bridge warnings persisted during the successful recovery. Therefore this cycle did not establish recovery of the absent Thunderbolt-side controllers, nor are those controllers required for this USB 2 Ethernet path to work. No fresh boot was needed for the observed recovery. No permanent fix has been applied or validated.

## DHCP conflict: identified and worked around

- Original profile `Wired connection 1`, UUID `00000000-0000-4000-8000-000000000001`, uses automatic IPv4, accepts DHCP routes, and does not suppress the default route. DHCP server `192.0.2.1` supplies gateway `192.0.2.1`. There was no manually configured static address on the MacBook.
- A plain profile reconnect at 18:55 repeatedly received `.28`, and NetworkManager rejected it because `02:00:00:00:00:03` claimed it.
- The installed IEEE OUI database identifies prefix `F8B95A` as LG Innotek. The user confirms LG TVs on the network, but the exact device is not yet identified in the router's device list.
- After releasing `.28` locally, probing `.28` through Wi-Fi populated the ARP neighbour entry with `02:00:00:00:00:03`. This independently confirms another device's claim. That device did not answer ICMP; no inference about it being offline follows from that.
- A temporary clone with a distinct DHCP client ID obtained `.25`, installed Ethernet routes, passed three Ethernet-bound pings to `1.1.1.1`, and returned HTTPS HTTP 200 from `example.com` bound explicitly to Ethernet.
- Setting the original profile to the keyword `stable` produced a different client ID than the temporary clone and was still offered `.28`. Therefore the final workaround uses the exact tested client ID `[DHCP_CLIENT_ID_REDACTED]` on the original profile. This is the only persistent profile-setting change. IPv6 and the other original settings are retained.
- At 19:04:30 the original profile obtained `.25`. Verification through that original profile passed three of three Ethernet-bound internet pings and an HTTPS HEAD request (HTTP 200). `ip -4 route get 1.1.1.1` selected Ethernet with source `.25`, metric 100; Wi-Fi's default route has metric 600. The temporary clone was deleted after validation.
- Original profile settings, experiment output, and final validation are in `ethernet-investigation/`. Rollback: `bash /home/example/macbookpro-ubuntu/ethernet-investigation/rollback-dhcp-client-id.sh`. This restores the original default DHCP identity and reconnects; the old address conflict may recur.

This avoids the conflicting lease on the MacBook; it does not repair the router's lease/reservation table or any static address on the LG device. Router/device configuration is needed to determine why the server offered an already-claimed address. Do not disable address-conflict detection or choose a guessed static address as a substitute.

### Additional ARP observation with both network interfaces active

There were also self-conflict messages: Ethernet's `.25` claimed by the MacBook's Wi-Fi MAC `02:00:00:00:00:02`, and Wi-Fi's `.32` claimed by the Ethernet MAC. Both interfaces have the Linux default `arp_ignore=0`, `arp_announce=0`, and `arp_filter=0`. The kernel documents that this permits answering for addresses assigned to other local interfaces. Some of the self-conflict messages occurred during forced-interface diagnostics while Ethernet lacked an address; these must not be confused with the independently verified LG claim on `.28`.

Ethernet-bound internet tests still passed after switching to `.25`, and the default route remained installed on subsequent inspection. NetworkManager did not expose the connected-subnet route in that inspection. ARP isolation remains a separate potential improvement if these self-conflicts cause further symptoms; no sysctl values have been changed.

Kernel ARP documentation: https://docs.kernel.org/networking/ip-sysctl.html#arp-ignore-integer
NetworkManager DHCP client ID documentation: https://www.networkmanager.dev/docs/api/latest/settings-ipv4.html

## USB runtime-power hypothesis and next test

The Genesys hub has `power/control=auto` and a zero-millisecond autosuspend delay. While Ethernet was missing it was runtime-suspended; with the Ethernet chip present it is active. Zero delay is normal Linux hub behavior, not proof of a fault. The upstream hub driver's comments explicitly discuss rare downstream devices whose initialization/reconnection can interact with hub autosuspend. This makes keeping the parent hub awake a targeted experiment, not an established fix.

The Realtek chip itself already has `power/control=on` and quirk mask `0x400` (`USB_QUIRK_NO_LPM`). The upstream quirk table applies that workaround to `0bda:8153`. Adding the same workaround again would not address this observation.

Prepared `ethernet-investigation/test-usb-hub.py`: captures a baseline; asks for a same-port unplug/replug; if the hub returns without Ethernet, writes `on` only to the matching Genesys hub's `power/control` for up to 15 seconds and observes whether the Ethernet chip appears. It restores the saved value afterward, including on Ctrl-C, and saves sysfs state plus a kernel journal. It does not reset devices, invoke firmware, suspend the computer, or install rules. A successful hold-awake recovery would implicate the runtime-PM path, including ancestor resume, rather than prove that the hub alone is defective. A non-reproducing replug or failed recovery does not establish a fix.

Administrator execution is required to write this sysfs setting. The earlier `sudo -n` attempt required interactive authentication. The user has been asked to run `sudo python3 /home/example/macbookpro-ubuntu/ethernet-investigation/test-usb-hub.py` in their terminal. No USB test result was available when this update was written.

Upstream hub implementation: https://github.com/torvalds/linux/blob/master/drivers/usb/core/hub.c
Upstream USB quirks: https://github.com/torvalds/linux/blob/master/drivers/usb/core/quirks.c
USB power-control semantics: https://docs.kernel.org/driver-api/usb/power-management.html

## User-run USB test result, 19:09

Results: `ethernet-investigation/usb-test-20261107-190930/`.

- Baseline hub device 17 and Ethernet device 18 were both present.
- They disconnected at 19:09:34–35. The same physical path `1-6` re-enumerated at 19:09:50 as hub device 19; Ethernet followed immediately as device 20, with `r8152` bound at 19:09:51 and carrier at 19:09:54.
- The hub remained `power/control=auto`; the result's `changes` list is empty. The script never exercised its hold-awake branch, so this is not evidence that disabling autosuspend fixes the issue.
- At 19:10:34, the original wired profile had `.25`, gateway `.1`, connected-subnet route and default route with metric 100. Thus the DHCP workaround survived a real USB disconnect/reconnect, and the earlier missing connected-subnet route was no longer missing at this observation.
- There were no USB enumeration/protocol errors in this capture. The fault remains intermittent and its component-level cause is not established. No permanent USB-power workaround is justified by this result.

The script now supports `--current` to preserve an already-failed state: if the hub-only symptom recurs, run `sudo python3 /home/example/macbookpro-ubuntu/ethernet-investigation/test-usb-hub.py --current` before unplugging or closing the lid. It captures the existing state, tests the temporary hold-awake setting, restores it, and saves evidence. When Ethernet is already present it reports that and makes no change.

## Reproduction after reboot: direct USB 3 controller loss

Boot ID `boot-example-001` began at 22:51:04. Evidence is saved in `ethernet-investigation/failure-20261107-225526/`, including a complete kernel boot journal. This new capture directly links the previously observed controller resume anomaly to Ethernet loss; it supersedes treating the controller anomaly as merely a separate observation for this reproduction.

Before suspend:

- Both Alpine Ridge xHCI controllers existed: `0000:06:00.0` and `0000:7c:00.0`, Intel `8086:15d4`.
- The adapter's USB 3 hub `05e3:0626` was at `4-2`, and RTL8153 was at `4-2.1`, on the `06:00.0` USB controller. Both were SuperSpeed devices. The USB 2 hub `05e3:0610` simultaneously existed at `1-8` on the PCH controller, with no Ethernet child, while the chip was using USB 3 instead.
- At 22:51:15, the original wired profile obtained `.25` and activated successfully. This verifies that the DHCP workaround persisted across reboot.

Failure sequence:

- 22:52:51: entered actual deep/S3 sleep.
- 22:52:57: during resume, upstream Thunderbolt bridges `03:00.0` and `79:00.0` and their downstream bridges became inaccessible. Root ports RP05/RP09 reported link width zero. The downstream trees reported D3cold; PCI reads showed unknown header type `7f`.
- PCI hotplug logged the internal xHCI slots as absent. Linux removed both Alpine Ridge xHCI controllers and their USB buses. RTL8153 at `4-2.1` disconnected as its USB bus was removed.
- The PCH USB controller stayed present, with the adapter's empty USB 2 hub still attached. No Ethernet interface remains. This failure occurs below the network driver/DHCP layer.

The earlier USB 2 recovery is consistent with the adapter later falling back to the PCH high-speed path. It did not demonstrate recovery of the missing SuperSpeed controllers. That explains why an occasional lid cycle or replug could restore reduced-speed Ethernet while leaving the underlying controller defect unresolved.

## Failed-state hub power test, 22:56

The user ran the prepared script with `--current`. Results: `ethernet-investigation/usb-test-20261107-225612/`.

- It held the same `1-8` hub awake: `power/control` changed from `auto` to `on`, and runtime state changed from `suspended` to `active`.
- All four downstream ports remained `not attached`; no Ethernet chip appeared during the 15-second observation.
- The script restored `power/control=auto`. Kernel log had no USB enumeration events during the test.

This rules out simply keeping the already-failed USB 2 hub awake as a recovery for this instance. It does not prove that runtime PM can never influence initial enumeration, but a permanent hub-autosuspend change is not supported as a fix for the demonstrated USB 3 controller loss.

## Matching upstream fix and implementation checks

An upstream patch posted November 3, 2026, **[PATCH v4] thunderbolt: Call SXFP() on Apple systems with Alpine Ridge when suspending**, describes this same attached-device/S3/link-down failure and adds a pre-suspend controller/firmware sequence. Primary author submission:

https://lore-kernel.gnuweeb.org/linux-usb/20261103115104.13845-1-fbeltranmillalen@gmail.com/

The proposed sequence clears a controller register bit before requesting the firmware's sleep-power operation, while the Thunderbolt control channel is still available. Timing matters. The author reports testing a backport on MacBookPro14,3 together with additional PCI/ACPICA changes; this is a candidate fix for this machine, not a hardware-validated repair for MacBookPro13,2. The retrieved submission is a patch under review, not proof of availability in a released Ubuntu kernel.

Local verification:

- Running kernel is `7.0.0-43-generic`, package `7.0.0-43.43`, with `pcie_port_pm=off` retained and actual sleep mode `deep`.
- Loaded-module srcversion: `6B073AB73CF32A6BD2827E2`. The matching on-disk Thunderbolt module contains `nhi_suspend_noirq` but neither the literal `SXFP` nor the proposed `tb_acpi_force_power`, `ar_pre_suspend_noirq`, or `tb_switch_set_bit26` symbols. Kallsyms also lacks the proposed symbols. This supports that the proposed workaround is absent from this installed driver; checks saved as `thunderbolt-module-check.json`.
- The previously captured SSDT5 was disassembled offline with iasl into `ethernet-investigation/acpi/SSDT5.dsl`. Both NHI firmware nodes define `SXFP` (lines 2067 and 6307), matching the method targeted by the patch. The file contains definitions only, no SXFP call sites. No firmware method was executed during this analysis.
- The local APT package cache lists `7.0.0-43.43` as the generic-kernel candidate. Package indexes were not refreshed; this is not a claim about all current online packages.

Next repair work would require checking/backporting the controller suspend sequence and its prerequisite fixes against Ubuntu's exact kernel source, compiling an isolated test build, and validating from a healthy boot with a rollback kernel retained. A shell-only invocation of the firmware method would lack the driver synchronization and register handling required by the proposed fix. No raw firmware calls, PCI removal/rescan, driver reload, boot-parameter changes, or additional suspend/reboot were performed by the agent in this reproduction.

### Patched kernel closed-lid result (2026-11-08)

On7.0.14-mbp132-tb1, the first open-lid timed tests resumed after about3 seconds. Improved measurement confirmed3.196 seconds suspended for a60-second alarm; RTC had not fired. Only lid wake-source event count rose(+1), with GPE6F+1 (mapped by firmware LID0._PRW); USB/iBridge/Ethernet/WiFi counts did not rise. User confirmed no input or lid movement. This mirrors an earlier stock open-lid failure and points to lid/firmware as a candidate; no wake suppression was installed.

Normal lid-close comparison validation-5yac3kyp stayed in deep sleep99.261 seconds, with exactly one successful cycle and no intervening resume. Lid-close14:22:17, deep entry14:22:19, lid-open/exit14:23:59; T1 recovery acknowledged14:24:15. Verifier passed at14:24:36: USB3 at5000Mbps, Ethernet1000Mbps, address192.0.2.25/default route and bound HTTPS200; both xHCI PCI configurations remained accessible. The unused7c controller still logs reinitialization USBSTS0x401, so longer and both-side testing remain necessary. This is promising short closed-lid recovery evidence, not a completed reliability validation or a reason to promote yet. Artifacts and preserved before/after timing evidence are inside that capture directory.

### Multi-hour closed-lid validation

`validation-3mtfzxvb` on the patched kernel passed after user normal lid-close use for several hours. One cycle, no failures, no intervening resume: close14:27:46, deep entry14:27:47, lid-open/exit17:12:57. Independent boottime-minus-monotonic clocks measure9908.864 seconds asleep (2h45m8.864s). T1 recovery acknowledged17:13:13; Ethernet postchecks passed at17:14:20, retaining USB5000Mbps/link1000Mbps/address.25/default routing and HTTPS200. User reports things working. This establishes successful multi-hour recovery on the currently used controller06. Opposite-side adapter trial remains; open-lid early wake and unused7c reinitialization remain separate limitations. No permanent wake suppression or kernel-default promotion applied.

### Opposite-side confirmation and promotion readiness

`validation-n689igio` adds a third distinct successful closed-lid cycle,104.941 seconds asleep, ending with lid opening. Adapter moved to controller0000:7c:00.0 (usb6), confirming actual opposite-controller use rather than another port on the original controller. Post-wake Ethernet retained USB5000/link1000/default route/.25 and successful HTTPS; both PCI controller IDs accessible; T1 acknowledgments succeeded. The inactive controller06 now logged reinitialization, while the newly active7c kept Ethernet. Three measured cycles, including2h45m, meet the prepared promotion checks. Promotion is ready but still requires the user sudo command; stock default unchanged during analysis. Open-lid premature wake remains a separate unresolved limitation.
