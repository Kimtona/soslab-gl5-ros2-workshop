#!/usr/bin/env python3
"""Workshop exercise: subscribe to the GL5 cloud and say what is in it.

Run it as-is first. It already receives messages and reports the rate, so you
can confirm data is flowing before you write anything. Then fill in the three
TODOs so it also describes the contents of a frame.

    ros2 run gl5_subscriber scan_listener

The answers are in scan_listener_solution.py. Look after you have tried.

What the message looks like (ml_node.cpp builds it this way, and fake_gl5.py
copies it exactly):

    height      1          one row - the GL5 is a 2D scanner
    width       1500       points per frame
    point_step  16         bytes per point
    fields      x  FLOAT32 at offset 0     metres
                y  FLOAT32 at offset 4     metres
                z  FLOAT32 at offset 8     always 0.0
                rgb UINT32 at offset 12    greyscale from intensity
    frame_id    "map"

So point i lives at msg.data[i * 16 : i * 16 + 16], and struct.unpack_from
reads it: '<fff' gives you x, y, z at the start of that slice.
"""
import math
import struct
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2

TOPIC = "/lidar0/pointcloud"
SPEC_HZ = 40.0          # GL5 datasheet frame rate
MIN_VALID_RANGE = 0.01  # metres; anything closer is a dropped return, not a wall


class ScanListener(Node):
    def __init__(self):
        super().__init__("scan_listener")

        # Best Effort matches the vendor node's Reliable publisher and is the
        # right choice for a 40 Hz stream: a late frame is worth less than the
        # next one.
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

        # Print the layout once, so you can check it against the docstring.
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

        # TODO 1. Walk the points and collect the ranges.
        #   For each point i in range(msg.width):
        #     x, y, z = struct.unpack_from('<fff', msg.data, i * msg.point_step)
        #   Keep a point only if math.isfinite of all three and the range
        #   math.hypot(x, y) is at least MIN_VALID_RANGE.
        valid = 0

        # TODO 2. Find the nearest valid point: its range in metres and its
        #   bearing in degrees, which is math.degrees(math.atan2(y, x)).
        nearest_range = float("nan")
        nearest_bearing = float("nan")

        # TODO 3. Track the largest abs(z) you saw. If the GL5 really is a 2D
        #   scanner this stays at 0.0, and that is the point of measuring it.
        max_abs_z = float("nan")

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
