*(Version française — [English](architecture.md))*

# Architecture & défis techniques

Ce document détaille **comment ça marche** et surtout **les problèmes rencontrés et leurs
solutions** — l'essentiel de l'effort de ce projet.

## Vue d'ensemble

Le lecteur est **une seule page HTML** qui embarque, en base64 :
- le **core pcsx_rearmed** compilé en WebAssembly (`.js` + `.wasm`) ;
- le moteur **Nostalgist.js** (UMD) qui pilote le core dans le navigateur.

Un **service worker** (`sw.js`) fournit le hors-ligne **et** les en-têtes d'isolation
(COOP/COEP) nécessaires au multi-threading. Cible principale : **iPhone en PWA** (Safari).

```
┌──────────────────── navigateur ────────────────────┐
│  Thread principal (UI, canvas, IndexedDB, fichiers) │
│     │  transfert OffscreenCanvas + proxy syscalls   │
│     ▼                                                │
│  em-pthread  ──►  RetroArch + pcsx_rearmed (WASM)    │
│                   rendu WebGL2, audio AudioWorklet   │
└──────────────────────────────────────────────────────┘
```

## Pourquoi un core *threadé* ?

pcsx_rearmed en émulation web n'a pas de dynarec (iOS interdit le JIT) → interpréteur.
Le build threadé (`PROXY_TO_PTHREAD`) sort l'émulateur du thread UI (fluidité) et permet
le rendu via **OffscreenCanvas**. Cela impose **SharedArrayBuffer**, donc un **contexte
isolé** (COOP/COEP).

---

## Les défis rencontrés (et résolus)

### 1. COOP/COEP sans serveur spécial
`SharedArrayBuffer` n'est disponible que si `crossOriginIsolated === true`, ce qui exige
les en-têtes `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy:
require-corp`. Un hébergeur statique ne les envoie pas forcément.

**Solution :** le **service worker** (`sw.js`) réécrit les réponses pour ajouter ces
en-têtes (pattern *coi-serviceworker*), fusionné avec le cache hors-ligne. L'app recharge
une fois au premier lancement pour obtenir l'isolation.
⚠️ Ne fonctionne qu'en **https** (ou `localhost`) — jamais en `file://`.

### 2. Charger un core threadé **inliné** (blob)
Le core est embarqué (pas servi comme fichier). Or emscripten (ES6 + pthreads) crée ses
workers ainsi : `new Worker(new URL("pcsx_rearmed_libretro.js", import.meta.url), {type:
"module"})`. Chargé depuis un **blob**, cela échoue de deux façons :
- `import.meta.url` d'un blob n'est **pas une base d'URL valide** → `Invalid base URL` ;
- un **module worker refuse un blob sans type MIME** (celui de Nostalgist est sans type).

**Solution :** l'app publie `globalThis.__PSX_CORE_URL = URL.createObjectURL(blob {type:
"text/javascript"})`, et un patch du core (`build/patch_core.py`) fait pointer les workers
pthread **et** l'AudioWorklet dessus. (WORKERFS lui aussi référencé mais inutilisé — voir §8.)

### 3. Rendu WebGL2 depuis le worker (OffscreenCanvas)
RetroArch crée son thread de rendu et lui **transfère le canvas** (`transferControlToOffscreen`),
puis `emscripten_webgl_create_context("#canvas")` dans le pthread. Chaque thread a sa
**propre table** de contextes WebGL (`GL.contexts`, indexée par `canvas.id`). Un contexte
détruit depuis un autre thread que celui qui l'a créé faisait planter le thread de rendu
(`Cannot read properties of undefined (reading 'GLctx')`).

**Solution :** garde-fou dans `GL.deleteContext` (patch) : si le contexte n'est pas dans
ce thread, on ne plante pas. Le rendu survit.

**Limite connue (Brave/Chromium) :** si l'accélération GPU est désactivée (fréquent sous
Linux — `brave://gpu` affiche `WebGL: Disabled`), `getContext('webgl2')` renvoie `null` →
écran noir. Ce n'est **pas** un bug du lecteur (Firefox fonctionne). L'app détecte
l'absence de WebGL2 et affiche un message clair. Correctif Brave :
`brave://flags/#ignore-gpu-blocklist` → *Enabled*.

### 4. API Nostalgist absentes du core récent
Nostalgist appelait des API emscripten disparues du core threadé :
- `Module.setCanvasSize(...)` → `TypeError` non rattrapé (le `catch` ne gérait que les
  `DOMException`) → échec du lancement. **Solution :** `resize()` rendu tolérant (repli
  sur `canvas.setAttribute`, ne lève plus).
- `JSEvents.eventHandlers` (gestion clavier) → `JSEvents` est `undefined` sur le thread
  principal en mode threadé. **Solution :** gardes défensives (`fireKeyboardEvent`,
  `updateKeyboardEventHandlers`, `exit`).

### 5. Contrôles tactiles en mode threadé
Le pad à l'écran passait par `JSEvents` (raccourci interne) → inopérant en threadé.

**Solution :** dispatcher un **vrai `KeyboardEvent`** sur le canvas. RetroArch écoute le
clavier sur `"#canvas"` (`emscripten_set_keydown_callback`, driver `rwebinput`) et lit le
champ `event.code` → un `KeyboardEvent` synthétique avec le bon `code` commande le jeu.

### 6. Sauvegardes d'état + SharedArrayBuffer + IndexedDB
En mode threadé, l'état renvoyé par `saveState()` est adossé à la **SharedArrayBuffer**
(tas WASM partagé). Or **IndexedDB refuse de stocker une vue SharedArrayBuffer**
(`DataCloneError`). Résultat : « Sauver état » échouait silencieusement, alors que
« Exporter état » marchait (le `Blob` d'export **copie** les octets).

**Solution :** copier dans un `ArrayBuffer` normal avant stockage
(`new Uint8Array(view)` si `view.buffer instanceof SharedArrayBuffer`), centralisé dans
la fonction de stockage.

### 7. Mémoire : les gros jeux (FF7/FF8) faisaient crasher l'onglet
Le disque était copié **2 à 3 fois** en RAM au chargement (lecture en ArrayBuffer, puis
`getUint8Array` → `createDataFile` → `readFile` → `writeFile` côté Nostalgist) → pic de
~1 Go pour un CD de FF (~450 Mo compressé) → Safari iOS tue l'onglet.

**Solution :** l'app passe l'objet `File` (non lu en RAM) et un `writeFile` patché
**écrit le disque par morceaux de 8 Mo** directement dans le système de fichiers. Pic
mémoire ≈ **1× la taille du disque**. (Le CHD étant compressé, un CD PS1 tient largement
en mémoire sur iPhone.)

### 8. WORKERFS : un cul-de-sac (documenté)
L'idée initiale était le **streaming WORKERFS** (lire le CHD par tranches sans le charger).
Vérifié dans le core : les syscalls fichiers d'un pthread sont **proxifiés vers le thread
principal** (`__syscall_openat → proxyToMainThread`), or `WORKERFS.mount` exige
`ENVIRONMENT_IS_WORKER` + `FileReaderSync` (worker uniquement). **Incompatible** avec ce
build RetroArch. Le mécanisme *lazy* alternatif (`createLazyFile`) a été **prouvé
faisable** (XHR synchrone *Range* « binary-string » sur blob URL → 206 + octets corrects
sous COEP) mais reste à implémenter (utile surtout pour le multi-disque).

### 9. CHD & SBI
- **CHD** : format compressé par *hunks*, décompressés à la demande par libchdr → faible
  empreinte de travail.
- **SBI** (protection *libcrypt*, jeux PAL) : pcsx_rearmed cherche le `.sbi` à côté de
  l'image, **même nom de base**. L'app écrit le `.sbi` en `game.sbi` pour matcher
  `game.chd` (sélectionner les deux fichiers ensemble).

---

## Confort / robustesse

- **Historique** « Jeux récents » (métadonnées seulement, pas les gros CHD → 0 stockage) ;
  reprise via re-sélection du fichier + rechargement automatique de la sauvegarde.
- **Sauvegarde automatique** toutes les 30 s (clé séparée, n'écrase pas la sauvegarde
  manuelle) — filet anti-crash ; la reprise charge la plus récente.
- **« Libérer la mémoire »** : sauvegarde + rechargement de page (RAM remise à zéro pour
  changer de jeu ; les sauvegardes persistent en IndexedDB).

## Limites & pistes

- **Mono-disque** pour l'instant ; le **multi-disque** (FF7 = 3 CD, changement de CD en
  jeu via `DISK_NEXT`) est la prochaine étape.
- Le **lazy loading** (§8) réduirait encore la RAM et faciliterait le multi-disque.
- **Interpréteur** (pas de dynarec) : parfait pour FF et la majorité des jeux ; les gros
  3D peuvent parfois ne pas tenir le plein framerate.
