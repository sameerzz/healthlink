"""Clinic database: sample doctors, anonymous users, and saved appointments."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class SlotTaken(Exception):
    pass


@contextmanager
def connect():
    path = Path(os.getenv("DATABASE_PATH", str(Path(__file__).parent / "data" / "healthlink.db")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY)")
            db.execute("""CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY, name TEXT, specialty TEXT, location TEXT)""")
            doctors = json.loads(Path(__file__).with_name("doctors.json").read_text())
            db.executemany("INSERT OR IGNORE INTO doctors VALUES (:id, :name, :specialty, :location)", doctors)
            db.execute("""CREATE TABLE IF NOT EXISTS appointments (
                booking_id TEXT PRIMARY KEY, user_id TEXT UNIQUE NOT NULL,
                patient_name TEXT NOT NULL, doctor_id INTEGER NOT NULL,
                doctor_name TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
                UNIQUE(doctor_id, date, time))""")
            # Preserve appointments created by the earlier version of this project.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(appointments)")}
            if "session_id" in columns:
                db.execute("ALTER TABLE appointments RENAME COLUMN session_id TO user_id")
            yield db
    finally:
        db.close()


def create_user():
    user_id = str(uuid4())
    with connect() as db:
        db.execute("INSERT INTO users VALUES (?)", (user_id,))
    return user_id


def user_exists(user_id):
    with connect() as db:
        return db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone() is not None


def list_doctors(specialty=None):
    with connect() as db:
        if specialty:
            rows = db.execute("SELECT * FROM doctors WHERE specialty=? COLLATE NOCASE", (specialty,))
        else:
            rows = db.execute("SELECT * FROM doctors ORDER BY id")
        return [dict(row) for row in rows]


def booking_for(user_id):
    with connect() as db:
        row = db.execute("SELECT * FROM appointments WHERE user_id=?", (user_id,)).fetchone()
    return {key: row[key] for key in row.keys() if key != "user_id"} if row else None


def occupied_slots():
    with connect() as db:
        return {(row["doctor_id"], row["date"], row["time"])
                for row in db.execute("SELECT doctor_id, date, time FROM appointments")}


def book_appointment(user_id, patient_name, slot):
    existing = booking_for(user_id)
    if existing:
        return existing
    if datetime.fromisoformat(f"{slot['date']}T{slot['time']}") <= datetime.now():
        raise SlotTaken
    booking = {"booking_id": str(uuid4()), "patient_name": patient_name, **slot}
    try:
        with connect() as db:
            db.execute("""INSERT INTO appointments
                (booking_id, user_id, patient_name, doctor_id, doctor_name, date, time)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", (
                    booking["booking_id"], user_id, patient_name, slot["doctor_id"],
                    slot["doctor_name"], slot["date"], slot["time"],
                ))
    except sqlite3.IntegrityError:
        existing = booking_for(user_id)
        if existing:
            return existing
        raise SlotTaken from None
    return booking
