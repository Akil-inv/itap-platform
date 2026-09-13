#!/usr/bin/env python3
"""Rewrites the ELF PT_INTERP path baked into every binary in
pg_bundle/bin/ (built by build_postgres_bundle.sh), so they load via
THAT bundle's own copy of musl's dynamic loader
(pg_bundle/lib/ld-musl-x86_64.so.1) rather than the placeholder path
baked in at build time, or a path that only existed on the machine
that built them.

Why this is needed at all: the ELF interpreter is a real, absolute
path baked in at link time — there is no `$ORIGIN`-relative or
PATH-searched form of it (unlike RPATH/RUNPATH, which this bundle
already resolves relative to itself). Every binary in pg_bundle/bin/
was deliberately linked with a long, obviously-fake placeholder path
(`/PGBUNDLEINTERPXXX...`, ~215 bytes reserved) for exactly this: swap
it, in place, for wherever this bundle actually landed.

Run this once, right after extracting/moving pg_bundle/ to wherever it
will actually live — start.sh does this automatically (and is a no-op
if already patched, so re-running by hand is always safe):

    python3 patch_interpreter.py            # run from inside pg_bundle/
    python3 postgres_service/patch_interpreter.py   # or from here, if
                                                      # pg_bundle/ is a
                                                      # sibling directory

Pure Python, no dependencies (works with whatever python3 the target
box already has) and no `patchelf` binary required — the ELF program
header is parsed by hand and the interpreter string is overwritten in
place, padded with NUL bytes, which is safe precisely because the
reserved space is generously oversized relative to any realistic real
path.
"""
from __future__ import annotations

import os
import struct
import sys

PLACEHOLDER_PREFIX = b"/PGBUNDLEINTERP"


def patch_interpreter(path: str, real_interp: bytes) -> bool:
    with open(path, "r+b") as f:
        data = bytearray(f.read())
        if data[:4] != b"\x7fELF":
            return False
        if data[4] != 2:  # not 64-bit
            return False
        e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
        e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
        e_phnum = struct.unpack_from("<H", data, 0x38)[0]

        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from("<I", data, off)[0]
            if p_type != 3:  # PT_INTERP
                continue
            p_offset, p_filesz = struct.unpack_from("<QQ", data, off + 8)
            current = bytes(data[p_offset : p_offset + p_filesz])
            if not current.startswith(PLACEHOLDER_PREFIX):
                return False  # already patched, or not our build
            if len(real_interp) + 1 > p_filesz:
                raise SystemExit(
                    f"{path}: real interpreter path is {len(real_interp)} bytes, "
                    f"but only {p_filesz} bytes are reserved. This bundle's "
                    f"placeholder wasn't built long enough for this install path."
                )
            new_value = real_interp + b"\x00" * (p_filesz - len(real_interp))
            data[p_offset : p_offset + p_filesz] = new_value
            f.seek(0)
            f.write(data)
            f.truncate()
            return True
    return False


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    # Works whether this script is run from inside pg_bundle/ itself
    # (bin/ is a direct sibling) or from apps/postgres_service/ (its
    # tracked source location, where pg_bundle/ is a subdirectory).
    bundle_dir = here if os.path.isdir(os.path.join(here, "bin")) else os.path.join(here, "pg_bundle")
    real_bin = os.path.join(bundle_dir, "bin")
    loader = os.path.join(bundle_dir, "lib", "ld-musl-x86_64.so.1").encode()

    patched = 0
    for name in sorted(os.listdir(real_bin)):
        full = os.path.join(real_bin, name)
        if not os.path.isfile(full):
            continue
        if patch_interpreter(full, loader):
            patched += 1
    print(f"Patched {patched} binaries to use interpreter: {loader.decode()}")


if __name__ == "__main__":
    sys.exit(main())
