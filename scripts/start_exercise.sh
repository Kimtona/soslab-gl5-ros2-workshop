#!/usr/bin/env bash
# Drop the subscriber exercise into the participant's own workspace.
#
# The package lives at /opt/exercise in the image, read-only and pristine. This
# copies it to ~/ws/src so it can be edited, and ~/ws is what setup_env.sh
# sources last, so a node built here shadows anything of ours.
set -euo pipefail

SRC="/opt/exercise/gl5_subscriber"
DEST_DIR="${HOME}/ws/src"
DEST="${DEST_DIR}/gl5_subscriber"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }

mkdir -p "$DEST_DIR"

if [ -e "$DEST" ]; then
  echo "gl5_subscriber is already in ${DEST_DIR}; leaving your copy alone."
  echo "To start over:  rm -rf ${DEST} && startex"
else
  cp -r "$SRC" "$DEST"
  echo "copied gl5_subscriber to ${DEST}"
fi

echo
bold "next"
cat <<'TXT'
  1. Start a data source, if nothing is publishing yet:
       fakegl5 &

  2. Build and source:
       cd ~/ws && colcon build --symlink-install --packages-select gl5_subscriber
       sauce

  3. Run it. It works before you edit anything - it reports the rate only:
       ros2 run gl5_subscriber scan_listener

  4. Open ~/ws/src/gl5_subscriber/gl5_subscriber/scan_listener.py and fill in
     the three TODOs. --symlink-install means you do NOT rebuild between edits,
     just restart the node.

  5. Compare with the answer:
       ros2 run gl5_subscriber scan_listener_solution
TXT
echo
