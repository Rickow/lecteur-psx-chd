# ISO/BIN/CUE → CHD converter

Converts your disc images (`.cue`, `.bin`, `.iso`, `.gdi`, `.toc`, `.nrg`) to the **CHD**
format (compressed, ideal for this player) using **`chdman`** (a MAME tool).

## Requirements

`chdman`:
- Debian/Ubuntu: `sudo apt install mame-tools`
- Fedora: `sudo dnf install mame-tools` · Arch: `sudo pacman -S mame-tools`
- macOS: `brew install rom-tools`

For the native GUI (`iso2chd_app.py`), also `python3-tk`
(`sudo apt install python3-tk`).

## Ways to use it

| File | Usage |
|---|---|
| **`iso2chd.py`** | command line (batch, recursive, options) |
| **`iso2chd_app.py`** | native window (Tkinter): file browser + progress bar |
| **`iso2chd_gui.py`** | local web UI (no GUI dependency) |
| **`Convertir-en-CHD.bat`** | **Windows, no Python** — drop it in a folder of disc images and double-click (needs only `chdman.exe` next to it or in PATH) |
| **`convertir-en-chd.sh`** | **Linux/macOS, no Python** — same idea: drop it in a folder of disc images and run it (needs only `chdman` in PATH) |

```bash
python3 iso2chd.py my-game.cue                 # → my-game.chd
python3 iso2chd.py /my/roms -r -o /out         # a whole folder, recursive
python3 iso2chd.py disc.bin                    # lone .bin → automatic temp cue
python3 iso2chd_app.py                         # windowed UI
```

Smart detection: a `.bin` referenced by a `.cue` is handled via the `.cue`; a lone `.bin`
gets an automatic temporary cue. Optional SHA1 verification (`--verify`).
Run `python3 iso2chd.py --help` for all options.

## Patching a game before conversion (`applyppf.py`)

Some improvements are distributed as **`.ppf`** patches applied to the disc image (the `.bin`),
**before** converting to CHD:

- a **60 Hz (PAL60) patch** → a PAL game runs at full NTSC speed (no more 50 Hz slowdown);
- an **anti-libcrypt patch** → removes the copy protection, so the `.sbi` is no longer needed.

`applyppf.py` applies a PPF (1.0 / 2.0 / 3.0) to a `.bin`/`.iso`:

```bash
python3 applyppf.py game.bin patch60hz.ppf          # patches game.bin (keeps game.bin.bak)
python3 applyppf.py game.bin nolibcrypt.ppf -o game-patched.bin   # to a copy, original untouched
```

Then convert the patched image to CHD as usual. The patch applies to the **data track** (`.bin`),
not the `.cue`. You provide the `.ppf` for your specific game (this repo ships **no** patches).
