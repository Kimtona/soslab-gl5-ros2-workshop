#!/usr/bin/env python3
"""Make the SOSLAB SDK compile on macOS.

There is exactly one non-portable construct in the SDK's 32 first-party files:
`#include <malloc.h>` in Netlink.h. macOS has no such header - the equivalents
live in <stdlib.h> and <malloc/malloc.h>. Neither Netlink.h nor Netlink.cpp
calls malloc, calloc, realloc, free, memalign or alloca anywhere, so the
include is dead weight left over from an MSVC habit.

It matters because Netlink.h is pulled in transitively:
    Lidar.cpp -> LidarImpl.h -> LidarRuntime.h -> Netlink.h -> <malloc.h>
so it breaks four translation units across three targets.

Everything else is portable: networking goes through vendored standalone Asio
(which selects kqueue on Darwin), byte order is handled by hand in Endian.h,
and the `if (WIN32)` guards have no Linux-only else branch.

Idempotent.
"""
import pathlib
import re
import sys

NETLINK_H = "soslab_api/internal/Netlink/include/Netlink.h"
MALLOC_INCLUDE = re.compile(r"^[ \t]*#[ \t]*include[ \t]*<malloc\.h>[ \t]*\r?\n", re.MULTILINE)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <sdk-root>", file=sys.stderr)
        return 2

    header = pathlib.Path(sys.argv[1]) / NETLINK_H
    if not header.is_file():
        print(f"patch_sdk_macos: {header} not found", file=sys.stderr)
        return 1

    original = header.read_text()
    patched = MALLOC_INCLUDE.sub("", original)

    if patched == original:
        if "malloc.h" in original:
            print(f"patch_sdk_macos: {header} still mentions malloc.h but the "
                  f"include did not match - check it by hand", file=sys.stderr)
            return 1
        print(f"patch_sdk_macos: {NETLINK_H} already patched")
        return 0

    header.write_text(patched)
    print(f"patch_sdk_macos: removed <malloc.h> from {NETLINK_H}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
