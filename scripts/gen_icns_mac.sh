#!/usr/bin/env bash
# Génère packaging/Beatfinder.icns sur macOS si absent.
#
# Pré-requis : un PNG 1024px (`packaging/beatfinder-1024.png`). S'il manque,
# on tente de le régénérer via `scripts/gen_icon.py` (nécessite Pillow).
#
# Pourquoi ce script : PyInstaller `BUNDLE` step exige Beatfinder.icns sur
# darwin. Le fichier .icns est gitignored (pesant, binaire, OS-spécifique)
# → faut le re-générer sur chaque Mac avant le 1er build. CI le fait
# automatiquement via .github/workflows/build.yml (lignes ~89-109), ce
# script reproduit la même logique pour `./build.command` local.
#
# Idempotent : exit 0 si .icns existe déjà.

set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$PWD"
ICNS="$ROOT/packaging/Beatfinder.icns"
SRC_PNG="$ROOT/packaging/beatfinder-1024.png"

if [[ "$OSTYPE" != "darwin"* ]]; then
  echo "✗ Ce script est macOS-only (iconutil n'existe pas ailleurs)."
  exit 1
fi

if [[ -f "$ICNS" ]]; then
  echo "✓ $ICNS déjà présent — skip."
  exit 0
fi

# Générer le PNG 1024 source si absent (cas Mac vierge sans git pull complet)
if [[ ! -f "$SRC_PNG" ]]; then
  echo "→ $SRC_PNG manquant, génération via gen_icon.py (Pillow requis)"
  VENV="$ROOT/.venv"
  if [[ -x "$VENV/bin/pip" ]]; then
    "$VENV/bin/pip" install --quiet pillow
    "$VENV/bin/python" "$ROOT/scripts/gen_icon.py"
  else
    echo "✗ Pas de venv à $VENV — install Pillow manuellement puis relance."
    exit 1
  fi
fi

if [[ ! -f "$SRC_PNG" ]]; then
  echo "✗ $SRC_PNG toujours absent après gen_icon.py — abort."
  exit 1
fi

ICONSET="$ROOT/Beatfinder.iconset"
echo "→ Compose iconset depuis $SRC_PNG"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

# Génération multi-résolutions (Apple HIG : 16/32/128/256/512 + @2x)
sips -z 16 16    "$SRC_PNG" --out "$ICONSET/icon_16x16.png"      >/dev/null
sips -z 32 32    "$SRC_PNG" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null
sips -z 32 32    "$SRC_PNG" --out "$ICONSET/icon_32x32.png"      >/dev/null
sips -z 64 64    "$SRC_PNG" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null
sips -z 128 128  "$SRC_PNG" --out "$ICONSET/icon_128x128.png"    >/dev/null
sips -z 256 256  "$SRC_PNG" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256  "$SRC_PNG" --out "$ICONSET/icon_256x256.png"    >/dev/null
sips -z 512 512  "$SRC_PNG" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512  "$SRC_PNG" --out "$ICONSET/icon_512x512.png"    >/dev/null
cp "$SRC_PNG"               "$ICONSET/icon_512x512@2x.png"

echo "→ Compile iconset vers $ICNS"
iconutil -c icns "$ICONSET" -o "$ICNS"
rm -rf "$ICONSET"

echo "✓ $ICNS généré"
