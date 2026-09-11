#!/usr/bin/env bash
# Brings up the virtual display stack, prints the one screen of context that
# answers most workshop questions, then hands off to the command.
set -euo pipefail

export XVFB_GEOMETRY="${XVFB_GEOMETRY:-1600x900x24}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"

if [ "${START_GUI:-1}" = "1" ]; then
  supervisord -c /etc/supervisor/conf.d/workshop.conf
  for _ in $(seq 1 50); do
    xdpyinfo -display :1 >/dev/null 2>&1 && break
    sleep 0.1
  done
fi

# ROS's setup.bash reads unset variables, so -u has to come off around it.
set +u
# shellcheck source=/dev/null
source /opt/scripts/setup_env.sh
set -u

bold() { printf '\033[1m%s\033[0m\n' "$*"; }

echo
bold "SOSLAB GL5 ROS2 workshop"
if [ "${START_GUI:-1}" = "1" ]; then
  echo "  RViz in a browser  http://localhost:${NOVNC_PORT}/vnc.html?autoconnect=1&resize=remote"
fi
echo "  ROS_DOMAIN_ID      ${ROS_DOMAIN_ID:-unset}"
echo "  RMW                ${RMW_IMPLEMENTATION:-unset}"
if [ -n "${ZENOH_CONFIG_OVERRIDE:-}" ]; then
  echo "  zenoh router       ${ZENOH_CONFIG_OVERRIDE}"
fi
if [ -f "${SOSLAB_WS:-/opt/soslab_ws}/install/setup.bash" ]; then
  echo "  vendor node        prebuilt -- ros2 launch ml gl5_viz.launch.py"
else
  echo "  vendor node        not built -- run buildsdk, or follow the README by hand"
fi
echo
# The single most useful line on the screen. If this says 172.17.x, the
# container is behind Docker's NAT and the GL5 stream will never arrive.
bold "  addresses"
ip -4 -brief addr show | sed 's/^/    /'
echo

exec "$@"
