#!/usr/bin/env bash
# Build the SOSLAB SDK and the ROS2 `ml` example, following the vendor README.
#
# Participants run this from inside the :dev image after they have tried the
# manual steps. The image build runs it with --slim for the :prebuilt target.
#
#   --slim          drop the unused cv_bridge/OpenCV/PCL/Boost dependencies from
#                   the example CMakeLists before building (saves ~1.5-2 GB)
#   --no-symlink    plain colcon install instead of --symlink-install. Required
#                   for the image build, where the install tree is copied into a
#                   stage that does not carry the SDK source any more, so
#                   symlinks back into it would dangle.
set -euo pipefail

SDK_DIR="${SOSLAB_SDK_DIR:-/opt/soslab_sdk}"
WS_DIR="${SOSLAB_WS:-/opt/soslab_ws}"
SLIM=0
SYMLINK=1
JOBS="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"

for arg in "$@"; do
  case "$arg" in
    --slim) SLIM=1 ;;
    --no-symlink) SYMLINK=0 ;;
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "1/5  Building the SDK  ($SDK_DIR)"
# The root CMakeLists picks the library suffix from pointer size alone, so this
# produces libLidar_x64_release.so on arm64 too -- which is the exact filename
# the example CMakeLists hardcodes. Convenient, but never validated by SOSLAB.
cmake -S "$SDK_DIR" -B "$SDK_DIR/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$SDK_DIR/build" -j "$JOBS"
ls -l "$SDK_DIR/_archive_/lib/"

say "2/5  Copying headers and libraries into the example  (copy_api2example.sh)"
# The script is written against ${PWD}, so it only works from the SDK root.
cd "$SDK_DIR"
chmod +x ./copy_api2example.sh
./copy_api2example.sh

say "3/5  Building soslab_ethinfo"
# Reads the sensor's flashed Ethernet config. The GL5 streams to the pcIp:pcPort
# stored on the device, so you need this to know what to bind to.
cmake -S "$SDK_DIR/soslab_ethinfo" -B "$SDK_DIR/soslab_ethinfo/build" \
      -DCMAKE_BUILD_TYPE=Release -DSOSLAB_ARCHIVE="$SDK_DIR/_archive_"
cmake --build "$SDK_DIR/soslab_ethinfo/build" -j "$JOBS"
install -D -m 0755 "$SDK_DIR/soslab_ethinfo/build/soslab_ethinfo" \
                   "$SDK_DIR/_archive_/bin/soslab_ethinfo"
sudo ln -sf "$SDK_DIR/_archive_/bin/soslab_ethinfo" /usr/local/bin/soslab_ethinfo

if [ "$SLIM" = "1" ]; then
  say "4/5  Slimming the example CMakeLists"
  # ml_node.cpp includes only rclcpp, sensor_msgs and Lidar.h. The find_package
  # calls for cv_bridge/OpenCV/PCL/Boost are dead weight, and none of them are
  # declared in package.xml, so rosdep would never install them anyway.
  python3 /opt/scripts/slim_cmakelists.py \
    "$SDK_DIR/examples/ros2_ml/src/ml/CMakeLists.txt"
else
  say "4/5  Keeping the vendor CMakeLists as-is"
fi

say "5/5  colcon build"
mkdir -p "$WS_DIR/src"
# Link rather than copy so participants can edit the vendor source in place.
ln -sfn "$SDK_DIR/examples/ros2_ml/src/ml" "$WS_DIR/src/ml"
# Ship a launch file that works outside src/ml/launch and defaults to GL5.
install -D -m 0644 /opt/patches/gl5_viz.launch.py \
                   "$SDK_DIR/examples/ros2_ml/src/ml/launch/gl5_viz.launch.py"
install -D -m 0644 /opt/patches/gl5.rviz \
                   "$SDK_DIR/examples/ros2_ml/src/ml/rviz/gl5.rviz"
python3 /opt/scripts/install_launch_share.py \
    "$SDK_DIR/examples/ros2_ml/src/ml/CMakeLists.txt"

# ROS's setup.bash reads unset variables, so -u has to come off around it.
set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u
cd "$WS_DIR"
colcon_args=(--cmake-args -DCMAKE_BUILD_TYPE=Release)
if [ "$SYMLINK" = "1" ]; then
  colcon_args=(--symlink-install "${colcon_args[@]}")
fi
colcon build "${colcon_args[@]}"

say "Done.  source $WS_DIR/install/setup.bash"
