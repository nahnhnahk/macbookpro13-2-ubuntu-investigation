#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# One-off manual install of a locally built, Apple-patched snd-hda-codec-cs8409.ko
# for the running kernel. This is the method validated on 2026-11-08; the DKMS
# setup in docs/AUDIO.md replaces it and survives kernel upgrades.
#
# Usage: sudo ./install-cs8409-apple.sh /path/to/snd-hda-codec-cs8409.ko
# Undo:  sudo rm /lib/modules/$(uname -r)/updates/cirrus/snd-hda-codec-cs8409.ko
#        sudo depmod -a && reboot
set -euo pipefail
KO=${1:?usage: $0 /path/to/snd-hda-codec-cs8409.ko}
KREL=$(modinfo -F vermagic "$KO" | cut -d' ' -f1)
[[ $(uname -r) == "$KREL" ]] || { echo "Module built for $KREL, running $(uname -r)"; exit 1; }
install -D -m 0644 "$KO" "/lib/modules/$KREL/updates/cirrus/snd-hda-codec-cs8409.ko"
depmod -a "$KREL"
echo "Now resolves to: $(modinfo -n -k "$KREL" snd_hda_codec_cs8409)"
echo "Reboot to load it."
