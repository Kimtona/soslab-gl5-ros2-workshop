#!/usr/bin/env bash
# Wrapper so VNC_PASSWORD can switch x11vnc between open and password-protected.
# supervisord has no conditional arguments, hence the script.
set -euo pipefail

args=(-display :1 -forever -shared -rfbport 5901 -noxdamage -quiet)

if [ -n "${VNC_PASSWORD:-}" ]; then
  # x11vnc wants a password file, not an argument; storepasswd writes one.
  pwfile=/tmp/.x11vnc_pw
  x11vnc -storepasswd "$VNC_PASSWORD" "$pwfile" >/dev/null 2>&1
  chmod 600 "$pwfile"
  args+=(-rfbauth "$pwfile")
else
  args+=(-nopw)
fi

exec x11vnc "${args[@]}"
