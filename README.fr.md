*(Version française — [English version](README.md))*

# 🎮 Lecteur PSX CHD

**Un émulateur PlayStation (PS1) dans une seule page web**, pensé pour tourner en **PWA
sur iPhone** (Safari) — mais qui marche aussi sur Firefox et Chrome desktop.

Chargez un jeu au format **`.chd`** (ou `.cue/.bin`, `.iso`, `.pbp`…), et jouez : image,
son, **contrôles tactiles**, sauvegardes d'état, historique. Tout reste **local** — rien
n'est envoyé sur un serveur.

> ⚙️ Ce projet **assemble** des briques open source exceptionnelles (voir
> [CREDITS.md](CREDITS.md)). Le mérite de l'émulation revient à leurs auteurs.

![Lecteur PSX CHD](screenshots/banner.svg)

> 📸 *Les vraies captures sont les bienvenues — déposez-les dans [`screenshots/`](screenshots/)
> (écran d'accueil, en jeu, manette tactile sur iPhone) et référencez-les ici.*

---

## ✨ Fonctionnalités

- ▶️ **Émulation PS1** via le core **pcsx_rearmed** compilé en WebAssembly (multi-thread).
- 📄 **Une seule page HTML autonome** (core + moteur inlinés) + un service worker.
- 📱 **PWA iPhone** : « Ajouter à l'écran d'accueil », jouable hors-ligne.
- 🕹️ **Manette tactile** à l'écran (D-pad, ○✕□△, L/R, Start/Select, sticks) **et** clavier.
- 💾 **Sauvegardes d'état** (en page, export/import fichier) + **carte mémoire**.
- ⏱️ **Sauvegarde automatique** toutes les 30 s (filet anti-crash).
- 🗂️ **Historique** des jeux récents, avec reprise.
- 🧠 **Optimisé mémoire** : gros jeux (Final Fantasy VII/VIII) jouables sur iPhone.
- 🌍 **Multi-langue de disques** : gestion **SBI** (protection *libcrypt*, jeux PAL).
- 🗜️ **Outil de conversion** ISO/BIN/CUE → **CHD** inclus (`tools/chd-converter`).

## 🧩 Basé sur

| Brique | Rôle |
|---|---|
| [pcsx_rearmed](https://github.com/notaz/pcsx_rearmed) | core d'émulation PS1 |
| [RetroArch](https://github.com/libretro/RetroArch) | build emscripten / frontend libretro |
| [libchdr](https://github.com/rtissera/libchdr) | lecture des fichiers CHD |
| [Nostalgist.js](https://github.com/arianrhodsandlot/nostalgist) | pilotage du core dans le navigateur |
| [Emscripten](https://emscripten.org/) | compilation C → WebAssembly |
| [chdman (MAME)](https://www.mamedev.org/) | conversion CD/DVD → CHD |

Détails, versions épinglées et licences : **[CREDITS.md](CREDITS.md)**.

## 🛠️ Comment ça marche (en bref)

Core **threadé** (pthreads) → nécessite `SharedArrayBuffer` → nécessite un **contexte
isolé** (en-têtes COOP/COEP fournis par le service worker). Rendu **WebGL2** via
**OffscreenCanvas** dans le thread de rendu. Le disque **CHD** (compressé) est écrit par
morceaux dans le système de fichiers virtuel pour tenir dans la mémoire d'un iPhone.

Le détail des **défis et solutions** (chargement d'un core threadé inliné, WebGL entre
threads, COOP/COEP, mémoire, SBI, l'impasse WORKERFS…) est dans
**[docs/architecture.md](docs/architecture.md)**.

---

## 🚀 Utilisation

### Il vous faut
- Un jeu **dont vous possédez le disque**, de préférence au format **`.chd`** (compressé,
  léger). Pour convertir vos ISO/BIN/CUE en CHD → voir [`tools/chd-converter`](tools/chd-converter).
- (Optionnel) un **BIOS PlayStation** (`scph*.bin`) — sinon le lecteur utilise le **HLE**
  (BIOS simulé). **Le BIOS n'est pas fourni** (droit d'auteur Sony).

### Tester en local (PC)

⚠️ Ne fonctionne **pas** en double-clic (`file://`) : le core threadé exige un contexte
servi avec COOP/COEP. Utilisez le petit serveur fourni :

```bash
python3 serve/lancer_lecteur_psx.py
```

Il sert la page avec les bons en-têtes et ouvre votre navigateur sur
`http://127.0.0.1:8901/lecteur-psx.html`.

> **Brave/Chrome** : si l'écran est noir, l'accélération GPU est probablement désactivée
> (`brave://gpu` → `WebGL: Disabled`). Activez `brave://flags/#ignore-gpu-blocklist`
> (*Enabled*) et l'accélération matérielle, ou utilisez **Firefox**.

### Installer en PWA sur iPhone

1. Servez `lecteur-psx.html` **+ `sw.js`** en **https** (indispensable pour l'isolation).
   Un hébergeur statique gratuit (GitHub Pages, Netlify…) convient : le `sw.js` fournit
   les en-têtes COOP/COEP.
2. Ouvrez l'URL dans **Safari** → **Partager** → **Sur l'écran d'accueil**.
3. Lancez depuis l'icône, chargez un `.chd`, jouez.

> Astuce : GitHub Pages sert bien la page, mais n'envoie pas COOP/COEP → c'est le `sw.js`
> (déjà inclus) qui s'en charge après le premier chargement.

### Convertir vos disques en CHD

Voir [`tools/chd-converter/README`](tools/chd-converter). En résumé (nécessite `chdman`,
paquet `mame-tools`) :

```bash
python3 tools/chd-converter/iso2chd.py mon-jeu.cue      # → mon-jeu.chd
python3 tools/chd-converter/iso2chd_app.py             # interface graphique (Tkinter)
```

## 📦 Formats supportés

`.chd` (recommandé), `.pbp`, `.cue`+`.bin`, `.iso`, `.img`, `.mdf`, `.m3u`, plus `.sbi`
(protection libcrypt — sélectionnez le `.chd` **et** son `.sbi` ensemble).

## 🔧 Reconstruire le core depuis les sources

Le core WASM embarqué est reproductible from scratch :

```bash
cd build && ./build.sh
```

Voir **[build/README.md](build/README.md)** (⚠️ chemin **sans espace** obligatoire).

## 🧭 Limites & feuille de route

- **Mono-disque** aujourd'hui → **multi-disque** (FF7 = 3 CD, changement en jeu) à venir.
- **Interpréteur** (pas de dynarec, iOS interdit le JIT) : plein régime pour FF et la
  plupart des jeux ; les gros 3D peuvent parfois dépasser le budget.
- **Lazy loading** du CHD (RAM minimale) : prouvé faisable, non encore branché.

## 📜 Licence

**GPL-3.0-or-later** — le core embarqué combine du code GPL-2.0 (pcsx_rearmed) linké via
RetroArch (GPL-3.0). Voir [LICENSE](LICENSE) et [CREDITS.md](CREDITS.md). Les sources de
build sont fournies dans [`build/`](build/).

### ⚠️ Ni BIOS, ni jeux
Ce dépôt **ne contient aucun BIOS ni aucune ROM/jeu**. N'utilisez que des sauvegardes de
**vos propres** jeux. « PlayStation » est une marque de Sony Interactive Entertainment ;
projet non affilié.

## 🙏 Remerciements

À **notaz**, l'équipe **RetroArch/libretro**, **arianrhodsandlot** (Nostalgist.js),
**Romain Tisserand** (libchdr), les équipes **Emscripten** et **MAME**. Sans eux, rien de
tout ça ne serait possible.
