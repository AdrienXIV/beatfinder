#!/usr/bin/env bash
# Build Linux executable Beatfinder desktop.
#  1. cd frontend && npm run build (statique → frontend/build/)
#  2. PyInstaller via beatfinder.spec (collecte librosa, numba, madmom, ...)
#  3. Binaire final : dist/beatfinder/beatfinder (lance le serveur + auto-open browser)
#
# Cross-compilation impossible : ce script doit tourner sur la plateforme cible.
# Pour macOS, lancer ./build.command (équivalent).
#
# Pré-requis :
#  - venv Python avec --enable-shared (sinon erreur "Python built without shared lib")
#    Rebuild via : PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install -f <version>
#  - requirements.txt + pyinstaller installés
#  - Node + npm

set -euo pipefail
cd "$(dirname "$0")"

ROOT="$PWD"
VENV="$ROOT/.venv"

if [[ ! -x "$VENV/bin/pyinstaller" ]]; then
  echo "✗ pyinstaller absent du venv. Installe : $VENV/bin/pip install pyinstaller"
  exit 1
fi

echo "→ build frontend (npm run build)"
cd "$ROOT/frontend"
npm run build
cd "$ROOT"

echo "→ build binaire PyInstaller (beatfinder.spec, low priority)"
# nice/ionice : PyInstaller pic à 3-5 GB RAM pendant l'analyse + collect des libs
# scientifiques. Sans ça, l'UI freeze sur les machines à faible RAM (16 GB et moins).
nice -n 19 ionice -c3 "$VENV/bin/pyinstaller" beatfinder.spec --clean --noconfirm

EXE="$ROOT/dist/beatfinder/beatfinder"
if [[ -x "$EXE" ]]; then
  size=$(du -sh "$ROOT/dist/beatfinder" | cut -f1)
  echo ""
  echo "✓ Build OK : $EXE"
  echo "  Taille bundle : $size"
  echo ""
  echo "  Pour tester :"
  echo "  $EXE"
else
  echo "✗ Binaire non trouvé à $EXE"
  exit 1
fi
