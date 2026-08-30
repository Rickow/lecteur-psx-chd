#!/usr/bin/env bash
# Installe des lanceurs de bureau (menu d'applications) pour le Lecteur PSX et le
# Convertisseur CHD, avec les bons chemins (celui où ce dépôt est cloné).
# Installs desktop launchers (app menu) for the PSX player and the CHD converter,
# with correct paths (wherever this repo is cloned).
#
#   Usage:  ./install-launchers.sh
#
# Prérequis / requirements:
#   - Lecteur PSX : python3 (le lanceur sert la page + ouvre le navigateur)
#   - Convertisseur : python3, mame-tools (chdman), python3-tk
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
APPDIR="$HOME/.local/share/applications"
mkdir -p "$APPDIR"

cat > "$APPDIR/lecteur-psx-chd.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Lecteur PSX (CHD)
Comment=Sert le lecteur PSX en local (COOP/COEP) et ouvre le navigateur
Exec=python3 "$REPO/serve/lancer_lecteur_psx.py"
Path=$REPO/serve
Icon=applications-games
Terminal=true
Categories=Game;
EOF

cat > "$APPDIR/convertisseur-chd.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Convertisseur CHD (ISO/BIN/CUE → CHD)
Comment=Convertit des images CD/DVD en .chd via chdman
Exec=python3 "$REPO/tools/chd-converter/iso2chd_app.py"
Path=$REPO/tools/chd-converter
Icon=media-optical
Terminal=false
Categories=Utility;
EOF

chmod +x "$APPDIR/lecteur-psx-chd.desktop" "$APPDIR/convertisseur-chd.desktop"
update-desktop-database "$APPDIR" 2>/dev/null || true

echo "OK — lanceurs installés dans le menu d'applications :"
echo "  • « Lecteur PSX (CHD) »"
echo "  • « Convertisseur CHD (ISO/BIN/CUE → CHD) »"
echo "Pour désinstaller : rm \"$APPDIR/lecteur-psx-chd.desktop\" \"$APPDIR/convertisseur-chd.desktop\""
