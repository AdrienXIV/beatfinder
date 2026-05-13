#!/bin/bash
# Launcher Beatfinder macOS double-cliquable.
# Retire le flag de quarantine que macOS appose sur les fichiers téléchargés
# (sinon dyld refuse de charger les .dylib ad-hoc signées), puis lance le
# binaire FastAPI qui ouvre la fenêtre Chrome.
cd "$(dirname "$0")"
xattr -cr . 2>/dev/null || true
exec ./beatfinder
