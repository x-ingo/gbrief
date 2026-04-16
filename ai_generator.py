# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ingo
import json
import threading
import urllib.request
import urllib.error
from database import DB_PATH

CONFIG_PATH = DB_PATH.parent / "config.json"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key={api_key}"
)

STILE = [
    "formell",
    "freundlich",
    "sachlich",
    "höflich",
    "bestimmt",
]

SYSTEM_PROMPT = (
    "Du bist ein Assistent, der professionelle deutsche Geschäftsbriefe verfasst. "
    "Schreibe ausschließlich den Fließtext des Briefes – ohne Anrede, ohne Grußformel, "
    "ohne Betreffzeile. Verwende korrektes Deutsch und einen dem gewünschten Stil "
    "entsprechenden Ton. Nutze bei Bedarf LaTeX-Formatierungen wie \\textbf{}, "
    "\\textit{}, \\begin{itemize}...\\end{itemize} oder "
    "\\begin{enumerate}...\\end{enumerate}."
)


def lade_api_key() -> str | None:
    if CONFIG_PATH.exists():
        try:
            daten = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return daten.get("gemini_api_key") or None
        except Exception:
            pass
    return None


def speichere_api_key(key: str):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    daten = {}
    if CONFIG_PATH.exists():
        try:
            daten = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    daten["gemini_api_key"] = key.strip()
    CONFIG_PATH.write_text(
        json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def generiere_text(api_key: str, stichpunkte: str, stil: str, callback):
    """
    Ruft die Gemini-API im Hintergrund auf.
    callback(text: str | None, fehler: str | None) wird aus dem Thread aufgerufen;
    der Aufrufer muss GLib.idle_add verwenden, um auf den GTK-Hauptthread zu wechseln.
    """
    def _run():
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Stichpunkte:\n{stichpunkte}\n\n"
            f"Gewünschter Stil: {stil}"
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}]
        }).encode("utf-8")

        url = GEMINI_URL.format(api_key=api_key)
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                antwort = json.loads(resp.read().decode("utf-8"))
            text = antwort["candidates"][0]["content"]["parts"][0]["text"].strip()
            callback(text, None)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(body)["error"]["message"]
            except Exception:
                msg = body[:300]
            callback(None, f"Gemini-Fehler: {msg}")
        except Exception as e:
            callback(None, str(e))

    threading.Thread(target=_run, daemon=True).start()
