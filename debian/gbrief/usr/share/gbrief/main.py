import sys
import os
import shutil
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Poppler", "0.18")

from gi.repository import Gtk, Adw, Gdk
from window import BriefFenster

APP_ID    = "de.xhomie.gbrief"
SKRIPT    = Path(__file__).resolve()
ICON_SRC  = SKRIPT.parent / "gbrief.svg"
ICON_DEST = Path.home() / ".local/share/icons/hicolor/scalable/apps" / f"{APP_ID}.svg"
DESK_DEST = Path.home() / ".local/share/applications" / f"{APP_ID}.desktop"


def _lokale_dateien_installieren():
    """Icon und .desktop-Datei beim ersten Start (oder nach Update) einrichten."""

    # Icon kopieren (immer aktuell halten)
    if ICON_SRC.exists():
        ICON_DEST.parent.mkdir(parents=True, exist_ok=True)
        if not ICON_DEST.exists() or ICON_SRC.stat().st_mtime > ICON_DEST.stat().st_mtime:
            shutil.copy2(ICON_SRC, ICON_DEST)
            # Icon-Cache aktualisieren damit GNOME Shell das Icon sofort findet
            subprocess.run(
                ["gtk-update-icon-cache", "-f", "-t",
                 str(Path.home() / ".local/share/icons/hicolor")],
                capture_output=True,
            )

    # .desktop-Datei schreiben (immer aktuell halten, Pfad könnte sich ändern)
    desktop = f"""\
[Desktop Entry]
Name=gbrief
GenericName=Briefschreiber
Comment=Professionelle Briefe mit LaTeX (scrlttr2)
Exec=/usr/bin/python3 {SKRIPT}
Icon={APP_ID}
Type=Application
Categories=Office;WordProcessor;
StartupWMClass={APP_ID}
StartupNotify=true
"""
    DESK_DEST.parent.mkdir(parents=True, exist_ok=True)
    DESK_DEST.write_text(desktop, encoding="utf-8")
    subprocess.run(
        ["update-desktop-database", str(DESK_DEST.parent)],
        capture_output=True,
    )


class GBriefApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        # Projektinternes Icon-Verzeichnis als Suchpfad ergänzen
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        theme.add_search_path(str(SKRIPT.parent / "icons"))

        win = BriefFenster(application=self)
        win.set_icon_name(APP_ID)
        win.maximize()
        win.present()


def main():
    # Im installierten Paket liegen Icon und .desktop-Datei bereits systemweit;
    # nur beim Ausführen aus dem Quellverzeichnis heraus selbst einrichten.
    if not str(SKRIPT).startswith("/usr/"):
        _lokale_dateien_installieren()
    app = GBriefApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
