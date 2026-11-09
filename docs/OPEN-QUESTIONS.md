# Open questions

1. **Premature wake with lid open.** RTC was still pending; lid events/GPE 6F increased and other relevant wake-source counters did not. The closed-lid trials remained asleep until lid opening. Determine the exact firmware/lid-state cause while preserving the user's preference for lid-opening wake. No wake suppression is installed.
2. **Inactive controller reinitialization.** The unused xHCI tree logs a reset on resume. Both active sides passed, but additional peripherals, repeated cold starts and longer opposite-side trials remain useful.
3. **Future kernels.** Track whether the complete kernel changes are accepted/backported, review any ordering changes and keep a patched security-maintained replacement available. Do not infer upstream acceptance from an author's proposed patch.
4. **Battery on the patched kernel.** Earlier successful stock deep-sleep measurements showed much lower drain than s2idle, with gauge-settling limitations. A controlled multi-hour discharge test under the new kernel is still needed for a new power claim.
5. **DHCP source of truth.** The tested client identity avoids the observed duplicate address. Router-side reservation/static-address cleanup and precise identification of the claimant remain separate work.
6. **Breadth of recovery coverage.** Three measured cycles on one MacBookPro13,2 validate these conditions, not every adapter, hub, external display or other MacBook model. Exact EDUP retail model remains unconfirmed.
7. **Audio beyond the internal speakers.** Complete and verify the DKMS install, including on the stock kernel. Check the headphone jack and detection, internal/headset microphones and speaker behavior after deep-sleep resume with the patched CS8409 driver. Track upstream Apple CS8409 support.

Preserve failed trials and their limitations. In particular, the old verifier's `passed: true` report without duration evidence must never be counted as a successful long sleep.
