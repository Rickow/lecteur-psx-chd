# Changelog

## v1.1.0

Multi-disc support, a much simpler "keep in memory / Continue" flow, an optional
display filter, and a batch of first-launch fixes.

### ✨ New features
- **Multi-disc games** (FF7 / FF8 / FF9…): select all the CDs at once, switch discs
  **in-game**, with only **one disc in RAM at a time** (lazy `.m3u`).
- **Keep in memory + one-click Continue**: the loaded game is stored in the browser
  (IndexedDB). On the home screen you get **“▶ Continue — <title>”** to relaunch it
  instantly (no re-selecting files) and resume your latest save, plus **“🗑 Clear memory”**
  to free it and load another game. No more history list to manage.
- **DualShock toggle** on the touch gamepad: show/hide the analog sticks (hidden in portrait).
- **Optional display filter**: the real RetroArch handheld **`dot`** shader, with two dedicated
  buttons — **Dot** and **Dot 2×** (bigger dots for hi-DPI / retina screens).

### 🐛 Fixes
- **Save / export state now works on the very first launch** (was failing with an `fs timeout`:
  the save-state directory wasn’t created, and an unused thumbnail was being waited on).
- **On-screen journal restored** (a CSS regression had made the log panel invisible).
- **First-launch audio offset auto-corrected**: a transient save→load realigns the audio
  buffer shortly after launch (without touching your saved states).
- **Cleaner memory when switching games**: loading a new game reloads the page for a fresh
  WASM heap, avoiding memory build-up (and iPhone out-of-memory crashes).
- **Core WebGL fix** (`gl2.c`): use `GL_RGBA` instead of `GL_BGRA_EXT` as the texture
  internalformat — BGRA is not a valid WebGL2 internalformat, which broke shader framebuffers.

### 🔧 Changes
- **Simplified home screen**: “Continue / Load a disc / Clear memory” instead of a toggle,
  a recent-games history list and a “free memory” button.
- **Removed** the non-functional FPS overlay (this build has no OSD font).

### ⚠️ Notes & known limits
- **Multi-pass shaders** (xBRz / ScaleFX, i.e. the fancy 3D “smoothing”) are **not available**
  in this WebGL build (framebuffer-format limitation). Single-pass filters like `dot` work.
- Still an **interpreter** (no dynarec — iOS forbids JIT): full speed for FF and most games;
  the heaviest 3D titles can occasionally miss the target framerate.

---

## v1.0.0

Initial public release: single-page PS1 emulator (pcsx_rearmed → WebAssembly, threaded),
iPhone PWA with COOP/COEP via a service worker, touch gamepad, save states, memory card,
SBI/libcrypt support, and an ISO/BIN/CUE → CHD converter.
