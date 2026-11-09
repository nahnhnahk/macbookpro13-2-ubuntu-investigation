#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Read-only check of the Apple CS8409 speaker driver. Run after every kernel
# install and after rebooting into a new kernel. Changes nothing.
set -u
status=0
echo "== DKMS"
dkms status snd_hda_macbookpro 2>/dev/null || echo "dkms not available"
echo "== Module selected for each installed kernel"
for dir in /lib/modules/*/; do
	k=$(basename "$dir")
	[[ -e $dir/modules.dep ]] || continue
	path=$(modinfo -n -k "$k" snd_hda_codec_cs8409 2>/dev/null || true)
	case $path in
		*/updates/*) verdict="patched (Apple)";;
		"") verdict="NO MODULE";;
		*) verdict="IN-TREE ONLY - speakers will be silent"; status=1;;
	esac
	echo "$k: $verdict${path:+  [$path]}"
done
echo "== Running kernel $(uname -r)"
if journalctl -k -b 0 --no-pager 2>/dev/null | grep -q 'patch_cs8409 NOT FOUND trying APPLE'; then
	echo "Apple CS8409 code path loaded this boot"
else
	echo "Apple code path NOT seen in this boot's kernel log (or journal unreadable)"
	status=1
fi
exit $status
