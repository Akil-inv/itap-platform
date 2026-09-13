#!/usr/bin/env bash
# Builds pg_bundle/ — a fully self-contained, relocatable Postgres for
# linux x86_64, needing NO system-installed database, NO glibc version
# match, and NO package install on the target machine: extract the tar,
# run pg_bundle/patch_interpreter.py once, then start.sh works.
#
# Why musl, statically-ish: the target CML runtime's OS/glibc is
# unknown and can't be assumed to match whatever built this (see
# postgres_service/README.md's "Getting real Postgres binaries onto
# your CML box"). Linking against musl instead of glibc, and shipping
# musl's own tiny runtime loader (lib/ld-musl-x86_64.so.1) alongside
# the binaries, removes the glibc-version-matching problem entirely —
# these binaries depend on nothing from the target system but the
# Linux kernel's syscall ABI, which is stable across any remotely
# modern distro.
#
# Not a "static binary" in the classic sense: PostgreSQL's own
# extension loading (dict_snowball, plpgsql — both required just to
# run initdb's default bootstrap) needs dlopen() at runtime, which a
# fully static binary cannot do at all. So these are dynamically
# linked, just against a bundled musl instead of the target's glibc.
#
# The one thing that CAN'T be made purely relative is the ELF
# interpreter path (unlike RPATH, the kernel requires PT_INTERP to be
# a real absolute path — no $ORIGIN, no PATH search). The fix:
# link every binary with a long, obviously-fake placeholder interpreter
# path (200+ bytes reserved) instead of a real one, then
# patch_interpreter.py rewrites it in place, at first use, to wherever
# this bundle actually landed on the target machine.
#
# Run this on a machine with: apt (Ubuntu/Debian), musl-tools, and
# outbound access to your OS's own package mirror (not arbitrary
# internet — this fetches Postgres source via `apt-get source`, not a
# separate download). Produces pg_bundle/ next to this script — commit
# it on the offline-deps branch (or your equivalent binary-artifacts
# branch), same convention as offline_deploy/wheelhouse: it doesn't
# belong on a branch that's meant to stay source-only.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$HERE/pg_bundle"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "== Installing build dependencies =="
apt-get update -qq
apt-get install -y --no-install-recommends musl-tools musl-dev dpkg-dev >/dev/null

# apt-get source needs a deb-src line; add one pointed at the same
# mirror apt itself already uses, if one isn't configured.
if ! apt-get source postgresql-16 --print-uris >/dev/null 2>&1; then
  MIRROR=$(grep -rhoP '(?<=URIs: )\S+' /etc/apt/sources.list.d/*.sources 2>/dev/null | head -1)
  MIRROR="${MIRROR:-http://archive.ubuntu.com/ubuntu/}"
  cat >> /etc/apt/sources.list.d/pg-bundle-build-deb-src.list <<-EOF
	deb-src $MIRROR $(lsb_release -cs) main universe restricted multiverse
	EOF
  apt-get update -qq
fi

echo "== Fetching PostgreSQL source =="
cd "$WORK_DIR"
apt-get source postgresql-16
SRC_DIR="$(find "$WORK_DIR" -maxdepth 1 -type d -name 'postgresql-16-*')"
apt-get build-dep -y postgresql-16 >/dev/null

echo "== Configuring (musl, minimal features — none of these need"
echo "   system libs beyond libc, keeping the bundle dependency-free) =="
cd "$SRC_DIR"
PREFIX="$WORK_DIR/install"
CC=musl-gcc ./configure \
  --prefix="$PREFIX" \
  --without-icu --without-openssl --without-ldap --without-gssapi \
  --without-readline --without-zlib --without-libxml --without-libxslt \
  --without-selinux --without-systemd --disable-nls --without-lz4 --without-zstd

# Reserve 215 bytes for the interpreter path (see module docstring
# above) — comfortably more than any realistic deployment path, and
# patch_interpreter.py refuses to patch (rather than silently
# truncate) if a real path somehow doesn't fit.
PLACEHOLDER="/PGBUNDLEINTERP$(printf 'X%.0s' $(seq 1 200))"
echo "LDFLAGS += -Wl,--dynamic-linker=$PLACEHOLDER" >> src/Makefile.global

echo "== Building (pg_upgrade is expected to fail — needs linux/fs.h,"
echo "   which musl doesn't ship, and nothing here needs pg_upgrade) =="
make -k -j"$(nproc)"

echo "== Relinking zic with a working interpreter =="
echo "   (a BUILD-time-only tool that must actually run during install"
echo "   to generate timezone data — never shipped in pg_bundle/bin) =="
sed -i 's|^LDFLAGS += -Wl,--dynamic-linker=/PGBUNDLEINTERP|#&|' src/Makefile.global
make -C src/timezone zic
sed -i 's|^#\(LDFLAGS += -Wl,--dynamic-linker=/PGBUNDLEINTERP\)|\1|' src/Makefile.global

echo "== Installing =="
for d in src/backend src/bin/initdb src/bin/pg_ctl src/bin/psql src/bin/pg_config \
         src/bin/pg_controldata src/bin/pg_resetwal src/bin/pg_waldump src/bin/pg_checksums \
         src/bin/pg_test_fsync src/bin/pg_test_timing src/bin/pg_archivecleanup \
         src/bin/pg_amcheck src/bin/pg_rewind src/bin/pg_verifybackup src/bin/pg_basebackup \
         src/bin/pg_dump src/bin/scripts src/bin/pgbench src/backend/snowball \
         src/pl/plpgsql/src src/interfaces/libpq; do
  make -C "$d" install
done

# Debian's packaging patches (applied automatically by `apt-get
# source`) hardcode loadable-module install paths to a fixed
# multi-version system location regardless of --prefix, for these two
# specifically — everything else respects --prefix correctly.
DEB_MODULE_DIR="/usr/lib/postgresql/16/lib"
cp "$DEB_MODULE_DIR/dict_snowball.so" "$PREFIX/lib/"
cp "$DEB_MODULE_DIR/plpgsql.so" "$PREFIX/lib/"

echo "== Trimming and finalizing the bundle =="
rm -rf "$PREFIX/include" "$PREFIX/lib/pkgconfig" "$PREFIX/lib/libpq.a"
strip "$PREFIX"/bin/* "$PREFIX"/lib/*.so* 2>/dev/null || true
cp /lib/ld-musl-x86_64.so.1 "$PREFIX/lib/ld-musl-x86_64.so.1"

rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"
cp -r "$PREFIX"/* "$BUNDLE_DIR/"
cp "$HERE/patch_interpreter.py" "$BUNDLE_DIR/"

echo "== Done =="
echo "Bundle: $BUNDLE_DIR ($(du -sh "$BUNDLE_DIR" | cut -f1))"
echo "Next: on the TARGET machine, after extracting, run once:"
echo "    python3 $BUNDLE_DIR/patch_interpreter.py"
