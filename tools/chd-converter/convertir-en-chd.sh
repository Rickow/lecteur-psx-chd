#!/usr/bin/env bash
# ============================================================
#  Convertir en CHD (Linux/macOS) — version autonome, sans Python.
#
#  UTILISATION : place ce script dans un dossier contenant tes
#  images CD/DVD (.cue/.bin, .iso, .gdi, .toc) et lance-le
#  (double-clic « Exécuter », ou ./convertir-en-chd.sh).
#  Il convertit tout le dossier en .chd (à côté des sources ;
#  les sources ne sont jamais supprimées, un .chd déjà présent
#  est ignoré).
#
#  PRÉREQUIS : chdman (paquet MAME).
#    Debian/Ubuntu : sudo apt install mame-tools
#    Fedora : sudo dnf install mame-tools · Arch : sudo pacman -S mame-tools
#    macOS  : brew install rom-tools
# ============================================================
cd "$(dirname "$0")" || exit 1

if ! command -v chdman >/dev/null 2>&1; then
  echo
  echo "  chdman introuvable."
  echo "  Installe-le : sudo apt install mame-tools   (ou dnf/pacman/brew rom-tools)"
  echo
  read -rp "Appuie sur Entrée pour fermer..."
  exit 1
fi

shopt -s nullglob nocaseglob
ok=0; skip=0; fail=0

echo
echo "  chdman  : $(command -v chdman)"
echo "  Dossier : $PWD"
echo

convert() {  # $1 = fichier d'entrée, $2 = sous-commande chdman
  local in="$1" sub="$2" out="${1%.*}.chd"
  if [ -e "$out" ]; then echo "  [ignore] $in"; skip=$((skip+1)); return; fi
  echo "  [chd]    $in ${3:+($sub)}"
  if chdman "$sub" -i "$in" -o "$out"; then ok=$((ok+1)); else echo "  [ECHEC]  $in"; fail=$((fail+1)); fi
}

# descripteurs multipistes
for f in *.cue *.gdi *.toc; do convert "$f" createcd; done

# .iso : DVD si >= 1 Go, sinon CD
for f in *.iso; do
  sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f")
  if [ "${sz:-0}" -ge 1000000000 ]; then convert "$f" createdvd show; else convert "$f" createcd; fi
done

# .bin isolé (sans .cue de même nom) : cue temporaire MODE2/2352 (format PS1 courant)
for f in *.bin; do
  base="${f%.*}"
  [ -e "$base.cue" ] && continue
  out="$base.chd"
  if [ -e "$out" ]; then echo "  [ignore] $f"; skip=$((skip+1)); continue; fi
  cue="$base.__tmp__.cue"
  printf 'FILE "%s" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n' "$f" > "$cue"
  echo "  [chd]    $f (bin isolé -> cue temporaire)"
  if chdman createcd -i "$cue" -o "$out"; then ok=$((ok+1)); else echo "  [ECHEC]  $f"; fail=$((fail+1)); fi
  rm -f "$cue"
done

echo
echo "  Terminé : $ok converti(s), $skip ignoré(s), $fail échec(s)."
echo
read -rp "Appuie sur Entrée pour fermer..."
