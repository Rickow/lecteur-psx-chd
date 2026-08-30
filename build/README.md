# Reconstruire le core (WebAssembly)

Le fichier `lecteur-psx.html` embarque, en base64, le core **pcsx_rearmed** compilé en
WebAssembly (js + wasm). Ce dossier contient tout le nécessaire pour **le reconstruire
à l'identique depuis les sources** (conformité GPL, reproductibilité).

## Lancer le build

```bash
cd build
./build.sh
```

⚠️ **Chemin sans espace obligatoire.** Les Makefiles emscripten cassent si le chemin
absolu contient un espace (le chemin d'`emcc` n'est pas quoté → `Error 127`). Clonez le
dépôt dans un chemin comme `~/psx-build`, pas `~/Mon Dossier/…`.

Le script :
1. installe l'**Emscripten SDK** (`emsdk`) ;
2. clone **pcsx_rearmed** (`notaz/pcsx_rearmed` @ `ba61a4f`) + le sous-module `libpicofe`,
   et ajoute `-pthread` à ses CFLAGS emscripten ;
3. clone **RetroArch** (`libretro/RetroArch` @ `282a12d`) et ajoute `-lworkerfs.js
   -s FORCE_FILESYSTEM=1` aux LIBS ;
4. compile le core en bitcode `.bc` ;
5. le linke via RetroArch en mode **threadé** :
   `PROXY_TO_PTHREAD=1 HAVE_RWEBAUDIO=0 HAVE_AUDIOWORKLET=1` → `.js` + `.wasm` ;
6. applique `patch_core.py` (voir ci-dessous) puis `inline_core.py` pour réinjecter le
   core dans `../lecteur-psx.html`.

## Les patchs appliqués au core

`patch_core.py` corrige le core emscripten pour qu'il fonctionne **chargé depuis un blob**
(le core est inliné, pas servi comme fichier) :

| Patch | Pourquoi |
|---|---|
| Worker pthread : `new Worker(new URL("core.js", import.meta.url))` → `new Worker(globalThis.__PSX_CORE_URL \|\| import.meta.url)` | `import.meta.url` d'un blob n'est pas une base d'URL valide (`Invalid base URL`), et un module worker refuse un blob sans type MIME. L'app fournit `__PSX_CORE_URL` (blob `text/javascript`). |
| AudioWorklet : idem via `__PSX_CORE_URL` | Même raison. |
| `GL.deleteContext` : garde-fou si le contexte n'existe pas dans ce thread | Évite un crash du thread de rendu quand WebGL est indisponible (contexte jamais créé). |

## Prérequis

`git`, `make`, `gcc`/`g++`, `python3`. Sous Debian/Ubuntu :
`sudo apt install build-essential git python3`.
