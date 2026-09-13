# Offline dependency bundle (air-gapped CML deployment)

For a CML workspace where `pip install` can't reach PyPI. Prebuilt
wheels for everything `apps/streamlit_ui/requirements.txt` needs
(streamlit, SQLAlchemy, pandas, openpyxl, psycopg2-binary, and their
full transitive dependency trees), for four Python versions (3.9,
3.10, 3.11, 3.12 — covering the common CML ML Runtime versions; the
exact one wasn't confirmed when this was built) on **linux x86_64**,
plus ITAP's own five capability packages (`party_identity`,
`assignment`, `rbac_scope`, `rotation_plan`, `catalog`) as
version-independent pure-Python wheels.

`psycopg2-binary` was added to `requirements.txt` in the same pass as
this directory — the project's own top-level README documents a
Postgres deployment (`DATABASE_URL=postgresql://...`) but nothing
previously declared the driver SQLAlchemy actually needs to talk to
Postgres; without it, connecting raises `ModuleNotFoundError: No
module named 'psycopg2'` regardless of how the rest of the app is
packaged.

A committed copy of an actual built bundle (this repo's `requirements.txt`
as of some commit, plus the wheel binaries themselves — for `git clone`
convenience rather than rebuilding from scratch) lives on the
`offline-deps` branch, not here. This directory (on `main`) is the
*tooling* — build scripts and source — kept separate from generated
binaries so `main`'s history doesn't carry ~100MB+ of wheels per Python
version forever.

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
this bundle is too large to move through a chat upload), or push it to
the `offline-deps` branch (`git add -f`, since the path is gitignored
on `main`) for `git clone` access instead.

## Installing on the air-gapped box

```bash
tar xzf itap_offline_bundle.tar.gz   # however you transferred it
bash offline_deploy/install_offline.sh
```

`install_offline.sh` detects the running Python's `(OS, CPU arch,
version)` automatically and installs from the matching
`wheelhouse/<os>_<arch>-py<version>/` directory (e.g.
`linux_x86_64-py311`) with `pip install --no-index` — no PyPI access,
no compiling. If your combo isn't one of the ones built, it says so and
lists what's available.

## Adding another platform/Python combo

Edit `PYVERSIONS` in `build_offline_bundle.sh` and re-run for another
Python version on linux x86_64. For a different architecture (e.g. an
arm64 CML Runtime) or OS (e.g. a macOS bundle for local dry-run
testing, not a CML target), swap the `--platform` flags for the
target's own tags — e.g. `--platform manylinux2014_aarch64` for linux
arm64, or `--platform macosx_11_0_arm64` for Apple Silicon macOS — and
change the output directory prefix to match (`linux_arm64-pyXY`,
`macos_arm64-pyXY`, etc.) since `install_offline.sh` looks wheels up by
that exact `<os>_<arch>-py<version>` key.

Note Intel Mac (`macosx_..._x86_64`) + very new Python versions can hit
real resolution dead ends — some packages (numpy included) have stopped
publishing Intel macOS wheels for the newest Python releases, which can
send pip's resolver down a chain trying to satisfy an older streamlit
version's stricter numpy pin instead, and fail outright.

## What still needs confirming with your CML admin/platform team

- **CPU architecture** — this assumes linux x86_64, by far the most
  common CML Runtime architecture. For arm64, see above.
- **Exact Python version** — check with `python3 --version` in a CML
  terminal. If it's outside 3.9-3.12, add it to `PYVERSIONS` and
  rebuild for it specifically.

See `apps/streamlit_ui/sso_auth.py`'s module docstring for the
separate (unrelated) set of things a CML admin needs to confirm about
SSO passthrough — this bundle only covers *installing* dependencies,
not authentication.
