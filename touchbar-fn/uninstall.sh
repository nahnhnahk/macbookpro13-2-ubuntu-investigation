#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Revert to the kernel's stock applespi and remove the keyd exclusion.
# Usage: sudo bash uninstall.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

dkms remove -m applespi-fn -v 0.1 --all || true
rm -rf /usr/src/applespi-fn-0.1
depmod "$(uname -r)"
sed -i '/^-0000:0001$/d' /etc/keyd/default.conf
if lsinitrd "/boot/initrd.img-$(uname -r)" 2>/dev/null | grep -q 'applespi\.ko'; then
	dracut -f "/boot/initrd.img-$(uname -r)" "$(uname -r)"
fi
modprobe -r applespi && modprobe applespi
systemctl restart keyd
echo "stock applespi: $(modinfo -n applespi)"
