import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Poppler", "0.18")

from gi.repository import Gtk, Adw, Gdk
from window import BriefFenster

APP_ID = "de.xhomie.gbrief"
ICON_SRC = Path(__file__).parent / "gbrief.svg"
ICON_DEST = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"


def _icon_installieren():
    """Icon einmalig ins lokale Icon-Theme kopieren."""
    if ICON_SRC.exists() and not ICON_DEST.exists():
        ICON_DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ICON_SRC, ICON_DEST)


class GBriefApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        # Icon-Suchpfad für diese Sitzung ergänzen (erwartet hicolor/scalable/apps/ Struktur)
        display = Gdk.Display.get_default()
        theme = Gtk.IconTheme.get_for_display(display)
        theme.add_search_path(str(Path(__file__).parent / "icons"))

        win = BriefFenster(application=self)
        win.set_icon_name(APP_ID)
        win.maximize()
        win.present()


def main():
    _icon_installieren()
    app = GBriefApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
