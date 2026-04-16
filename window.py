# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ingo
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Poppler", "0.18")

from gi.repository import Gtk, Adw, GtkSource, GLib, Gio, Poppler
import shutil
import database as db
import latex_builder
import session
import ai_generator
from preview import PdfVorschau

DEBOUNCE_MS = 1200


class BriefFenster(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("gbrief")
        self.set_default_size(1200, 800)

        self._kompilier_timer = None
        self._aktiver_absender = None
        self._aktuelles_pdf = None
        self._aktiver_empfaenger = {"name": "", "strasse": "", "plz": "", "ort": ""}
        self._empfaenger_daten = []

        db.init_db()
        self._baue_ui()
        self._sitzung_laden()
        self.connect("close-request", self._beim_schliessen)

    # ------------------------------------------------------------------ #
    # UI-Aufbau
    # ------------------------------------------------------------------ #

    def _baue_ui(self):
        hauptbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(hauptbox)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)

        # Burger-Menü
        menu = Gio.Menu()
        menu.append("Info", "win.info")
        menu.append("Schließen", "win.schliessen")

        info_action = Gio.SimpleAction.new("info", None)
        info_action.connect("activate", lambda *_: self._info_dialog())
        self.add_action(info_action)

        schliessen_action = Gio.SimpleAction.new("schliessen", None)
        schliessen_action.connect("activate", lambda *_: self.close())
        self.add_action(schliessen_action)

        burger_btn = Gtk.MenuButton()
        burger_btn.set_icon_name("open-menu-symbolic")
        burger_btn.set_tooltip_text("Menü")
        burger_btn.set_menu_model(menu)
        header.pack_end(burger_btn)

        hauptbox.append(header)

        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_vexpand(True)
        hauptbox.append(self._paned)

        self._paned.set_start_child(self._baue_eingabeseite())
        self._paned.set_end_child(self._baue_vorschauseite())

    def _baue_eingabeseite(self):
        # Scrollbarer oberer Bereich (Felder)
        felder_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        felder_box.set_margin_top(12)
        felder_box.set_margin_bottom(8)
        felder_box.set_margin_start(12)
        felder_box.set_margin_end(12)

        # --- Absender ---
        absender_gruppe = Adw.PreferencesGroup(title="Absender")

        absender_zeile = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._absender_dropdown = Gtk.DropDown()
        self._absender_dropdown.set_hexpand(True)
        self._absender_string_liste = Gtk.StringList()
        self._absender_dropdown.set_model(self._absender_string_liste)
        self._absender_dropdown.connect("notify::selected", self._absender_geaendert)
        absender_zeile.append(self._absender_dropdown)

        absender_neu_btn = Gtk.Button(icon_name="list-add-symbolic")
        absender_neu_btn.set_tooltip_text("Neuen Absender anlegen")
        absender_neu_btn.connect("clicked", self._absender_neu_dialog)
        absender_zeile.append(absender_neu_btn)

        absender_edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
        absender_edit_btn.set_tooltip_text("Absender bearbeiten")
        absender_edit_btn.connect("clicked", self._absender_bearbeiten_dialog)
        absender_zeile.append(absender_edit_btn)

        absender_wrapper = Adw.ActionRow(title="Profil")
        absender_wrapper.add_suffix(absender_zeile)
        absender_gruppe.add(absender_wrapper)
        felder_box.append(absender_gruppe)

        # --- Empfänger ---
        empfaenger_gruppe = Adw.PreferencesGroup(title="Empfänger")

        empfaenger_zeile = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._empfaenger_dropdown = Gtk.DropDown()
        self._empfaenger_dropdown.set_hexpand(True)
        self._empfaenger_string_liste = Gtk.StringList()
        self._empfaenger_dropdown.set_model(self._empfaenger_string_liste)
        self._empfaenger_dropdown.connect("notify::selected", self._empfaenger_geaendert)
        empfaenger_zeile.append(self._empfaenger_dropdown)

        empf_neu_btn = Gtk.Button(icon_name="list-add-symbolic")
        empf_neu_btn.set_tooltip_text("Neuen Empfänger anlegen")
        empf_neu_btn.connect("clicked", self._empfaenger_neu_dialog)
        empfaenger_zeile.append(empf_neu_btn)

        empf_edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
        empf_edit_btn.set_tooltip_text("Empfänger bearbeiten")
        empf_edit_btn.connect("clicked", self._empfaenger_bearbeiten_dialog)
        empfaenger_zeile.append(empf_edit_btn)

        empfaenger_wrapper = Adw.ActionRow(title="Adressbuch")
        empfaenger_wrapper.add_suffix(empfaenger_zeile)
        empfaenger_gruppe.add(empfaenger_wrapper)
        felder_box.append(empfaenger_gruppe)

        # --- Briefkopf ---
        brief_gruppe = Adw.PreferencesGroup(title="Brief")

        self._subject = Adw.EntryRow(title="Betreff")
        self._subject.connect("changed", self._eingabe_geaendert)
        brief_gruppe.add(self._subject)

        self._opening = Adw.EntryRow(title="Anrede")
        self._opening.set_text("Sehr geehrte Damen und Herren,")
        self._opening.connect("changed", self._eingabe_geaendert)
        brief_gruppe.add(self._opening)

        self._closing = Adw.EntryRow(title="Grußformel")
        self._closing.set_text("Mit freundlichen Grüßen")
        self._closing.connect("changed", self._eingabe_geaendert)
        brief_gruppe.add(self._closing)
        felder_box.append(brief_gruppe)

        felder_scroll = Gtk.ScrolledWindow()
        felder_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        felder_scroll.set_min_content_width(400)
        felder_scroll.set_vexpand(False)
        felder_scroll.set_propagate_natural_height(True)
        felder_scroll.set_child(felder_box)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_vexpand(True)
        outer.set_hexpand(True)
        outer.append(felder_scroll)

        # --- Formatierungs-Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(4)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.add_css_class("linked")

        def _format_btn(label, tooltip, vor, nach=""):
            btn = Gtk.Button(label=label)
            btn.set_tooltip_text(tooltip)
            btn.connect("clicked", lambda _: self._text_einfuegen(vor, nach))
            toolbar.append(btn)

        _format_btn("B", "Fettdruck  \\textbf{…}", "\\textbf{", "}")
        _format_btn("I", "Kursiv  \\textit{…}", "\\textit{", "}")
        _format_btn("U", "Unterstrichen  \\underline{…}", "\\underline{", "}")

        for _ in range(1):
            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            sep.set_margin_start(4)
            sep.set_margin_end(4)
            toolbar.append(sep)

        _format_btn("¶", "Neuer Absatz", "\n\n")
        _format_btn("—", "Gedankenstrich  --", "--")
        _format_btn("\u201e\u201c", "Anführungszeichen  \\glqq...\\grqq{}", "\\glqq ", "\\grqq{}")

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep2.set_margin_start(4)
        sep2.set_margin_end(4)
        toolbar.append(sep2)

        _format_btn("•", "Aufzählung", "\\begin{itemize}\n  \\item ", "\n\\end{itemize}")
        _format_btn("1.", "Nummerierung", "\\begin{enumerate}\n  \\item ", "\n\\end{enumerate}")

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep3.set_margin_start(4)
        sep3.set_margin_end(4)
        toolbar.append(sep3)

        _format_btn("\u21b5", "Zeilenumbruch  \\\\", "\\\\\n")
        _format_btn("…", "Auslassungspunkte  \\ldots", "\\ldots{}")

        sep4 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep4.set_margin_start(4)
        sep4.set_margin_end(4)
        toolbar.append(sep4)

        ki_btn = Gtk.Button(label="KI")
        ki_btn.set_tooltip_text("Text mit Gemini KI generieren")
        ki_btn.connect("clicked", lambda _: self._ki_dialog())
        toolbar.append(ki_btn)

        outer.append(toolbar)
        outer.append(Gtk.Separator())

        self._source_view = GtkSource.View()
        self._source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self._source_view.set_monospace(False)
        self._source_view.set_show_line_numbers(False)
        self._source_view.set_auto_indent(True)
        self._source_view.set_vexpand(True)
        self._source_view.set_pixels_above_lines(2)
        self._source_view.set_pixels_below_lines(2)
        self._source_view.set_left_margin(8)
        self._source_view.set_right_margin(8)
        self._source_view.set_top_margin(8)
        self._source_view.set_bottom_margin(8)

        self._source_buffer = self._source_view.get_buffer()
        self._source_buffer.connect("changed", self._eingabe_geaendert)

        text_scroll = Gtk.ScrolledWindow()
        text_scroll.set_vexpand(True)
        text_scroll.set_hexpand(True)
        text_scroll.set_child(self._source_view)

        text_frame = Gtk.Frame()
        text_frame.set_vexpand(True)
        text_frame.set_hexpand(True)
        text_frame.set_margin_start(12)
        text_frame.set_margin_end(12)
        text_frame.set_margin_bottom(12)
        text_frame.set_child(text_scroll)
        outer.append(text_frame)
        return outer

    def _baue_vorschauseite(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Toolbar mit CenterBox: Zoom zentriert, PDF-Aktionen rechts
        toolbar = Gtk.CenterBox()
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        toolbar.set_margin_start(6)
        toolbar.set_margin_end(6)

        # Zoom-Steuerung (Mitte)
        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        zoom_out = Gtk.Button(icon_name="zoom-out-symbolic")
        zoom_out.connect("clicked", lambda _: self._zoom_aendern(-0.1))
        zoom_box.append(zoom_out)

        self._zoom_label = Gtk.Label(label="Auto")
        self._zoom_label.set_size_request(55, -1)
        zoom_box.append(self._zoom_label)

        zoom_in = Gtk.Button(icon_name="zoom-in-symbolic")
        zoom_in.connect("clicked", lambda _: self._zoom_aendern(0.1))
        zoom_box.append(zoom_in)

        zoom_fit_btn = Gtk.Button(icon_name="zoom-fit-best-symbolic")
        zoom_fit_btn.set_tooltip_text("An Breite anpassen")
        zoom_fit_btn.connect("clicked", lambda _: self._zoom_anpassen())
        zoom_box.append(zoom_fit_btn)

        toolbar.set_center_widget(zoom_box)

        # PDF-Aktionen (rechts)
        aktionen_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        speichern_btn = Gtk.Button(icon_name="document-save-symbolic")
        speichern_btn.set_tooltip_text("PDF speichern")
        speichern_btn.connect("clicked", self._speichern_als)
        aktionen_box.append(speichern_btn)

        drucken_btn = Gtk.Button(icon_name="printer-symbolic")
        drucken_btn.set_tooltip_text("Drucken")
        drucken_btn.connect("clicked", self._drucken)
        aktionen_box.append(drucken_btn)

        kompilier_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        kompilier_btn.set_tooltip_text("Neu kompilieren")
        kompilier_btn.add_css_class("suggested-action")
        kompilier_btn.connect("clicked", lambda _: self._kompiliere_jetzt())
        aktionen_box.append(kompilier_btn)

        toolbar.set_end_widget(aktionen_box)

        box.append(toolbar)

        self._vorschau = PdfVorschau(zoom_geaendert_cb=self._zoom_label_aktualisieren)
        self._vorschau.zeige_info("Warten auf Eingabe …")
        box.append(self._vorschau)

        return box

    # ------------------------------------------------------------------ #
    # Absender-Verwaltung
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Sitzungszustand
    # ------------------------------------------------------------------ #

    def _sitzung_laden(self):
        zustand = session.laden()

        # Fenstergröße wiederherstellen
        breite = zustand.get("fenster_breite", 1200)
        hoehe = zustand.get("fenster_hoehe", 800)
        self.set_default_size(breite, hoehe)

        # Paned-Position nach erstem Layout-Durchlauf setzen
        paned_pos = zustand.get("paned_position")

        def _layout_fertig(*_):
            breite = self.get_width()
            if breite < 100:
                return True  # Fenster noch nicht dargestellt, erneut versuchen
            if paned_pos:
                self._paned.set_position(paned_pos)
            else:
                self._paned.set_position(int(breite * 0.40))
            return False

        GLib.idle_add(_layout_fertig)

        # Absender laden und auswählen
        self._lade_absender_liste(auswahl_id=zustand.get("absender_id"))

        # Empfänger laden und auswählen
        self._lade_empfaenger_liste(auswahl_id=zustand.get("empfaenger_id"))

        # Brieftext wiederherstellen
        if zustand.get("brieftext"):
            self._source_buffer.set_text(zustand["brieftext"])

        # Betreff / Anrede / Grußformel
        if zustand.get("subject"):
            self._subject.set_text(zustand["subject"])
        if zustand.get("opening"):
            self._opening.set_text(zustand["opening"])
        if zustand.get("closing"):
            self._closing.set_text(zustand["closing"])

    def _beim_schliessen(self, *_):
        buf = self._source_buffer
        zustand = {
            "absender_id": self._aktiver_absender.get("id") if self._aktiver_absender else None,
            "empfaenger_id": self._aktiver_empfaenger.get("id") if self._aktiver_empfaenger else None,
            "brieftext": buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False),
            "subject": self._subject.get_text(),
            "opening": self._opening.get_text(),
            "closing": self._closing.get_text(),
            "fenster_breite": self.get_width(),
            "fenster_hoehe": self.get_height(),
            "paned_position": self._paned.get_position(),
        }
        session.speichern(zustand)
        return False  # Fenster normal schließen lassen

    def _lade_absender_liste(self, auswahl_id=None):
        self._absender_daten = [dict(r) for r in db.alle_absender()]
        while self._absender_string_liste.get_n_items() > 0:
            self._absender_string_liste.remove(0)
        for a in self._absender_daten:
            self._absender_string_liste.append(a["name"])
        if not self._absender_daten:
            return
        # Gespeicherte Auswahl wiederherstellen, sonst ersten Eintrag nehmen
        if auswahl_id is not None:
            for i, a in enumerate(self._absender_daten):
                if a["id"] == auswahl_id:
                    self._absender_dropdown.set_selected(i)
                    self._aktiver_absender = a
                    return
        self._absender_dropdown.set_selected(0)
        self._aktiver_absender = self._absender_daten[0]

    def _absender_geaendert(self, dropdown, _param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._absender_daten):
            self._aktiver_absender = dict(self._absender_daten[idx])
            self._starte_debounce()

    def _absender_neu_dialog(self, _btn):
        self._absender_dialog(None)

    def _absender_bearbeiten_dialog(self, _btn):
        self._absender_dialog(self._aktiver_absender)

    def _absender_dialog(self, daten):
        dialog = Adw.Dialog()
        dialog.set_title("Absender" if daten is None else "Absender bearbeiten")
        dialog.set_content_width(400)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        seite = Adw.PreferencesPage()
        gruppe = Adw.PreferencesGroup()

        felder = {}
        for schluessel, titel in [
            ("name", "Name"),
            ("strasse", "Straße"),
            ("plz", "PLZ"),
            ("ort", "Ort"),
            ("telefon", "Telefon"),
            ("email", "E-Mail"),
            ("logo_pfad", "Logo-Pfad"),
        ]:
            zeile = Adw.EntryRow(title=titel)
            if daten and daten.get(schluessel):
                zeile.set_text(daten[schluessel])
            gruppe.add(zeile)
            felder[schluessel] = zeile

        seite.add(gruppe)

        speichern_btn = Gtk.Button(label="Speichern")
        speichern_btn.add_css_class("suggested-action")

        def _speichern(_btn):
            werte = {k: felder[k].get_text() for k in felder}
            if not werte["name"].strip():
                return
            if daten is None:
                db.absender_speichern(**werte)
            else:
                db.absender_aktualisieren(daten["id"], **werte)
            self._lade_absender_liste()
            dialog.close()

        speichern_btn.connect("clicked", _speichern)
        header.pack_end(speichern_btn)

        toolbar_view.set_content(seite)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    # ------------------------------------------------------------------ #
    # Empfänger-Dialog / Adressbuch
    # ------------------------------------------------------------------ #

    def _lade_empfaenger_liste(self, auswahl_id=None):
        self._empfaenger_daten = [dict(r) for r in db.alle_empfaenger()]
        while self._empfaenger_string_liste.get_n_items() > 0:
            self._empfaenger_string_liste.remove(0)
        for e in self._empfaenger_daten:
            self._empfaenger_string_liste.append(e["name"])
        # Auswahl wiederherstellen
        if auswahl_id is not None:
            for i, e in enumerate(self._empfaenger_daten):
                if e["id"] == auswahl_id:
                    self._empfaenger_dropdown.set_selected(i)
                    self._aktiver_empfaenger = e
                    return
        if self._empfaenger_daten:
            self._empfaenger_dropdown.set_selected(0)
            self._aktiver_empfaenger = self._empfaenger_daten[0]
        else:
            self._aktiver_empfaenger = {"name": "", "strasse": "", "plz": "", "ort": ""}

    def _empfaenger_geaendert(self, dropdown, _param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._empfaenger_daten):
            self._aktiver_empfaenger = self._empfaenger_daten[idx]
            self._starte_debounce()

    def _empfaenger_neu_dialog(self, _btn):
        self._empfaenger_dialog(None)

    def _empfaenger_bearbeiten_dialog(self, _btn):
        self._empfaenger_dialog(self._aktiver_empfaenger)

    def _empfaenger_dialog(self, daten):
        dialog = Adw.Dialog()
        dialog.set_title("Empfänger" if daten is None else "Empfänger bearbeiten")
        dialog.set_content_width(400)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        seite = Adw.PreferencesPage()
        gruppe = Adw.PreferencesGroup()

        felder = {}
        for schluessel, titel in [
            ("name", "Name / Firma"),
            ("strasse", "Straße"),
            ("plz", "PLZ"),
            ("ort", "Ort"),
        ]:
            zeile = Adw.EntryRow(title=titel)
            if daten and daten.get(schluessel):
                zeile.set_text(daten[schluessel])
            gruppe.add(zeile)
            felder[schluessel] = zeile

        if daten:
            loeschen_gruppe = Adw.PreferencesGroup()
            loeschen_btn_row = Adw.ButtonRow(title="Empfänger löschen")
            loeschen_btn_row.add_css_class("destructive-action")

            def _loeschen(_row):
                bestaetig = Adw.AlertDialog(
                    heading="Empfänger löschen?",
                    body=f"{daten['name']} aus dem Adressbuch entfernen?",
                )
                bestaetig.add_response("abbrechen", "Abbrechen")
                bestaetig.add_response("loeschen", "Löschen")
                bestaetig.set_response_appearance("loeschen", Adw.ResponseAppearance.DESTRUCTIVE)
                bestaetig.set_default_response("abbrechen")

                def _bestaetigt(d, response):
                    if response == "loeschen":
                        db.empfaenger_loeschen(daten["id"])
                        self._aktiver_empfaenger = {"name": "", "strasse": "", "plz": "", "ort": ""}
                        if self._kompilier_timer is not None:
                            GLib.source_remove(self._kompilier_timer)
                            self._kompilier_timer = None
                        self._lade_empfaenger_liste()
                        dialog.close()

                bestaetig.connect("response", _bestaetigt)
                bestaetig.present(dialog)

            loeschen_btn_row.connect("activated", _loeschen)
            loeschen_gruppe.add(loeschen_btn_row)
            seite.add(loeschen_gruppe)

        seite.add(gruppe)

        speichern_btn = Gtk.Button(label="Speichern")
        speichern_btn.add_css_class("suggested-action")

        def _speichern(_btn):
            werte = {k: felder[k].get_text().strip() for k in felder}
            if not werte["name"]:
                return
            if daten is None:
                new_id = db.empfaenger_speichern_oder_aktualisieren(
                    werte["name"], werte["strasse"], werte["plz"], werte["ort"]
                )
                self._lade_empfaenger_liste(auswahl_id=new_id)
            else:
                db.empfaenger_loeschen(daten["id"])
                new_id = db.empfaenger_speichern_oder_aktualisieren(
                    werte["name"], werte["strasse"], werte["plz"], werte["ort"]
                )
                self._lade_empfaenger_liste(auswahl_id=new_id)
            self._starte_debounce()
            dialog.close()

        speichern_btn.connect("clicked", _speichern)
        header.pack_end(speichern_btn)

        toolbar_view.set_content(seite)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    # ------------------------------------------------------------------ #
    # Textformatierung
    # ------------------------------------------------------------------ #

    def _text_einfuegen(self, vor: str, nach: str = ""):
        buf = self._source_buffer
        if buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            text = buf.get_text(start, end, False)
            buf.delete(start, end)
            buf.insert(buf.get_iter_at_offset(start.get_offset()), vor + text + nach)
        else:
            buf.insert_at_cursor(vor + nach)
            if nach:
                it = buf.get_iter_at_mark(buf.get_insert())
                it.backward_chars(len(nach))
                buf.place_cursor(it)
        self._source_view.grab_focus()

    # ------------------------------------------------------------------ #
    # Debounce & Kompilierung
    # ------------------------------------------------------------------ #

    def _eingabe_geaendert(self, *_args):
        self._starte_debounce()

    def _starte_debounce(self):
        if self._kompilier_timer is not None:
            GLib.source_remove(self._kompilier_timer)
        self._kompilier_timer = GLib.timeout_add(DEBOUNCE_MS, self._kompiliere_jetzt)

    def _kompiliere_jetzt(self):
        self._kompilier_timer = None

        if not self._aktiver_empfaenger.get("name"):
            self._vorschau.zeige_info("Bitte zuerst einen Empfänger angeben.")
            return GLib.SOURCE_REMOVE

        daten = self._sammle_daten()
        if not daten:
            return GLib.SOURCE_REMOVE

        self._vorschau.zeige_info("Kompiliere …")

        def _fertig(pdf_pfad, fehler):
            GLib.idle_add(self._kompilierung_fertig, pdf_pfad, fehler)

        latex_builder.kompiliere_brief(daten, _fertig)
        return GLib.SOURCE_REMOVE

    def _kompilierung_fertig(self, pdf_pfad, fehler):
        if pdf_pfad:
            self._aktuelles_pdf = pdf_pfad
            self._vorschau.lade_pdf(pdf_pfad)
        else:
            self._vorschau.zeige_fehler(fehler or "Unbekannter Fehler")

    def _sammle_daten(self):
        buf = self._source_buffer
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

        e = self._aktiver_empfaenger
        daten = {
            "body": text,
            "to_name": e.get("name", ""),
            "to_street": e.get("strasse", ""),
            "to_zip": e.get("plz", ""),
            "to_city": e.get("ort", ""),
            "subject": self._subject.get_text(),
            "opening": self._opening.get_text(),
            "closing": self._closing.get_text(),
        }

        if self._aktiver_absender:
            a = self._aktiver_absender
            daten.update({
                "from_name": a.get("name", ""),
                "from_street": a.get("strasse", ""),
                "from_zip": a.get("plz", ""),
                "from_city": a.get("ort", ""),
                "from_phone": a.get("telefon", ""),
                "from_email": a.get("email", ""),
                "from_logo": a.get("logo_pfad", ""),
            })

        return daten

    # ------------------------------------------------------------------ #
    # Speichern & Drucken
    # ------------------------------------------------------------------ #

    def _dateiname_vorschlag(self):
        import datetime
        import re
        datum = datetime.date.today().strftime("%Y-%m-%d")
        name = self._aktiver_empfaenger.get("name", "").strip() or "unbekannt"
        name_sauber = re.sub(r"[^\w\-]", "_", name)
        return f"{datum}-{name_sauber}-gbrief.pdf"

    def _speichern_als(self, _btn):
        if not self._aktuelles_pdf:
            self._zeige_fehler_dialog("Bitte zuerst einen Brief kompilieren.")
            return

        dialog = Gtk.FileDialog()
        dialog.set_title("PDF speichern")
        dialog.set_initial_name(self._dateiname_vorschlag())

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF-Dateien")
        filter_pdf.add_mime_type("application/pdf")
        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        filter_store.append(filter_pdf)
        dialog.set_filters(filter_store)
        dialog.set_default_filter(filter_pdf)

        dialog.save(self, None, self._speichern_fertig)

    def _speichern_fertig(self, dialog, result):
        try:
            datei = dialog.save_finish(result)
            ziel = datei.get_path()
            shutil.copy2(self._aktuelles_pdf, ziel)
        except GLib.Error:
            pass

    def _drucken(self, _btn):
        if not self._aktuelles_pdf:
            self._zeige_fehler_dialog("Bitte zuerst einen Brief kompilieren.")
            return

        uri = GLib.filename_to_uri(self._aktuelles_pdf, None)
        doc = Poppler.Document.new_from_file(uri, None)

        op = Gtk.PrintOperation()
        op.set_n_pages(doc.get_n_pages())
        op.set_job_name("gbrief")

        def _seite_zeichnen(operation, ctx, seiten_nr):
            cr = ctx.get_cairo_context()
            seite = doc.get_page(seiten_nr)
            s_breite, s_hoehe = seite.get_size()
            skalierung = min(ctx.get_width() / s_breite, ctx.get_height() / s_hoehe)
            cr.scale(skalierung, skalierung)
            seite.render(cr)

        op.connect("draw-page", _seite_zeichnen)
        op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self)

    # ------------------------------------------------------------------ #
    # KI-Textgenerierung (Gemini)
    # ------------------------------------------------------------------ #

    def _ki_dialog(self):
        api_key = ai_generator.lade_api_key()
        if not api_key:
            self._api_key_dialog(danach=self._ki_dialog)
            return

        dialog = Adw.Dialog()
        dialog.set_title("Text mit KI generieren")
        dialog.set_content_width(420)

        toolbar_view = Adw.ToolbarView()
        ki_header = Adw.HeaderBar()
        toolbar_view.add_top_bar(ki_header)

        seite = Adw.PreferencesPage()

        eingabe_gruppe = Adw.PreferencesGroup(title="Inhalt")

        stichpunkte_zeile = Adw.EntryRow(title="Stichpunkte")
        stichpunkte_zeile.set_tooltip_text("z. B.: Kündigung zum nächstmöglichen Termin, Bitte um Bestätigung")
        eingabe_gruppe.add(stichpunkte_zeile)

        stil_auswahl = Gtk.StringList()
        for s in ai_generator.STILE:
            stil_auswahl.append(s)
        stil_zeile = Adw.ComboRow(title="Stil")
        stil_zeile.set_model(stil_auswahl)
        eingabe_gruppe.add(stil_zeile)

        seite.add(eingabe_gruppe)

        status_gruppe = Adw.PreferencesGroup()
        self._ki_status_zeile = Adw.ActionRow(title="")
        self._ki_status_zeile.set_visible(False)
        status_gruppe.add(self._ki_status_zeile)
        seite.add(status_gruppe)

        toolbar_view.set_content(seite)

        generieren_btn = Gtk.Button(label="Generieren")
        generieren_btn.add_css_class("suggested-action")

        def _generieren(_btn):
            stichpunkte = stichpunkte_zeile.get_text().strip()
            if not stichpunkte:
                return
            stil = ai_generator.STILE[stil_zeile.get_selected()]
            generieren_btn.set_sensitive(False)
            self._ki_status_zeile.set_title("Generiere Text …")
            self._ki_status_zeile.set_visible(True)

            def _callback(text, fehler):
                def _im_hauptthread():
                    generieren_btn.set_sensitive(True)
                    self._ki_status_zeile.set_visible(False)
                    if text:
                        buf = self._source_buffer
                        buf.set_text(text)
                        dialog.close()
                    else:
                        self._ki_status_zeile.set_title(fehler or "Unbekannter Fehler")
                        self._ki_status_zeile.set_visible(True)
                GLib.idle_add(_im_hauptthread)

            ai_generator.generiere_text(api_key, stichpunkte, stil, _callback)

        generieren_btn.connect("clicked", _generieren)
        ki_header.pack_end(generieren_btn)

        api_key_btn = Gtk.Button(icon_name="preferences-system-symbolic")
        api_key_btn.set_tooltip_text("API-Key ändern")
        api_key_btn.connect("clicked", lambda _: (
            dialog.close(),
            self._api_key_dialog(danach=self._ki_dialog),
        ))
        ki_header.pack_start(api_key_btn)

        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _api_key_dialog(self, danach=None):
        dialog = Adw.Dialog()
        dialog.set_title("Gemini API-Key")
        dialog.set_content_width(420)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        seite = Adw.PreferencesPage()
        gruppe = Adw.PreferencesGroup(
            title="Google Gemini API-Key",
            description='Kostenlosen Key unter aistudio.google.com erstellen.',
        )

        key_zeile = Adw.PasswordEntryRow(title="API-Key")
        vorhandener = ai_generator.lade_api_key()
        if vorhandener:
            key_zeile.set_text(vorhandener)
        gruppe.add(key_zeile)
        seite.add(gruppe)
        toolbar_view.set_content(seite)

        speichern_btn = Gtk.Button(label="Speichern")
        speichern_btn.add_css_class("suggested-action")

        def _speichern(_btn):
            key = key_zeile.get_text().strip()
            if not key:
                return
            ai_generator.speichere_api_key(key)
            dialog.close()
            if danach:
                danach()

        speichern_btn.connect("clicked", _speichern)
        header.pack_end(speichern_btn)

        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _info_dialog(self):
        dialog = Adw.Dialog()
        dialog.set_title("Über gbrief")
        dialog.set_content_width(380)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        icon = Gtk.Image.new_from_icon_name("de.xhomie.gbrief")
        icon.set_pixel_size(64)
        box.append(icon)

        titel = Gtk.Label(label="<b>gbrief</b>")
        titel.set_use_markup(True)
        box.append(titel)

        beschreibung = Gtk.Label(
            label="Professionelle Briefe im DIN-5008-Stil schreiben\nund als PDF exportieren.\n\nNutzt LaTeX (KOMA-Script scrlttr2) im Hintergrund\nmit einer modernen GTK4/Adwaita-Oberfläche."
        )
        beschreibung.set_justify(Gtk.Justification.CENTER)
        beschreibung.set_wrap(True)
        box.append(beschreibung)

        link = Gtk.LinkButton.new_with_label(
            "https://github.com/x-ingo/gbrief", "GitHub-Projekt"
        )
        box.append(link)

        toolbar_view.set_content(box)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _zeige_fehler_dialog(self, meldung):
        dialog = Adw.AlertDialog(heading="Hinweis", body=meldung)
        dialog.add_response("ok", "OK")
        dialog.present(self)

    # ------------------------------------------------------------------ #
    # Zoom
    # ------------------------------------------------------------------ #

    def _zoom_label_aktualisieren(self, zoom: float):
        self._zoom_label.set_label(f"{int(zoom * 100)}%")

    def _zoom_aendern(self, delta):
        self._vorschau.setze_zoom(self._vorschau._zoom + delta, auto=False)

    def _zoom_anpassen(self):
        self._vorschau.zoom_an_breite_anpassen()
