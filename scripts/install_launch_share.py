#!/usr/bin/env python3
"""Make ml/CMakeLists.txt install the rviz/ directory into share/ml.

The vendor installs launch/ but not rviz/, and its ml_viz.py then reaches for
the config with the relative path '../rviz/config.rviz'. That is why the README
tells you to cd into src/ml/launch before launching. Installing rviz/ lets a
launch file resolve the config through get_package_share_directory() instead,
which is what patches/gl5_viz.launch.py does.

Idempotent.
"""
import sys

BLOCK = """
install(
  DIRECTORY rviz
  DESTINATION share/${PROJECT_NAME}
)
"""


def main() -> int:
    path = sys.argv[1]
    with open(path) as fh:
        text = fh.read()
    if "DIRECTORY rviz" in text:
        print(f"install_launch_share: {path} already installs rviz/")
        return 0
    if "ament_package()" not in text:
        print(f"install_launch_share: no ament_package() in {path}", file=sys.stderr)
        return 1
    text = text.replace("ament_package()", BLOCK.strip() + "\n\nament_package()")
    with open(path, "w") as fh:
        fh.write(text)
    print(f"install_launch_share: added rviz/ install rule to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
