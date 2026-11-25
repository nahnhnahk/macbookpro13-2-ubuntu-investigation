#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Build brcmfmac with brcmfmac-apple-43602-femctrl.patch for the running kernel
# (or KVERSION=...). Takes the driver from a kernel source tree or Ubuntu's
# linux-source tarball. Runs without root; writes only to wifi/src.
#
# Usage: ./build.sh <kernel-source-dir | /usr/src/linux-source-X.Y.0.tar.bz2>
# Then:  sudo ./install.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:?usage: $0 <kernel-source-dir | linux-source tarball>}"
KVERSION=${KVERSION:-$(uname -r)}
SUB=drivers/net/wireless/broadcom/brcm80211
OUT="$HERE/src"

rm -rf "$OUT"; mkdir -p "$OUT"
if [ -d "$SRC" ]; then
	cp -r "$SRC/$SUB/brcmfmac" "$SRC/$SUB/include" "$OUT/"
else
	top="$( (tar -tf "$SRC" || true) | head -1 | cut -d/ -f1)"
	[ -n "$top" ] || { echo "cannot list $SRC" >&2; exit 1; }
	tar -xf "$SRC" -C "$OUT" --strip-components=6 "$top/$SUB/brcmfmac" "$top/$SUB/include"
fi
patch -d "$OUT/brcmfmac" -p7 --forward < "$HERE/brcmfmac-apple-43602-femctrl.patch"
make -C "/lib/modules/$KVERSION/build" M="$OUT/brcmfmac" modules -j"$(nproc)"
grep -q femctrl "$OUT/brcmfmac/brcmfmac.ko" || { echo "patched code missing from module" >&2; exit 1; }
echo "Built for $KVERSION in $OUT/brcmfmac. Install with: sudo $HERE/install.sh"
