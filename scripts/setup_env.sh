# Sourced from .bashrc and from the entrypoint. Must stay tolerant of missing
# workspaces: the :dev image has no built workspace until the participant
# builds one.
# shellcheck shell=bash

source "/opt/ros/${ROS_DISTRO:-humble}/setup.bash"

# Prebuilt vendor node, present only in the :prebuilt image.
if [ -f "${SOSLAB_WS:-/opt/soslab_ws}/install/setup.bash" ]; then
  source "${SOSLAB_WS:-/opt/soslab_ws}/install/setup.bash"
fi

# The participant's own workspace wins, so a node they build shadows ours.
if [ -f "$HOME/ws/install/setup.bash" ]; then
  source "$HOME/ws/install/setup.bash"
fi

export RCUTILS_COLORIZED_OUTPUT=1

# buildsdk and netcheck are real commands on PATH; sauce has to stay an alias
# so that sourcing affects the calling shell.
alias sauce='source /opt/scripts/setup_env.sh'
