#!/usr/bin/env python3
"""Let the SDK receive the GL5 stream through a NAT.

The vendor's UDPNetlink connect()s its UDP socket to the sensor:

    udpSocket->bind(localEndpoint);
    udpSocket->connect(serverEndpoint);

A connected UDP socket makes the kernel drop every datagram whose source is not
exactly lidarIP:lidarPort. That is fine on a machine that owns the sensor's
wire, and fatal anywhere the packets arrive translated - which is every Docker
Desktop port publish, where the container sees the gateway as the source.

This rewrites the socket to the unconnected form: keep the bind, remember the
sensor endpoint, and send with send_to(). Receiving is unchanged; recv() on an
unconnected UDP socket is well defined and asio's async_receive maps to it.

Nothing is lost on a host that does own the wire. The datagrams still come from
the sensor, they are just no longer filtered by the kernel on the way in.

Three edits across two files:
  Netlink.h    add an endpoint member to UDPNetlink
  Netlink.cpp  assign the member instead of a local, drop connect(), send_to()

Idempotent.
"""
import pathlib
import sys

NETLINK_H = "soslab_api/internal/Netlink/include/Netlink.h"
NETLINK_CPP = "soslab_api/internal/Netlink/src/Netlink.cpp"

# Each entry is (description, exact text to find, replacement). Exact strings
# rather than regexes: the SDK is pinned by SHA, so a miss means the pin moved
# and a human should look at it.
EDITS_H = [
    (
        "UDPNetlink endpoint member",
        "\t\tvoid asycReceiver(const std::error_code& errorCode, std::size_t bytesReceived);\n"
        "\t\tstd::unique_ptr<asio::ip::udp::socket> udpSocket;\n"
        "\t};\n"
        "\n"
        "\tclass SerialNetlink : public Netlink",
        "\t\tvoid asycReceiver(const std::error_code& errorCode, std::size_t bytesReceived);\n"
        "\t\tstd::unique_ptr<asio::ip::udp::socket> udpSocket;\n"
        "\t\t// Kept because the socket is no longer connect()ed; see\n"
        "\t\t// scripts/patch_sdk_docker_udp.py.\n"
        "\t\tasio::ip::udp::endpoint serverEndpoint;\n"
        "\t};\n"
        "\n"
        "\tclass SerialNetlink : public Netlink",
    ),
]

EDITS_CPP = [
    (
        "assign serverEndpoint member",
        "\tasio::ip::udp::endpoint serverEndpoint = asio::ip::udp::endpoint("
        "asio::ip::address::from_string(udpInfo.lidarIP), udpInfo.lidarPort);",
        "\tserverEndpoint = asio::ip::udp::endpoint("
        "asio::ip::address::from_string(udpInfo.lidarIP), udpInfo.lidarPort);",
    ),
    (
        "drop connect()",
        "\t\t// IF UDP Send is required, connect() is more effective\n"
        "\t\tudpSocket->connect(serverEndpoint);\n",
        "\t\t// Deliberately not connect()ed, so datagrams that arrive with a\n"
        "\t\t// translated source address are not dropped by the kernel.\n",
    ),
    (
        "send_to instead of send",
        "\t\t\tstd::size_t bytesSent = udpSocket->send(asio::buffer(msg));",
        "\t\t\tstd::size_t bytesSent = udpSocket->send_to(asio::buffer(msg), serverEndpoint);",
    ),
]


def apply(path: pathlib.Path, edits, label: str) -> int:
    if not path.is_file():
        print(f"patch_sdk_docker_udp: {path} not found", file=sys.stderr)
        return 1

    text = path.read_text()
    changed = 0

    for description, old, new in edits:
        if new in text:
            continue
        if old not in text:
            print(f"patch_sdk_docker_udp: {label}: cannot find '{description}'. "
                  f"The SDK source has moved; patch it by hand.", file=sys.stderr)
            return 1
        if text.count(old) != 1:
            print(f"patch_sdk_docker_udp: {label}: '{description}' matches "
                  f"{text.count(old)} times, expected 1.", file=sys.stderr)
            return 1
        text = text.replace(old, new)
        changed += 1

    if changed:
        path.write_text(text)
        print(f"patch_sdk_docker_udp: {label}: applied {changed} edit(s)")
    else:
        print(f"patch_sdk_docker_udp: {label}: already patched")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <sdk-root>", file=sys.stderr)
        return 2

    root = pathlib.Path(sys.argv[1])
    return (apply(root / NETLINK_H, EDITS_H, "Netlink.h")
            or apply(root / NETLINK_CPP, EDITS_CPP, "Netlink.cpp"))


if __name__ == "__main__":
    sys.exit(main())
