#!/usr/bin/env bash
# Installe l'AppImage dans le menu d'applications GNOME/KDE :
# - copie l'AppImage dans ~/Applications/
# - copie l'icône dans ~/.local/share/icons/hicolor/256x256/apps/
# - crée ~/.local/share/applications/beatfinder.desktop
# - rafraîchit la DB des applications

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

SRC_APPIMAGE="$ROOT/dist/beatfinder-x86_64.AppImage"
SRC_ICON="$ROOT/packaging/beatfinder.png"

if [[ ! -x "$SRC_APPIMAGE" ]]; then
  echo "✗ AppImage absente : $SRC_APPIMAGE"
  echo "  Lance ./scripts/build_appimage.sh d'abord."
  exit 1
fi

# Destinations standard XDG
APP_DIR="$HOME/Applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$APP_DIR" "$ICON_DIR" "$DESKTOP_DIR"

DST_APPIMAGE="$APP_DIR/beatfinder-x86_64.AppImage"
DST_ICON="$ICON_DIR/beatfinder.png"
DST_DESKTOP="$DESKTOP_DIR/beatfinder.desktop"

echo "→ copie AppImage : $DST_APPIMAGE"
cp -f "$SRC_APPIMAGE" "$DST_APPIMAGE"
chmod +x "$DST_APPIMAGE"

echo "→ copie icône : $DST_ICON"
cp -f "$SRC_ICON" "$DST_ICON"

echo "→ écriture .desktop : $DST_DESKTOP"
cat > "$DST_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Beatfinder
GenericName=Audio Pattern Analyzer
Comment=Analyseur de patterns audio pour beatmakers (BPM, tonalité, énergie, spectre)
Exec="$DST_APPIMAGE"
Icon=beatfinder
Categories=AudioVideo;Audio;Music;
Terminal=false
StartupNotify=true
Keywords=beat;music;audio;analysis;spotify;production;
EOF

echo "→ nettoyage entrées AppImageLauncher orphelines"
rm -f "$DESKTOP_DIR"/appimagekit_*beatfinder*.desktop 2>/dev/null || true
rm -f "$HOME/.cache/appimagelauncher.log" 2>/dev/null || true

if command -v update-desktop-database >/dev/null 2>&1; then
  echo "→ rafraîchissement DB applications"
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  echo "→ rafraîchissement cache icônes"
  gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo ""
echo "✓ Beatfinder installé."
echo ""
echo "  Tu peux maintenant lancer l'app via :"
echo "  - le menu Activities / dash (cherche \"Beatfinder\")"
echo "  - clic droit sur le bureau → Show Applications"
echo "  - direct : $DST_APPIMAGE"
echo ""
echo "  Pour désinstaller : ./scripts/uninstall_appimage.sh"
