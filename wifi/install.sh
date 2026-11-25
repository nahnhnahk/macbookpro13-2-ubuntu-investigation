#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Install the brcmfmac modules built by build.sh into updates/ (preferred by
# modprobe over the in-tree driver) and reload the driver. Wi-Fi drops for a
# few seconds; no reboot needed. Undo: sudo ./uninstall.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
B="$HERE/src/brcmfmac"
KVERSION=${KVERSION:-$(uname -r)}
DEST=/lib/modules/$KVERSION/updates/brcmfmac-femctrl
[ -f "$B/brcmfmac.ko" ] || { echo "run build.sh first" >&2; exit 1; }
modinfo -F vermagic "$B/brcmfmac.ko" | grep -q "^$KVERSION " || { echo "built for another kernel; rerun build.sh" >&2; exit 1; }
install -D -m 0644 "$B/brcmfmac.ko"         "$DEST/brcmfmac.ko"
install -D -m 0644 "$B/wcc/brcmfmac-wcc.ko" "$DEST/brcmfmac-wcc.ko"
install -D -m 0644 "$B/cyw/brcmfmac-cyw.ko" "$DEST/brcmfmac-cyw.ko"
install -D -m 0644 "$B/bca/brcmfmac-bca.ko" "$DEST/brcmfmac-bca.ko"
depmod -a "$KVERSION"
echo "brcmfmac now resolves to: $(modinfo -n -k "$KVERSION" brcmfmac)"
if [ "$KVERSION" = "$(uname -r)" ]; then
	modprobe -r brcmfmac_wcc brcmfmac 2>/dev/null || modprobe -r brcmfmac
	sleep 1; modprobe brcmfmac; sleep 3
	journalctl -k -b --no-pager -g femctrl | tail -1
fi
