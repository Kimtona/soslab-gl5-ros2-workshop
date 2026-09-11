#!/usr/bin/env bash
# Start the Zenoh router, unless this container was told not to.
#
# rmw_zenoh_cpp needs a router even for two processes on the SAME machine:
# without one, `ros2 topic list` in one shell cannot see a publisher in another,
# and RViz opens to an empty scene. That failure looks exactly like a broken
# sensor, so the router runs by default rather than being something to remember.
#
# On a LiDAR host with host networking this same process is the team's router,
# which teammates point their viewers at on tcp/7447.
set -euo pipefail

if [ "${START_ROUTER:-1}" = "0" ]; then
  echo "START_ROUTER=0, not starting a Zenoh router"
  exit 0
fi

# shellcheck source=/dev/null
set +u
source /opt/scripts/setup_env.sh
set -u

exec ros2 run rmw_zenoh_cpp rmw_zenohd
