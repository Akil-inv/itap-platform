#!/usr/bin/env bash
# Rebuilds the offline dependency bundle from scratch, for air-gapped
# CML deployment (see README.md in this directory). Builds for
# **linux x86_64** only — the assumed CML Runtime target; for a macOS
# dry-run bundle (or any other platform), swap the manylinux --platform
# flags below for the target platform's own tags (see README.md's
# "Adding another platform/Python combo" section) and change the
# `linux_x86_64-py...` prefix on DEST to match, since install_offline.sh
# looks wheels up by "<os>_<arch>-py<version>". Run this on any machine
# WITH internet access (this doesn't need to be the air-gapped CML box
# itself) — `pip download` fetches prebuilt manylinux wheels for each
# target Python version without needing that interpreter installed
# locally, so one machine can build for all of them.
#
# Output (wheelhouse/, requirements.txt) is gitignored — it's a build
# artifact, not something to commit; tar it up and transfer it
# out-of-band to the air-gapped box instead (see this directory's
# README.md).
#
# Re-run this whenever apps/streamlit_ui/requirements.txt changes, or to
# add another Python version — edit PYVERSIONS below and re-run.
#
# Usage: ./build_offline_bundle.sh [/path/to/itap-platform]
#   (defaults to this script's own repo checkout if omitted)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-$(cd "$HERE/../../.." && pwd)}"
REQUIREMENTS="$REPO/apps/streamlit_ui/requirements.txt"
PYVERSIONS=(3.9 3.10 3.11 3.12)

if [ ! -f "$REQUIREMENTS" ]; then
  echo "Couldn't find requirements.txt at $REQUIREMENTS" >&2
  echo "Pass the itap-platform repo root explicitly: $0 /path/to/itap-platform" >&2
  exit 1
fi

rm -rf "$HERE/wheelhouse"
mkdir -p "$HERE/wheelhouse/local"

for PYVER in "${PYVERSIONS[@]}"; do
  ABI="cp${PYVER//./}"
  DEST="$HERE/wheelhouse/linux_x86_64-py${PYVER//./}"
  echo "=== Downloading wheels for Python $PYVER ($ABI) ==="
  python3 -m pip download \
    --only-binary=:all: \
    --platform manylinux2014_x86_64 \
    --platform manylinux_2_17_x86_64 \
    --platform manylinux_2_24_x86_64 \
    --platform manylinux_2_27_x86_64 \
    --platform manylinux_2_28_x86_64 \
    --platform linux_x86_64 \
    --python-version "$PYVER" \
    --implementation cp \
    --abi "$ABI" \
    -r "$REQUIREMENTS" \
    -d "$DEST"
done

echo "=== Building ITAP's own capability packages (pure Python, version-independent) ==="
python3 -m pip wheel --no-deps -w "$HERE/wheelhouse/local" \
  "$REPO/capabilities/party_identity" \
  "$REPO/capabilities/assignment" \
  "$REPO/capabilities/rbac_scope" \
  "$REPO/capabilities/rotation_plan" \
  "$REPO/capabilities/catalog"

cp "$REQUIREMENTS" "$HERE/requirements.txt"

echo "Done. Bundle contents:"
du -sh "$HERE/wheelhouse"/*
echo ""
echo "Tar it up with: tar czf itap_offline_bundle.tar.gz -C \"$(dirname "$HERE")\" \"$(basename "$HERE")\""
