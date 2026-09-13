# Offline dependency bundle (air-gapped CML deployment)

For a CML workspace where `pip install` can't reach PyPI. Prebuilt
wheels for everything `apps/streamlit_ui/requirements.txt` needs
(streamlit, SQLAlchemy, pandas, openpyxl, psycopg2-binary, and their
full transitive dependency trees), for four Python versions (3.9,
3.10, 3.11, 3.12 — covering the common CML ML Runtime versions; the
exact one wasn't confirmed when this was built), plus ITAP's own five
capability packages (`party_identity`, `assignment`, `rbac_scope`,
`rotation_plan`, `catalog`) as version-independent pure-Python wheels.

`psycopg2-binary` was added to `requirements.txt` in the same pass as
this directory — the project's own top-level README documents a
Postgres deployment (`DATABASE_URL=postgresql://...`) but nothing
previously declared the driver SQLAlchemy actually needs to talk to
Postgres; without it, connecting raises `ModuleNotFoundError: No
module named 'psycopg2'` regardless of how the rest of the app is
packaged.

## Building the bundle

Run this on any machine **with internet access** — it does not have to
be the air-gapped box, and it doesn't need Python 3.9/3.10/3.12
actually installed: `pip download` fetches manylinux wheels for a
target Python version straight from PyPI without executing them.

```bash
./build_offline_bundle.sh          # defaults to this repo checkout
# or: ./build_offline_bundle.sh /path/to/itap-platform
```

This writes `wheelhouse/` and a `requirements.txt` copy into this same
directory — both gitignored (build output, not source). Tar the whole
`offline_deploy/` directory and transfer it to the air-gapped box
out-of-band (however files already get into that environment — most of
this bundle is too large to move through a chat upload, which is why
these are build scripts and not a committed tarball).

## Installing on the air-gapped box

```bash
tar xzf itap_offline_bundle.tar.gz   # however you transferred it
bash offline_deploy/install_offline.sh
```

It detects the running Python's version automatically and installs
from the matching `wheelhouse/pyXY/` directory with `pip install
--no-index` — no PyPI access, no compiling. If your Runtime's Python
version isn't one of the four built, it says so and lists what's
available; re-run `build_offline_bundle.sh` for the missing version
(edit `PYVERSIONS` in that script) on a machine with internet, then
re-transfer.

## What still needs confirming with your CML admin/platform team

- **CPU architecture** — this assumes linux x86_64, by far the most
  common CML Runtime architecture. For arm64, substitute
  `--platform manylinux2014_aarch64` (etc.) in
  `build_offline_bundle.sh` and rebuild.
- **Exact Python version** — check with `python3 --version` in a CML
  terminal. If it's outside 3.9-3.12, add it to `PYVERSIONS` and
  rebuild for it specifically.

See `apps/streamlit_ui/sso_auth.py`'s module docstring for the
separate (unrelated) set of things a CML admin needs to confirm about
SSO passthrough — this bundle only covers *installing* dependencies,
not authentication.
