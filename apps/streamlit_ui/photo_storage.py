"""Where an uploaded associate photo actually lands on disk.

`catalog.domain.AssociateProfile.photo_url` is a plain `Optional[str]` —
the domain layer doesn't care whether it's a URL or a local path (see
`views/associate_portfolio.py`, which already just does
`st.image(profile.photo_url)`, and that works equally well for a local
file path). There is no blob-storage adapter anywhere in this codebase,
so rather than invent one, `photos.zip` images are written to a plain
directory on disk and `photo_url` is set to that path — same "follow the
existing shape" judgment call the task asked for. Revisit with a real
object-storage adapter if/when this needs to run across multiple
app instances that don't share a filesystem.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID


def storage_dir() -> Path:
    path = Path(os.environ.get("PHOTO_STORAGE_DIR", "./uploaded_photos"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_photo(agent_id: UUID, filename: str, data: bytes) -> str:
    """Writes `data` under a name keyed by the Agent's id (stable even if
    the source filename changes on a later re-upload) but keeping the
    original extension, and returns the path to store on
    AssociateProfile.photo_url."""
    suffix = Path(filename).suffix or ".jpg"
    dest = storage_dir() / f"{agent_id}{suffix}"
    dest.write_bytes(data)
    return str(dest)
