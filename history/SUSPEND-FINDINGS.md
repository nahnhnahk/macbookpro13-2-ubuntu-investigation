> Historical working notes, sanitized for publication. Early statements describe the state at that stage and may have been superseded by later entries. Use [current state](../docs/CURRENT-STATE.md) for the final configuration. Paths, MACs, IPs, UUIDs and boot IDs are examples or redacted.

# MacBookPro13,2 suspend investigation

Status: battery drain is diagnosed in part; no complete suspend solution validated.

## Preserved baseline

- Ubuntu 26.04.1, kernel 7.0.0-43-generic.
- Keep `pcie_port_pm=off`, `mem_sleep_default=s2idle`, and the existing systemd `MemorySleepMode=s2idle` override.
- Keep `apple_ibridge skip_acpi_power=1`. Do not invoke SOCW as a recovery experiment.
- Original custom Touch Bar checkpoint: `touchbar-display-fix/apple-touchbar.c.original`, SHA256 `d5b9e801ca91369a4f1110124f062c2b133346b83b10855cbc78e2990ad33266`, module srcversion `240BB09A92D495CAC9F76E5`.
- This checkpoint is restored and loaded. The experimental display patch was rolled back.

## Periodic wake evidence

- Spontaneous wakes at 17:01 and 17:41 were 40 minutes apart despite different suspend-entry times.
- PM diagnostics identify IRQ 9, ACPI non-EC GPE wakeup. GPE 6D increased once during the 17:41 wake.
- Captured firmware maps XHC1 USB wake (`_PRW`) to GPE 6D. Its handler sends shared wake notifications, including PWRB, so power-button counters do not prove a physical press.
- With Touch Bar forced off, a spontaneous wake still occurred.
- With Touch Bar forced off AND iBridge USB remote wake disabled, suspend lasted 88 minutes until manual keyboard wake; GPE 6D did not increase. This strongly supports iBridge remote wake as a preventable trigger, but a test changing only remote wake with a fully working Touch Bar remains pending.
- Remote wake suppression is currently not installed permanently; it was restored to enabled after tests.

## Power measurements

- Overnight UPower history: 72.797% to 2.310% over approximately 6 h 40 min.
- Early baseline snapshots included eight minutes awake, so their 4.20 W mean is not suspended power.
- Touch Bar off test: approximately 2.6–2.9 W over a short interval.
- 88-minute remote-wake-disabled test: approximately 3.3–4.0 W, with significant battery gauge settling after resume. This establishes substantial residual drain, not a precise steady suspended wattage.
- Eliminating periodic wakes alone has not demonstrated efficient suspend.

## Deep suspend and Touch Bar

- Two one-minute tests entered actual ACPI S3 and resumed automatically with the PCIe workaround retained.
- Both left the Touch Bar dark and unresponsive; the second started from a confirmed working fresh boot.
- Latest capture: `deep-60s-LOvOSXEi`. HID bindings and settings did not change across suspend. iBridge remained enumerated and underwent a USB reset on resume.
- Therefore, re-binding during resume is not an established explanation for this S3 failure.
- Earlier mode/display recovery requests, driver reload, experimental display patch, and targeted display-interface rebind did not recover it.
- USB monitoring showed full-length successful mode and display control transfers. Transport success did not restore visible output.
- Restoring the original checkpoint followed by shutdown/restart and power-button startup recovered display and touch input. Driver restoration and restart were combined, so their individual contributions cannot be isolated.
- Latest test cleanup restored s2idle, disabled diagnostic logging, and cleared the RTC alarm. Do not make deep permanent or repeat it without a specific new hypothesis and approval.

## Open work

1. Recover the Touch Bar after the latest S3 test using an explicitly approved normal restart; no firmware power calls.
2. Validate iBridge remote-wake suppression alone while retaining functional Touch Bar operation through s2idle.
3. Only then consider persistent wake suppression with backup and rollback.
4. Efficient overnight suspend remains unresolved. Any future deep-resume driver fix requires specific evidence and hardware validation. Hibernation requires separate swap/resume/security and device validation; current swap is 4 GiB against roughly 15 GiB RAM.

The reboot script requested `reboot.target`; the journal ended before firmware restart. The reason manual power-on was needed is not established.

## Additional finding, November 7

The one-minute `power/persist=0` test (`deep-60s-pQtANzwF`) did force a real disconnect and new USB enumeration (device number 2 to 3). Touch Bar operation still failed. Importantly, reprobe logged `list_add double add` in `input_register_handler`, called from `appletb_probe`, and duplicate keyboard/trackpad input-handler connections.

The original driver sets `active=false` during suspend, but uses `active` to decide whether removal should unregister its input handler and remove sysfs state. Disconnect while suspended can therefore skip teardown, then attempt to register the same handler again. This is a concrete reconnect lifecycle defect; it is not yet established as the cause of the earlier persistent-device S3 failure.

An isolated patch in `touchbar-lifecycle-fix/lifecycle.patch` separates registration lifetime (`initialized`) from run/suspend activity and guards a missing display-interface dereference in cleanup. It compiles against 7.0.0-43-generic (srcversion `D521E1602E61EB9488ED344`). It has NOT been installed or validated on hardware. Do not unload/reload the current module after the list-corruption warning. Install only after approval, start from a fresh boot, and verify a working baseline before any more suspend tests. Persistence was restored to 1; s2idle and ACPI protection remain active.

### Lifecycle fix validation update

The user subsequently installed the lifecycle patch and restarted. Loaded srcversion `D521E1602E61EB9488ED344` was verified; display and touch worked before suspend. The one-minute rediscovery test `deep-60s-RX2Hu4mv` completed real S3, disconnected USB device 2 and enumerated device 3. No duplicate-connect, double-list-add, input-handler-registration, or sysfs-registration warnings appeared. Thus the reconnect cleanup fix addresses the observed registration failure, but does NOT recover the Touch Bar after S3: display remains dark and touch fails. The mode-off `-19` during disconnect is consistent with the old USB device already being gone and is not itself evidence of the original resume cause. Original driver display behavior remains in place; the earlier display-control patch is not installed. Persistence restored to 1, s2idle restored, diagnostic logging off, and `skip_acpi_power=1` retained.

Next investigation: disassemble the captured ACPI firmware tables offline to examine the S3 iBridge power sequence. No ACPI methods should be evaluated. Further suspend repetitions without a new hypothesis are not useful.

Offline disassembly subsequently identified the distinct SOCW EC-mailbox sleep/wake handshake and found a closely matching upstream primary report: https://github.com/AJ-dev-i60/t1-touchbar/issues/4. Detailed evidence and limitations are in `acpi-analysis/FIRMWARE-FINDINGS.md`. The user explicitly prohibited unsafe SOCW power experiments; no calls or resume hooks have been run. No safe, hardware-validated deep-suspend Touch Bar fix is established yet.

The user later explicitly relaxed that constraint. A one-shot, post-S3 SOCW(1) returned Integer 0 and recovered display AND touch without restarting (`t1-firmware-wake-SjQDJQWV`). Firmware wake is now hardware-validated for one recovery. Probe protection remains enabled, no permanent sleep hook is installed, and a complete S3 sleep/wake pair plus repeated/longer testing remains necessary. See the firmware findings for details.

### Complete handshake success

`t1-deep-handshake-KVqgvbLu` completed true S3 with one SOCW(0) before suspend and one SOCW(1) afterward (after the 15-second resume capture). Both returned Integer 0. The user confirmed working display and touch input. USB persistence remained enabled; HID bindings were unchanged. This validates a complete firmware sleep/wake cycle on this laptop. It does not yet validate repeated cycles or efficient overnight consumption.

An automatic systemd-suspend integration is prepared under `t1-s3-fix/` with a refusal-to-overwrite installer and uninstall script. It has passed six simulated mode/ordering/failure tests but has NOT yet been installed or tested on hardware. It leaves the default at s2idle, uses the same 15-second post-resume delay, preserves skip_acpi_power=1 and pcie_port_pm=off, and makes no firmware calls for s2idle. Next: installation with user authorization, one short S3 check through systemd hooks, then repeated and longer battery validation before changing the sleep default.

The automatic integration was subsequently installed and validated by `deep-60s-I7G4eLKN`: both firmware return values were 0, S3 completed, and the user confirmed working Touch Bar, keyboard/trackpad and Wi-Fi after resume. There are no duplicate registration warnings in that capture. Default mode was restored to s2idle and persistence is 1. Next: 30-minute battery-only test (`test-deep-battery-30min.sh`), then consider a separately backed-up default-mode change if energy and device checks pass. Current driver is the lifecycle-fixed checkpoint, not the initial checkpoint; the earlier display-control experiment remains rolled back.

### Fifteen-minute battery test

At the user's request the battery test was shortened to 900 seconds. `deep-900s-8R5UAtl2` recorded 898.329 seconds suspended, one successful S3 cycle, no reported PM failures, charger disconnected at both ends, and both automatic firmware calls returning Integer 0. It woke at the expected alarm interval; s2idle and persistence=1 were restored afterward. Device operation after this particular test is awaiting user confirmation.

This test does NOT provide a reliable suspended wattage: UPower energy was 34.4687 Wh before, 35.5212 Wh immediately after the post-handshake, then 34.5030 Wh 15 seconds later. The unpowered increase and approximately 1 Wh change in seconds demonstrate gauge settling. Raw charge was 2994 mAh before, 3105 mAh at the first after-snapshot, and 2983 mAh at the final snapshot. The final net decline of 11 mAh (about 0.126 Wh at nominal voltage) is encouraging but includes gauge uncertainty and 35.5 seconds awake. Do not report negative consumption, zero drain, a precise wattage, or a validated overnight estimate from these readings. A longer unplugged measurement is necessary.

The user confirmed all devices working after the fifteen-minute test. A backed-up, guarded default-mode change is prepared (`enable-deep-default.sh`) but not yet installed by the agent. It creates only `/etc/systemd/sleep.conf.d/90-mbp132-deep.conf`, sets runtime mode to deep, preserves GRUB/probe protection, and refuses activation unless the tested automatic handshake integration is installed. Exact rollback is `sudo bash disable-deep-default.sh`. The handshake uninstall script now refuses removal until that managed deep default is disabled. Longer battery validation remains outstanding.

### Default enabled, premature wake under investigation

The user enabled the managed deep default; `s2idle [deep]` and the override were verified. A physical lid-close/open test recovered all devices normally. The subsequent intended one-hour battery capture `deep-3600s-ymK9gIGa` slept only 2.247 seconds. The RTC alarm remained scheduled an hour ahead; both firmware calls returned 0. Lid event count increased by one and GPE 6F by one, unlike the successful fifteen-minute test. USB controller/iBridge and Wi-Fi wake-source counters did not increase. GPEs 32/33 also increased, but these increments occurred during successful earlier RTC tests and are not uniquely diagnostic. The user confirmed the lid was fully open and untouched. A spurious lid/EC wake is a candidate, not a confirmed cause. A temporary five-minute test disabling only lid-opening wake is prepared; no permanent wake-source change has been made.

### One-hour trial with lid-opening wake temporarily disabled

The user requested an hour instead of five minutes. `deep-3600s-fKI8pevr` completed 3598.928 seconds actually suspended, one successful S3 cycle, expected RTC wake, both firmware Integer-0 acknowledgments, and no intermediate resume. AC was disconnected at both capture endpoints. User confirmed working Touch Bar and keyboard/trackpad; Wi-Fi initially failed to reconnect, then connected. Network journal shows association retries (including status_code=16) and connection at 02:24:27, about 113 seconds after PM suspend exit at 02:22:34. Exact cause of Wi-Fi association delay is not established; no Wi-Fi settings/modules were changed. Extended network journal is saved as `wifi-recovery.log` in this capture.

UPower before: 32.5239 Wh; after post-handshake: 32.7756 Wh; final: 31.7460 Wh. Net reported loss 0.7779 Wh over 3632.745 seconds (~0.771 W including ~33.8 seconds awake). Raw final charge loss: 84 mAh (~0.961 Wh nominal). These are provisional indicators because immediate post-resume gauge settling is comparable in magnitude to the total measured loss; do not claim a precise suspended wattage or verified overnight consumption.

The test restored lid-opening wake to enabled. This single isolation run supports, but does not confirm, a spurious lid-related early-wake hypothesis. Deep default and the firmware handshake integration remain enabled. Permanent lid-wake suppression has NOT been installed; it would sacrifice lid-opening wake (keyboard/trackpad wake could remain). Further comparison is needed if preserving lid-opening wake is required.

### User preference and real-world overnight validation

The user explicitly chose to preserve lid-opening wake and plans normal overnight sleep with the lid closed. Lid and SPI wake were verified enabled, deep selected, probe protection 1, persistence 1, and RTC alarm empty. No additional wake suppression is authorized. `record-overnight.py start|end` is a read-only recorder for this use: no firmware invocation, suspend, reboot, alarm scheduling, or power-setting changes. It records energy/counters and journals across boots, with post-wake samples to expose gauge settling. The overnight result remains pending. Current one-hour reported power is only provisional; a closed-lid interval with lid wake enabled is necessary to assess the remaining early-wake hypothesis and actual overnight battery performance.

### Successful closed-lid overnight result

The user returned on November 7 at approximately 12:59 and confirmed device recovery worked. `overnight-ivpie4vl/before.json` exists; the formal `record-overnight.py end` had not yet been run. The agent therefore saved a read-only `observed-on-return.json` and `journal-on-return.log` without overwriting the formal after-snapshot paths.

Journal evidence: lid closed 02:30:05, firmware sleep acknowledged, deep entry 02:30:06, lid opened 12:57:58, deep exit 12:57:58, firmware wake acknowledged 12:58:13. No intervening suspend exit/re-entry occurred. Clock differences give 10.4638 hours (about 10 h 27 min 50 s) actually suspended. Lid-opening wake remained enabled, as did SPI wake; deep default, PCIe workaround and probe protection remain in place. No RTC alarm had been scheduled. The 40-minute s2idle cycling did not recur during this real-world deep-suspend interval.

Battery remained on discharge at both observed endpoints. Raw charge declined from 2591 mAh to 2144 mAh at the agent's return snapshot, a nominal 5.114 Wh across 10.495 hours (~0.487 W including ~113 seconds awake). Saved UPower history went from 70.831% before closure to 60.498% shortly after wake; with the same 41.8475 Wh full estimate, this corresponds to approximately 4.32 Wh. Given the known post-resume gauge settling and endpoint timing differences, report roughly 4–5 Wh over 10.5 hours and approximately 0.4–0.5 W, not a precision suspended wattage. This is substantially below the earlier several-watt s2idle measurements. Formal privileged end capture remains requested to complete the archive, but the successful uninterrupted overnight suspend and recovery are already supported by the journal and user report.
