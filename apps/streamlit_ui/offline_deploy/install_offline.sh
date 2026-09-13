#!/usr/bin/env bash
# Air-gapped install for the ITAP Streamlit app — no PyPI/internet access
# needed. Run this from inside the extracted offline bundle directory,
# with the same Python that will actually run `streamlit run app.py`
# (e.g. inside your CML Runtime's terminal, or a local Python for a
# dry-run test — see this directory's README for the difference).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Wheels are platform- AND Python-version-specific (a manylinux wheel
# won't install on macOS, an arm64 wheel won't install on Intel, etc.),
# so the wheelhouse subdirectory is keyed by both — see this directory's
# README for the naming convention and which combos have been built.
OS_ARCH=$(python3 - <<'PY'
import platform
system = platform.system()
machine = platform.machine().lower()
if system == "Linux":
    os_name = "linux"
elif system == "Darwin":
    os_name = "macos"
else:
    os_name = system.lower()
if machine in ("x86_64", "amd64"):
    arch = "x86_64"
elif machine in ("arm64", "aarch64"):
    arch = "arm64"
else:
    arch = machine
print(f"{os_name}_{arch}")
PY
)
PYVER=$(python3 -c "import sys; print(f'py{sys.version_info.major}{sys.version_info.minor}')")
KEY="${OS_ARCH}-${PYVER}"

if [ ! -d "$HERE/wheelhouse/$KEY" ]; then
  echo "No prebuilt wheels for $KEY in this bundle." >&2
  echo "Available: $(ls "$HERE/wheelhouse" | grep -v '^local$' | tr '\n' ' ')" >&2
  echo "Re-run build_offline_bundle.sh (linux) for this combo on a machine with internet access, then re-copy the bundle." >&2
  exit 1
fi

echo "Installing third-party packages for $KEY ..."
python3 -m pip install --no-index \
  --find-links "$HERE/wheelhouse/$KEY" \
  -r "$HERE/requirements.txt"

echo "Installing ITAP's own capability packages ..."
python3 -m pip install --no-index \
  --find-links "$HERE/wheelhouse/local" \
  party-identity assignment rbac-scope rotation_plan catalog

echo "Done. Verify with: python3 -c 'import streamlit, sqlalchemy, pandas, openpyxl, psycopg2, party_identity, assignment, rbac_scope, rotation_plan, catalog; print(\"all imports OK\")'"
