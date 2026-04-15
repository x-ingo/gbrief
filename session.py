# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ingo
import json
from database import DB_PATH

SESSION_PATH = DB_PATH.parent / "session.json"

_STANDARD = {
    "absender_id": None,
    "empfaenger_id": None,
    "brieftext": "",
    "opening": "Sehr geehrte Damen und Herren,",
    "closing": "Mit freundlichen Grüßen",
}


def laden() -> dict:
    if SESSION_PATH.exists():
        try:
            daten = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
            return {**_STANDARD, **daten}
        except Exception:
            pass
    return dict(_STANDARD)


def speichern(zustand: dict):
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(zustand, ensure_ascii=False, indent=2), encoding="utf-8")
