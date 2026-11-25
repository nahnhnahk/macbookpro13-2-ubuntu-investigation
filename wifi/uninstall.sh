#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Remove the patched brcmfmac and go back to the in-tree driver.
set -eu
KVERSION=${KVERSION:-$(uname -r)}
rm -rf "/lib/modules/$KVERSION/updates/brcmfmac-femctrl"
depmod -a "$KVERSION"
if [ "$KVERSION" = "$(uname -r)" ]; then
	modprobe -r brcmfmac_wcc brcmfmac 2>/dev/null || modprobe -r brcmfmac
	modprobe brcmfmac
fi
echo "brcmfmac now resolves to: $(modinfo -n -k "$KVERSION" brcmfmac)"
