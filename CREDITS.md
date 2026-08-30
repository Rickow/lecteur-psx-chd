# Crédits & licences

Ce projet **ne fait qu'assembler** des briques open source remarquables. Tout le mérite
de l'émulation revient à leurs auteurs. Merci à eux.

## Composants embarqués / utilisés

| Composant | Rôle | Auteur·rice·s | Licence |
|---|---|---|---|
| **[pcsx_rearmed](https://github.com/notaz/pcsx_rearmed)** | Core d'émulation PlayStation (compilé en WASM, embarqué) | notaz & contributeurs (dérivé de PCSX / PCSX-ReARMed) | **GPL-2.0** |
| **[RetroArch](https://github.com/libretro/RetroArch)** | Frontend libretro / build emscripten (link du core en WASM threadé) | The RetroArch/Libretro Team | **GPL-3.0** |
| **[libchdr](https://github.com/rtissera/libchdr)** | Lecture/décompression des fichiers CHD (inclus dans pcsx_rearmed) | Romain Tisserand & al. | **BSD** |
| **[Nostalgist.js](https://github.com/arianrhodsandlot/nostalgist)** | Pilotage du core libretro dans le navigateur (loader, input, config) | arianrhodsandlot | **MIT** |
| **[Emscripten](https://emscripten.org/)** | Compilation C/C++ → WebAssembly | Emscripten Contributors | **MIT / NCSA** |
| **[chdman](https://www.mamedev.org/) (MAME tools)** | Conversion CD/DVD → CHD (outil `tools/chd-converter`) | MAMEdev | **GPL-2.0 / BSD-3-Clause** |
| **coi-serviceworker (pattern)** | Injection COOP/COEP via service worker | Guido Zuidhof (idée) | **MIT** |

### Versions épinglées (core embarqué)

- pcsx_rearmed : commit `ba61a4f`
- RetroArch : commit `282a12d`
- Emscripten : 6.0.8
- chdman : MAME 0.285

## Licence de ce dépôt

Le core embarqué combine du code **GPL-2.0** (pcsx_rearmed) linké via **RetroArch
(GPL-3.0)**. L'œuvre combinée est donc distribuée sous **GPL-3.0-or-later** (voir
[`LICENSE`](LICENSE)). Les sources permettant de reconstruire le binaire embarqué sont
fournies dans [`build/`](build/).

Le code applicatif original de ce dépôt (interface `lecteur-psx.html`, service worker,
scripts de service et de conversion) est publié sous la même licence pour cohérence.

## ⚠️ Ce qui n'est PAS fourni (et ne le sera jamais)

- **Aucun BIOS** PlayStation (`scph*.bin`) — protégé par le droit d'auteur de Sony.
  Le lecteur fonctionne en **HLE** (BIOS simulé) ou avec **votre propre** BIOS.
- **Aucun jeu** / image disque — n'utilisez que des sauvegardes de **vos propres** jeux.

« PlayStation » et « PS1 » sont des marques de Sony Interactive Entertainment. Ce projet
n'est ni affilié, ni approuvé par Sony.
