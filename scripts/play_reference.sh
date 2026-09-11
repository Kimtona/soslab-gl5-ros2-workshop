#!/usr/bin/env bash
# Reference station: replay a recorded GL5 scan on a loop, forever.
#
# The five available sensors go to the five teams, so the reference station gets
# none - and it doesn't need one. A GL5 produces about 958 KB/s of topic, so a
# few minutes of recording is a small file that plays back indistinguishably
# from a live sensor for viewing purposes.
#
# This is the safety net: whatever happens at the team stations, everyone can
# open a browser and see a live scan.
set -euo pipefail

BAG="${REFERENCE_BAG:-/opt/reference_bag}"
RATE="${REFERENCE_RATE:-1.0}"

if [ ! -e "$BAG" ] && [ ! -d "$BAG" ]; then
  cat >&2 <<EOF
No reference bag at $BAG.

Record one during prep, with a GL5 attached to any working host:

    ros2 bag record -o reference_bag /lidar0/pointcloud
    # let it run five minutes, then Ctrl-C

Then mount it into this container. docker-compose.yaml expects it at
./reference_bag on the host.

To run the reference station without a recording at all, use the synthetic
publisher instead:

    docker compose --profile reference run --rm reference fakegl5
EOF
  exit 1
fi

# shellcheck source=/dev/null
set +u
source /opt/scripts/setup_env.sh
set -u

echo "replaying $BAG on a loop at ${RATE}x"
exec ros2 bag play "$BAG" --loop --rate "$RATE"
