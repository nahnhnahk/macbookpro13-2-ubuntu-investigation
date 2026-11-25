#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Read-only: which brcmfmac each installed kernel loads, and what the patched
# driver logged this boot. "was CLEARED, restored" after a battery deep sleep
# means the fix did its job; "already set" is normal after a boot or AC sleep.
set -u
for k in /lib/modules/*/; do
	k=$(basename "$k")
	m=$(modinfo -n -k "$k" brcmfmac 2>/dev/null) || continue
	case $m in */updates/brcmfmac-femctrl/*) s=patched ;; *) s="in-tree (no fix)" ;; esac
	printf '%-28s %s\n' "$k" "$s"
done
echo "--- this boot:"
journalctl -k -b --no-pager -o short -g 'femctrl|PM: suspend entry' 2>/dev/null | tail -20
