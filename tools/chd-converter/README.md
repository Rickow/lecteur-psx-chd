# Convertisseur ISO/BIN/CUE → CHD

Convertit vos images de disque (`.cue`, `.bin`, `.iso`, `.gdi`, `.toc`, `.nrg`) au format
**CHD** (compressé, idéal pour ce lecteur) en s'appuyant sur **`chdman`** (outil MAME).

## Prérequis

`chdman` :
- Debian/Ubuntu : `sudo apt install mame-tools`
- Fedora : `sudo dnf install mame-tools` · Arch : `sudo pacman -S mame-tools`
- macOS : `brew install rom-tools`

Pour l'interface native (`iso2chd_app.py`) : aussi `python3-tk`
(`sudo apt install python3-tk`).

## Trois façons de l'utiliser

| Fichier | Usage |
|---|---|
| **`iso2chd.py`** | ligne de commande (lot, récursif, options) |
| **`iso2chd_app.py`** | fenêtre native (Tkinter) : explorateur + barre de progression |
| **`iso2chd_gui.py`** | interface web locale (aucune dépendance graphique) |

```bash
python3 iso2chd.py mon-jeu.cue                 # → mon-jeu.chd
python3 iso2chd.py /mes/roms -r -o /sortie     # tout un dossier, récursif
python3 iso2chd.py disque.bin                  # .bin isolé → cue temporaire auto
python3 iso2chd_app.py                         # interface fenêtrée
```

Détection intelligente : un `.bin` référencé par un `.cue` est géré via le `.cue` ; un
`.bin` isolé reçoit un cue temporaire automatique. Vérification SHA1 optionnelle
(`--verify`). `python3 iso2chd.py --help` pour toutes les options.
