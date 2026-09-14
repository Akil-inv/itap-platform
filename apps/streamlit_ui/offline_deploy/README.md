# Offline dependency bundle (air-gapped CML deployment)

**You're on the `offline-deps` branch** — unlike `main`, the actual
wheel binaries are committed here so this whole thing is fetchable with
plain `git`, no chat upload needed. `wheelhouse/` and `requirements.txt`
are gitignored on `main` (build output, not source) but force-added on
this branch on purpose — see the commit that added them.

For a CML workspace where `pip install` can't reach PyPI. Prebuilt
wheels for everything `apps/streamlit_ui/requirements.txt` needs
(streamlit, SQLAlchemy, pandas, openpyxl, psycopg2-binary, and their
full transitive dependency trees).

## What's here

- `wheelhouse/linux_x86_64-py38/`, `-py311/` — every third-party
  package `apps/streamlit_ui/requirements.txt` needs, built separately
  for each **confirmed-in-use** Python version on linux x86_64 (py311
  was the original guess; py38 is a real CML box's actual version,
  confirmed 2026-09). Only combos someone has actually hit are kept
  committed here — `build_offline_bundle.sh`'s own `PYVERSIONS` covers
  3.8-3.12 so building another one is a one-line edit and a re-run
  (see "Adding another platform/Python combo" below), but committing
  every possible version speculatively just bloats this branch's
  download size for versions nobody's confirmed using.
- `wheelhouse/macos_arm64-py313/` — the same, for **Python 3.13 on
  Apple Silicon macOS** — added for a local dry-run test on a
  MacBook before touching the actual air-gapped box. This is
  **not** a CML deployment target; it exists purely so you can sanity-
  check the install flow locally first.
- `wheelhouse/local/` — ITAP's own 5 capability packages
  (`party_identity`, `assignment`, `rbac_scope`, `rotation_plan`,
  `catalog`) as pure-Python wheels — version- and platform-independent,
  used by every combo above.
- `requirements.txt` — a copy of `apps/streamlit_ui/requirements.txt`
  as of the commit that built these wheels.

`psycopg2-binary` was added to `requirements.txt` (on `main`, carried
over here) in the same pass as this bundle — the project's top-level
README documents a Postgres deployment
(`DATABASE_URL=postgresql://...`) but nothing previously declared the
driver SQLAlchemy actually needs to talk to Postgres; without it,
connecting raises `ModuleNotFoundError: No module named 'psycopg2'`
regardless of how the rest of the app is packaged.

`ldap3` (+ its one dependency, `pyasn1`) was added later for
`apps/streamlit_ui/ad_auth.py` — a real username/password login bound
against Active Directory, as a second real-auth path alongside CML SSO
passthrough. See that module's docstring (on `main`) for the AD-side
config it needs.

## Installing

Run this on any machine **with internet access** — it does not have to
be the air-gapped box, and it doesn't need Python 3.8/3.9/3.10/3.11/
3.12 actually installed: `pip download` fetches manylinux wheels for a
target Python version straight from PyPI without executing them.

```bash
git clone --branch offline-deps --single-branch <this-repo-url> itap-offline
cd itap-offline
bash apps/streamlit_ui/offline_deploy/install_offline.sh
```

`install_offline.sh` detects the running Python's `(OS, CPU arch,
version)` automatically and installs from the matching
`wheelhouse/<os>_<arch>-py<version>/` directory with `pip install
--no-index` — no PyPI access, no compiling. If your combo isn't one of
the ones built, it says so and lists what's available.

## Adding another platform/Python combo

Wheels are built with `pip download`, which fetches prebuilt wheels for
a target platform + Python version straight from PyPI without
executing them or needing that interpreter installed locally — so any
one machine with internet access can build for combos it isn't
actually running. `main`'s `build_offline_bundle.sh` covers the linux
case (edit `PYVERSIONS`/the `--platform` flags for a different
architecture); for macOS, the same `pip download` invocation with
`--platform macosx_11_0_arm64` (Apple Silicon) or
`--platform macosx_10_9_x86_64` (Intel) in place of the manylinux flags
does it — note Intel Mac + very new Python versions can hit real
resolution dead ends (some packages, numpy included, have stopped
publishing Intel macOS wheels for the newest Python releases), which is
why only arm64 was built here.

Once built, add it under `wheelhouse/<os>_<arch>-py<version>/` on this
branch (`git add -f`, since the path is gitignored on `main`) and push.

## What still needs confirming with your CML admin/platform team

- **CPU architecture** — the linux builds all assume the most common
  CML Runtime architecture (x86_64). For arm64 CML Runtimes, a
  `linux_arm64-pyXY` build is needed instead.
- **Exact Python version** — check with `python3 --version` in a CML
  terminal. If it's outside 3.8-3.12, add it to `PYVERSIONS` (in
  `main`'s `build_offline_bundle.sh`) and rebuild for it specifically.

See `apps/streamlit_ui/sso_auth.py`'s module docstring (on `main`) for
the separate (unrelated) set of things a CML admin needs to confirm
about SSO passthrough — this bundle only covers *installing*
dependencies, not authentication.
