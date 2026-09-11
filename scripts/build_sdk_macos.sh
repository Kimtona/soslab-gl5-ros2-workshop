#!/usr/bin/env bash
# Build `soslab_ethinfo` natively on macOS - no VM, no Docker, no ROS.
#
# Why this exists: the GL5 carries commands and the point cloud on a single UDP
# socket that the SDK binds locally and then connect()s to the sensor, so the
# kernel drops anything not sourced from the sensor itself. That makes this tool
# a direct test of whether a given Mac can talk to a GL5 at all - if it reads the
# sensor's config, the wire and the addressing are right, and any container or VM
# work built on top has a foundation. It also reports the flashed pcPort, which
# is the value the vendor launch file gets wrong by defaulting to 0.
#
# The SDK needs one one-line fix to compile here; see scripts/patch_sdk_macos.py.
set -euo pipefail

SDK_REF="${SDK_REF:-9a1f4c46f0842a8a23e62cab7e8f39da9c09f9ef}"   # v1.1.0
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_DIR="${SDK_DIR:-$REPO_DIR/.sdk}"
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

[ "$(uname -s)" = "Darwin" ] || { echo "this script is for macOS; on Linux use build_sdk.sh" >&2; exit 1; }
command -v cmake >/dev/null || { echo "cmake not found. brew install cmake" >&2; exit 1; }

say "1/4  Fetching SDK ${SDK_REF:0:7}"
if [ ! -d "$SDK_DIR" ]; then
  mkdir -p "$SDK_DIR"
  curl -fsSL "https://github.com/SOSLAB-github/SOSLAB_SDK/archive/${SDK_REF}.tar.gz" \
    | tar xz --strip-components=1 -C "$SDK_DIR"
else
  echo "already present at $SDK_DIR"
fi

say "2/4  Patching for macOS"
python3 "$REPO_DIR/scripts/patch_sdk_macos.py" "$SDK_DIR"

say "3/4  Building the SDK"
# Outputs land in _archive_ via a POST_BUILD copy, not via `make install`.
cmake -S "$SDK_DIR" -B "$SDK_DIR/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$SDK_DIR/build" -j "$JOBS"
ls -l "$SDK_DIR/_archive_/lib/"

say "4/4  Building soslab_ethinfo"
cmake -S "$REPO_DIR/tools/soslab_ethinfo" -B "$SDK_DIR/ethinfo-build" \
      -DCMAKE_BUILD_TYPE=Release -DSOSLAB_ARCHIVE="$SDK_DIR/_archive_"
cmake --build "$SDK_DIR/ethinfo-build" -j "$JOBS"

BIN="$SDK_DIR/ethinfo-build/soslab_ethinfo"
say "Done.  $BIN"
echo
echo "Plug the GL5 into a USB-C Ethernet adapter, give that interface an address"
echo "on the sensor's subnet, then read the sensor:"
echo
echo "    networksetup -listallhardwareports          # find the adapter, e.g. en6"
echo "    sudo ipconfig set en6 MANUAL 192.168.1.15 255.255.255.0"
echo "    $BIN --ip 192.168.1.10 --port 2000"
echo
