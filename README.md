# gbrief – GNOME Briefschreiber

Professionelle Briefe im DIN-5008-Stil direkt am Desktop schreiben und als PDF exportieren. gbrief nutzt LaTeX (KOMA-Script `scrlttr2`) im Hintergrund und bietet eine moderne GTK4/Adwaita-Oberfläche.

![Screenshot Platzhalter](https://github.com/x-ingo/gbrief/releases)

## Features

- Absender-Verwaltung mit optionalem Firmenlogo
- Empfänger-Datenbank mit Autovervollständigung
- Live-Vorschau des fertigen Briefes als PDF
- Sitzungsspeicherung (letzter Zustand wird wiederhergestellt)
- Lokale Datenhaltung in `~/.local/share/gbrief/`

## Installation

### Debian/Ubuntu – fertiges Paket

Das `.deb`-Paket von der [Releases-Seite](https://github.com/x-ingo/gbrief/releases) herunterladen und installieren:

```bash
sudo dpkg -i gbrief_*.deb
sudo apt-get install -f   # fehlende Abhängigkeiten nachinstallieren
```

Danach ist gbrief im Anwendungsmenü unter **Büro** zu finden und per Terminal mit `gbrief` startbar.

### Aus dem Quellcode starten

**Voraussetzungen:**

```bash
sudo apt-get install \
  python3 python3-gi \
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gtksource-5 gir1.2-poppler-0.18 \
  latexmk texlive-latex-recommended texlive-lang-german
```

**Starten:**

```bash
git clone https://github.com/x-ingo/gbrief.git
cd gbrief
python3 main.py
```

Beim ersten Start werden Icon und Desktop-Eintrag automatisch im Benutzerverzeichnis eingerichtet.

## Datenspeicherung

Alle Nutzerdaten liegen ausschließlich lokal:

| Datei | Inhalt |
|---|---|
| `~/.local/share/gbrief/gbrief.db` | Absender und Empfänger (SQLite) |
| `~/.local/share/gbrief/session.json` | Letzter Sitzungszustand |

## Technologie

- [GTK4](https://gtk.org/) + [Adwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/) – UI-Framework
- [GtkSourceView 5](https://wiki.gnome.org/Projects/GtkSourceView) – Texteditor
- [Poppler](https://poppler.freedesktop.org/) – PDF-Vorschau
- [KOMA-Script scrlttr2](https://www.ctan.org/pkg/koma-script) – Briefsatz mit LaTeX
- [latexmk](https://ctan.org/pkg/latexmk) – LaTeX-Kompilierung

## Lizenz

[GPL v3](LICENSE) — Weiterentwicklungen müssen ebenfalls als Open Source veröffentlicht werden.
