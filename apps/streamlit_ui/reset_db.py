"""Wipes the configured DATABASE_URL back to empty — for demoing or
starting a client deployment over from scratch, per
docs/associate_journey_redesign.md's "Client deployment & setup data
model" section ("A console command ... wipes a deployment back to
empty").

Deliberately a plain script, not a Streamlit action — resetting
production-ish data should never be one click away inside the app itself.

Drops every table this app's four capabilities know about (party_identity,
assignment, rotation_plan, catalog) using each package's own SQLAlchemy
`metadata`, then recreates the (now-empty) schema via the same
`create_schema()` calls `services.py` runs on every app start — so the
app comes back up cleanly against a truly empty database, not a
half-migrated one.

Usage:
    python reset_db.py                 # uses $DATABASE_URL (or the same
                                        # sqlite:///itap.db default as the
                                        # app)
    DATABASE_URL=postgresql://... python reset_db.py

Also clears the local photo storage directory ($PHOTO_STORAGE_DIR,
default ./uploaded_photos), since a photo on disk with no AssociateProfile
row pointing at it would otherwise be orphaned.
"""
from __future__ import annotations

import os
import shutil
import sys

from sqlalchemy import create_engine

from assignment.adapters.sql import create_schema as create_assignment_schema
from assignment.adapters.sql import metadata as assignment_metadata
from catalog.adapters.sql import create_schema as create_catalog_schema
from catalog.adapters.sql import metadata as catalog_metadata
from party_identity.adapters.sql import create_schema as create_party_schema
from party_identity.adapters.sql import metadata as party_metadata
from rotation_plan.adapters.sql import create_schema as create_rotation_plan_schema
from rotation_plan.adapters.sql import metadata as rotation_plan_metadata


def reset(database_url: str) -> None:
    engine = create_engine(database_url)

    print(f"Resetting {database_url} ...")
    for metadata in (assignment_metadata, rotation_plan_metadata, catalog_metadata, party_metadata):
        metadata.drop_all(engine)

    create_party_schema(engine)
    create_assignment_schema(engine)
    create_rotation_plan_schema(engine)
    create_catalog_schema(engine)
    print("All tables dropped and recreated empty: party_identity, assignment, rotation_plan, catalog.")

    photo_dir = os.environ.get("PHOTO_STORAGE_DIR", "./uploaded_photos")
    if os.path.isdir(photo_dir):
        shutil.rmtree(photo_dir)
        print(f"Removed local photo storage directory: {photo_dir}")


if __name__ == "__main__":
    if "--yes" not in sys.argv and os.environ.get("RESET_DB_CONFIRM") != "yes":
        answer = input(
            "This will PERMANENTLY delete all data. Type 'yes' to continue: "
        ).strip().lower()
        if answer != "yes":
            print("Aborted — no changes made.")
            sys.exit(1)

    reset(os.environ.get("DATABASE_URL", "sqlite:///itap.db"))
