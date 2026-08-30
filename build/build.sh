#!/usr/bin/env bash
# =============================================================================
#  Reconstruit le core pcsx_rearmed (WebAssembly threadé) et le ré-inline dans
#  lecteur-psx.html. Fournit la « source » du binaire embarqué (conformité GPL).
#
#  Prérequis : git, make, gcc/g++, python3, ~2 Go d'espace + réseau.
#    Debian/Ubuntu :  sudo apt install build-essential git python3
#
#  ⚠️ IMPORTANT : ne lancez PAS ce build depuis un chemin contenant un ESPACE
#     (ex. « /home/moi/Mon Dossier/ ») : les Makefiles emscripten cassent sur
#     l'espace (le chemin absolu d'emcc n'est pas quoté). Utilisez un chemin sans
#     espace, ex. ~/psx-build.
#
#  Usage :
#     cd build && ./build.sh
#  Résultat : ../lecteur-psx.html mis à jour avec le core fraîchement compilé.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
WORK="$HERE/.build-workspace"
JOBS="$(nproc 2>/dev/null || echo 4)"

# Versions épinglées (celles utilisées pour le core embarqué)
PCSX_COMMIT="ba61a4f"          # notaz/pcsx_rearmed
RA_COMMIT="282a12d"            # libretro/RetroArch

case "$HERE" in
  *" "*) echo "ERREUR : le chemin '$HERE' contient un espace → les Makefiles emscripten vont casser."
         echo "        Clonez le dépôt dans un chemin SANS espace (ex. ~/psx-build) et relancez."; exit 1;;
esac

mkdir -p "$WORK"; cd "$WORK"

echo "==> [1/6] Emscripten SDK"
if [ ! -d emsdk ]; then git clone --depth 1 https://github.com/emscripten-core/emsdk.git; fi
( cd emsdk && ./emsdk install latest && ./emsdk activate latest )
# shellcheck disable=SC1091
source emsdk/emsdk_env.sh
emcc --version | head -1

echo "==> [2/6] Source pcsx_rearmed ($PCSX_COMMIT) + patch -pthread"
if [ ! -d pcsx_rearmed ]; then
  git clone https://github.com/notaz/pcsx_rearmed.git
  ( cd pcsx_rearmed && git checkout "$PCSX_COMMIT" && git submodule update --init --depth 1 frontend/libpicofe )
fi
# ABI atomics/bulk-memory pour pouvoir linker dans un RetroArch threadé
sed -i 's/-msimd128 -ftree-vectorize/-msimd128 -ftree-vectorize -pthread/' pcsx_rearmed/Makefile.libretro

echo "==> [3/6] Source RetroArch ($RA_COMMIT) + flags WORKERFS"
if [ ! -d RetroArch ]; then
  git clone https://github.com/libretro/RetroArch.git
  ( cd RetroArch && git checkout "$RA_COMMIT" )
fi
grep -q 'lworkerfs.js' RetroArch/Makefile.emscripten || \
  sed -i 's/^LIBS   := -s USE_ZLIB=1/&\nLIBS   += -lworkerfs.js -s FORCE_FILESYSTEM=1/' RetroArch/Makefile.emscripten

echo "==> [4/6] Compilation du core (.bc)"
( cd pcsx_rearmed && emmake make -f Makefile.libretro platform=emscripten -j"$JOBS" )
cp pcsx_rearmed/pcsx_rearmed_libretro_emscripten.bc RetroArch/libretro_emscripten.bc

echo "==> [5/6] Link RetroArch threadé (.js + .wasm)"
( cd RetroArch && emmake make -f Makefile.emscripten LIBRETRO=pcsx_rearmed \
    PROXY_TO_PTHREAD=1 HAVE_RWEBAUDIO=0 HAVE_AUDIOWORKLET=1 -j"$JOBS" )

echo "==> [6/6] Patch du core + ré-inline dans lecteur-psx.html"
CORE_JS="RetroArch/pcsx_rearmed_libretro.js"
CORE_WASM="RetroArch/pcsx_rearmed_libretro.wasm"
python3 "$HERE/patch_core.py" "$CORE_JS"
python3 "$HERE/inline_core.py" "$REPO/lecteur-psx.html" "$CORE_JS" "$CORE_WASM"

echo ""
echo "OK — core reconstruit et ré-inliné dans $REPO/lecteur-psx.html"
