#!/usr/bin/env python3
"""Publish a synthetic GL5 scan, byte-for-byte shaped like the vendor node's.

Lets you exercise the whole viewing path - RViz config, noVNC, zenoh routing,
a teammate's viewer - without a sensor on the desk. Useful for setting up the
day before, and as a fallback for anyone whose hardware will not cooperate.

Matches examples/ros2_ml/src/ml/src/ml_node.cpp exactly: height 1, width 1500,
point_step 16, fields x/y/z as FLOAT32 and rgb as UINT32 at offset 12, frame_id
"map", 40 Hz. The GL5 is a 2D scanner - GL5.cpp sets point.z = 0.0 - so every
point here is planar too.

    ros2 run ... no, just: python3 fake_gl5.py [--topic T] [--rate HZ]
"""
import argparse
import math
import struct

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2, PointField

POINTS = 1500          # GL5.h: numAllPoints
H_FOV_DEG = 270.0      # GL5.h: h_fov_
MAX_RANGE_M = 9.0      # datasheet
POINT_STEP = 16


def intensity_to_rgb(inten: int, max_intensity: int = 3000) -> int:
    """Same mapping as ml_node.cpp's intensity_to_rgb."""
    v = int(inten * 255 / max_intensity)
    v = max(0, min(255, v))
    return (v << 16) | (v << 8) | v


class FakeGL5(Node):
    def __init__(self, topic: str, rate: float):
        super().__init__("fake_gl5")
        # Match the vendor node: depth 1, reliable. A Best Effort subscriber
        # still matches a Reliable publisher.
        qos = QoSProfile(depth=1,
                         reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST)
        self.pub = self.create_publisher(PointCloud2, topic, qos)
        self.angles = [
            math.radians(i * H_FOV_DEG / (POINTS - 1) - (H_FOV_DEG / 2.0 - 90.0))
            for i in range(POINTS)
        ]
        self.tick = 0
        self.create_timer(1.0 / rate, self.publish_scan)
        self.get_logger().info(f"publishing {POINTS} points on {topic} at {rate} Hz")

    def ranges(self):
        """A rectangular room with a moving obstacle, clipped to sensor range."""
        phase = self.tick * 0.05
        out = []
        for a in self.angles:
            # Walls of a 6 x 4 m room, as seen from the middle.
            cos_a, sin_a = math.cos(a), math.sin(a)
            candidates = []
            for half, comp in ((3.0, cos_a), (2.0, sin_a)):
                if abs(comp) > 1e-6:
                    d = half / abs(comp)
                    if d > 0:
                        candidates.append(d)
            r = min(candidates) if candidates else MAX_RANGE_M

            # A person-sized blob orbiting the sensor.
            blob = 1.6 + 0.4 * math.sin(phase)
            if abs(math.sin((a - phase) / 2.0)) < 0.06:
                r = min(r, blob)

            out.append(min(r, MAX_RANGE_M))
        return out

    def publish_scan(self):
        msg = PointCloud2()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"      # ml_node.cpp DEFAULT_FRAME_ID
        msg.height = 1                   # GL5.cpp: frameData.rows = 1
        msg.width = POINTS
        msg.fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name="rgb", offset=12, datatype=PointField.UINT32, count=1),
        ]
        msg.is_bigendian = False
        msg.point_step = POINT_STEP
        msg.row_step = POINT_STEP * POINTS
        msg.is_dense = True

        buf = bytearray(msg.row_step)
        for i, (a, r) in enumerate(zip(self.angles, self.ranges())):
            # Nearer returns come back stronger, so intensity tracks 1/r.
            inten = int(3000 * min(1.0, 1.2 / max(r, 0.2)))
            struct.pack_into(
                "<fffI", buf, i * POINT_STEP,
                r * math.cos(a), r * math.sin(a), 0.0,   # GL5.cpp: z is always 0
                intensity_to_rgb(inten))
        msg.data = bytes(buf)

        self.pub.publish(msg)
        self.tick += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="/lidar0/pointcloud")
    ap.add_argument("--rate", type=float, default=40.0)
    args = ap.parse_args()

    rclpy.init()
    node = FakeGL5(args.topic, args.rate)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
