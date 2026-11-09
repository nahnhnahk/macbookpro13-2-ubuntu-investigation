#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Install the applespi "separate Fn device" fix as DKMS and make keyd ignore
# that device, so the Touch Bar driver sees Fn presses and keyboard activity.
# Usage: sudo bash install.sh
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/src/dkms.conf" ] || { echo "run ./prepare-dkms-source.sh first" >&2; exit 1; }
PKG=applespi-fn
VER=0.1
KVER="$(uname -r)"
KEYD_CONF=/etc/keyd/default.conf
FN_ID="0000:0001"   # vendor:product of "Apple SPI Fn Key"

kbd_present() { grep -q 'Name="Apple SPI Keyboard"' /proc/bus/input/devices; }

rollback() {
	echo "!! keyboard did not come back with the new module; rolling back" >&2
	dkms remove -m "$PKG" -v "$VER" -k "$KVER" >/dev/null 2>&1 || true
	depmod "$KVER"
	modprobe -r applespi 2>/dev/null || true
	modprobe applespi
	exit 1
}

echo "== DKMS: $PKG/$VER for $KVER"
rm -rf "/usr/src/$PKG-$VER"
cp -r "$HERE/src" "/usr/src/$PKG-$VER"
dkms remove -m "$PKG" -v "$VER" --all >/dev/null 2>&1 || true
dkms add -m "$PKG" -v "$VER"
dkms build -m "$PKG" -v "$VER" -k "$KVER"
dkms install -m "$PKG" -v "$VER" -k "$KVER" --force
echo "modprobe resolves applespi to: $(modinfo -k "$KVER" -n applespi)"

echo "== keyd: exclude $FN_ID from [ids]"
if grep -qx -- "-$FN_ID" "$KEYD_CONF"; then
	echo "already excluded"
else
	cp -a "$KEYD_CONF" "$KEYD_CONF.bak-fn-$(date +%Y%m%d-%H%M%S)"
	# add the exclusion right after the [ids] header
	sed -i "/^\[ids\]\$/a -$FN_ID" "$KEYD_CONF"
fi
sed -n '/^\[ids\]/,/^\[/p' "$KEYD_CONF"

echo "== initramfs"
if lsinitrd "/boot/initrd.img-$KVER" 2>/dev/null | grep -q 'applespi\.ko'; then
	echo "applespi is in the initramfs; regenerating"
	dracut -f "/boot/initrd.img-$KVER" "$KVER"
else
	echo "applespi not in initramfs; nothing to do"
fi

echo "== reloading applespi (keyboard/touchpad drop out for ~2s)"
modprobe -r applespi && modprobe applespi
for _ in $(seq 20); do kbd_present && break; sleep 0.5; done
kbd_present || rollback
systemctl restart keyd

sleep 2
echo "== result"
grep -A5 -E 'Name="Apple SPI (Keyboard|Fn Key)"' /proc/bus/input/devices | grep -E '^(N|H):'
journalctl -u keyd -b --no-pager -n 20 | grep -E 'Apple SPI|0000:0001' || true
echo "loaded srcversion: $(cat /sys/module/applespi/srcversion)"
