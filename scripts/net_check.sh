#!/usr/bin/env bash
# Diagnose why the GL5 stream is not arriving, in the order the failures happen.
set -uo pipefail

LIDAR_IP="${1:-${SOSLAB_DEVICE_IP:-192.168.1.10}}"
LIDAR_PORT="${2:-${SOSLAB_DEVICE_PORT:-2000}}"

ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; }
note() { printf '        %s\n' "$*"; }

echo
echo "checking against ${LIDAR_IP}:${LIDAR_PORT}"
echo

echo "1. container addresses"
ip -4 -brief addr show | sed 's/^/    /'
if ip -4 addr show | grep -qE 'inet 172\.(1[7-9]|2[0-9]|3[01])\.'; then
  bad "on a Docker bridge network"
  note "The SDK connect()s its UDP socket to the sensor, so datagrams that"
  note "arrive translated through NAT are dropped by the kernel. This"
  note "container needs host networking on a real Linux host."
else
  ok "not obviously behind a Docker bridge"
fi
echo

echo "2. route to the sensor"
if ip route get "$LIDAR_IP" >/dev/null 2>&1; then
  ok "$(ip route get "$LIDAR_IP" | head -1)"
else
  bad "no route to $LIDAR_IP"
  note "Give the host NIC an address on the sensor's subnet."
fi
echo

echo "3. icmp"
if ping -c 2 -W 2 "$LIDAR_IP" >/dev/null 2>&1; then
  ok "sensor answers ping"
else
  bad "no ping response"
  note "Not fatal on its own, some units ignore icmp, but usually means"
  note "cabling, a wrong subnet, or a firewall."
fi
echo

echo "4. receive buffer"
note "net.core.rmem_default = $(cat /proc/sys/net/core/rmem_default)"
note "net.core.rmem_max     = $(cat /proc/sys/net/core/rmem_max)"
if [ "$(cat /proc/sys/net/core/rmem_default)" -lt 1048576 ]; then
  bad "rmem_default is small"
  note "The SDK never calls setsockopt(SO_RCVBUF), so the socket takes this"
  note "value verbatim. Raising only rmem_max changes nothing. Set it on the"
  note "host: sudo sysctl -w net.core.rmem_default=8388608"
else
  ok "rmem_default looks adequate"
fi
echo

echo "5. udp errors so far"
netstat -su 2>/dev/null | grep -iE 'receive buffer errors|packet receive errors' | sed 's/^/    /' \
  || note "netstat unavailable"
echo

echo "next: watch the wire while the node runs"
echo "    sudo tcpdump -ni any -vv 'udp and host ${LIDAR_IP}'"
echo "  The destination port of the stream packets is the value you must pass"
echo "  as ip_port_pc. Read it from the sensor directly with:"
echo "    soslab_ethinfo --ip ${LIDAR_IP} --port ${LIDAR_PORT}"
echo
