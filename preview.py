import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Poppler", "0.18")
from gi.repository import Gtk, Poppler, GLib


class PdfVorschau(Gtk.ScrolledWindow):
    def __init__(self, zoom_geaendert_cb=None):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self._dokument = None
        self._seite = 0
        self._zoom = 1.0
        self._auto_fit = True
        self._zoom_geaendert_cb = zoom_geaendert_cb

        self._zeichenflaeche = Gtk.DrawingArea()
        self._zeichenflaeche.set_draw_func(self._zeichnen)

        self._info_label = Gtk.Label()
        self._info_label.set_wrap(True)
        self._info_label.set_valign(Gtk.Align.CENTER)
        self._info_label.set_halign(Gtk.Align.CENTER)
        self._info_label.set_margin_start(20)
        self._info_label.set_margin_end(20)

        self._platzhalter = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._platzhalter.set_vexpand(True)
        self._platzhalter.set_hexpand(True)
        self._platzhalter.append(self._info_label)

        self.set_child(self._platzhalter)

        # Auf Größenänderung reagieren
        self.connect("notify::width", self._on_groesse_geaendert)

    # ------------------------------------------------------------------ #
    # Öffentliche API
    # ------------------------------------------------------------------ #

    def lade_pdf(self, pfad: str):
        try:
            uri = GLib.filename_to_uri(pfad, None)
            self._dokument = Poppler.Document.new_from_file(uri, None)
            self._seite = 0
            self.set_child(self._zeichenflaeche)
            # Breite erst nach dem nächsten Layout-Durchlauf korrekt → idle_add
            GLib.idle_add(self.zoom_an_breite_anpassen)
        except Exception as e:
            self.zeige_fehler(str(e))

    def zeige_fehler(self, meldung: str):
        self._dokument = None
        self._info_label.set_label(f"Fehler:\n{meldung}")
        self.set_child(self._platzhalter)

    def zeige_info(self, meldung: str):
        self._dokument = None
        self._info_label.set_label(meldung)
        self.set_child(self._platzhalter)

    def setze_zoom(self, zoom: float, auto: bool = False):
        self._auto_fit = auto
        self._zoom = max(0.2, min(zoom, 4.0))
        self._aktualisiere_groesse()
        self._zeichenflaeche.queue_draw()
        if self._zoom_geaendert_cb:
            self._zoom_geaendert_cb(self._zoom)

    def zoom_an_breite_anpassen(self):
        if not self._dokument:
            return
        seite = self._dokument.get_page(self._seite)
        s_breite, _ = seite.get_size()
        # Verfügbare Breite: Scrolled-Window-Breite minus Scrollleiste (~16px) minus etwas Padding
        verfuegbar = self.get_width() - 24
        if verfuegbar > 50:
            self._auto_fit = True
            self._zoom = verfuegbar / s_breite
            self._aktualisiere_groesse()
            self._zeichenflaeche.queue_draw()
            if self._zoom_geaendert_cb:
                self._zoom_geaendert_cb(self._zoom)

    # ------------------------------------------------------------------ #
    # Interne Methoden
    # ------------------------------------------------------------------ #

    def _on_groesse_geaendert(self, *_):
        if self._auto_fit and self._dokument:
            self.zoom_an_breite_anpassen()

    def _aktualisiere_groesse(self):
        if self._dokument is None:
            return
        seite = self._dokument.get_page(self._seite)
        breite, hoehe = seite.get_size()
        self._zeichenflaeche.set_content_width(int(breite * self._zoom))
        self._zeichenflaeche.set_content_height(int(hoehe * self._zoom))

    def _zeichnen(self, widget, cr, breite, hoehe):
        if self._dokument is None:
            return
        seite = self._dokument.get_page(self._seite)

        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, breite, hoehe)
        cr.fill()

        cr.scale(self._zoom, self._zoom)
        seite.render(cr)
