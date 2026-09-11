#!/usr/bin/env python3
"""Filled-in version of scan_listener.py.

    ros2 run gl5_subscriber scan_listener_solution

Read scan_listener.py first. The only difference is the body of report().
"""
import math
import struct
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2

TOPIC = "/lidar0/pointcloud"
SPEC_HZ = 40.0
MIN_VALID_RANGE = 0.01


class ScanListener(Node):
    def __init__(self):
        super().__init__("scan_listener")

        qos = QoSProfile(depth=1,
                         reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST)
        self.create_subscription(PointCloud2, TOPIC, self.on_cloud, qos)

        self.latest = None
        self.frames = 0
        self.window_start = time.monotonic()
        self.described = False

        self.create_timer(1.0, self.report)
        self.get_logger().info(f"listening on {TOPIC}")

    def on_cloud(self, msg: PointCloud2):
        self.latest = msg
        self.frames += 1

        if not self.described:
            self.described = True
            fields = ", ".join(f.name for f in msg.fields)
            self.get_logger().info(
                f"layout: height={msg.height} width={msg.width} "
                f"point_step={msg.point_step} fields=[{fields}] "
                f"frame_id={msg.header.frame_id}")

    def report(self):
        now = time.monotonic()
        elapsed = now - self.window_start
        hz = self.frames / elapsed if elapsed > 0 else 0.0
        self.frames = 0
        self.window_start = now

        if self.latest is None:
            self.get_logger().warn(f"no frames on {TOPIC} yet")
            return

        msg = self.latest

        valid = 0
        nearest_range = float("inf")
        nearest_bearing = float("nan")
        max_abs_z = 0.0

        # One unpack per point. 1500 of them once a second costs nothing, and
        # the explicit loop is easier to read than a numpy view when the point
        # is to understand the layout.
        for i in range(msg.width):
            x, y, z = struct.unpack_from("<fff", msg.data, i * msg.point_step)

            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                continue

            rng = math.hypot(x, y)
            if rng < MIN_VALID_RANGE:
                continue

            valid += 1
            max_abs_z = max(max_abs_z, abs(z))

            if rng < nearest_range:
                nearest_range = rng
                nearest_bearing = math.degrees(math.atan2(y, x))

        if valid == 0:
            nearest_range = float("nan")

        self.get_logger().info(
            f"{hz:5.1f} Hz (spec {SPEC_HZ:.0f})   "
            f"{valid:4d}/{msg.width} valid   "
            f"nearest {nearest_range:5.2f} m at {nearest_bearing:7.1f} deg   "
            f"max|z| {max_abs_z:.3f} m")


def main(args=None):
    rclpy.init(args=args)
    node = ScanListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        # No rclpy.shutdown() here. On Humble the SIGINT handler has already
        # shut the context down by this point, and calling shutdown() or
        # try_shutdown() again raises RCLError - so every Ctrl-C would end in
        # a traceback. The interpreter cleans the context up on exit.


if __name__ == "__main__":
    main()
