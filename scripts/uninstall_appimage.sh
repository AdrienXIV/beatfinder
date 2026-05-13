#!/usr/bin/env bash
# Désinstalle Beatfinder du menu d'applications.
#
# Usage :
#   ./scripts/uninstall_appimage.sh           # retire l'app, garde les données
#   ./scripts/uninstall_appimage.sh --purge   # retire l'app ET ~/.beatfinder/

set -euo pipefail

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge|--all) PURGE=1 ;;
    -h|--help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *)
      echo "✗ Option inconnue : $arg (utilise --purge ou --help)"
      exit 2
      ;;
  esac
done

DST_APPIMAGE="$HOME/Applications/beatfinder-x86_64.AppImage"
DST_ICON="$HOME/.local/share/icons/hicolor/256x256/apps/beatfinder.png"
DST_DESKTOP="$HOME/.local/share/applications/beatfinder.desktop"
DATA_DIR="$HOME/.beatfinder"

rm -f "$DST_APPIMAGE" "$DST_ICON" "$DST_DESKTOP"
# Aussi les entrées orphelines d'AppImageLauncher
rm -f "$HOME/.local/share/applications"/appimagekit_*beatfinder*.desktop 2>/dev/null || true

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo "✓ Beatfinder désinstallé du menu d'applications."

if [[ $PURGE -eq 1 ]]; then
  if [[ -d "$DATA_DIR" ]]; then
    size=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
    echo ""
    echo "  Contenu de $DATA_DIR ($size) :"
    du -sh "$DATA_DIR"/* 2>/dev/null | sed 's/^/    /' || true
    echo ""
    if [[ -t 0 ]]; then
      read -rp "  Supprimer toutes ces données ? [y/N] " confirm
      if [[ ! "$confirm" =~ ^[yYoO]$ ]]; then
        echo "  Annulé. Les données restent dans $DATA_DIR."
        exit 0
      fi
    fi
    rm -rf "$DATA_DIR"
    echo "✓ $DATA_DIR supprimé."
  else
    echo "  $DATA_DIR n'existe pas, rien à purger."
  fi
else
  if [[ -d "$DATA_DIR" ]]; then
    echo "  Les données utilisateur restent dans $DATA_DIR (relance avec --purge pour tout nettoyer)."
  fi
fi
