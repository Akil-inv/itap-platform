"""Quick diagnostic: lists every Party row in the ITAP database, so you
can see whether an Admin has already been onboarded and under what
email/identity.

Exists because hand-typing a one-line psycopg2 query in a terminal that
doesn't support reliable copy-paste is extremely error-prone (long
lines full of =, quotes, and parens are exactly what gets mangled), and
`psql` isn't on a plain CML Session's PATH (it's only inside the
project's pg_bundle/, not a system package). Fetch this file directly
instead of typing it:

    curl -o /tmp/check_parties.py https://raw.githubusercontent.com/Akil-inv/itap-platform/offline-deps/apps/postgres_service/check_parties.py
    export PGPASSWORD='<same PG_PASSWORD as the Application>'
    python3 /tmp/check_parties.py

Reads the same PG_PORT/PG_USER/PG_DB env var conventions as start.sh
(see that script), defaulting to the same values (5432/itap/itap) if
unset -- only PGPASSWORD is required.
"""
import os

import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1",
    port=os.environ.get("PG_PORT", "5432"),
    user=os.environ.get("PG_USER", "itap"),
    password=os.environ["PGPASSWORD"],
    dbname=os.environ.get("PG_DB", "itap"),
)
cur = conn.cursor()
cur.execute("select id, party_type, display_name, email from parties;")
rows = cur.fetchall()
if not rows:
    print("No parties found -- the database is empty.")
else:
    print(f"{len(rows)} party row(s):")
    for row in rows:
        print(row)
conn.close()
