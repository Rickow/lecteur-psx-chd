# Rebuilding the core (WebAssembly)

`lecteur-psx.html` embeds, as base64, the **pcsx_rearmed** core compiled to WebAssembly
(js + wasm). This folder contains everything needed to **rebuild it identically from
source** (GPL compliance, reproducibility).

## Run the build

```bash
cd build
./build.sh
```

⚠️ **A space-free path is required.** The emscripten Makefiles break if the absolute path
contains a space (emcc's path isn't quoted → `Error 127`). Clone the repo into a path like
`~/psx-build`, not `~/My Folder/…`.

The script:
1. installs the **Emscripten SDK** (`emsdk`);
2. clones **pcsx_rearmed** (`notaz/pcsx_rearmed` @ `ba61a4f`) + the `libpicofe` submodule,
   and adds `-pthread` to its emscripten CFLAGS;
3. clones **RetroArch** (`libretro/RetroArch` @ `282a12d`) and adds `-lworkerfs.js
   -s FORCE_FILESYSTEM=1` to its LIBS;
4. compiles the core to `.bc` bitcode;
5. links it via RetroArch in **threaded** mode:
   `PROXY_TO_PTHREAD=1 HAVE_RWEBAUDIO=0 HAVE_AUDIOWORKLET=1` → `.js` + `.wasm`;
6. applies `patch_core.py` (see below) then `inline_core.py` to re-inject the core into
   `../lecteur-psx.html`.

## Patches applied to the core

`patch_core.py` fixes the emscripten core so it works when **loaded from a blob** (the core
is inlined, not served as a file):

| Patch | Why |
|---|---|
| pthread worker: `new Worker(new URL("core.js", import.meta.url))` → `new Worker(globalThis.__PSX_CORE_URL \|\| import.meta.url)` | a blob's `import.meta.url` isn't a valid URL base (`Invalid base URL`), and a module worker rejects a blob with no MIME type. The app provides `__PSX_CORE_URL` (a `text/javascript` blob). |
| AudioWorklet: same, via `__PSX_CORE_URL` | same reason. |
| `GL.deleteContext`: guard when the context doesn't exist in this thread | avoids crashing the render thread when WebGL is unavailable (context never created). |

## Requirements

`git`, `make`, `gcc`/`g++`, `python3`. On Debian/Ubuntu:
`sudo apt install build-essential git python3`.
