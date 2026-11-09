# Validation record

## Timing and evidence

Actual suspended time is measured as the change in `CLOCK_BOOTTIME - CLOCK_MONOTONIC`. Boottime includes suspended time while monotonic excludes it. Awake time spent preparing sleep, waiting for the T1 recovery helper or running networking checks therefore does not inflate measured sleep duration.

The manual comparisons require the same boot ID, exactly one successful suspend-counter increment, no failure increment, one deep entry/exit, one lid close/open and the acknowledged T1 sleep/wake pair. A successful read-only post-wake verifier establishes driver/hardware/network readiness but cannot independently establish time asleep. Both kinds of evidence are preserved together.

| Capture | Result | Timing/evidence |
|---|---|---|
| `validation-6lgmwrhh` | Historical false positive | Original verifier reported pass without measuring duration; kernel logs show early wake. This report does not qualify for promotion. |
| `validation-jpzj_1kb` | Correctly failed duration | 3.196 seconds asleep for a 60-second alarm; no input/lid movement reported; RTC had not fired. |
| `validation-5yac3kyp` | Closed-lid pass | 99.261 seconds asleep, one cycle, controller 06. |
| `validation-3mtfzxvb` | Extended closed-lid pass | 9908.864 seconds asleep, one cycle, no intermediate wake, controller 06. |
| `validation-n689igio` | Opposite-side closed-lid pass | 104.941 seconds asleep, one cycle, adapter sysfs path confirms controller 7c. |

The three successful comparisons correspond to distinct success counters 6, 7 and 8 in the same boot. Public boot IDs are synthetic but consistently substituted. Raw clock samples are retained.

## Hardware and network checks

After each successful closed-lid trial:

- Both controller PCI configuration headers matched Intel `8086:15d4` and were accessible.
- Ethernet carrier was present, with a 1000 Mbps negotiated Ethernet link.
- USB transport was SuperSpeed, 5000 Mbps, rather than the earlier USB 2 fallback.
- IPv4 default routing used Ethernet.
- An HTTPS HEAD request explicitly bound to Ethernet succeeded.
- Source/build/loaded-module guards and standalone client readiness passed.
- The ordinary systemd T1 sleep and delayed wake calls acknowledged Integer 0.

The user reported working devices after the extended trial. This report does not infer a measured throughput benchmark, complete testing of every peripheral or a new-kernel battery wattage.

## Promotion criteria

The promotion script requires three distinct duration-verified cycles and at least one with **900 measured seconds** asleep. It accepts fully checked RTC trials or independently evidenced manual lid comparisons. Repeated reports of the same boot/counter cycle count once. A current read-only hardware verification must also pass.

An RTC trial requires at least requested duration minus 15 seconds, allowing for pre-entry overhead. Manual comparisons require at least 30 actual seconds and their full clock/counter/journal evidence. Missing evidence, changed boot, multiple cycles in one comparison, failed recovery and early wake are rejected. The three closed-lid comparisons met these criteria before promotion.

## Automated checks

The published snapshot retains 51 standard-library unit tests across driver guards/handshake (29), permission handling (8), GRUB parsing (5), and suspend timing/wait/evidence qualification (9). Hardware and firmware calls in these tests are mocked. Public snapshot integrity and privacy checks run separately. CI does not install a kernel or request suspend.

Selected journal excerpts are filtered to relevant kernel and suspend/logind events. Full original machine logs and build trees remain local; see [publication handling](PUBLICATION.md).
