#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Assemble the applespi-fn DKMS source in touchbar-fn/src from a kernel source
# tree (or Ubuntu's linux-source tarball) plus applespi-separate-fn-device.patch.
# Runs without root and changes nothing outside touchbar-fn/src.
#
# Usage: ./prepare-dkms-source.sh <kernel-source-dir | /usr/src/linux-source-X.Y.0.tar.bz2>
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:?usage: $0 <kernel-source-dir | linux-source tarball>}"
OUT="$HERE/src"
KBD=drivers/input/keyboard
FILES=(applespi.c applespi.h applespi_trace.h)

rm -rf "$OUT"
mkdir -p "$OUT/$KBD"

if [ -d "$SRC" ]; then
	for f in "${FILES[@]}"; do cp "$SRC/$KBD/$f" "$OUT/$KBD/"; done
else
	# Ubuntu tarballs have one top-level directory, e.g. linux-source-7.0.0/
	# (head closes the pipe early; tar's SIGPIPE must not trip pipefail)
	top="$( (tar -tf "$SRC" || true) | head -1 | cut -d/ -f1)"
	[ -n "$top" ] || { echo "cannot list $SRC" >&2; exit 1; }
	tar -xf "$SRC" -C "$OUT" --strip-components=1 \
		"${FILES[@]/#/$top/$KBD/}"
fi

(cd "$OUT" && patch -p1 --forward < "$HERE/applespi-separate-fn-device.patch")
mv "$OUT/$KBD/"* "$OUT/"
rm -rf "$OUT/drivers"

# Out-of-tree build: the trace header must be found next to applespi.c, not
# at its in-tree location (the Makefile adds -I$(src)).
sed -i 's#^\#define TRACE_INCLUDE_PATH ../../drivers/input/keyboard$#\#define TRACE_INCLUDE_PATH .#' \
	"$OUT/applespi_trace.h"
grep -q '^#define TRACE_INCLUDE_PATH \.$' "$OUT/applespi_trace.h" ||
	{ echo "applespi_trace.h: TRACE_INCLUDE_PATH not rewritten" >&2; exit 1; }

cp "$HERE/dkms/Makefile" "$HERE/dkms/dkms.conf" "$OUT/"
echo "DKMS source ready in $OUT"
echo "Optional rootless test build: make -C $OUT KVERSION=\$(uname -r)"
