"""
Simple DB tools for HealthLink.

Usage:
  python scripts/db_tools.py inspect
  python scripts/db_tools.py seed-doctors
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "healthlink.db"
DOCTORS_CSV = ROOT / "data" / "doctors.csv"


def inspect_db() -> None:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    tables = [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    print(f"db_path={DB_PATH}")
    print(f"tables={tables}")

    for table in tables:
        if table.startswith("sqlite_"):
            continue
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}_rows={count}")

    conn.close()


def seed_doctors() -> None:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return
    if not DOCTORS_CSV.exists():
        print(f"CSV not found: {DOCTORS_CSV}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = cur.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    if existing > 0:
        print(f"doctors table already has {existing} rows, skipping insert")
        conn.close()
        return

    with DOCTORS_CSV.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("No rows found in doctors.csv")
        conn.close()
        return

    cols = [
        "name",
        "specialty",
        "experience_years",
        "rating",
        "availability",
        "location",
        "email",
        "phone",
        "qualifications",
        "languages",
        "consultation_type",
    ]
    values = [tuple(r.get(c) for c in cols) for r in rows]

    cur.executemany(
        """
        INSERT INTO doctors (
          name, specialty, experience_years, rating, availability, location,
          email, phone, qualifications, languages, consultation_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    conn.commit()

    inserted = cur.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    print(f"seeded_doctors={inserted}")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="HealthLink DB tools")
    parser.add_argument("command", choices=["inspect", "seed-doctors"])
    args = parser.parse_args()

    if args.command == "inspect":
        inspect_db()
    elif args.command == "seed-doctors":
        seed_doctors()


if __name__ == "__main__":
    main()

