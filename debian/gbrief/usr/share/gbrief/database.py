import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "gbrief" / "gbrief.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS absender (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                strasse TEXT,
                plz TEXT,
                ort TEXT,
                telefon TEXT,
                email TEXT,
                logo_pfad TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS empfaenger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                strasse TEXT,
                plz TEXT,
                ort TEXT,
                zuletzt_verwendet INTEGER DEFAULT 0
            )
        """)
        conn.commit()


# --- Absender ---

def alle_absender():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM absender ORDER BY name").fetchall()


def absender_speichern(name, strasse, plz, ort, telefon, email, logo_pfad):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO absender (name, strasse, plz, ort, telefon, email, logo_pfad) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, strasse, plz, ort, telefon, email, logo_pfad),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def absender_aktualisieren(aid, name, strasse, plz, ort, telefon, email, logo_pfad):
    with get_connection() as conn:
        conn.execute(
            "UPDATE absender SET name=?, strasse=?, plz=?, ort=?, telefon=?, email=?, logo_pfad=? WHERE id=?",
            (name, strasse, plz, ort, telefon, email, logo_pfad, aid),
        )
        conn.commit()


def absender_loeschen(aid):
    with get_connection() as conn:
        conn.execute("DELETE FROM absender WHERE id=?", (aid,))
        conn.commit()


# --- Empfänger ---

def alle_empfaenger():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM empfaenger ORDER BY zuletzt_verwendet DESC, name").fetchall()


def empfaenger_suchen(suchbegriff):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM empfaenger WHERE name LIKE ? OR ort LIKE ? ORDER BY zuletzt_verwendet DESC LIMIT 10",
            (f"%{suchbegriff}%", f"%{suchbegriff}%"),
        ).fetchall()


def empfaenger_speichern_oder_aktualisieren(name, strasse, plz, ort):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM empfaenger WHERE name=? AND strasse=? AND plz=? AND ort=?",
            (name, strasse, plz, ort),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE empfaenger SET zuletzt_verwendet=strftime('%s','now') WHERE id=?",
                (existing["id"],),
            )
            conn.commit()
            return existing["id"]
        else:
            conn.execute(
                "INSERT INTO empfaenger (name, strasse, plz, ort, zuletzt_verwendet) VALUES (?, ?, ?, ?, strftime('%s','now'))",
                (name, strasse, plz, ort),
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def empfaenger_loeschen(eid):
    with get_connection() as conn:
        conn.execute("DELETE FROM empfaenger WHERE id=?", (eid,))
        conn.commit()
