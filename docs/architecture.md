*(English version — [Version française](architecture.fr.md))*

# Architecture & technical challenges

This document explains **how it works** and, above all, **the problems encountered and how
they were solved** — the bulk of the effort behind this project.

## Overview

The player is **a single HTML page** that embeds, as base64:
- the **pcsx_rearmed core** compiled to WebAssembly (`.js` + `.wasm`);
- the **Nostalgist.js** engine (UMD) which drives the core in the browser.

A **service worker** (`sw.js`) provides offline support **and** the isolation headers
(COOP/COEP) required for multi-threading. Primary target: **iPhone as a PWA** (Safari).

```
┌──────────────────── browser ───────────────────────┐
│  Main thread (UI, canvas, IndexedDB, files)         │
│     │  OffscreenCanvas transfer + syscall proxying  │
│     ▼                                                │
│  em-pthread  ──►  RetroArch + pcsx_rearmed (WASM)    │
│                   WebGL2 rendering, AudioWorklet     │
└──────────────────────────────────────────────────────┘
```

## Why a *threaded* core?

Web pcsx_rearmed has no dynarec (iOS forbids JIT) → interpreter. The threaded build
(`PROXY_TO_PTHREAD`) moves the emulator off the UI thread (smoothness) and enables
rendering via **OffscreenCanvas**. This requires **SharedArrayBuffer**, hence a
**cross-origin isolated** context (COOP/COEP).

---

## The challenges (and their solutions)

### 1. COOP/COEP without a special server
`SharedArrayBuffer` is only available when `crossOriginIsolated === true`, which requires
the headers `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy:
require-corp`. A static host does not necessarily send them.

**Solution:** the **service worker** (`sw.js`) rewrites responses to add those headers
(the *coi-serviceworker* pattern), merged with the offline cache. The app reloads once on
first launch to obtain isolation.
⚠️ Only works over **https** (or `localhost`) — never `file://`.

### 2. Loading an **inlined** (blob) threaded core
The core is embedded (not served as a file). But emscripten (ES6 + pthreads) spawns its
workers with: `new Worker(new URL("pcsx_rearmed_libretro.js", import.meta.url), {type:
"module"})`. Loaded from a **blob**, this fails two ways:
- a blob's `import.meta.url` is **not a valid URL base** → `Invalid base URL`;
- a **module worker rejects a blob with no MIME type** (Nostalgist's blob has none).

**Solution:** the app publishes `globalThis.__PSX_CORE_URL = URL.createObjectURL(blob
{type: "text/javascript"})`, and a core patch (`build/patch_core.py`) points the pthread
workers **and** the AudioWorklet at it. (WORKERFS is also referenced but unused — see §8.)

### 3. WebGL2 rendering from the worker (OffscreenCanvas)
RetroArch creates its render thread and **transfers the canvas** to it
(`transferControlToOffscreen`), then `emscripten_webgl_create_context("#canvas")` inside
the pthread. Each thread has its **own table** of WebGL contexts (`GL.contexts`, keyed by
`canvas.id`). Destroying a context from a thread other than the one that created it crashed
the render thread (`Cannot read properties of undefined (reading 'GLctx')`).

**Solution:** a guard in `GL.deleteContext` (patch): if the context isn't in this thread,
don't crash. Rendering survives.

**Known limitation (Brave/Chromium):** if GPU acceleration is disabled (common on Linux —
`chrome://gpu` shows `WebGL: Disabled`), `getContext('webgl2')` returns `null` → black
screen. This is **not** a player bug (Firefox works). The app detects missing WebGL2 and
shows a clear message. Fix: `chrome://flags/#ignore-gpu-blocklist` → *Enabled*.

### 4. Nostalgist APIs missing from the recent core
Nostalgist called emscripten APIs that are gone from the threaded core:
- `Module.setCanvasSize(...)` → an unhandled `TypeError` (the `catch` only handled
  `DOMException`) → launch failure. **Solution:** made `resize()` tolerant (falls back to
  `canvas.setAttribute`, never throws).
- `JSEvents.eventHandlers` (keyboard handling) → `JSEvents` is `undefined` on the main
  thread in threaded mode. **Solution:** defensive guards (`fireKeyboardEvent`,
  `updateKeyboardEventHandlers`, `exit`).

### 5. Touch controls in threaded mode
The on-screen pad went through `JSEvents` (an internal shortcut) → inoperative when threaded.

**Solution:** dispatch a **real `KeyboardEvent`** on the canvas. RetroArch listens for the
keyboard on `"#canvas"` (`emscripten_set_keydown_callback`, the `rwebinput` driver) and
reads `event.code` → a synthetic `KeyboardEvent` with the right `code` drives the game.

### 6. Save states + SharedArrayBuffer + IndexedDB
In threaded mode, the state returned by `saveState()` is backed by the **SharedArrayBuffer**
(shared WASM heap). But **IndexedDB refuses to store a SharedArrayBuffer view**
(`DataCloneError`). As a result "Save state" failed silently, while "Export state" worked
(the export `Blob` **copies** the bytes).

**Solution:** copy into a regular `ArrayBuffer` before storing
(`new Uint8Array(view)` when `view.buffer instanceof SharedArrayBuffer`), centralised in
the storage function.

### 7. Memory: big games (FF7/FF8) crashed the tab
The disc was copied **2–3 times** in RAM on load (read into an ArrayBuffer, then
`getUint8Array` → `createDataFile` → `readFile` → `writeFile` on Nostalgist's side) → a
~1 GB spike for a FF disc (~450 MB compressed) → iOS Safari kills the tab.

**Solution:** the app passes the `File` object (not read into RAM) and a patched `writeFile`
**writes the disc in 8 MB chunks** directly into the filesystem. Peak memory ≈ **1× the
disc size**. (Being compressed, a PS1 CHD fits comfortably in an iPhone's memory.)

### 8. WORKERFS: a dead-end (documented)
The initial idea was **WORKERFS streaming** (reading the CHD in slices without loading it).
Verified in the core: a pthread's file syscalls are **proxied to the main thread**
(`__syscall_openat → proxyToMainThread`), yet `WORKERFS.mount` requires
`ENVIRONMENT_IS_WORKER` + `FileReaderSync` (worker only). **Incompatible** with this
RetroArch build. The alternative *lazy* mechanism (`createLazyFile`) was **proven feasible**
(synchronous "binary-string" *Range* XHR on a blob URL → 206 + correct bytes under COEP) but
is not implemented yet (mostly useful for multi-disc).

### 9. CHD & SBI
- **CHD**: a hunk-compressed format, hunks decompressed on demand by libchdr → small working
  footprint.
- **SBI** (libcrypt protection, PAL games): pcsx_rearmed looks for the `.sbi` next to the
  image, **same base name**. The app writes the `.sbi` as `game.sbi` to match `game.chd`
  (select both files together).

---

## Convenience / robustness

- **"Recent games" history** (metadata only, not the large CHDs → no storage cost); resume
  by re-selecting the file + automatic save reload.
- **Auto-save** every 30 s (separate key, does not overwrite the manual save) — a crash
  safety net; resume loads the most recent one.
- **"Free memory"**: save + page reload (RAM reset to switch games; saves persist in
  IndexedDB).

## Limitations & directions

- **Single-disc** for now; **multi-disc** (FF7 = 3 CDs, in-game switching via `DISK_NEXT`)
  is the next step.
- **Lazy loading** of the CHD (§8) would further reduce RAM and ease multi-disc.
- **Interpreter** (no dynarec): perfect for FF and most games; heavy 3D titles may sometimes
  exceed the budget.
