# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ingo
import subprocess
import tempfile
import os
import threading
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "brief.tex"


def _render_template(daten: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Logo
    if daten.get("from_logo"):
        logo_pfad = daten["from_logo"].replace("\\", "/")
        template = template.replace("%%LOGO_PACKAGE%%", "\\usepackage{graphicx}")
        template = template.replace(
            "%%LOGO_COMMAND%%",
            f"\\setkomavar{{fromlogo}}{{\\includegraphics[height=2cm]{{{logo_pfad}}}}}",
        )
    else:
        template = template.replace("%%LOGO_PACKAGE%%", "")
        template = template.replace("%%LOGO_COMMAND%%", "")

    replacements = {
        "%%FROM_NAME%%": daten.get("from_name", ""),
        "%%FROM_STREET%%": daten.get("from_street", ""),
        "%%FROM_ZIP%%": daten.get("from_zip", ""),
        "%%FROM_CITY%%": daten.get("from_city", ""),
        "%%FROM_PHONE%%": daten.get("from_phone", ""),
        "%%FROM_EMAIL%%": daten.get("from_email", ""),
        "%%TO_NAME%%": daten.get("to_name", ""),
        "%%TO_STREET%%": daten.get("to_street", ""),
        "%%TO_ZIP%%": daten.get("to_zip", ""),
        "%%TO_CITY%%": daten.get("to_city", ""),
        "%%OPENING%%": daten.get("opening", "Sehr geehrte Damen und Herren,"),
        "%%BODY%%": daten.get("body", ""),
        "%%CLOSING%%": daten.get("closing", "Mit freundlichen Grüßen"),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template


def kompiliere_brief(daten: dict, callback):
    """
    Kompiliert den Brief im Hintergrund.
    callback(pdf_path: str | None, fehler: str | None) wird im Hauptthread aufgerufen.
    """
    def _run():
        workdir = tempfile.mkdtemp(prefix="gbrief_")
        try:
            tex_datei = os.path.join(workdir, "brief.tex")
            latex_inhalt = _render_template(daten)
            with open(tex_datei, "w", encoding="utf-8") as f:
                f.write(latex_inhalt)

            ergebnis = subprocess.run(
                ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "brief.tex"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            pdf_pfad = os.path.join(workdir, "brief.pdf")
            if ergebnis.returncode == 0 and os.path.exists(pdf_pfad):
                callback(pdf_pfad, None)
            else:
                # Fehler aus dem Log extrahieren
                log_pfad = os.path.join(workdir, "brief.log")
                fehler_text = ""
                if os.path.exists(log_pfad):
                    with open(log_pfad, "r", encoding="utf-8", errors="replace") as lf:
                        zeilen = lf.readlines()
                    fehler_zeilen = [z for z in zeilen if z.startswith("!") or "Error" in z]
                    fehler_text = "".join(fehler_zeilen[:10])
                if not fehler_text:
                    fehler_text = ergebnis.stderr or "Unbekannter Fehler"
                callback(None, fehler_text)
        except subprocess.TimeoutExpired:
            callback(None, "Zeitüberschreitung beim Kompilieren (>30s)")
        except Exception as e:
            callback(None, str(e))
        # workdir wird nicht gelöscht — Callback braucht die PDF noch.
        # Aufräumen ist Aufgabe des Aufrufers nach dem Laden.

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
