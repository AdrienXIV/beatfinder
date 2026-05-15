#!/usr/bin/env bash
# Désinstalle proprement Beatfinder sur macOS.
# Double-clic depuis le Finder, ou ./uninstall_macos.command en CLI.
#
# Usage :
#   ./uninstall_macos.command           # retire l'app, garde les données utilisateur
#   ./uninstall_macos.command --purge   # retire l'app ET ~/.beatfinder/
#
# Pourquoi ce script existe : macOS LaunchServices cache la metadata des
# bundles par bundle_identifier. Après un upgrade par drag-and-drop, Finder
# peut continuer d'afficher l'ancienne version dans Get Info / Spotlight /
# Dock. Ce script supprime l'app puis force un reset du cache pour repartir
# proprement avant de réinstaller.

set -euo pipefail

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge|--all) PURGE=1 ;;
    -h|--help)
      sed -n '2,11p' "$0"
      exit 0
      ;;
    *)
      echo "✗ Option inconnue : $arg (utilise --purge ou --help)"
      exit 2
      ;;
  esac
done

APP_PATH="/Applications/Beatfinder.app"
DATA_DIR="$HOME/.beatfinder"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

echo "→ Quitter Beatfinder s'il tourne…"
osascript -e 'tell application "Beatfinder" to quit' 2>/dev/null || true
sleep 1
pkill -x Beatfinder 2>/dev/null || true

echo "→ Démonter les volumes Beatfinder déjà montés…"
for v in /Volumes/Beatfinder*; do
  [[ -d "$v" ]] && hdiutil detach "$v" -force >/dev/null 2>&1 || true
done

if [[ -d "$APP_PATH" ]]; then
  echo "→ Supprimer $APP_PATH…"
  rm -rf "$APP_PATH"
else
  echo "  $APP_PATH absent, rien à retirer côté /Applications."
fi

if [[ -x "$LSREGISTER" ]]; then
  echo "→ Reset cache LaunchServices (peut prendre quelques secondes)…"
  "$LSREGISTER" -kill -r -domain local -domain system -domain user >/dev/null 2>&1 || true
fi

echo "→ Relancer Finder + Dock pour vider la metadata cached…"
killall Finder >/dev/null 2>&1 || true
killall Dock >/dev/null 2>&1 || true

echo ""
echo "✓ Beatfinder désinstallé. Tu peux maintenant remonter le DMG et glisser"
echo "  la nouvelle version dans /Applications sans interférence du cache."

if [[ $PURGE -eq 1 ]]; then
  if [[ -d "$DATA_DIR" ]]; then
    size=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
    echo ""
    echo "  Contenu de $DATA_DIR ($size) :"
    du -sh "$DATA_DIR"/* 2>/dev/null | sed 's/^/    /' || true
    echo ""
    if [[ -t 0 ]]; then
      read -rp "  Supprimer toutes ces données (analyses, sessions, settings) ? [y/N] " confirm
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
    echo "  Tes analyses et sessions restent dans $DATA_DIR."
    echo "  (Relance avec --purge pour tout effacer.)"
  fi
fi
