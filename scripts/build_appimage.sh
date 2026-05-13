#!/usr/bin/env bash
# Construit beatfinder-x86_64.AppImage à partir du binaire PyInstaller existant.
# Pré-requis : ./build.sh déjà exécuté (dist/beatfinder/ présent),
# mksquashfs disponible (paquet squashfs-tools).
#
# Approche : au lieu d'utiliser appimagetool (FUSE + zstd absent des releases
# stables AppImageKit/continuous), on construit l'AppImage manuellement.
# Le format = runtime ELF + squashfs concaténés. Donne contrôle total sur
# les flags mksquashfs (zstd + cap RAM + cap CPU).

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

DIST="$ROOT/dist/beatfinder"
APPDIR="$ROOT/dist/beatfinder.AppDir"
PACKAGING="$ROOT/packaging"
RUNTIME="/tmp/appimage-runtime-x86_64"
SQUASHFS="/tmp/beatfinder.squashfs"
APPIMAGE="$ROOT/dist/beatfinder-x86_64.AppImage"

if [[ ! -x "$DIST/beatfinder" ]]; then
  echo "✗ Binaire absent à $DIST/beatfinder. Lance ./build.sh d'abord."
  exit 1
fi

if ! command -v mksquashfs >/dev/null 2>&1; then
  echo "✗ mksquashfs absent. Installe : sudo apt install squashfs-tools"
  exit 1
fi

# Récupérer le runtime AppImage type 2 (ELF ~30 KB, charge le squashfs concaténé)
if [[ ! -x "$RUNTIME" ]]; then
  echo "→ téléchargement runtime AppImage"
  curl -sLo "$RUNTIME" \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/runtime-x86_64"
  chmod +x "$RUNTIME"
fi

# Vérifier l'icône
if [[ ! -f "$PACKAGING/beatfinder.png" ]]; then
  echo "→ génération icônes (gen_icon.py)"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/gen_icon.py"
fi

echo "→ nettoyage AppDir précédent"
rm -rf "$APPDIR"
rm -f "$SQUASHFS" "$APPIMAGE"

echo "→ création structure AppDir"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

echo "→ copie binaire + libs PyInstaller"
cp -r "$DIST"/* "$APPDIR/usr/bin/"

echo "→ copie launcher + .desktop + icône"
install -m 755 "$PACKAGING/AppRun" "$APPDIR/AppRun"
# Le .desktop à la racine de l'AppDir suffit.
install -m 644 "$PACKAGING/beatfinder.desktop" "$APPDIR/beatfinder.desktop"
install -m 644 "$PACKAGING/beatfinder.png" "$APPDIR/beatfinder.png"
install -m 644 "$PACKAGING/beatfinder.png" "$APPDIR/.DirIcon"
install -m 644 "$PACKAGING/beatfinder.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/beatfinder.png"

echo "→ mksquashfs (zstd, cap 2 cores + 1 GB RAM, low priority)"
# -comp zstd : 3-5× moins de RAM que xz, ~2× plus rapide
# -processors 2 + -mem 1G : cap explicite pour éviter de saturer le système
# -all-root : owner root (convention AppImage)
# -no-progress : log propre dans le terminal
# nice/ionice : laisse l'UI responsive
nice -n 19 ionice -c3 mksquashfs "$APPDIR" "$SQUASHFS" \
  -comp zstd -Xcompression-level 19 \
  -processors 2 -mem 1G \
  -root-owned -noappend -no-progress

echo "→ assemblage AppImage (runtime + squashfs)"
cat "$RUNTIME" "$SQUASHFS" > "$APPIMAGE"
chmod +x "$APPIMAGE"
rm -f "$SQUASHFS"

if [[ -x "$APPIMAGE" ]]; then
  size=$(du -sh "$APPIMAGE" | cut -f1)
  echo ""
  echo "✓ AppImage construite : $APPIMAGE ($size)"
  echo ""
  echo "  Pour tester : $APPIMAGE"
  echo "  Pour installer dans le menu apps : ./scripts/install_appimage.sh"
else
  echo "✗ AppImage non construite"
  exit 1
fi
