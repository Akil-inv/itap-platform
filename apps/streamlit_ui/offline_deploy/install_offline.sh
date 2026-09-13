#!/usr/bin/env bash
# Air-gapped install for the ITAP Streamlit app — no PyPI/internet access
# needed. Run this from inside the extracted offline_bundle/ directory,
# with the same Python that will actually run `streamlit run app.py`
# (e.g. inside your CML Runtime's terminal).
set -euo pipefail

PYVER=$(python3 -c "import sys; print(f'py{sys.version_info.major}{sys.version_info.minor}')")
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$HERE/wheelhouse/$PYVER" ]; then
  echo "No prebuilt wheels for $PYVER in this bundle." >&2
  echo "Available: $(ls "$HERE/wheelhouse" | grep '^py' | tr '\n' ' ')" >&2
  echo "Re-run build_offline_bundle.sh for your Python version on a machine with internet access, then re-copy the bundle." >&2
  exit 1
fi

echo "Installing third-party packages for $PYVER ..."
python3 -m pip install --no-index \
  --find-links "$HERE/wheelhouse/$PYVER" \
  -r "$HERE/requirements.txt"

echo "Installing ITAP's own capability packages ..."
python3 -m pip install --no-index \
  --find-links "$HERE/wheelhouse/local" \
  party-identity assignment rbac-scope rotation_plan catalog

echo "Done. Verify with: python3 -c 'import streamlit, sqlalchemy, pandas, openpyxl, psycopg2, party_identity, assignment, rbac_scope, rotation_plan, catalog; print(\"all imports OK\")'"
