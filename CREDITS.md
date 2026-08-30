# Credits & licences

This project **only assembles** remarkable open-source building blocks. All emulation
credit belongs to their authors. Thank you.

## Bundled / used components

| Component | Role | Author(s) | Licence |
|---|---|---|---|
| **[pcsx_rearmed](https://github.com/notaz/pcsx_rearmed)** | PlayStation emulation core (compiled to WASM, embedded) | notaz & contributors (derived from PCSX / PCSX-ReARMed) | **GPL-2.0** |
| **[RetroArch](https://github.com/libretro/RetroArch)** | libretro frontend / emscripten build (links the core as threaded WASM) | The RetroArch/Libretro Team | **GPL-3.0** |
| **[libchdr](https://github.com/rtissera/libchdr)** | CHD reading/decompression (bundled in pcsx_rearmed) | Romain Tisserand & al. | **BSD** |
| **[Nostalgist.js](https://github.com/arianrhodsandlot/nostalgist)** | drives the libretro core in the browser (loader, input, config) | arianrhodsandlot | **MIT** |
| **[Emscripten](https://emscripten.org/)** | C/C++ → WebAssembly compilation | Emscripten Contributors | **MIT / NCSA** |
| **[chdman](https://www.mamedev.org/) (MAME tools)** | CD/DVD → CHD conversion (`tools/chd-converter`) | MAMEdev | **GPL-2.0 / BSD-3-Clause** |
| coi-serviceworker (pattern) | COOP/COEP injection via a service worker | Guido Zuidhof (idea) | **MIT** |

### Pinned versions (embedded core)

- pcsx_rearmed: commit `ba61a4f`
- RetroArch: commit `282a12d`
- Emscripten: 6.0.8
- chdman: MAME 0.285

## Licence of this repository

The embedded core combines **GPL-2.0** code (pcsx_rearmed) linked via **RetroArch
(GPL-3.0)**. The combined work is therefore distributed under **GPL-3.0-or-later** (see
[`LICENSE`](LICENSE)). The sources needed to rebuild the embedded binary are provided in
[`build/`](build/).

This repository's original application code (the `lecteur-psx.html` UI, the service worker,
the serving and conversion scripts) is released under the same licence for consistency.

## ⚠️ What is NOT provided (and never will be)

- **No PlayStation BIOS** (`scph*.bin`) — protected by Sony's copyright. The player works
  in **HLE** (simulated BIOS) or with **your own** BIOS.
- **No games** / disc images — only use backups of **your own** games.

"PlayStation" and "PS1" are trademarks of Sony Interactive Entertainment. This project is
neither affiliated with, nor endorsed by, Sony.
