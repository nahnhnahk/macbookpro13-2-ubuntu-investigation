# Investigation timeline

Dates identify the investigation events; the Git commits publishing this archive are made afterward and are not backdated. Historical source notes retain the sequence of changing hypotheses.

| Date/stage | Observation or action | Outcome |
|---|---|---|
| Nov 5–6 | Baseline s2idle, battery history, USB/ACPI wake capture | Periodic wakes and substantial residual drain; no complete fix established |
| Nov 6 | Touch Bar-off and USB remote-wake isolation | Longer sleep in a combined trial, but not proof of a single cause or efficient suspend |
| Nov 6–7 | True S3 tests and USB persistence experiments | Deep sleep worked; Touch Bar display/touch failed; transport success did not prove firmware recovery |
| Nov 7 | Driver reconnect lifecycle investigation | Found skipped teardown and duplicate input-handler registration; lifecycle patch validated separately |
| Nov 7 | Offline ACPI disassembly, then explicitly authorized firmware test | SOCW wake returned 0 and recovered display/touch; complete paired recovery subsequently validated |
| Nov 7 | Guarded systemd integration and deep default | Short and longer S3 trials passed with the 15-second post-resume sequence |
| Nov 7 | Earlier stock closed-lid overnight observation | About 10 h 28 min without intermediate wake; device recovery reported working; power figures remain configuration-specific |
| Nov 7 | EDUP adapter detection investigation | Hub-only symptom; occasional USB 2 fallback recovery; separate DHCP conflict identified |
| Nov 7 | Distinct DHCP identity tested and applied to original profile | Different address, bound HTTPS, reconnect and reboot validation passed |
| Nov 7, fresh boot | Reproduced USB 3 controller loss after S3 | Both Alpine Ridge controller trees removed; Ethernet disconnected with its parent bus |
| Nov 7 | Failed-state parent-hub hold-awake test | Hub became active, Ethernet stayed absent; setting restored |
| Nov 7–8 | Exact-source kernel backport and isolated build | Added Thunderbolt/PCI/ACPICA changes; exported headers compiled both T1 modules |
| Nov 8, build completion | Final image generation needed `gawk`; package dependency initially assumed initramfs-tools | Extracted hash-checked gawk locally; corrected dependency to accept installed dracut; no kernel restart from scratch |
| Nov 8, initial install | Build workspace modes left package directories at 0775 | Security guard correctly stopped before test initramfs/boot scheduling |
| Nov 8, package repair | Corrected archives alone did not fix existing directories | Real isolated dpkg upgrade reproduced mode preservation; added explicit scoped 0775→0755 directory repair and tests |
| Nov 8, boot selection | Installer produced submenu→stock→test path | Parser had matched a quoted default reference; fixed declaration matching, uniqueness/device checks and readback; booted test kernel |
| Nov 8, first menu suspend | Suspend cancelled before kernel entry | Ubuntu acpidbg dispatcher lacked a custom-kernel tool path; installed approved standalone client and preflight check |
| Nov 8, early timed tests | Ethernet recovered but tests lasted about 23 seconds | About 3 seconds asleep plus active recovery; original verifier false positives retained as historical evidence |
| Nov 8, corrected duration test | 3.196 seconds asleep for a 60-second alarm | Correctly failed duration; RTC still pending; lid event and GPE 6F increased |
| Nov 8, closed-lid trial | 99.261 seconds asleep | No intermediate wake; Ethernet/T1 recovery passed |
| Nov 8, extended closed-lid trial | 9908.864 seconds asleep | About 2 h 45 min uninterrupted; woke on lid opening; recovery passed |
| Nov 8, opposite-controller trial | 104.941 seconds asleep with adapter on 7c:00.0 | Ethernet retained USB 3 and 1 Gbps link; both sides now exercised |
| Nov 8, promotion | User completed the final promotion step | Installed GRUB configuration independently verified to select patched kernel; stock fallback retained |
| Nov 8, publication | Sanitized docs, source snapshots, evidence and regression tests assembled | Actual public Git history begins with this archive; future changes should append dated evidence |
| Nov 7–8, audio | Internal speakers silent since install; userspace sink at full volume | In-tree CS8409 driver uses generic fallback for Apple ID `0x106b3600`; speaker amplifiers never initialized |
| Nov 8 00:24, audio | Community driver added to DKMS | Pre-build failed: `linux-source-7.0.0.tar.bz2` missing; state stayed `added`, unnoticed |
| Nov 8, audio | Rebooted into patched kernel; still silent | Custom kernel's cs8409 module identical to stock (`srcversion`); script would also look for nonexistent `linux-source-7.0.14` |
| Nov 8, audio | Built patched driver rootless from the archived `7.0.0-43.43` source; user installed it into `updates/` and rebooted | `patch_cs8409 NOT FOUND trying APPLE`; user confirmed the speakers play |
| Nov 8, audio | Source-lookup fallback patch for the DKMS hook; tested rootless for both installed kernels | Both build; root DKMS install, stock-kernel playback, headphones/mic and post-resume behavior not yet validated |
| Nov 8, Touch Bar Fn | Holding Fn did not switch the Touch Bar to F-keys; `tbkbd` attached and `fnmode=1` | keyd's exclusive grab of the Apple SPI Keyboard; `input_pass_values()` delivers grabbed events only to the grabber, and keyd does not emit `KEY_FN` |
| Nov 8, Touch Bar Fn | Chose an `applespi`-only fix over patching `apple-touchbar` | Changing the pinned T1 source would block deep sleep until re-approval |
| Nov 8 20:58, Touch Bar Fn | DKMS `applespi-fn/0.1` installed, module reloaded, keyd restarted with `-0000:0001` | `tbkbd` now on "Apple SPI Fn Key"; user confirmed Fn switches the bar; reboot/resume/keep-alive/stock kernels not yet checked |
| Nov 23, Wi-Fi | After some deep sleeps Wi-Fi could not rejoin; every attempt `ASSOC-REJECT` with all-zero BSSID, status 16; only reboot fixed it | Read as access points refusing the laptop; driver reload, PCI rescan, daemon restarts, EC power cut of the chip and kexec all failed to recover |
| Nov 24, Wi-Fi | brcmfmac firmware-console reading (`debug=0x100000`) followed by 13 good wakes | Mistaken for a fix: all 13 were on AC; problem stayed away after removal |
| Nov 24 evening, Wi-Fi | User noticed failures only when sleeping on battery | UPower history: battery 18/20 stuck, AC 2/43; swapping power mid-sleep still failed |
| Nov 24, Wi-Fi | Power-cut hook before sleep, wake-on-WLAN, Bluetooth chip power cut, both chips together | None helped; power-cut hook made an AC sleep fail; driver re-probes after every resume, so firmware loss alone is not the difference |
| Nov 25 00:00, Wi-Fi | Wrong-password band probe | Firmware handshake offload makes a wrong password status 16 too; stuck 2.4 GHz still associated, 5 GHz did not |
| Nov 25, Wi-Fi | Parallel Codex session found upstream patch "restore FEM control pin mode on Apple BCM43602" (v3, Acked-by Broadcom), covering subsystem `106b:0157` | Battery S3 clears ChipCommon chipcontrol bit 4; boot firmware sets it; nothing in Linux restores it |
| Nov 25 12:01, Wi-Fi | Backported patch with logging, installed in `updates/` | `chipcontrol 0x01400090` after boot, `0x00000000` after each of two battery sleeps, restored to `0x00000010`; Wi-Fi reconnected; longer sleeps and stock kernels not yet checked |

The initial investigation had deliberately narrower authorization for firmware experiments. Later explicit user authorization and validation superseded those restrictions in the recorded session. Historical warning paragraphs describe their original stage; they are not a substitute for the final configuration or permission to experiment on another machine.
