#!/usr/bin/env python3
"""Drop the unused heavy dependencies from the vendor's ml/CMakeLists.txt.

ml_node.cpp includes only rclcpp, sensor_msgs and the SDK's Lidar.h. The
find_package() calls for cv_bridge, OpenCV, Boost and PCL are inherited from
the ML-X example and link nothing that is actually referenced. They are also
absent from package.xml, so `rosdep install` never provides them -- which is
the error most people hit first when they follow the vendor README.

Removing them cuts roughly 1.5-2 GB from the image.

Idempotent: running it twice is a no-op.
"""
import re
import sys

DROP_PACKAGES = ("cv_bridge", "OpenCV", "Boost", "PCL")
DROP_VARS = ("PCL_LIBRARIES", "Boost_LIBRARIES", "OpenCV_LIBS",
             "PCL_INCLUDE_DIRS", "Boost_INCLUDE_DIRS")

FIND_PACKAGE = re.compile(r"^\s*find_package\(\s*(\w+)")
LINK_DIRS_BLOCK = re.compile(r"^\s*link_directories\([^)]*PCL_LIBRARY_DIRS[^)]*\)\s*$",
                             re.MULTILINE | re.DOTALL)
AMENT_DEPS_OPEN = re.compile(r"^\s*ament_target_dependencies\(")


def slim(text: str) -> str:
    text = LINK_DIRS_BLOCK.sub("", text)

    out = []
    in_ament_deps = False
    for line in text.splitlines(keepends=True):
        m = FIND_PACKAGE.match(line)
        if m and m.group(1) in DROP_PACKAGES:
            continue
        if any(f"${{{v}}}" in line for v in DROP_VARS):
            continue
        if AMENT_DEPS_OPEN.match(line):
            in_ament_deps = True
        elif in_ament_deps:
            if line.strip() == "cv_bridge":
                continue
            if ")" in line:
                in_ament_deps = False
        out.append(line)

    return re.sub(r"\n{3,}", "\n\n", "".join(out))


def main() -> int:
    path = sys.argv[1]
    with open(path) as fh:
        original = fh.read()
    slimmed = slim(original)
    if slimmed == original:
        print(f"slim_cmakelists: {path} already slim")
        return 0
    with open(path, "w") as fh:
        fh.write(slimmed)
    print(f"slim_cmakelists: {path} -- "
          f"{len(original.splitlines()) - len(slimmed.splitlines())} lines removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
