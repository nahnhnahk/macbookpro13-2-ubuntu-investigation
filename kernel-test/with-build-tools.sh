#!/bin/bash
set -euo pipefail
TASK_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TOOL_ROOT="$TASK_ROOT/build-tools"
export PATH="$TOOL_ROOT/usr/bin:$PATH"
export LD_LIBRARY_PATH="$TOOL_ROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export BISON_PKGDATADIR="$TOOL_ROOT/usr/share/bison"
export M4="$TOOL_ROOT/usr/bin/m4"
export PKG_CONFIG_SYSROOT_DIR="$TOOL_ROOT"
export PKG_CONFIG_LIBDIR="$TOOL_ROOT/usr/lib/x86_64-linux-gnu/pkgconfig:$TOOL_ROOT/usr/share/pkgconfig"
export HOSTCFLAGS="-I$TOOL_ROOT/usr/include -I$TOOL_ROOT/usr/include/x86_64-linux-gnu"
export HOSTLDFLAGS="-L$TOOL_ROOT/usr/lib/x86_64-linux-gnu -Wl,-rpath,$TOOL_ROOT/usr/lib/x86_64-linux-gnu"
export KBUILD_BUILD_USER=builder
export KBUILD_BUILD_HOST=mbp132-test
export KBUILD_BUILD_VERSION=1
exec "$@"
